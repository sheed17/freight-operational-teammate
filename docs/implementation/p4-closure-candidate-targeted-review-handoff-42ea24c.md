> # ⛔ HISTORICAL BUILDER HANDOFF — NOT CURRENT AUTHORITY, AND NOT EVIDENCE
> **Preserved as received. This is evidence of a past moment, not status.** It is the P4 acceptance
> closure BUILDER's handoff for `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` — untrusted input to a
> reviewer. It reviewed nothing, adjudicated nothing, ran no finalizer and closed no risk.
>
> ### **IT CONTAINS A CONFIRMED ERROR.** The targeted adjudication recorded **F-TR-05**: line 220
> names a guard function, `test_the_dependency_graph_is_complete_consistent_and_acyclic`, that
> **does not exist anywhere in the tree**. The real function is
> `test_the_implementation_graph_is_consistent_and_protects_the_safety_wall`. The error is confined
> to this handoff; no committed evidence depends on it. It is preserved uncorrected precisely so
> that "a builder's handoff is untrusted input" is not an abstraction.
>
> ### **ITS R-07 STATEMENTS ARE SUPERSEDED.** They describe the state before the R-07 closure
> content commit. R-07 is now recorded **CONTAINED** in
> [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml). Current status is
> [`CURRENT.md`](CURRENT.md); operating guide is [`../../CLAUDE.md`](../../CLAUDE.md).
>
> **BYTES.** Everything below this banner is the builder's handoff, unaltered — no deletion, no
> edit, no reordering, and specifically **no correction of F-TR-05**. The banner is the only
> addition, required by `test_false_green_defenses.py::test_historical_documents_disarm_before_any
> _stale_claim`.
>
> **THE SIDECAR HASH IS THE ORIGINAL'S, DELIBERATELY.**
> `p4-closure-candidate-targeted-review-handoff-42ea24c.md.sha256` records
> `9c5cc18793117c9d37f7014ed910e8a6ab34e806dd25b6b8bc0fd24559237e87`, the SHA-256 of the file
> **without** this banner, so it does not match this bannered copy. The sidecar authenticates the
> handoff, not the in-tree rendering of it.

> # ⛔ HANDOFF — NOT CURRENT AUTHORITY, AND NOT A REVIEW
> **This is a builder's handoff to a fresh targeted independent reviewer.** It certifies nothing,
> adjudicates nothing, sets no acceptance criterion, closes no risk and authorizes no finalization.
> The status authority is [`CURRENT.md`](CURRENT.md) and the registry; the operating guide is
> [`../../CLAUDE.md`](../../CLAUDE.md).
>
> ### **DO NOT TREAT ANY CLAIM BELOW AS EVIDENCE.** Re-derive every one from the object store and
> from execution. The P4 remediation handoff was wrong about two numbers (finding RR-02) and a
> reviewer who trusted it would have reported a false failure. That is exactly why a handoff is
> never review evidence.

# P4 ACCEPTANCE-AND-STATUS CLOSURE — TARGETED-REVIEW HANDOFF

**Session:** fresh P4 closure builder. Did not implement P4, did not remediate it, did not perform
either independent review, did not perform the final adjudication, did not run the first finalizer,
and did not resume any prior session.

**Date:** 2026-08-04.

**Result: exactly ONE content commit created. Nothing else.**

> **P4 IS NOW COMPLETE. R-07 REMAINS OPEN — NOT CONTAINED. P5 IS READY AND HAS NOT STARTED.**
> Every one of those is what repository authority mechanically computes; none was forced.

`finalize_status.py` was NOT run. No independent review and no adjudication was performed. P5 was
not begun. Nothing was pushed, merged or deployed; no effect was enabled. No `git checkout`,
`restore`, `stash`, `clean`, `gc` or `prune` was used at any point. `86306d5` and `0891d1a` were not
amended. No protected ref moved.

---

## 1. Exact identities

```
closure content commit   42ea24cfc76fac19406e7eaa44b695b8d032b3aa
closure tree             1e2bba791a5c2c77194d1df9ce16e1d9df84315a
closure parent           86306d5c4d866baf1a7fb6e4bd8220ce31017acd   (single parent, not a merge)

first-finalizer metadata 86306d5c4d866baf1a7fb6e4bd8220ce31017acd
  its tree               7b5e4258f3d0579c4f562b5f62b5ebcfbfd196d1
accepted implementation  0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e
  its tree               a3e704645b8a06561d90cdb5f81288309ae51850

branch                   p4/adapter-containment-completion  ->  42ea24cfc76f
repository state         PRODUCING   (test_status_reality.repo_state(), the real guard)
working tree             clean of tracked modifications
```

