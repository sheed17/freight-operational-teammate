> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **Preserved as received. This is evidence of a past moment, not status.** It is the TARGETED
> INDEPENDENT REVIEW of the P4 acceptance closure content commit
> `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` (tree `1e2bba791a5c2c77194d1df9ce16e1d9df84315a`),
> **not** an adjudication: it set no acceptance criterion, marked no phase complete, closed no risk
> and authorized no finalization. It returned **ACCEPT FOR SEPARATE TARGETED ADJUDICATION**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The R-07 closure content commit did not
> exist when this was written, and its R-07 statements describe the state BEFORE that commit —
> R-07 is now recorded **CONTAINED** in
> [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml). Nothing here may be cited as
> an independent review of the R-07 closure commit, which owes its own fresh targeted review and
> its own targeted adjudication. The separate adjudication that acted on this report is
> [`p4-closure-candidate-targeted-adjudication-report-42ea24c.md`](p4-closure-candidate-targeted-adjudication-report-42ea24c.md);
> current status is [`CURRENT.md`](CURRENT.md); operating guide is [`../../CLAUDE.md`](../../CLAUDE.md).
>
> **BYTES.** Everything below this banner is the reviewer's report, unaltered — no deletion, no
> edit, no reordering. The banner is the only addition, and it is required by this repository's own
> control system (`test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale
> _claim`), which refuses any tracked historical review a grep-first reader could mistake for
> authority.
>
> **THE SIDECAR HASH IS THE ORIGINAL'S, DELIBERATELY.**
> `p4-closure-candidate-targeted-review-report-42ea24c.md.sha256` records
> `5547aa5e8d89ced661b4f6e415767f8259809bdf5d175615065158fa871a8ea5`, the SHA-256 of the reviewer's
> file **without** this banner. It therefore does **not** match this bannered copy, and that is
> correct: the sidecar authenticates the report, not the in-tree rendering of it. The byte-exact
> original is preserved unmodified at `refs/preserve/p4-closure-targeted-review-42ea24c`, a commit
> whose parent is the reviewed candidate `42ea24c`. To verify:
>
> ```
> git show refs/preserve/p4-closure-targeted-review-42ea24c:docs/implementation/p4-closure-candidate-targeted-review-report-42ea24c.md | shasum -a 256
> # expect 5547aa5e8d89ced661b4f6e415767f8259809bdf5d175615065158fa871a8ea5
> ```

# ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY, AND NOT AN ADJUDICATION

> **This is a FRESH TARGETED INDEPENDENT REVIEW.** It sets no acceptance criterion, marks no phase
> complete, closes no risk, awards no weight and authorizes no finalization. It reviewed the P4
> acceptance-and-status **closure content commit**
> `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` (tree `1e2bba791a5c2c77194d1df9ce16e1d9df84315a`,
> parent `86306d5c4d866baf1a7fb6e4bd8220ce31017acd`).
>
> The status authority is [`CURRENT.md`](CURRENT.md) and
> [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml); the operating guide is
> [`../../CLAUDE.md`](../../CLAUDE.md). This document owes a **separate targeted adjudication**
> before any second finalizer runs. Nothing here may be cited as that adjudication.

# P4 CLOSURE CANDIDATE — FRESH TARGETED INDEPENDENT REVIEW REPORT

**Reviewed candidate: `42ea24cfc76fac19406e7eaa44b695b8d032b3aa`**

**Date:** 2026-08-04.

---

## A. Exact artifact verified

Every hash below was re-derived from the object store with `git cat-file` / `git rev-parse`. No
abbreviated hash was trusted, and no claim was inherited from the handoff.

```
closure content commit   42ea24cfc76fac19406e7eaa44b695b8d032b3aa   VERIFIED
closure tree             1e2bba791a5c2c77194d1df9ce16e1d9df84315a   VERIFIED
closure parent           86306d5c4d866baf1a7fb6e4bd8220ce31017acd   VERIFIED, single parent
object type              commit (not a tag, not a merge)            VERIFIED

first-finalizer metadata 86306d5c4d866baf1a7fb6e4bd8220ce31017acd
  its tree               7b5e4258f3d0579c4f562b5f62b5ebcfbfd196d1   VERIFIED
  its parent             0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e   VERIFIED

accepted implementation  0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e
  its tree               a3e704645b8a06561d90cdb5f81288309ae51850   VERIFIED
  its parent             f1e8e1893eff2460d68f3f168f18fd29635b250d   VERIFIED

branch                   p4/adapter-containment-completion -> 42ea24c   VERIFIED
```

| Identity requirement | Result |
|---|---|
| Candidate commit, tree and parent are exactly as specified | **PASS** |
| Exactly ONE content commit above the first finalizer metadata commit | **PASS** — `git log --first-parent 86306d5..42ea24c` returns exactly `42ea24c` |
| No second consecutive content commit | **PASS** — the chain is `42ea24c` (content) → `86306d5` (metadata) → `0891d1a` (content); `42ea24c` has no children in any ref |
| Repository state is legal `PRODUCING` | **PASS** — recomputed through `test_status_reality.repo_state()`: recorded `content_commit` `0891d1a` == `HEAD^^`; `HEAD^` (`86306d5`) changed exactly the five `STATUS_METADATA_FILES` and no stray path |
| Nothing pushed | **PASS** — `git ls-remote --heads origin` (live, network reachable) carries **no** `p4/adapter-containment-completion` ref; five commits are unpushed |
| `main` / `origin/main` unmoved | **PASS** — both `152574e4f4f2969468c9d31b1e705188896175b5`; `main`'s reflog shows no movement |
| Protected refs unmoved | **PASS** — all 18 `refs/preserve/*`, 3 `archive/p4/*`, 5 `refs/remotes/origin/*` and 3 `refs/tags/*` resolve unchanged |

