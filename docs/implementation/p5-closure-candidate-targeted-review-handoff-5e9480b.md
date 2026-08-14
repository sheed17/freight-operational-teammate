# P5 CLOSURE CANDIDATE — TARGETED-REVIEW HANDOFF

> # ⛔ HANDOFF — NOT CURRENT AUTHORITY, AND NOT A REVIEW
> **This is the closure author's handoff to a fresh targeted independent reviewer.** It certifies
> nothing, adjudicates nothing, sets no acceptance criterion, closes no risk and authorizes no
> finalization. The status authority is [`CURRENT.md`](CURRENT.md) and the registry; the operating
> guide is [`../../CLAUDE.md`](../../CLAUDE.md).
>
> ### **DO NOT TREAT ANY CLAIM BELOW AS EVIDENCE. RE-DERIVE EVERY ONE** from the object store and
> from execution. The P4 remediation handoff was wrong about two numbers (finding `RR-02`), and the
> P4 closure handoff named a guard function that **does not exist anywhere in the tree** (finding
> `F-TR-05`) — it is preserved uncorrected precisely so that *"a builder's handoff is untrusted
> input"* is not an abstraction. Assume this document contains at least one error too.

**Session:** the P5 final adjudicator. It adjudicated content commit `91ba4e6` and then authored the
closure content commit `5e9480b` that transcribes that adjudication. It did **not** implement P5,
remediate it, perform its independent review, or run any finalizer.

**Date:** 2026-08-14.

**Result: exactly ONE content commit created. Nothing else.**

> **P5 IS RECORDED COMPLETE AT 14/14. IT IS NOT FINALIZED. P6 IS `READY` AND MUST NOT BEGIN.
> R-07 REMAINS CONTAINED — unchanged. `main` REMAINS AT `152574e` — untouched.**

`finalize_status.py` was **NOT** run, and no finalizer receipt was fabricated. No independent review
and no targeted adjudication was performed by this session. Nothing under `src/` or `scripts/` was
modified. No `git checkout`, `restore`, `stash`, `clean`, `gc` or `prune` was used at any point. No
commit was amended. No protected ref moved. `refs/heads/main` and `refs/remotes/origin/main` are
both still `152574e4f4f2969468c9d31b1e705188896175b5`.

---

## 1. Exact identities — verify all of these first

| Property | Value |
|---|---|
| **Closure candidate (review THIS)** | `5e9480bf6c53485c3ed399952ed980f615055982` |
| Its parent | `4150149401d42252e7ca5be862f4c66c367f5f70` (the finalizer metadata commit) |
| Recorded `content_commit` in `CURRENT.md` | `91ba4e6560d456eeee5a3e8b96748319d358a33d` = `HEAD^^` |
| **Repository state** | `PRODUCING` — legal under `PROGRESS-PROTOCOL.md` §10 |
| Branch | `p5/u5-1-g2-spec-correction`, pushed to origin at `5e9480b` |
| Adjudication report | `p5-final-adjudication-report-91ba4e6.md`, SHA-256 `691f98c48e5ac01def4723ef5be043362a6441e97697377c17a8b36a9f2f1c28`, preserved at `refs/preserve/p5-final-adjudication-91ba4e6` (`af1e9b91`, parent `4150149`) |
| Independent review report | `p5-independent-review-report-1216254.md`, SHA-256 `f028696b68235a7700491585b230c3290081138825fa1fa31f860dcacdc533f0`, preserved at `refs/preserve/p5-independent-review-1216254` (`192aaad5`) |

### **The digest trap, stated so you do not report it as a defect.**
Both review artifacts' in-tree copies **differ from their `.sha256` sidecars**, and that is correct.
The sidecar authenticates the **byte-exact preserved original**; the in-tree copy carries one
prepended disarming banner required by
`test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale_claim`.
`p4-independent-rereview-report-0891d1a.md` diverges from its sidecar the same way for the same
reason. **Hash the preserve ref's blob, not the worktree file.** The final adjudication report has
no banner (it is current authority), so all three of its hashes agree.

---

## 2. What this commit does — and the ONE thing it must be checked hardest on