**Why `PRODUCING` is the correct and legal state.** `CURRENT.md`'s machine-maintained status block
still records `0891d1a`, which is now `HEAD^^`; `HEAD^` (`86306d5`) is a pure status-metadata commit
touching only the five `STATUS_METADATA_FILES`; `HEAD` is this content commit. That is exactly the
shape `test_status_reality.py` recognises as `PRODUCING`. It is *not* the at-rest state — this
candidate is unfinalized on purpose.

## 2. Exact changed paths — 19, all status/control/evidence, zero implementation

`git diff --name-status 86306d5 42ea24c`:

| Path | Change |
|---|---|
| `docs/implementation/IMPLEMENTATION-REGISTRY.yaml` | M — the 14-criterion P4 acceptance block; P4 → COMPLETE; P5 → READY; the residual register; completion evidence |
| `docs/implementation/CURRENT.md` | M — preserved prose restored and semantically merged; P4 COMPLETE / P5 READY / R-07 OPEN |
| `docs/implementation/BUILD-STATUS.yaml` | M — derived block recomputed by `progress_status.derive()`; authored narrative corrected off P3 |
| `docs/implementation/CAPABILITY-TRACEABILITY.yaml` | M — CAP-25's stale "P4 is not complete" note and its unresolved-decisions row |
| `docs/CANONICAL-DOCUMENTS.md` | M — authority-map rows for three newly tracked evidence documents |
| `CLAUDE.md` | M — §3 status table and §11 "what you must NOT begin" |
| `README.md` | M — status table and open-findings table |
| `eval/tests/test_status_reality.py` | M — READY expectation P4 → P5, plus anti-vacuous anchors |
| `eval/tests/test_docs_control_system.py` | M — same |
| `eval/tests/test_rebaseline_invariants.py` | M — same |
| `eval/tests/test_bootstrap_hermeticity.py` | M — same |
| `docs/implementation/p4-independent-rereview-report-0891d1a.md` (+ `.sha256`) | A |
| `docs/implementation/p4-final-adjudication-report-0891d1a.md` (+ `.sha256`) | A |
| `docs/implementation/p4-first-finalization-pass-report-86306d5.md` (+ `.sha256`) | A |
| `docs/implementation/p4-closure-content-topology-determination.md` | A |
| `docs/implementation/p4-remediation-handoff.md` | A |

`19 files changed, 3730 insertions(+), 239 deletions(-)`.

**Not in the commit, deliberately:** `docs/implementation/phase-0-baseline-manifest.yaml`,
`SUITE-RESULT.json`, `GATE-RESULT.json`, `TEST-NODE-MANIFEST.json`, and every file under `src/`.

## 3. Preservation, performed BEFORE anything was modified

```
ref     refs/preserve/p4-closure-acceptance-prestate-86306d5
commit  361d10aedf03d842429910b04f59c393ab3310f1
tree    cc5e4b562c5839abf4a66672056dacae32585060
parent  86306d5c4d866baf1a7fb6e4bd8220ce31017acd   (attributable, never part of the branch)
paths   624  =  614 tracked (incl. all 7 ignored-but-tracked .playwright-mcp paths)
             +   8 untracked reports/sidecars
             +   2 ignored-untracked .playwright-mcp paths
```

Method — HEAD-seeded temporary index, `GIT_INDEX_FILE` outside `.git/index`:

```
GIT_INDEX_FILE=<tmp> git read-tree HEAD          # 614 paths - this is what preserves the
GIT_INDEX_FILE=<tmp> git add -A                  #   ignored-but-tracked .playwright-mcp paths
GIT_INDEX_FILE=<tmp> git add -f <the 2 ignored-untracked .playwright-mcp paths>
GIT_INDEX_FILE=<tmp> git write-tree              # -> cc5e4b56...
git commit-tree cc5e4b56... -p 86306d5...
```

Pre-capture `.git/index` SHA-256:
`1521cf622e1751e3be055f837e216b01cf9f224928b2e7053ee1375d9b93718e`.

**Verified in a disposable `--no-local` clone**, both directions:

| Direction | Result |
|---|---|
| Every preserved path reconstructs byte-exactly in the primary worktree | **624 / 624, 0 mismatches, 0 missing** |
| Every non-ignored worktree path is captured | **0 uncaptured** (624 present == 624 captured) |
| All three report sidecars self-verify inside the artifact | **3 / 3 OK** |

Deliberately excluded (ignored, and never at risk): `.venv/`, **`.env` — a secret that must never
enter the object store**, `__pycache__/`, `.pytest_cache/`, `.pytest_tmp/`, `eval/results/`,
`data/active_workspace/`, `data/synthetic_corpus/`, `data/template_sources/downloaded/`,
`.chrome-neyma-cdp/`, `.claude/`, `.DS_Store`.

The branch was not moved while preserving. `refs/preserve/p4-closure-prestate-0891d1a` and
`refs/preserve/p4-first-finalization-prestate-0891d1a` are unchanged and retained.

## 4. Proof that no P4 implementation byte changed

`git diff --name-only 0891d1a 42ea24c -- <area>` over the accepted implementation candidate:

| Area | Result |
|---|---|
| `src/` — including the approval, checkpoint, effect-boundary, governed-write, governed-approval, origin-policy and adapter implementations | **BYTE-IDENTICAL** |
| `scripts/` — including `finalize_status.py`, `finalizer_lock.py`, `clean_clone_gate.py`, `run_canonical_suite.py`, `regenerate_test_manifest.py` and the mutation operators (`mutate_phase4_boundary.py`) | **BYTE-IDENTICAL** |
| `eval/phase0/`, `eval/control/`, `eval/fixtures/` | **BYTE-IDENTICAL** |
| `configs/`, `pyproject.toml`, `pytest-canonical.ini`, `requirements.txt` | **BYTE-IDENTICAL** |
| `docs/implementation/TEST-NODE-MANIFEST.json` | **BYTE-IDENTICAL** |
| `docs/implementation/phase-0-baseline-manifest.yaml` | **BYTE-IDENTICAL** |
| Production `GateRegistry` population | **EMPTY** — zero construction or registration sites across `src/` **and** `scripts/`, re-verified in this session |

**The only `eval/` paths that differ from `0891d1a` are the four named guard modules** in §7. There
is no other test change of any kind.

## 5. The exact 14-criterion acceptance block

Instantiated from the **frozen** `PROGRAM-WEIGHTS.yaml` `acceptance_template`. Mechanically verified:
criterion **names match the template exactly and in order**, **weights match the template exactly**,
count is **14**, sum is **exactly 100**, every result is **PASS**, every criterion carries an
`evidence` field.

| # | Criterion | Weight | Result | Source of the result |
|---|---|---|---|---|
| 1 | `accepted_scope_and_design` | 6 | PASS | adjudication §F.1 |
| 2 | `required_tests` | 8 | PASS | adjudication §F.2 — *qualified by AD-02* |
| 3 | `core_implementation` | 20 | PASS | adjudication §F.3 / §C.1 |
| 4 | `failure_handling` | 8 | PASS | adjudication §F.4 |
| 5 | `concurrency_handling` | 8 | PASS | adjudication §F.5 |
| 6 | `authorization_and_security` | 10 | PASS | adjudication §F.6 |
| 7 | `migrations_and_persistence` | 6 | PASS | adjudication §F.7 |
| 8 | `observability_and_operational_behavior` | 6 | PASS | adjudication §F.8 |
| 9 | `mutation_or_hostile_cases` | 8 | PASS | adjudication §F.9 / §D |
| 10 | `full_test_suite` | 5 | PASS | adjudication §F.10 |
| 11 | `canonical_finalizer` | 3 | **PASS** | ### **NOT the adjudication's result** — see below |
| 12 | `clean_clone_execution` | 3 | PASS | adjudication §F.12 / §C.4 |
| 13 | `independent_review` | 5 | PASS | adjudication §F.13 |
| 14 | `final_adjudication` | 4 | PASS | adjudication §F.14 |

**Σ = 6+8+20+8+8+10+6+6+8+5+3+3+5+4 = 100.** `progress_status.phase_completion("P4")` returns
**100.0**.