**Preservation prestate independently verified.** `refs/preserve/p4-closure-acceptance-prestate-86306d5`
= `361d10aedf03d842429910b04f59c393ab3310f1`, tree `cc5e4b562c5839abf4a66672056dacae32585060`,
parent `86306d5` (attributable, never part of the branch), **624 paths**, containing all five
carried reports plus `p4-independent-review-report.md`. `.env` and `.venv/` are correctly absent.

## B. Review environment and independence statement

**Independence.** This session did not implement P4, did not remediate it, did not author the
closure candidate or its handoff, did not perform either earlier independent review, did not perform
the final adjudication, and did not run the first finalizer. No prior Claude session was resumed.

**Environment.** The review was **not** performed from the primary dirty worktree. A disposable
`git clone --no-local` was created at
`…/scratchpad/rv`, checked out **detached** at `42ea24c`, with a fresh
`python -m venv` and `pip install -e ".[dev]"` (declared dependencies only). A second, separate
throwaway clone (`…/scratchpad/probe`) was used for hostile guard mutation so the review clone was
never dirtied. The review clone's `git status --porcelain` was empty before and after the canonical
suite, and its tree remained `1e2bba79…`.

**Ownership and locks — probed, not assumed.** Both `.git/neyma-finalizer.lock` and
`.git/neyma-builder-worktree.lock` were `flock(LOCK_EX|LOCK_NB)`-probed and are **UNHELD**. No
`finalize_status`, `clean_clone_gate`, `regenerate_test_manifest` or `mutate_phase4_boundary` process
is running. No builder or finalizer owns the primary repository.

**What this session did NOT do.** It modified no product code, no test, no status file, no report,
no index, no commit, no branch and no worktree. It ran **no** finalizer, performed **no**
remediation and **no** adjudication, began **no** P5 work, pushed nothing, merged nothing, deployed
nothing and enabled no effect. Its only repository write is the additive preservation ref in §L.

## C. Exact closure delta — 19 paths, `86306d5` → `42ea24c`

`19 files changed, 3730 insertions(+), 239 deletions(-)`. **Zero implementation paths.**

| Path | Δ | Class |
|---|---|---|
| `docs/implementation/IMPLEMENTATION-REGISTRY.yaml` | M | the 14-criterion P4 acceptance block; P4 → COMPLETE; P5 → READY; residual register |
| `docs/implementation/CURRENT.md` | M | 323 → 622 lines; preserved prose restored and semantically merged |
| `docs/implementation/BUILD-STATUS.yaml` | M | derived block recomputed; authored narrative moved off P3 |
| `docs/implementation/CAPABILITY-TRACEABILITY.yaml` | M | CAP-25 stale note + unresolved-decisions row |
| `docs/CANONICAL-DOCUMENTS.md` | M | three new authority-map rows |
| `CLAUDE.md` | M | §3 status table, §11 prohibitions |
| `README.md` | M | status table, open-findings table |
| `eval/tests/test_status_reality.py` | M | READY expectation + anti-vacuous anchors |
| `eval/tests/test_docs_control_system.py` | M | same |
| `eval/tests/test_rebaseline_invariants.py` | M | same |
| `eval/tests/test_bootstrap_hermeticity.py` | M | same |
| `p4-independent-rereview-report-0891d1a.md` (+`.sha256`) | A | evidence, now tracked |
| `p4-final-adjudication-report-0891d1a.md` (+`.sha256`) | A | evidence, now tracked |
| `p4-first-finalization-pass-report-86306d5.md` (+`.sha256`) | A | evidence, now tracked |
| `p4-closure-content-topology-determination.md` | A | evidence, now tracked |
| `p4-remediation-handoff.md` | A | evidence, now tracked |

**Correctly absent:** `phase-0-baseline-manifest.yaml`, `SUITE-RESULT.json`, `GATE-RESULT.json`,
`TEST-NODE-MANIFEST.json`, and every path under `src/`, `scripts/`, `configs/` and `data/`.

**Topological legality of a content commit that touches status files — CONFIRMED, not assumed.**
`repo_state()` forbids a *metadata* commit from carrying non-status files; it places no restriction
on a *content* commit touching status files. Repository authority explicitly directs this act:
`p4-first-finalization-pass-report-86306d5.md` §7.1 states the acceptance block was **NOT DONE**,
that `finalize_status.py` cannot write it, that an authorized session must transcribe adjudication
§F with `canonical_finalizer` = PASS, set P4 COMPLETE and move P5 BLOCKED → READY **in the same
commit**, and that *"topologically this is legal from here: state is FINALIZED, so one further
commit makes recorded == HEAD^^ with HEAD^ a pure metadata commit → PRODUCING."* §7.2 directs that
the preserved `CURRENT.md` prose be restored in that same commit. **The candidate is exactly the act
repository authority named.**

## D. Implementation byte-equality verdict — **PASS**

Proved by **tree-object identity**, which is stronger than a path-wise diff: two trees with the same
SHA-1 are byte-identical in every descendant.