It transcribes the fourteen weighted results from the adjudication report's §E into the registry,
sets P5's triple to `COMPLETE / COMPLETE / PHASE_ACCEPTANCE_COMPLETE`, hands the selector to P6, and
corrects the record so that no live document asserts P5's infrastructure does not exist.

### **THE HIGHEST-RISK CHANGE IS THE GUARD RE-POINTING. ATTACK IT FIRST.**

Nine guards pinned the literal `ready == ["P5"]` or equivalent. All nine were changed. Function
names are frozen so `TEST-NODE-MANIFEST.json` node identity is unchanged (verify: node count 2675,
node set unchanged). **A closure commit that quietly loosens the guards protecting it is the single
most valuable defect you could find here.** Three were *generalised* rather than swapped, and each
generalisation is a place a reviewer should be suspicious:

| Guard | Change | What to attack |
|---|---|---|
| `test_bootstrap_hermeticity::test_the_implementation_graph_is_consistent_and_protects_the_safety_wall` | Was `ready == ["P5"]` + hand-named P4. Now derives the selector and checks the dependency contract for **whichever** unit holds it, plus a positive anchor sweeping P3/P4/P5 | Does it still refuse a selector whose dependency is not COMPLETE on a full-weight fully-PASS contract? Is the positive anchor real, or can the loop pass vacuously? |
| `test_rebaseline_invariants::test_exactly_one_ready_unit_and_it_is_p3` | Was `ready == ["P5"]` gating the R-07 CONTAINED record. Now requires the selector to be `P≥5` | ### **Does it still refuse a BACK-DATED R-07 record?** The claim is that on any tree where P4 was not adjudicated the selector is at P4 or earlier. **Test that claim.** |
| `test_p5_canonical_event_mint::test_the_recorded_program_invariants_are_untouched_by_this_unit` | Was `p5["status"] == "READY"` and all fourteen `PENDING`. Now branches: if COMPLETE, requires weights=100 and `independent_review` + `final_adjudication` both PASS; else requires READY + all PENDING | This is the guard that stops a **specification amendment** advancing a phase. Can a mint now reach COMPLETE through the new branch? It should not — it cannot supply either un-self-suppliable criterion |

The other six are literal re-points (`P5`→`P6`), plus `test_docs_control_system` and
`test_status_reality` whose adjudicated-phase sweeps **gained P5** (`("P3","P4")` → `("P3","P4","P5")`).
Confirm that widened coverage rather than moving it.

### **One new assertion FAILED its own mutation proof and was replaced. Verify the replacement.**
`test_status_reality` briefly asserted `P5\b.{0,400}ADJUDICATED` under `re.I`. A mutant that stripped
the word from the P5 record **still passed** — `re.I` matched unrelated lowercase "adjudication"
prose about P4 elsewhere in the file. That is the substring-guard failure `CLAUDE.md` §9 names. It is
now a filename assertion requiring `CURRENT.md` to cite both P5 evidence artifacts by name, and was
re-proven 3/3. **Re-run that mutation yourself; do not take 3/3 on trust.**

---

## 3. The registry/record changes

- **Fourteen criteria** `PENDING` → `PASS`, each with attributable evidence naming its source. Weights
  unchanged, still summing to exactly 100. **Verify none was invented, renamed, combined, deleted or
  reweighted against the frozen `PROGRAM-WEIGHTS.yaml` `acceptance_template`.**
- **P5 triple** → `COMPLETE / COMPLETE / PHASE_ACCEPTANCE_COMPLETE`. **P6** → `READY / NOT_STARTED /
  NO_CHECKPOINT`. Exactly one READY unit at all times.
- **Five sub-unit `final_adjudication` markers** `OWED` → `PERFORMED`; five `record_type` markers
  updated. No guard reads `record_type` — verify that claim.