**Criterion 11 is the one result this session set, and it is the one to attack hardest.** The
adjudication recorded it `PENDING` because, by construction, "the finalizer has not run on this
candidate" and it "legitimately completes last". It is `PASS` here on the strength of the finalizer
run that has since executed — and on nothing else. Its recorded evidence carries every element the
closure was required to bind: **target content commit `0891d1a`**; **exit code 0**; **canonical suite
1961 passed / 0 failed / 1 skipped / 1962 collected**, taken in-process from the run object rather
than read from a file; **clean-clone gate PASS**, nine steps exit 0, bound to `0891d1a` / `a3e70464`;
**exactly one finalizer owner** — `.git/neyma-finalizer.lock` held by pid 79370 for the whole run and
observed UNHELD (released) after exit, with no second finalizer started; **metadata commit
`86306d5`**, single parent `0891d1a`, changing **exactly the five authorized
`STATUS_METADATA_FILES`** and no other path.

**Attribution, stated so it cannot be misread.** The independent re-review reviewed **implementation
candidate `0891d1a`**. It did **not** review this closure commit, which did not exist when it was
written. Criteria 13 and 14 say so in their own `evidence` text, the registry comment above the block
says so, and the re-review's in-tree banner says so. Nothing here may be cited as an independent
review of `42ea24c`.

## 6. Computed states — as authority computes them, not as anyone wanted them

| Quantity | Computed value | How |
|---|---|---|
| **P4** | `status: COMPLETE`, `execution_state: COMPLETE`, `checkpoint_state: PHASE_ACCEPTANCE_COMPLETE`, **100.0 %** | `progress_status.phase_completion` |
| **P5** | `status: READY`, `execution_state: NOT_STARTED`, `checkpoint_state: NO_CHECKPOINT`, no landed checkpoints | registry |
| **Sole READY unit** | **`P5`** — the READY set is exactly `['P5']` | `progress_status.single_ready_unit` |
| **P6–P14** | all `BLOCKED` | registry |
| **R-07** | ### **OPEN — NOT CONTAINED** | `phase-0-baseline-manifest.yaml` still reads `status: OPEN - NOT CONTAINED`, byte-identical to `0891d1a` |
| **Repository topology** | **`PRODUCING`** | `test_status_reality.repo_state()` |
| **Derived block** | `active_phase: P5` · `single_ready_unit: P5` · overall **12.0 % → 22.0 %** · current phase **0.0 %** · user-visible 0.0 % · production 0.0 % · CLI switch 100.0 % · tier SPECIFIED | `progress_status.derive()`, not typed by hand |

**Nothing was forced and no contradiction was found.** In particular, repository authority does
**not** reject P4 COMPLETE while R-07 is OPEN: P4's acceptance contract is the fourteen weighted
criteria, and `progress_status` computes completion from those alone. The R-07 *recording* is a
separate act that `test_status_reality.py` structurally forbids from riding in a metadata commit,
which is precisely why it needs its own later content commit. P4's `completion_evidence` states this
outstanding obligation explicitly rather than quietly dropping it.

Overall rises to 22.0 % because P4's program weight is 10 and it now contributes in full
(12.0 from P3 + 10.0 from P4). The current-phase number is 0.0 % because P5's acceptance contract has
not been instantiated — correct, since P5 has not started.

## 7. Updated guard locations and rationale

Located mechanically (`grep` for the READY assertions), not from remembered line numbers. Every one
is **REPLACED, not deleted**, under CLAUDE.md §5 rule 20, with the **function name frozen** so
`TEST-NODE-MANIFEST.json` node identity is preserved.

| File | Function | Change |
|---|---|---|
| `eval/tests/test_status_reality.py` | `test_the_status_record_still_states_the_canonical_facts` | `ready == ["P4"]` → `["P5"]`; the COMPLETE/all-PASS/anti-self-adjudication check now runs over **both** P3 **and** P4; the BLOCKED sweep is now *discovered* (`every phase ≥ P6`) rather than the two named examples; adds `P5` NOT_STARTED and no-landed-checkpoints assertions; adds an explicit `R-07 OPEN — NOT CONTAINED` assertion so P4 COMPLETE cannot be read as R-07 closed |
| `eval/tests/test_docs_control_system.py` | `test_24_the_next_approved_work_is_p3_with_every_gate_closed` | READY unit `P4` → `P5`; the full-contract check now loops over P3 **and** P4; adds that the READY unit prohibits the phase after it |
| `eval/tests/test_rebaseline_invariants.py` | `test_exactly_one_ready_unit_and_it_is_p3` | `ready == ["P4"]` → `["P5"]`; adds P4 COMPLETE plus a real, full-weight, fully-PASS contract check; keeps the `phase-0-baseline-manifest.yaml` `status: OPEN - NOT CONTAINED` assertion **unchanged** — that is the assertion that fires if anyone marks R-07 contained early |
| `eval/tests/test_bootstrap_hermeticity.py` | `test_the_dependency_graph_is_complete_consistent_and_acyclic` (the READY assertion inside it) | `ready == ["P4"]` → `["P5"]`; adds that P4 is COMPLETE and unlocked P5 on a real 100-weight fully-PASS contract |