| Surface | `0891d1a` | `42ea24c` | Verdict |
|---|---|---|---|
| `src/` (approval, checkpoint, witness, grant, claim, effect boundary, governed write provider/route/registry, origin policy, browser-use read/write boundary, adapters) | `0204261b17baecd2bab3dc1b7d25a7494eb3b22d` | **identical** | **BYTE-IDENTICAL** |
| `scripts/` (runtime scripts, `finalize_status.py`, `finalizer_lock.py`, `clean_clone_gate.py`, `run_canonical_suite.py`, `regenerate_test_manifest.py`, mutation operators) | `ca99a45efb7ac7c03680f6a92b317c48268913bf` | **identical** | **BYTE-IDENTICAL** |
| `configs/` | `124ae4bcbbec96cc0ff9282d183d7c97aa1914f5` | **identical** | **BYTE-IDENTICAL** |
| `data/` | `8d02102277273f6858ce15d3753002e7875bb9df` | **identical** | **BYTE-IDENTICAL** |
| `pyproject.toml` · `pytest-canonical.ini` · `requirements.txt` · `AGENTS.md` · `ARCHITECTURE.md` · `PRODUCT.md` | blob-identical | | **BYTE-IDENTICAL** |
| `docs/implementation/TEST-NODE-MANIFEST.json` | `ffa06d39c562cf6985cf5f105f23c4a423fdd599` | **identical** | **BYTE-IDENTICAL** |
| `docs/implementation/phase-0-baseline-manifest.yaml` | `dd00f197f899fba0a28cd6752ee803fb442ae75c` | **identical** | **BYTE-IDENTICAL** |