- **`P6.prohibited_scope` gained `provenance (P7)`.** ### **Scrutinise this: it is the only change
  that touches a unit's contract.** The argument is that every other unit's `prohibited_scope` names
  the phase immediately after it (P5's named `entities (P6), provenance (P7)`) and P6's omitted P7
  while naming P8 and P9. It grants no scope and removes none. **A reviewer could reasonably call
  this out of an adjudicator's scope** — it is disclosed here rather than buried.

### The `derived:` block — the second-highest-risk change
Three fields moved: `active_phase` P5→P6, `single_ready_unit` P5→P6, `overall_program_percent`
22.0→34.0. **They were written by calling `progress_status.derive()`, not typed.** `content_commit`
and `content_tree` are deliberately untouched, and `current_phase_percent` stays 0.0. The P4 closure
commit `42ea24c` moved the identical three fields. **Re-derive all five percentages yourself and
confirm no number was raised by hand** — an inflated figure here is exactly what
`test_progress_protocol` exists to catch.

### Record corrections — `ADJ-P5-01`, `ADJ-P5-02`
`BUILD-STATUS.yaml`'s authored snapshot still asserted *"The event contracts, GC-1 corpus, replay
sandbox, audit reconstruction and PostgreSQL do not exist"* and *"U5.1 … IS STILL UNREVIEWED"*; two
further stale instances survived in `CURRENT.md` and the registry. Each is preserved in its own words.
The roadmap-completeness guard independently caught five navigation documents. **Check that every
preserved-in-own-words block is self-labelling and cannot be read as a live claim.**

### `ADJ-P5-03` — disclosed, not waived
`readiness_target: STAGING_READY` for the persistence infrastructure is **NOT met and is not claimed
met**. PostgreSQL is proven against a real server on a developer machine, never deployed to staging.
`readiness_target` is a maturity target, not one of the fourteen criteria; ADR-016 assigns deployment
to P11. **If you disagree that this is non-blocking, say so — it is the most arguable call here.**

---

## 4. What the adjudicator executed (re-execute, do not trust)

Canonical suite on the committed tree **2674 · 0 · 1**; clean-clone gate **9/9 exit 0**; PostgreSQL
P5 gate against a database it created (**26 steps, 0 on replay, 8 REFUSED, 2 controls ACCEPTED, 17
runtime probes PASS**); replay/audit mutants **24/24**; contract mutants **37/37**;
`generate_event_contracts.py --check` matches the specification; its own import-closure probe with a
positive control that fires.

### **Its first import-closure probe was DEFECTIVE and is reported as such** — empty closures for
every module and a positive control that found the control module absent, i.e. a probe that could not
have failed. The defect was relative-import resolution. **Verify the corrected probe independently**;
a closure proof is the load-bearing evidence for `CLAUDE.md` rule 11.

**Note on skips:** on a dirty tree the suite reports **3 skipped** — two are self-describing
`NOT-RUN: dirty working tree` skips in `test_status_reality`. On the committed tree it is **1
skipped** (the approved AC-SAFE-012/013 skip). If you see 3, commit or stash-free your tree first;
the finalizer refuses dirty trees and treats those skips as failure.

---

## 5. What must NOT happen next

- ### **Do not run the finalizer** until this commit has passed your review **and** a separate
  targeted adjudication. Precedent, twice, strictly ordered in commit time: P4 acceptance closure
  `42ea24c → c30a43b → d3cf1de → 06ebfdb`; R-07 closure `a31a94a → c26aeae → 035cb55 → 6e8127d`.
- ### **Do not add a second content commit to this branch.** Recorded `content_commit` is `HEAD^^`
  today (`PRODUCING`). A further commit makes it `HEAD^^^` — *"stale beyond every legal state"*.
  Preserve your report at `refs/preserve/p5-closure-targeted-review-<sha>` parented on `5e9480b`,
  with a digest sidecar, exactly as the adjudication was preserved. **This handoff is preserved the
  same way and is deliberately NOT in the working tree**, for this reason.
- ### **Do not touch `main`, and do not rebase, merge, squash or force-push anything.** `main` is at
  `152574e` in the known-illegal merge-commit state, and the P4/R-07/P5 work has never been
  integrated. That is **R-21 integration debt**, to be discharged by the binding
  `integration-topology-procedure.md` campaign **once, after P5 is formally COMPLETE** — not here.
- ### **Do not begin P6.** It is `READY`, which is selection only.

---

## 6. Retrieving this handoff

It is preserved at `refs/preserve/p5-closure-targeted-review-handoff-5e9480b`:

```
git show refs/preserve/p5-closure-targeted-review-handoff-5e9480b:docs/implementation/p5-closure-candidate-targeted-review-handoff-5e9480b.md
```