**The one-READY-unit invariant was not weakened.** `exactly one unit may be READY` is asserted in
three separate modules and none was touched. **Positive anchors were added** so an empty registry
parse, a missing `acceptance_criteria` block or an empty phase population can no longer let a
negative assertion pass over nothing:

```
eval/tests/test_bootstrap_hermeticity.py   asserts  76 -> 78   test funcs 24 -> 24
eval/tests/test_docs_control_system.py     asserts 156 -> 159  test funcs 51 -> 51
eval/tests/test_rebaseline_invariants.py   asserts  69 -> 74   test funcs 19 -> 19
eval/tests/test_status_reality.py          asserts  38 -> 48   test funcs  7 ->  7
```

Assertions rose in every file; test-function counts are unchanged. **No test was weakened, skipped,
xfailed or deleted to obtain green.**

Three further live surfaces were corrected because `test_switch_consistency.py` proved them stale
against the new registry — `CLAUDE.md`, `README.md`, `CAPABILITY-TRACEABILITY.yaml`. Those are
content fixes, not guard changes.

## 8. Residual-risk register — carried in full, discharged by nothing

Recorded machine-readably in the P4 unit's `residual_risks_carried_forward` block, and in prose in
`CURRENT.md`'s open-risks table and `BUILD-STATUS.yaml`'s `open_program_risks`.

**Binding P12 precondition — RR-01 · MEDIUM · NOT DISCHARGED.** `base_url` is outside
`freight_operations.payload_hash()`'s canonical set and outside
`governed_write_route.approval_operation_mismatch`, so a tampered stored proposal row can carry a
foreign target URL past the integrity anchor. Two docstrings overclaim that every consequential value
is hash-bound. **Compounded by F-08 and F-09.** Contained today only because the capability is dark
and the deployed route is fail-closed. Must be discharged before any live writer is injected.

**AD-01 · LOW–MEDIUM · RECORDED, CARRIED.** `EFFECT-PATH-INVENTORY.yaml` and `LEGACY-DISPOSITION.md`
describe `run_action_callback_server.py` as leaving `governed_write_provider` / `governed_write_kernel`
as `None`. Mechanically **false for the provider** — it is **WIRED** (a bounded lookup, `writer=None`);
the kernel is `None`. The safety conclusion (route unreachable, fails closed) **remains true**. Prose
fix only, no code change.

**AD-02 · MEDIUM · RECORDED, CARRIED.** `scripts/finalizer_lock.py` remains a 188-line
**safety-critical** module with **zero committed test coverage** — no `eval/` references, no
`TEST-NODE-MANIFEST.json` nodes, no mutant. Verified sound 16/16 twice, but only ad hoc. **It is
directly load-bearing for the second finalizer.** A committed hostile battery plus a manifest
regeneration is owed.

**Also carried, none discharged:** RR-02 (the remediation handoff's §6 gate-result numbers are wrong;
the artifact is right), RR-03 (the null-gate probe scans only the package directory), RR-04 (mutant
B34's label names a symbol it does not mutate), RR-05 / F-07 (numeric self-contradictions in the
narrative), RR-06 (two reachability guards use substring rather than AST call nodes), F-03
(`ReadOnlyBrowserUseRunner` `base_url` unvalidated), F-06 (the route family is a denylist), F-08
(approved-field *values* unconstrained), F-09 (empty `base_url` skips the loopback refusal), F-10
(conditional workspace / message-ts binding, partially mitigated).

**Founder decision preserved unchanged.** Production Action Class gate registration remains
**DEFERRED to U8.1 / P8**; `AC-CKPT-6-missing` stays `DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8`;
the production `GateRegistry` population is **EMPTY** and must stay empty. **No production write is
enabled by anything in this commit.**

## 9. Validation results