**Full `git diff --name-status 0891d1a 42ea24c`** returns exactly 21 paths: the 19 of the closure
delta plus `SUITE-RESULT.json` and `GATE-RESULT.json`, both of which changed in `86306d5` (the
finalizer's own write set) and are byte-unchanged between `86306d5` and `42ea24c`.

**Test changes are confined to the authorized set.** The only `eval/` paths differing from
`0891d1a` are the four named guard modules. `eval/phase0/`, `eval/control/`, `eval/fixtures/` and
every other test module are byte-identical.

**Production `GateRegistry` population — EMPTY.** Re-derived across `src/` **and** `scripts/`: the
only occurrences are the class definition (`src/freight_recon/checkpoint.py:233`), two type
assertions in the kernel constructor, an explicit removal marker
(`governed_write_registry.py:394` — *"A `GateRegistry` construction belonged here. It is REMOVED,
and deliberately not relocated"*), and two deferral comments in `run_action_callback_server.py`.
**Zero construction sites, zero registration sites.**

**Verdict: the closure candidate changes no P4 runtime implementation and no runtime behavior.**

## E. Acceptance-block verdict — **PASS, with one adjudication item (§J, F-TR-06)**

Re-derived by parsing `PROGRAM-WEIGHTS.yaml`'s `acceptance_template` (itself byte-unchanged from
`0891d1a`, therefore still FROZEN) and P4's `acceptance_criteria`, and comparing as ordered pairs.

| Requirement | Result |
|---|---|
| Exactly 14 criteria | **PASS** — 14 |
| Template names, exact and **in template order** | **PASS** — ordered-pair equality with the template |
| Template weights, exact | **PASS** — 6·8·20·8·8·10·6·6·8·5·3·3·5·4 |
| No renamed / removed / combined / invented criterion | **PASS** — set difference against the template is empty in both directions; no duplicate names |
| Weights sum exactly to 100 | **PASS** — Σ = 100 |
| All 14 PASS | **PASS** — result set is `{'PASS'}` |
| Every PASS carries attributable evidence | **PASS** — 14/14 non-empty `evidence`; criterion keys are exactly `{criterion, weight, result, evidence}` |
| `progress_status.phase_completion("P4")` | **100.0** |

**13 criteria bind to `0891d1a` — VERIFIED VERBATIM.** Criteria 1–10 and 12–14 were compared
against `p4-final-adjudication-report-0891d1a.md` §F (lines 383–398). **Every result matches the
adjudication's result exactly**, and each `evidence` field names its §F subsection. Criteria 13 and
14 additionally name the preservation refs, report SHA-256s and verdicts, and each carries an
explicit disclaimer that it bound `0891d1a` and **not** this commit.

**Criterion 11 (`canonical_finalizer`, weight 3) — the one result this session attacked hardest.**
The adjudication recorded it `PENDING` ("the finalizer has not run on this candidate"). It is `PASS`
here. Every element of its recorded evidence was independently re-derived:

| Evidence element | Independent verification |
|---|---|
| target content commit `0891d1a` (tree `a3e70464`) | **CONFIRMED** — `86306d5`'s single parent is `0891d1a` |
| exit code 0 | **CONFIRMED** — `p4-first-finalization-pass-report-86306d5.md:157` |
| 1961 passed / 0 failed / 1 skipped / 1962 collected, in-process | **CONFIRMED** — report L186, L192, L195, L199; and reproduced by me (§I) |
| clean-clone gate PASS, nine steps exit 0, bound to `0891d1a`/`a3e70464` | **CONFIRMED** — report L186; `GATE-RESULT.json` `passed: true`, `commit 0891d1a…`, `tree a3e70464…` |
| exactly one finalizer owner, pid 79370, lock released after exit | **CONFIRMED** — report L160–L174, L239; lock re-probed UNHELD today |
| metadata commit `86306d5`, single parent, **exactly five** authorized `STATUS_METADATA_FILES` | **CONFIRMED** — `git diff --name-only 0891d1a 86306d5` returns exactly `SUITE-RESULT.json`, `GATE-RESULT.json`, `CURRENT.md`, `IMPLEMENTATION-REGISTRY.yaml`, `BUILD-STATUS.yaml`; every one is in `finalize_status.STATUS_METADATA_FILES`; **zero stray paths** |

**Criterion 11's evidence is true in every element.** Its provenance — set by the closure builder
rather than by an adjudicating session — is disclosed in the criterion text itself, the registry
comment, the commit message, `CURRENT.md` and `BUILD-STATUS.yaml`, and is recorded as an
adjudication item at **F-TR-06**.

**No artifact claims the prior reviewer reviewed `42ea24c` — VERIFIED.** A tree-wide grep for
`42ea24c` across all `*.md`, `*.yaml`, `*.json` and `*.py` returns **zero** hits. The only text in
the tree touching the question is `CURRENT.md:620`, which **negates** it: *"None of those four
reports reviewed the closure commit itself."* Criteria 13 and 14, the re-review's banner, the
adjudication's own header and `CANONICAL-DOCUMENTS.md`'s new rows all say the same.

## F. P4 / P5 state-transition verdict — **PASS**

All values recomputed by executing the repository's own composer, not read from the file:

| Quantity | Recomputed | Committed | Verdict |
|---|---|---|---|
| `phase_completion("P4")` | 100.0 | — | **PASS** |
| `phase_completion("P3")` | 100.0 | — | **PASS** |
| `phase_completion("P5")` | 0.0 | — | **PASS** (no contract instantiated — correct, P5 has not started) |
| `overall_program_percent` | 22.0 | 22.0 | **PASS** (12.0 from P3 + 10.0 from P4) |
| `single_ready_unit` | `P5` | `P5` | **PASS** |
| `progress_status.derive(...)` | 10/10 fields | 10/10 fields | **EXACT MATCH — zero divergent keys** |
| `progress_status.build_status_errors(...)` | `[]` | | **PASS** — no PROGRESS-PROTOCOL §8 rejection condition holds |

**Registry state, re-parsed:** P4 `status: COMPLETE`, `execution_state: COMPLETE`,
`checkpoint_state: PHASE_ACCEPTANCE_COMPLETE`. P5 `status: READY`, `execution_state: NOT_STARTED`,
`checkpoint_state: NO_CHECKPOINT`, `landed_checkpoints` absent, **no `acceptance_criteria` block**,
`dependencies: [P4]`, and its G2 transition/event `validation_blockers` entry present and
undischarged. **P6–P14 all `BLOCKED`.** The READY set is exactly `['P5']`.

**P5 implementation has not begun — structurally proved.** `src/` and `scripts/` are tree-identical
to `0891d1a`; the delta contains no source path at all. No event contract, outbox, inbox, replay
sandbox or PostgreSQL work exists.

**R-07 remains OPEN — NOT CONTAINED.** `phase-0-baseline-manifest.yaml` is blob-identical to
`0891d1a` (`dd00f197…`) and line 229 still reads `status: OPEN - NOT CONTAINED`.

### F.2 Guard changes — narrow, strengthened, and hostilely probed

Located mechanically. All four are **replacements with the function name frozen**, so
`TEST-NODE-MANIFEST.json` node identity is preserved.

| File | Function | Verified |
|---|---|---|
| `test_status_reality.py` | `test_the_status_record_still_states_the_canonical_facts` | READY `P4`→`P5`; contract check now loops **P3 and P4**; BLOCKED sweep now *discovered* (`every P≥6`) rather than two named examples; adds P5 `NOT_STARTED` + no-landed-checkpoints; adds an explicit `R-07 OPEN — NOT CONTAINED` assertion against `CURRENT.md` |
| `test_docs_control_system.py` | `test_24_the_next_approved_work_is_p3_with_every_gate_closed` | READY `P4`→`P5`; contract check loops **P3 and P4**; retains P3's gate-ancestry evidence checks; adds that the READY unit prohibits the phase after it |
| `test_rebaseline_invariants.py` | `test_exactly_one_ready_unit_and_it_is_p3` | READY `P4`→`P5`; adds P4 COMPLETE on a real full-weight fully-PASS contract; the `phase-0-baseline-manifest.yaml` `status: OPEN - NOT CONTAINED` assertion is **unchanged** |
| `test_bootstrap_hermeticity.py` | `test_the_implementation_graph_is_consistent_and_protects_the_safety_wall` | READY `P4`→`P5`; adds P4 COMPLETE on a real 100-weight fully-PASS contract |

| Structural check | Result |
|---|---|
| Assertion counts | 76→**78** · 156→**159** · 69→**74** · 38→**48** — **rose in all four** |
| Test-function counts | 24→24 · 51→51 · 19→19 · 7→7 — **unchanged** |
| Test-function **name sets** | **identical in all four files** (`diff` of sorted `def test_` lines is empty) — node identity preserved |
| Any test deleted, skipped or xfailed | **NONE** |
| One-READY-unit invariant | **INTACT** — `len(ready) == 1` asserted in `test_docs_control_system.py` (×3, incl. L443 inside the changed guard), `test_roadmap_completeness_control.py:183`, `test_switch_consistency.py:80`. **None was touched.** |

**Hostile anti-vacuity probes — I tried to make each replaced guard pass over nothing.** Run in a
separate throwaway clone; all four guards executed against each mutation:

| Mutation | Guards failing |
|---|---|
| Baseline (unmutated) | 0 of 4 (all pass) |
| P4 `acceptance_criteria` **key removed** | **4 of 4 FAIL** |
| P4 `acceptance_criteria` **emptied to `[]`** | **4 of 4 FAIL** |
| `units` **emptied to `[]`** (registry parses to nothing) | **4 of 4 FAIL** |
| one P4 criterion → `PENDING` | **4 of 4 FAIL** |
| one P4 weight altered (Σ ≠ 100) | **4 of 4 FAIL** |
| P6 also marked `READY` (two READY units) | **4 of 4 FAIL** |
| `phase-0-baseline-manifest.yaml` → `status: CONTAINED` (early R-07 close) | **1 of 4 FAIL** — `test_rebaseline_invariants`, the guard that owns that assertion |
| P5 `execution_state` → `IN_PROGRESS` | **1 of 4 FAIL** — `test_status_reality`, the guard that added it |

**No guard was deleted or weakened; assertions are positively anchored; empty inventories cannot
pass vacuously.** Every mutation was reverted and the probe clone returned to a clean tree.

## G. `CURRENT.md` and `BUILD-STATUS.yaml` verdict — **PASS**

### G.1 `CURRENT.md` semantic merge (323 → 622 lines)

The 476-line preserved copy lives at
`refs/preserve/p4-first-finalization-prestate-0891d1a:docs/implementation/CURRENT.md`. I compared it
line-by-line against the 622-line result.

- **65 of 476 lines are absent.** I read **all 65**. Every one is a superseded in-flight claim that
  *had* to go: `P4 … EXECUTING — NOT COMPLETE`, `the next approved unit is P4`, the stale
  `content_commit: 3d231731` / `suite_passed: 1630` status block, `only completing P4 closes R-07`,
  and the mid-flight "remains" lists for EP-1/EP-3/EP-8/EP-14 and F2. **No valid material was lost.**
- **The durable P4 execution narrative was preserved and extended**, not dropped: §"The P4 execution
  record — how containment was actually built" (L294–494) carries items 1–9 including the EP-8/F2
  cut, the EP-3 cut and provenance hardening, EP-14, the EP-1 read half and the EP-1 write half.
- **No silent duplication.** One repeated substantive line, a benign `IMPLEMENTATION-REGISTRY.yaml`
  link appearing in two onboarding lists.
- **No contradictory P3/P4 claims.** P3 COMPLETE and P4 COMPLETE are stated once each, consistently.

| Required content | Result |
|---|---|
| Accepted candidate `0891d1a` accurately named | **PASS** — L8, L30–31, L139 |
| Accepted independent re-review accurately named | **PASS** — L59, L130, and marked as reviewing `0891d1a` |
| Adjudication accurately named | **PASS** — L59, L132 |
| First finalizer `86306d5` accurately named | **PASS** — L10, L59, L164 |
| P4 14/14 and COMPLETE accurately stated | **PASS** — L7–9, L59, L128 |
| P5 READY but NOT STARTED accurately stated | **PASS** — L11, L60, L497–505 |
| R-07 still OPEN | **PASS** — L12–15, L98–99, L538–545, plus the L620 attribution disclaimer |
| Residual risks retained | **PASS** — RR-01 (L104), AD-01 (L105), AD-02 (L106), RR-02…RR-06/F-03/F-06/F-07/F-10 (L107) |
| Phase-8 production-gate deferral retained | **PASS** — L112, L557 |
| No production writes claimed enabled | **PASS** — L169–173, L186–190, L560 |
| Historical EP-1 design note labelled historical and non-current | **PASS** — L449–456: inside a `<details>` block titled *"HISTORICAL — SUPERSEDED DESIGN NOTE (NOT current instruction)"*, opening *"NOT CURRENT AUTHORITY … SUPERSEDED by what was actually done"*, and pointing at the live account |
| The `<details>` quarantine block's own false-transition record retained and self-labelling | **PASS** — L568–597 |
| Machine-maintained status block untouched by this content commit | **PASS** — byte-identical to `86306d5`'s |

### G.2 `BUILD-STATUS.yaml`

**Derived block: produced by the repository-authorized composer, not fabricated.** I executed
`progress_status.derive()` in the clean clone and compared all ten fields against the committed
block: **exact match, zero divergent keys**. `build_status_errors()` returns `[]`.

**Authored narrative no longer falsely describes P3.** Every requested field was read and checked:

| Field | Verdict |
|---|---|
| `active_work_unit` | **PASS** — P5, SELECTED and NOT STARTED, "READY is a selection, never a claim of progress" |
| `next_approved_unit` | **PASS** — P5, with its undischarged G2 blocker named |
| `blockers_to_p5` (was `blockers_to_p4`) | **PASS** — no code reads this key (`grep` for `blockers_to` in `scripts/`+`eval/` is empty), so the rename drops no check |
| `finalizer_result` | **PASS** — binds to `0891d1a`, one exclusive lock, exit 0, metadata commit `86306d5`, five files; states **"NO SECOND FINALIZER HAS RUN … no receipt was fabricated"** |
| `clean_clone_result` | **PASS** — bound to `0891d1a`/`a3e70464`, nine steps exit 0, hashes cross-checked against the candidate's own files |
| `independent_review_status` | **PASS** — full P4 chain with SHA-256s and preserve refs, and an explicit **"THESE REVIEWS ARE BOUND TO IMPLEMENTATION CANDIDATE `0891d1a`"** disclaimer |
| `current phase narrative` / `expected_founder_experience` | **PASS** — states P4 complete, 12%→22%, ships dark, R-07 still open, P5 not started, 0% correct |
| `residual-risk narrative` (`open_program_risks`) | **PASS** — R-07, RR-01, AD-01, AD-02, the RR-02…F-10 group, and the U8.1/P8 founder deferral |
| `last_verified_test_evidence` | **PASS** — explicitly notes the evidence describes `0891d1a` and that **this commit has no receipt of its own** |

### G.3 No forged receipt for `42ea24c` — **VERIFIED**

`SUITE-RESULT.json` (`e74dd313…`) and `GATE-RESULT.json` (`2e7e12a5…`) are **blob-identical to
`86306d5`** and still bound to `commit 0891d1a…` / `tree a3e70464…`, with `passed: 1961, failed: 0,
skipped: 1, collected: 1962, exit_status: 0` and `passed: true`. This is **consistent, not stale
misuse**: under the two-commit convention the receipts describe the recorded content baseline, which
`CURRENT.md`'s block still names as `0891d1a`, and the next finalizer rebinds them. `repo_state()`
returns `PRODUCING` precisely because that binding is one content commit behind. No artifact anywhere
carries a receipt, hash or exit status attributed to `42ea24c`.

## H. R-07 and residual-register verdict — **PASS**

- `phase-0-baseline-manifest.yaml` blob `dd00f197f899fba0a28cd6752ee803fb442ae75c` — **byte-identical
  to `0891d1a`**; L229 reads `status: OPEN - NOT CONTAINED`.
- **The closure candidate nowhere claims R-07 closure.** It states the opposite in the commit
  message, `CURRENT.md` (×4 sites), `BUILD-STATUS.yaml`, `CLAUDE.md`, `README.md`,
  `CAPABILITY-TRACEABILITY.yaml`, the registry's `remaining_before_p4_completion` (item 6, marked
  `### NOT DONE`), and in a **new guard assertion** that fails if `CURRENT.md` stops saying it.
