# CURRENT — The Repository Status Authority

> ### **This is the ONLY short-form current-status authority in this repository.**
> Every phase review, blocker review and planning document is **historical evidence**. Do not
> reconstruct status by reading them — that is the failure this file exists to prevent.
>
> **Last updated:** P3 — Checkpoint Witness, seven-step atomic checkpoint and claim CAS
> **ADJUDICATED COMPLETE.** All 14 weighted P3 criteria PASS on independent evidence. **P4 (adapter
> containment) is the sole READY unit; its implementation checkpoint landed this session but it is
> NOT COMPLETE — independent review and final adjudication are PENDING.** R-07 stays OPEN — NOT
> CONTAINED.

---

## Position

**The block below is machine-maintained and machine-verified.** It is written by
`scripts/update_current_status.py` from `git rev-parse` and a real suite run — never by hand — and
[`eval/tests/test_status_reality.py`](../../eval/tests/test_status_reality.py) fails the build when
it disagrees with the checked-out commit. The zero-context rehearsal proved a hand-maintained
version of this block goes stale within one commit and nothing notices.

```yaml
# status-block: maintained by scripts/finalize_status.py - do not edit by hand
recorded_authoring_branch: p4/adapter-containment-completion   # advisory; not verified across bundles/clones
content_commit: 3d231731b8b0984b3decded34177907f8d3898d1
content_tree: 50cd012079cb48eaaf59e8e5e5406270ba5bd154
suite_passed: 1630
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
| **P3** — checkpoint, witness, claim CAS | ### **COMPLETE** | [`phase-3-implementation-review.md`](phase-3-implementation-review.md) — the implementer's record · [`p3-independent-review-findings.md`](p3-independent-review-findings.md) — the first INDEPENDENT review, which P3 **did not pass** (9 findings, 60/100) · [`p3-findings-remediation-review.md`](p3-findings-remediation-review.md) — the remediation · [`p3-genuine-independent-review.md`](p3-genuine-independent-review.md) — the FRESH independent review of the remediated, finalized tree, **PASS** (zero new defects, 13/13 hostile probes) · [`p3-final-adjudication-review.md`](p3-final-adjudication-review.md) — ### **the FINAL ADJUDICATION: all 14 weighted criteria PASS, P3 recorded COMPLETE.** The kernel still ships dark; only completing P4 closes R-07 |
| **P4** — adapter containment | ### **SELECTED (`READY`) AND EXECUTING — NOT COMPLETE** | two implementation checkpoints landed; independent review + final adjudication PENDING. See the P4 unit block and its `landed_checkpoints` in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) |
| **P5–P14** | **NOT STARTED** | [`PHASE-OUTPUTS.md`](PHASE-OUTPUTS.md) |

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
| Guard files / guard tests *(discovered by `guard_files()`, never enumerated — the transcribed "25 / 367" figure is retired: no executable source ever computed it. **Method, stated so the figure is reproducible:** files = `len(test_phase2_guard_registry.guard_files())`; tests = the AST count of `def test_*` functions across those files — test FUNCTIONS, not collected nodes, so parametrization does not inflate it)* | **42 / 631** *(was 38 / 578, then 41 / 624 after the P3 findings remediation added three guard files — ledger compatibility, step order, observability — and 46 test functions; the N-1 receipt-consistency correction then added one guard file — the BUILD-STATUS receipt-consistency guard — and 7 test functions)* |
| Canonical transitions | **134** |
| Canonical emitted events | **98** |
| Canonical loops | **11** |
| Domain entities | **40** · adapters **18** · safety invariants **28** |
| **AC-CKPT checkpoint matrix** | **105 / 105 GREEN** (7 steps × 15 conditions) |

## ⛔ Open risks and findings — ALL STILL OPEN

| ID | Finding | Status | Closes at |
|---|---|---|---|
| **R-07** | Ungated live-write paths | ### **OPEN — NOT CONTAINED** | **P4** |
| — | **6 production-reachable live-write paths** — EP-1, EP-3, EP-6, EP-7, EP-9, EP-10 (the P0 baseline finding) | OPEN | P4 |
| — | **31 direct adapter-import edges** across 18 importer modules (the P0 baseline finding) | OPEN | P4 |
| — | P4 CHECKPOINT (prior session): EP-6/7/9/10 **DELETED** → 2 live-write paths remain (EP-1, EP-3); edges cut 31 → 20; effect-capable gate violations 12 → 5 | ### **STILL OPEN** | P4 |
| — | P4 CONTAINMENT CUTOVER CHECKPOINT (this session): findings **F1 + F4 fixed** (F1 = EP-12's live `--browser` path removed + AST structural quarantine proof; F4 = a generic post-attempt adapter exception becomes UNKNOWN_OUTCOME, never CLAIMED, never FAILED); **brain_runtime → tms_write edge cut** by injection; the **orphan-effect detective sweep mechanism implemented and mutation-proven** (`run_detective_sweep` is its per-cycle invocation surface; **no production/runtime caller exists yet** — production scheduling is deferred to P11 and the boundary still ships dark); gate violations **5 → 4**, edges **20 → 18**, importer modules **14 → 13**. The remaining 4 violations (EP-1, EP-3, EP-8, EP-14) + finding **F2** are DEFERRED — browser-untestable in this environment. | ### **STILL OPEN** | P4 |
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
### **ADJUDICATED COMPLETE.**
Implementer's record: [`phase-3-implementation-review.md`](phase-3-implementation-review.md);
final adjudication: [`p3-final-adjudication-review.md`](p3-final-adjudication-review.md).

> ### **How P3 reached COMPLETE.** Its weighted acceptance contract has 14 criteria. Twelve were
> supplied by the implementing lineage; **`independent_review` (weight 5) and `final_adjudication`
> (weight 4) could not be** — by construction they require a session other than the implementing
> one, which is why P3 stood at **91/100 at best** until a different session closed them. All 14 are
> now `PASS`, so under [`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md) §3 the phase computes to
> **100/100** and P3 is recorded **COMPLETE**.
>
> ### **THE FULL REVIEW HISTORY, PRESERVED.** The first INDEPENDENT review (commit `38f2714`)
> returned **9 findings — 1 CRITICAL, 3 HIGH, 3 MEDIUM, 2 LOW — 60/100, `NOT READY`**
> ([findings](p3-independent-review-findings.md)); **P3 did not pass it.** All nine were
> **remediated** ([dispositions](p3-findings-remediation-review.md)) by a session that was neither
> the reviewer nor the adjudicator. A **FRESH INDEPENDENT** review of the remediated, finalized tree
> then **PASSED** with zero new defects and 13/13 hostile probes
> ([`p3-genuine-independent-review.md`](p3-genuine-independent-review.md)). Finally, a **separate
> ADJUDICATING session** — which did not implement P3, perform either review, remediate the
> findings, normalize the git history, correct N-1, or author the genuine review — set the 14
> criteria from that evidence ([`p3-final-adjudication-review.md`](p3-final-adjudication-review.md)).
> ### **Remediation is not adjudication, and no session adjudicated its own work** — the two-key
> discipline held end to end.
>
> ### **The finalizer and clean-clone gate EXECUTED and PASSED on the finalized P3 tree.** The
> CRITICAL finding (F-A) — a mis-anchored rebaseline-invariant guard that failed the canonical suite
> — is fixed; the earlier illegal-history deadlock (two unfinalized content commits) is resolved by
> consolidating the content and finalizing it. `SUITE-RESULT.json` (green) and `GATE-RESULT.json`
> (`passed: true`) bind to the recorded content commit and tree. The finalizer PRODUCED the status
> record by executing the suite, the clean-clone gate and the acceptance gates itself.

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
bearing only when **P4** contains the adapters behind it. **Completing P3 did NOT close R-07** —
the six live-write paths were physically untouched by P3, exactly as its prohibited scope required.
(P4 has since deleted EP-6/7/9/10; R-07 nonetheless stays OPEN — EP-1/EP-3 and the read-only paths
remain and nothing routes through the kernel yet.)