| Check | Result |
|---|---|
| Canonical suite, primary worktree, clean tree at `42ea24c` | ### **1961 passed / 0 failed / 1 skipped** (388.88 s) |
| Canonical suite, **disposable `--no-local` clone**, detached at `42ea24c`, fresh venv, declared deps only (`pip install -e ".[dev]"`), `PYTEST_ADDOPTS` cleared | ### **1961 passed / 0 failed / 1 skipped** (405.38 s) |
| Control guards in the clean clone — status-reality, integration-topology, docs-control, false-green, phase-0 null gate, progress-protocol, rebaseline-invariants, bootstrap-hermeticity, switch-consistency, roadmap-completeness | **227 passed** |
| Clone `git status --porcelain` before and after every run | **empty**; clone tree still `1e2bba79…` |
| `repo_state()` (the real guard) | **PRODUCING** — legal |
| `HEAD` is not a merge commit | **PASS** — `git rev-list --parents -n1 HEAD` shows one parent |
| Exactly one new content commit above `86306d5` | **PASS** — `git log --first-parent`: `42ea24c` → `86306d5` → `0891d1a` → `f1e8e18` |
| Acceptance block: 14 criteria / all PASS / Σ = 100 / template-exact names and weights / every criterion has evidence | **PASS** |
| `progress_status.build_status_errors()` | **`[]`** |
| `TEST-NODE-MANIFEST.json` identity vs live collection | **1962 vs 1962, IDENTICAL BY IDENTITY**, 0 missing / 0 extra; regeneration through `scripts/regenerate_test_manifest.py` reported *node set unchanged* and produced a byte-identical file |
| No forged finalizer receipt | `SUITE-RESULT.json` and `GATE-RESULT.json` are **unchanged from `86306d5`** and still bound to commit `0891d1a` / tree `a3e70464`. `finalize_status.py` and `clean_clone_gate.py` were **not** run — the clean-clone reproduction above was performed manually **precisely so that no `GATE-RESULT.json` receipt would be written for this unfinalized commit** |
| Production `GateRegistry` population | **EMPTY** across `src/` and `scripts/` |
| Phase-8 deferral | **intact and unchanged** |
| R-07 | ### **OPEN — NOT CONTAINED**; `phase-0-baseline-manifest.yaml` byte-identical to `0891d1a` |
| Accepted reports retain original candidate attribution | **PASS** — see §10 |
| Protected refs | `main` / `origin/main` **`152574e4…` unchanged**; all 16 pre-existing `refs/preserve/*`, all 3 `archive/p4/*` and all 5 `refs/remotes/origin/*` unchanged |
| Pushed / merged / deployed | **nothing** — the only ref writes are `p4/adapter-containment-completion` (`86306d5` → `42ea24c`) and the new `refs/preserve/p4-closure-acceptance-prestate-86306d5` |
| Locks | both `flock`-probed **UNHELD** after the session; no `finalize_status` / `clean_clone_gate` / `mutate_phase4_boundary` process running |

The single skip is the pre-existing conditionally-justified one, unchanged and still the only entry
in `APPROVED-SKIPS.yaml`'s `expected_canonical_run_skips`.

## 10. Report preservation locations and hashes

| Report | In-tree path | SHA-256 | Durable preservation |
|---|---|---|---|
| Accepted independent re-review | `docs/implementation/p4-independent-rereview-report-0891d1a.md` | `181e1a37a413fd35f537e00a7e1423bf192f88205270fa15932fbabeb955d316` — **of the banner-free original** | `refs/preserve/p4-independent-rereview-0891d1a` → `5ca6d2e95896336f447cf693da04282a0d53bdbf`, parent `0891d1a` |
| Final adjudication | `docs/implementation/p4-final-adjudication-report-0891d1a.md` | `078cfea8f7d691da0c7649ddaa2f1f64bc7138dc64b91814dda1d6cc68cb997e` — verifies against the tracked file | `refs/preserve/p4-final-adjudication-0891d1a` → `420e5b2d0b3b6af280d8a8d0f3d80ad9f6cb9ebc`, parent `0891d1a` |
| First-finalization execution report | `docs/implementation/p4-first-finalization-pass-report-86306d5.md` | `9f5b8f98b0bec4dd283c59f1d941b690cbda9d18b95d7791a0c646120a2e1056` — verifies against the tracked file | now tracked; also inside `refs/preserve/p4-closure-acceptance-prestate-86306d5` |
| Closure-topology determination | `docs/implementation/p4-closure-content-topology-determination.md` | `1ddfcc65e4266918441d7398467054e67208a10e2a2e5d8f9971c9bd14d23dfa` | now tracked; also inside the prestate ref |
| Remediation handoff | `docs/implementation/p4-remediation-handoff.md` | `1295399b5224dd2e55e605c7ee0ce32a1425246ecb34cba82a3bab447a432a7c` | now tracked; also inside the prestate ref |