- **Complete residual register present** in P4's `residual_risks_carried_forward`, none discharged:

| Group | Members |
|---|---|
| `binding_p12_preconditions` | **RR-01** — MEDIUM, `NOT DISCHARGED - BINDING P12 PRECONDITION`, compounded by **F-08** and **F-09**, with its `required_before_any_live_writer` remediation spelled out. **Not described as discharged anywhere.** |
| `recorded_non_blocking` | **AD-01**, **AD-02**, **RR-02**, **RR-03**, **RR-04**, **RR-05**, **RR-06**, **F-03**, **F-06**, **F-07**, **F-08**, **F-09**, **F-10** — each with severity and disposition |
| `founder_decision_preserved_unchanged` | Production Action Class gate registration **DEFERRED TO U8.1 / P8**; `AC-CKPT-6-missing` stays `DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8`; production `GateRegistry` population **EMPTY and MUST STAY EMPTY** |

  All fourteen adjudicated residuals are present. Production `GateRegistry` population is
  independently confirmed **EMPTY** (§D). No production write is enabled.

## I. Test, manifest and topology results — all reproduced independently

| Check | Claimed | **My independent result** |
|---|---|---|
| Canonical suite, disposable `--no-local` clone detached at `42ea24c`, fresh venv, declared deps only, `PYTEST_ADDOPTS` cleared, `-c pytest-canonical.ini` | 1961 / 0 / 1 | **1961 passed, 0 failed, 1 skipped — exit 0** (398.19 s) |
| Collected node count | 1962 | **1962** |
| `TEST-NODE-MANIFEST.json` identity vs live collection | identical by identity | **1962 vs 1962 — 0 missing, 0 extra, exact set equality** |
| Control guards (status-reality, integration-topology, docs-control, false-green, phase-0 null gate, progress-protocol, rebaseline-invariants, bootstrap-hermeticity, switch-consistency, roadmap-completeness) | 227 passed | **227 passed** |
| Clone `git status --porcelain` before and after | empty | **empty**; tree still `1e2bba79…` |
| `repo_state()` | PRODUCING | **PRODUCING** |
| `HEAD` is not a merge | single parent | **single parent** |
| Production `GateRegistry` site exists | none | **none across `src/` and `scripts/`** |
| Protected refs unchanged | unchanged | **unchanged**, verified against the live remote |