### Gate history — ### **BOTH GATES ARE CLOSED**, all on independent evidence

> These two gates are closed. ### **Neither is a P3 review.** They predate P3 and say nothing
> about the checkpoint kernel; P3's own `independent_review` was performed **separately** (the
> genuine independent review of the remediated tree) and is now adjudicated `PASS`.
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

### **P4 — ADAPTER CONTAINMENT. IT IS THE SOLE `READY` UNIT, IT IS EXECUTING, AND IT IS NOT COMPLETE.**

### **The next approved unit is `P4`.** The checkpoint-kernel phase is COMPLETE — all 14 weighted
criteria PASS on independent evidence — so P4's sole dependency is satisfied and P4 is the selected
unit. **`READY` is the SELECTION state, not a claim that nothing has happened:** P4's
`execution_state` is `IN_PROGRESS` and its `checkpoint_state` is
`CHECKPOINT_ACCEPTED_FOR_CONTINUATION`. The three fields are defined in `meta.status_model` of
[`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml).

Unit `P4` in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) — **the one and only
READY unit.** It routes every external effect through the adapter boundary and the two-key rule,
deletes or de-actuates the six production-reachable live-write paths, converts or removes the 31
adapter-import edges, and turns on the CI import gate. ### **P4 is READY but NOT COMPLETE.** Two
sessions have advanced it, both **awaiting independent review**:

1. The **implementation checkpoint** (prior session): the containment boundary, the boundary-aware
   import gate, and the DELETE cutover of EP-6/7/9/10 — acceptance-proven (33 boundary cases) and
   mutation-proven (14/14 mutants caught).
2. The **containment cutover checkpoint** (this session): the mandated review findings **F1** and
   **F4** are fixed, the **brain_runtime → tms_write** edge is cut by injection, and the
   **orphan-effect detective sweep** mechanism is implemented and mutation-proven
   (`run_detective_sweep` is its per-cycle invocation surface; **no production/runtime caller exists
   yet** — production scheduling is deferred to P11 and the boundary still ships dark). The boundary
   mutation battery is now **21/21** (added F4 B15/B16, F1
   B17/B18, brain_runtime B19, detective B20/B21). Gate violations fell **5 → 4**; edges **20 → 18**.
   The remaining four violations (**EP-1, EP-3, EP-8, EP-14**) and finding **F2** (cdp_session.evaluate
   is an ungated actuation primitive) were DEFERRED at that checkpoint: each hinges on
   correctness-critical browser code with no live-browser/live-TMS runtime available to verify
   against, so per CLAUDE.md §9 they were NOT done blind. EP-1 in particular routes the
   OperationRouter→OperatorAgent autonomous browser write (the live R-07 write), whose containment
   is the P12-scale supervised-write integration.

4. **F2 built and verified, EP-8 cut (this session).** **F2 is no longer deferred**:
   `cdp_readonly.ReadOnlyCdpObserver` is a genuinely read-only CDP surface with three independent
   barriers — no mutation API exists on it; caller data travels as `Runtime.callFunctionOn`
   `arguments`, never as source; the channel allowlists CDP methods and vetted scripts by exact
   value. The deferral's premise ("no live browser here") did not hold: Chrome for Testing launches
   in this environment and `scripts/verify_readonly_cdp.py` proves the surface against a real
   browser. **EP-8 is now CUT** on it (U4.7): `scripts/orient_tms.py` imports **no adapter module at
   all**, so it is structurally read-only rather than read-only by convention — the gap-matrix
   row-34 target state, reached by an absent API rather than a promise. Gate violations **4 → 3**;
   edges **18 → 16**; boundary mutation battery **24/24** (added EP-8 B22/B23/B24: re-import the
   actuator, re-import the mutation-capable session, smuggle the actuator in dynamically — all
   caught). The click-driven deep walk is **RETAINED, not deleted**, in
   `system_orientation.orient_system`/`orient_record_actions` for the authorized actuator-capable
   caller behind the effect boundary; what EP-8 loses is reach to it, not the capability itself.

5. **EP-3 cut (this session).** `propose_ar_from_tms.py` holds a `ReadOnlyCdpNavigator` and imports
   no adapter module. Its browser surface was the worst remaining instance of F2's defect: it
   navigated via `cdp_session.evaluate("location.href=…")` — caller data interpolated into
   JavaScript source — with a `cdp_actuator.click(load_ref)` fallback to open a load's detail page
   for the POD check. Both are gone. The navigator adds exactly **one** capability over the
   observer, a document fetch, and that is a **reduction** in reachable behaviour: a click
   dispatches the SPA's `onclick` handler, which can POST an invoice while being no kind of form
   submit target, whereas `Page.navigate` never runs it. `follow()` accepts only a URL the observed
   page itself published as an `<a href>`; schemes `javascript:/data:/file:/vbscript:/blob:` are
   refused; the transport carries exactly `{Page.enable, Page.navigate}` and has no script path.
   The click fallback was **deleted, not guarded** — no structural test on an element can classify
   a SPA click as safe — so a load the list did not link to stays POD-unknown, which blocks the
   money button. `ReadOnlyCdpObserver` is **untouched**: the navigator composes it. Gate violations
   **3 → 2**; edges **16 → 14**; boundary mutation battery **30/30** (added EP-3 B25–B30).

So the EP-1 ADAPT conversion, the EP-14 read-only cut, and flipping the gate to assert EMPTY
remain — **R-07 stays OPEN** under P4's own acceptance contract.

How P3 got here, in order (all done): mutation proofs (guard battery 8/8; kernel battery K1–K11);
green final-tree validation via [`scripts/finalize_status.py`](../../scripts/finalize_status.py),
which EXECUTES the suite, the clean-clone gate and the acceptance gates itself; the first
INDEPENDENT review — which **P3 failed** (9 findings, 60/100) — then remediation of all nine; a
**FRESH INDEPENDENT** review of the remediated, finalized tree
([`p3-genuine-independent-review.md`](p3-genuine-independent-review.md), **PASS**, zero new
defects, 13/13 hostile probes); and a **separate FINAL ADJUDICATION**
([`p3-final-adjudication-review.md`](p3-final-adjudication-review.md)) that set the 14 criteria PASS
— by a session that neither implemented P3, reviewed it, remediated it, normalized the history, nor
corrected N-1.

> ### **R-07 is OPEN — NOT CONTAINED, and neither completing P3 nor either P4 checkpoint changed
> that.** The P0 finding was 31 direct adapter-import edges and all six live-write paths; P4 has
> since deleted EP-6/7/9/10 and cut the brain_runtime edge (2 live-write paths and 18 adapter-import
> edges remain, **4 effect-capable gate violations**), but nothing routes through the checkpoint
> kernel in production yet and the gate is not flipped to EMPTY. **Only completing P4 closes R-07** —
> not P3, not a plan, not operator discipline, and not a partial implementation checkpoint.

## ⛔ What must NOT begin yet

| Not yet | Why |
|---|---|
| ### **Implementation Phase 5** (events, outbox/inbox, replay isolation, PostgreSQL) | Requires `P4` COMPLETE; also blocked on the **G2** transition/event adjudication. ### **P4 itself is now READY and MAY begin** — it is deliberately no longer in this table |
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
>
> ### **SUBSEQUENT NOTE — the transition later happened, properly.** The paragraph above is
> preserved verbatim as the record of a false claim and of the reasoning that caught it; it is
> **historical, and its closing sentence is no longer current.** P3 was afterwards genuinely
> reviewed by a fresh independent session and adjudicated COMPLETE by a separate adjudicating
> session, and P4 became the selected unit — that evidence lives in the live tables above, never
> here. The lesson is unchanged: **a false claim inside a quarantined block is more dangerous than
> one in live text**, which is why the roadmap-completeness drift guard reads live text only and
> requires historical blocks to be self-labelling rather than silently trusted.

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