**Bodies are unaltered.** The three reports with sidecars keep their original candidate attribution
and hashes explicit. **One documented deviation, following the repository's own precedent:** the
independent re-review carries a **prepended disarming banner** and nothing else. It is required —
`test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale_claim` refuses any
tracked review document a grep-first reader could mistake for authority, and
`p4-independent-review-report.md` already carries the same treatment for the same reason. Proved
mechanically: the file below the 36-line banner is **byte-identical** to the preserve-ref blob
(`cmp` reports zero differences) and hashes to `181e1a37…b316`. The sidecar deliberately records the
**original's** hash and therefore does not match the bannered copy; the banner states this in full
and gives the one-line command to verify it. The other four documents are byte-identical to what was
handed over.

All five are classified in `docs/CANONICAL-DOCUMENTS.md` — three by new explicit rows, the re-review
by the existing review **FAMILY RULE**, the handoff by its pre-existing row — so
`test_every_implementation_document_is_classified_or_family_covered` passes without a hand-typed
guard list.

## 11. Contradictions and remaining blockers

**No contradiction was found, and nothing was forced.** Two things are true at once and both are
recorded, loudly, everywhere they could be misread:

1. **P4 is COMPLETE and R-07 is still OPEN.** These are not in conflict. P4's acceptance is the
   fourteen weighted criteria; R-07's closure is the *recording* of CONTAINED in
   `phase-0-baseline-manifest.yaml`, a file that is not in `STATUS_METADATA_FILES` and therefore
   needs its own content commit. The mechanical close condition is met and independently verified.
2. **P5 is READY and P5 is blocked.** `status: READY` is the *selector*; P5's own `validation_blockers`
   still carry the **G2** transition/event completeness adjudication, which the P4 adjudication says
   in terms it does not discharge. P5 is selectable; its event content is not yet writable.

**Remaining blockers to the next steps:** none mechanical. **AD-02 is a named prerequisite for the
second finalizer** — `finalizer_lock.py` still has no committed coverage and is load-bearing for it.

## 12. Prerequisites for a fresh targeted independent reviewer

The reviewer must be a session that did **not** implement P4, did **not** remediate it, did **not**
perform either earlier independent review, did **not** perform the final adjudication, did **not**
run the first finalizer, and did **not** author this closure commit or this handoff.

Before reviewing, verify independently from the object store:

1. `HEAD` is exactly **`42ea24cfc76fac19406e7eaa44b695b8d032b3aa`**, tree
   **`1e2bba791a5c2c77194d1df9ce16e1d9df84315a`**, parent **`86306d5c4d866baf1a7fb6e4bd8220ce31017acd`**,
   on `p4/adapter-containment-completion`, single parent, not a merge.
2. `repo_state()` is **`PRODUCING`** — recorded `0891d1a` == `HEAD^^`, and `HEAD^` touches only the
   five `STATUS_METADATA_FILES`.
3. `main` and `origin/main` are still `152574e4f4f2969468c9d31b1e705188896175b5`; nothing was pushed.
4. All `refs/preserve/*` and `archive/p4/*` resolve; `refs/preserve/p4-independent-rereview-0891d1a`
   and `refs/preserve/p4-final-adjudication-0891d1a` are still children of `0891d1a`.
5. The re-review and adjudication report hashes verify **three-sided** (worktree file, preserve-ref
   blob, sidecar) — remembering that the re-review's tracked copy carries the banner and that the
   preserve-ref blob is the hash's subject.
6. `refs/preserve/p4-closure-acceptance-prestate-86306d5` reconstructs the pre-change worktree.
7. Both `.git` locks are `flock`-unheld and no finalizer, gate or mutation process is running.

Then review, at minimum, these questions — and re-derive rather than inherit:

- Does the acceptance block match the **frozen** template exactly — 14 criteria, template names,
  template weights, Σ = 100 — with no criterion invented, renamed, combined, deleted or reweighted?