The single skip is the pre-existing conditionally-justified one. `finalize_status.py` was **not**
run; **no test was weakened**; every guard mutation in §F.2 was reverted.

### I.2 Report preservation — durable readability and attribution **VERIFIED**

| Report | Tracked SHA-256 | Sidecar | Preservation |
|---|---|---|---|
| Independent re-review | `66038843…c274f` (bannered copy) | records `181e1a37…b316` — **deliberately the original's** | `refs/preserve/p4-independent-rereview-0891d1a` = `5ca6d2e95896336f447cf693da04282a0d53bdbf`, **parent = `0891d1a`**, adds only the report + sidecar |
| Final adjudication | `078cfea8…997e` | **matches** | `refs/preserve/p4-final-adjudication-0891d1a` = `420e5b2d0b3b6af280d8a8d0f3d80ad9f6cb9ebc`, **parent = `0891d1a`** |
| First-finalization report | `9f5b8f98…1056` | **matches** | tracked; also inside the prestate ref |
| Closure-topology determination | `1ddfcc65…3dfa` | (none) | tracked; also inside the prestate ref |
| Remediation handoff | `1295399b…2a7f` | (none) | tracked; also inside the prestate ref |

**The re-review's banner deviation is exactly as declared, and I proved it mechanically.** The
tracked file is 813 lines; the preserve-ref blob is 777. `tail -n 777` of the tracked file `cmp`s
**byte-identical, zero differences** against the preserve-ref blob and hashes to
`181e1a37a413fd35f537e00a7e1423bf192f88205270fa15932fbabeb955d316` — the sidecar's value. The
36-line banner is the only addition, it is required by
`test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale_claim`, it follows
the precedent already set for `p4-independent-review-report.md`, it states the sidecar mismatch in
full and gives the verification command. **No historical report was rewritten to claim it reviewed
`42ea24c`**; every one retains its original candidate attribution.

## J. Findings, ordered by severity

None of the findings below is a false-green, and none invalidates any verdict in §D–§I.

---

### **F-TR-01 — MEDIUM — confirmed defect — `ARCHITECTURE.md` §28/§29 still asserts P4 incomplete**

**Requirement.** `docs/CANONICAL-DOCUMENTS.md:63` classifies `ARCHITECTURE.md` as **CANONICAL**, and
`eval/control/inventory.root_control_like_documents()` lists it beside `CLAUDE.md` and `README.md`.
`CURRENT.md`'s opening forbids reconstructing status from other documents *because* stale copies
mislead; `CLAUDE.md` §5 rule 20 requires a claim that has become false to be **replaced, not left**.

**File and range.** `ARCHITECTURE.md:272–273` and `:280`.

**Proof.** After `42ea24c`, live text with no historical label and no status-deferral clause reads:

- L272 — `| **P4** | 🔄 READY *(selected)* — **IN PROGRESS, NOT COMPLETE** | … Two checkpoints
  landed; EP-1/EP-3/EP-8/EP-14 and finding F2 remain, so **R-07 stays OPEN** |`
- L273 — `| **P5+** | ⛔ NOT STARTED | everything below |`
- L280 — `Phase 3 did NOT route any external effect through it. **Nothing does, until P4.**`

Verified not inside a `<details>` block (`0` unclosed `<details>` before L272). The file's header
banner defers only on **architecture** disagreements to the ADRs and specs — it contains no
status-defers-to-`CURRENT.md` clause. The registry now records P4 `COMPLETE`, P5 `READY`, and
EP-1/EP-3/EP-8/EP-14 and F2 all cut.

**Consequence.** A grep-first reader of a document the repository itself calls CANONICAL is told P4
is in progress, that the four EPs and F2 remain, and that P5 has not been selected. `git diff
0891d1a 42ea24c -- ARCHITECTURE.md` is empty: the closure commit corrected `CLAUDE.md`, `README.md`
and `CAPABILITY-TRACEABILITY.yaml` for precisely this staleness and did not correct their peer. The
correction set was **guard-driven** (`test_switch_consistency.py` flags only what it covers) rather
than **scope-driven**, and the guard population does not reach `ARCHITECTURE.md` prose —
`test_no_secondary_file_carries_its_own_volatile_status_claim` scans that file only for numeric
`NNN passed` figures.

**Blocks the second finalizer?** **No.** No guard fails, the canonical suite is green,
`build_status_errors()` is `[]`, and the finalizer's write set does not include this file. But if it
is not corrected first, the finalized state ships a CANONICAL document contradicting the record.

**Narrowly scoped remediation.** In a later content commit, replace L272 with a P4 `COMPLETE` row
(adjudicated 14/14, ships dark, **R-07 still OPEN pending its own content commit**), replace L273
with a P5 `READY — NOT STARTED` row plus `P6+ NOT STARTED`, and re-point L280. Change nothing else
in the file.

---

### **F-TR-02 — LOW — confirmed defect — `AGENTS.md` status paragraph stale, including the R-07 conflation**

**Requirement.** Same as F-TR-01; `AGENTS.md` is classified **EVIDENCE**
(`CANONICAL-DOCUMENTS.md:66`) and is in `root_control_like_documents()`.

**File and range.** `AGENTS.md:38–43`.

**Proof.** *"P4 (adapter containment) is the sole READY unit AND is executing — checkpoints landed,
NOT COMPLETE; R-07 OPEN — NOT CONTAINED (… **only completing P4 closes R-07**)."* Untouched by the
closure commit. The parenthetical is the exact P4-COMPLETE ⇒ R-07-contained conflation the candidate
spent four other files and a new guard assertion preventing.

**Mitigating fact, verified.** The section is headed *"Do not read status from this file, and do not
add it here. `CURRENT.md` is the single authority"* and ends *"If this line and `CURRENT.md` ever
disagree, `CURRENT.md` is right and this line is stale."* The file structurally cedes authority.

**Consequence.** A reader who ignores the disarming clause infers that completing P4 closed R-07.

**Blocks the second finalizer?** **No.**

**Narrowly scoped remediation.** In a later content commit, re-point the paragraph to P0–P4
COMPLETE / P5 sole READY and NOT STARTED, and replace *"only completing P4 closes R-07"* with *"only
the separate `phase-0-baseline-manifest.yaml` content commit closes R-07."*

---

### **F-TR-03 — LOW — confirmed defect — `FREIGHT-CAPABILITY-MAP.md` states P4 not complete**

**File and line.** `docs/product/FREIGHT-CAPABILITY-MAP.md:251` — *"routing effects through it is P4
(READY, not complete); **R-07 OPEN**"*.

**Mitigating fact, verified.** Its header states *"current status → `CURRENT.md` … On any conflict
the cited source wins"*, and `CANONICAL-DOCUMENTS.md:79` records that it *"states nothing as
implemented"*.

**Blocks the second finalizer?** **No.** **Remediation:** re-point the `Current state` bullet in a
later documentation commit.

---

### **F-TR-04 — LOW — confirmed defect — `EFFECT-PATH-INVENTORY.yaml` states P4 not complete**

**File and line.** `docs/implementation/EFFECT-PATH-INVENTORY.yaml:91` — *"R-07 REMAINS OPEN - NOT
CONTAINED, and **P4 REMAINS NOT COMPLETE**: this records remediation, not adjudication."* The R-07
half remains true; the P4 half is now false. The surrounding `p4_f01_governed_join` narrative also
repeats the provider-wiring claim that **AD-01** already records as mechanically false, and the
adjacent `p4_write_half_residual` block *is* correctly marked `HISTORICAL - superseded`.

**Blocks the second finalizer?** **No.** **Remediation:** fold into AD-01's already-scheduled prose
correction, extending it to this sentence and marking the block `HISTORICAL` as its sibling already
is.

---

### **F-TR-05 — LOW — evidence deficiency (handoff only, not the candidate) — misnamed guard function**