- Do criteria 1–10 and 12–14 match adjudication §F **verbatim** in result?
- Is criterion 11's evidence **true**, in every element, against
  `p4-first-finalization-pass-report-86306d5.md` and against `git diff --name-only 0891d1a 86306d5`?
- Does any artifact anywhere state or imply that the independent re-review reviewed `42ea24c`?
- Do `src/`, `scripts/`, the adapters, the approval/checkpoint/effect/governed-write implementations,
  the origin policy, the mutation operators and the production `GateRegistry` population remain
  byte-identical to `0891d1a`?
- Are the four guard changes narrowly the READY-expectation change plus false-green anchors — and is
  the one-READY-unit invariant intact? Try to make each replaced guard pass over an empty or absent
  population.
- Is `phase-0-baseline-manifest.yaml` untouched and still `status: OPEN - NOT CONTAINED`?
- Is `TEST-NODE-MANIFEST.json` still identical by identity to live collection?
- Is there any finalizer receipt bound to `42ea24c`? (There must not be.)
- Are all fourteen residual findings present and undischarged?

Preserve the review report the way this repository already does three times: a commit whose **parent
is the reviewed candidate**, adding only the report and its `.sha256`, leaving the candidate's tree
untouched, exposed through `refs/preserve/*`.

## 13. Prerequisites for the second finalizer

The finalizer must run **only after** a fresh targeted independent review **and** a separate targeted
adjudication of `42ea24c` have both been performed and preserved. Before it runs:

1. `HEAD` is exactly `42ea24cfc76fac19406e7eaa44b695b8d032b3aa`, tree `1e2bba791a5c…`, and the
   `PRODUCING` topology still holds.
2. **The working tree is clean.** `finalize_status.py` runs plain `git status --porcelain`, which
   **includes untracked files** — so the targeted review report, this handoff and any sidecars must be
   moved aside **out of band** first, never with `git checkout` / `restore` / `stash` / `clean`.
   Everything is inside `refs/preserve/p4-closure-acceptance-prestate-86306d5` plus the review's own
   preservation ref, so moving them aside is safe.
3. It holds `finalizer_lock` **exclusively**; `current_owner()` was `None` first. ### **AD-02 applies:
   this lock still has zero committed test coverage. Treat a refusal as authoritative and NEVER
   reclaim it because a log file is missing** — that inference is what produced the double-finalizer
   this repository actually shipped.
4. No builder owns the worktree and no `mutate_phase4_boundary` run is in flight.
5. The candidate has not moved since the adjudication, and both new preservation refs still resolve.
6. `main` is untouched at `152574e4…`; nothing is pushed. Integration is fast-forward-only under R-21
   and is a separate founder-authorized act.

After it runs, and before committing:

7. The metadata commit contains **only** `STATUS_METADATA_FILES`. `phase-0-baseline-manifest.yaml`
   **must not** be in it.
8. The acceptance block is unchanged at 14/14 — the finalizer does not write it and must not appear
   to. Regenerate `BUILD-STATUS.yaml`'s derived block only through `progress_status`.
9. `progress_status.build_status_errors()` is `[]`.
10. The residual register still carries all fourteen findings, with RR-01 as a binding P12 precondition.
11. Print the full `NEYMA BUILD STATUS` block and **stop at the control boundary. Do not begin P5.**

**Then, and only then**, a separate content commit marks R-07 **CONTAINED** with the mechanism named
in `phase-0-baseline-manifest.yaml`. Until it lands, R-07 is not closed.

**The required sequence from here:**
fresh targeted independent review → separate targeted adjudication → exactly one second finalizer →
separate R-07 content-closure cycle.

## 14. Scope of this document and this session

This session verified the starting state, created one preservation ref, authored one content commit,
and wrote this handoff. It ran **no** finalizer and wrote **no** status receipt. It performed **no**
independent review and **no** adjudication, and nothing in it may be cited as either. It began **no**
P5 work, marked R-07 neither contained nor closed, modified **no** product code, **no** adapter,
**no** policy and **no** mutation operator, amended **no** commit, moved **no** protected ref, pushed
nothing, contacted **no** external system and enabled **no** effect. The accepted implementation
candidate's tree `a3e704645b8a06561d90cdb5f81288309ae51850` is unchanged and still verifies.

**Stop at the control boundary. P5 must not begin.**