**File and line.** `docs/implementation/p4-closure-candidate-targeted-review-handoff-42ea24c.md:220`
names the changed `test_bootstrap_hermeticity.py` guard
`test_the_dependency_graph_is_complete_consistent_and_acyclic`. **No such function exists** in the
file (`grep` returns nothing). The actual function is
`test_the_implementation_graph_is_consistent_and_protects_the_safety_wall`, and the changed
assertion is at `eval/tests/test_bootstrap_hermeticity.py:427`.

**Consequence.** A reviewer or adjudicator locating the change from the handoff by name finds
nothing and could report a false failure — the identical failure mode the handoff's own banner warns
about for RR-02. **The commit itself is correct**; only the handoff is wrong. The handoff is
untracked and its sidecar verifies (`9c5cc187…37e87`), so nothing in the reviewed tree is affected.

**Blocks the second finalizer?** **No.** **Remediation:** none required of the candidate; the
targeted adjudication should locate guard changes mechanically, as this review did.

---

### **F-TR-06 — non-blocking residual risk — ADJUDICATION ITEM — criterion 11 is the one result not sourced from an adjudication**

**Requirement.** `PROGRESS-PROTOCOL.md` §8 and `CLAUDE.md` §5 rule 20 forbid a phase reaching 100%
without `independent_review` and `final_adjudication` PASS, and forbid self-adjudication.

**Statement.** Thirteen of the fourteen results are verbatim transcriptions of an adjudication by a
session that did not implement, remediate or review P4 (§E — verified verbatim). The fourteenth,
`canonical_finalizer` (weight 3), was `PENDING` in that adjudication and was set to `PASS` by the
**closure builder**. Its evidence is true in every element (§E), the act is explicitly directed by
`p4-first-finalization-pass-report-86306d5.md` §7.1 and adjudication §G.7.8, and it is disclosed in
six places. But it means P4's 100/100 rests on **3 weight points whose result no adjudicating session
set**, and 97/100 would not have reached COMPLETE.

**Consequence.** This is precisely why `42ea24c` owes a **separate targeted adjudication**. That
adjudication — not this review — must ratify criterion 11 and the resulting COMPLETE.

**Blocks the second finalizer?** **Yes, indirectly** — not as a defect, but because the finalizer
must not run before the separate targeted adjudication ratifies this. Classified **non-blocking
residual risk** for the review itself.

---

### **F-TR-07 — non-blocking residual risk (pre-existing AD-02) — `finalizer_lock.py` remains untested and is load-bearing for the second finalizer**

Re-confirmed today: `scripts/finalizer_lock.py` has zero `eval/` references and zero
`TEST-NODE-MANIFEST.json` nodes. Recorded as **AD-02** and carried correctly by the candidate. The
adjudication named it a prerequisite for the finalizer. **Not a defect of `42ea24c`** — recorded so
it is not lost at the finalization boundary.

---

## K. Verdict

# ACCEPT FOR SEPARATE TARGETED ADJUDICATION

The closure candidate does what repository authority directed and nothing else. Its identity,
topology and preservation verify from the object store. **No P4 runtime implementation byte changed**
— `src/` and `scripts/` are tree-object-identical to the accepted candidate `0891d1a`, and the
production `GateRegistry` population is EMPTY. The 14-criterion acceptance block matches the frozen
template exactly in name, weight, order and count, sums to 100, is fully PASS with attributable
evidence, and its thirteen adjudication-sourced results match §F verbatim; criterion 11's evidence is
true in every element I could test. The P4 → P5 transition is what the repository's own composer
computes, `build_status_errors()` is `[]`, the one-READY-unit invariant is intact, all four guard
changes are narrow replacements that gained assertions and **failed every anti-vacuity mutation I
threw at them**. `CURRENT.md`'s merge lost no valid material. R-07 remains OPEN — NOT CONTAINED on a
byte-identical manifest, the full residual register is carried with RR-01 binding and undischarged,
the Phase-8 deferral is intact, no production write is enabled, no receipt was forged, and every
preserved report keeps its original `0891d1a` attribution. The canonical suite, the node-manifest
identity and the 227 control guards all reproduce exactly in a disposable `--no-local` clone.

**No finding is a false green, and none blocks the second finalizer.** F-TR-01 through F-TR-04 are
stale status prose in documents outside the changed set, three of which self-disarm; F-TR-05 is an
error in the handoff, not the tree. **F-TR-01 should be remediated before finalization** so the
finalized state does not ship a CANONICAL document contradicting the record — that is a
recommendation for the adjudicator, not a rejection.

**F-TR-06 is the item the targeted adjudication must decide**: whether a builder-set
`canonical_finalizer` on true evidence may carry the last 3 weight points to 100/100. **This review
does not decide it.**

**Required sequence from here, unchanged:** separate targeted adjudication of `42ea24c` → exactly one
second finalizer → the separate R-07 content commit. **Stop at the control boundary. P5 must not
begin.**

## L. Preservation

```
report        docs/implementation/p4-closure-candidate-targeted-review-report-42ea24c.md
sidecar       docs/implementation/p4-closure-candidate-targeted-review-report-42ea24c.md.sha256
preservation  refs/preserve/p4-closure-targeted-review-42ea24c
parent        42ea24cfc76fac19406e7eaa44b695b8d032b3aa   (the exact reviewed candidate)
```

The preservation commit adds **only** the report and its `.sha256`, leaving the candidate's tree
otherwise untouched — the same mechanism already used by
`refs/preserve/p4-independent-rereview-0891d1a` and `refs/preserve/p4-final-adjudication-0891d1a`.
The reviewed candidate was not modified, no earlier report was overwritten, and the product branch
was not moved.
