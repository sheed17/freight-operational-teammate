# ⛔ SEPARATE TARGETED ADJUDICATION — NOT A FINALIZATION, NOT A REVIEW

> **This is the SEPARATE TARGETED ADJUDICATION of the P4 closure content commit**
> `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` (tree `1e2bba791a5c2c77194d1df9ce16e1d9df84315a`,
> parent `86306d5c4d866baf1a7fb6e4bd8220ce31017acd`).
>
> It ran **no** finalizer, wrote **no** status metadata, marked **no** phase complete, closed
> **no** risk, remediated **nothing**, amended nothing, moved no protected ref, pushed nothing and
> enabled no effect. It did not begin P5 and did not close R-07. The status authority remains
> [`CURRENT.md`](CURRENT.md) and [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml);
> the operating guide is [`../../CLAUDE.md`](../../CLAUDE.md).
>
> Its only repository write is the additive preservation ref in §M.

# P4 CLOSURE CANDIDATE — SEPARATE TARGETED ADJUDICATION REPORT

**Adjudicated candidate: `42ea24cfc76fac19406e7eaa44b695b8d032b3aa`**

**Date:** 2026-08-04.

---

## A. Independence and environment

**Independence.** This session did not implement P4, did not remediate it, did not author the
closure candidate or its handoff, did not perform any earlier independent review, did not perform
the targeted independent review, did not perform the P4 final adjudication of `0891d1a`, and did
not run the first finalizer. No prior Claude session was resumed.

**Environment.** The adjudication was **not** performed from the primary dirty worktree. A
disposable `git clone --no-local` was created at `…/scratchpad/adj/clone42ea24c`, checked out
**detached** at `42ea24c`, with a fresh `python -m venv` (Python 3.14.4) and
`pip install -e ".[dev]"` — declared dependencies only. Two further throwaway `--no-local` clones
(`…/scratchpad/probe`, `…/scratchpad/probe2`) were used for topology and anti-vacuity mutation so
the adjudication clone was never dirtied; **both were deleted after use**. The adjudication clone's
`git status --porcelain` was empty before and after the canonical suite, and its tree remained
`1e2bba791a5c2c77194d1df9ce16e1d9df84315a`.

**Primary repository, probed rather than assumed.**

| Check | Result |
|---|---|
| `HEAD` | `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` |
| Tracked modifications (`git status --porcelain -uno`) | **none** |
| Index vs `HEAD` (`git diff --cached`) | **identical** |
| Untracked paths | exactly 4 — the targeted-review report/handoff and their sidecars |
| `.git/neyma-finalizer.lock` | `flock(LOCK_EX\|LOCK_NB)` probe → **UNHELD** |
| `.git/neyma-builder-worktree.lock` | `flock(LOCK_EX\|LOCK_NB)` probe → **UNHELD** |
| `finalizer_lock.current_owner(repo)` | **`None`** |
| Running `finalize_status` / `clean_clone_gate` / `regenerate_test_manifest` / `mutate_phase4_boundary` | **none** |
| Worktrees | one live at the candidate; one prunable stale entry on an unrelated docs branch |

**No builder and no finalizer owns the primary repository. The finalizer lock is unheld.**

## B. Identity, topology and preservation — verified from the object store

Every hash was re-derived with `git cat-file` / `git rev-parse`. Nothing was taken from the prompt
or the handoff.

```
closure content commit   42ea24cfc76fac19406e7eaa44b695b8d032b3aa   VERIFIED
closure tree             1e2bba791a5c2c77194d1df9ce16e1d9df84315a   VERIFIED
closure parent           86306d5c4d866baf1a7fb6e4bd8220ce31017acd   VERIFIED, single parent
object type              commit, not a tag, not a merge             VERIFIED

first-finalizer metadata 86306d5c4d866baf1a7fb6e4bd8220ce31017acd
  tree                   7b5e4258f3d0579c4f562b5f62b5ebcfbfd196d1   VERIFIED
  parent                 0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e   VERIFIED

implementation candidate 0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e
  tree                   a3e704645b8a06561d90cdb5f81288309ae51850   VERIFIED
  parent                 f1e8e1893eff2460d68f3f168f18fd29635b250d   VERIFIED
```

| Requirement | Result |
|---|---|
| Exact candidate commit / tree / parent | **CONFIRMED** |
| Exactly ONE content commit above `86306d5` | **CONFIRMED** — `git log --first-parent 86306d5..42ea24c` returns exactly one hash, the candidate |
| `HEAD` is not a merge | **CONFIRMED** — `git rev-list --parents -n1` shows one parent |
| Legal `PRODUCING` topology | **CONFIRMED** — I executed the real guard: `test_status_reality.repo_state()` → **`PRODUCING`**. Recorded `content_commit` in `CURRENT.md` is `0891d1a` == `HEAD^^`; `HEAD^` (`86306d5`) changed **exactly five** paths, every one a member of `finalize_status.STATUS_METADATA_FILES` |
| No protected ref movement | **CONFIRMED** — `main` and `origin/main` both `152574e4f4f2969468c9d31b1e705188896175b5`; all 19 `refs/preserve/*`, 3 `archive/p4/*`, 5 `refs/remotes/origin/*` and 3 `refs/tags/*` hold pre-existing values |
| Nothing pushed | **CONFIRMED** — live `git ls-remote --heads origin` carries **no** `p4/adapter-containment-completion`; five commits unpushed |
| No branch advances past the candidate | **CONFIRMED** — swept every `refs/heads` and `refs/remotes`; no descendant. The candidate's **only** child is the review preservation commit |
| Candidate not changed after review | **CONFIRMED** — `p4/adapter-containment-completion@{0}` **is** the candidate; no amend, reset, rebase or update follows it. The review preservation commit was authored ~66 min after the candidate and is a child, not a successor |

**Targeted-review preservation — VALID.**

| Element | Verified |
|---|---|
| Preservation ref | `refs/preserve/p4-closure-targeted-review-42ea24c` → `c30a43be5bf8d92a07a30136c94c0642c6792b12` |
| Preservation parent | **`42ea24cfc76fac19406e7eaa44b695b8d032b3aa`** — the exact adjudicated candidate |
| Preservation delta | **additive only** — `2 files changed, 582 insertions(+)`, zero deletions: the report and its `.sha256` |
| Report SHA-256 (from the preserve-commit blob) | `5547aa5e8d89ced661b4f6e415767f8259809bdf5d175615065158fa871a8ea5` — **matches the expected value** |
| Report SHA-256 (untracked worktree copy) | **same hash** |
| Committed sidecar | records the same hash against the correct filename — **match ×3** |
| Candidate attribution | the report's header names `42ea24c`, tree `1e2bba79`, parent `86306d5` — it reviewed **this** commit |

I read the complete 581-line targeted-review report.

## C. Exact closure delta — 19 paths, `86306d5` → `42ea24c`

`19 files changed`. **Zero implementation paths**, re-derived by me:

- **Status / control:** `IMPLEMENTATION-REGISTRY.yaml`, `CURRENT.md`, `BUILD-STATUS.yaml`,
  `CAPABILITY-TRACEABILITY.yaml`, `docs/CANONICAL-DOCUMENTS.md`, `CLAUDE.md`, `README.md`
- **Guards (4):** `test_status_reality.py`, `test_docs_control_system.py`,
  `test_rebaseline_invariants.py`, `test_bootstrap_hermeticity.py`
- **Evidence now tracked (8):** the re-review, the final adjudication, the first-finalization
  report (each with `.sha256`), the closure-topology determination, the remediation handoff

`git diff --name-only 86306d5 42ea24c -- src scripts configs data` returns **0 paths**.

## D. Accepted review evidence — CONFIRMED or REJECTED, item by item

Every row below was **re-derived by this session**, not inherited.

| Reviewer's claim | My independent result | Verdict |
|---|---|---|
| Runtime implementation byte-identical to `0891d1a` | `src/` `0204261b17baecd2bab3dc1b7d25a7494eb3b22d` — **identical**; `scripts/` `ca99a45efb7ac7c03680f6a92b317c48268913bf` — **identical**; `configs/` and `data/` also tree-identical | **CONFIRMED** |
| `src/` tree-object identity exact | tree SHA equal on both commits — byte-identical in every descendant | **CONFIRMED** |
| `scripts/` tree-object identity exact | tree SHA equal on both commits | **CONFIRMED** |
| Production `GateRegistry` population EMPTY | AST sweep over **all** `src/` and `scripts/` `.py`: **0** `GateRegistry(...)` constructions, **0** `register_gate(...)` calls. The only textual occurrences are the class definition, two kernel type assertions, one explicit removal marker and two deferral comments | **CONFIRMED** |
| Test changes confined to four authorized READY-unit guards | `git diff --name-only 0891d1a 42ea24c -- eval/` returns **exactly** those four files | **CONFIRMED** |
| 14 acceptance criteria | 14 | **CONFIRMED** |
| Exact template names and weights | Parsed the frozen `acceptance_template` and compared as **ordered pairs**: names equal `True`, weights equal `True`; weights `6·8·20·8·8·10·6·6·8·5·3·3·5·4` | **CONFIRMED** |
| All 14 PASS | result set is exactly `{'PASS'}`; all 14 carry non-empty `evidence`; criterion keys are exactly `{criterion, weight, result, evidence}` | **CONFIRMED** |
| Weights sum to 100 | Σ = **100** (template Σ = 100 also) | **CONFIRMED** |
| P4 100% and COMPLETE | `phase_completion("P4")` = **100.0**; registry `status: COMPLETE`, `execution_state: COMPLETE`, `checkpoint_state: PHASE_ACCEPTANCE_COMPLETE` | **CONFIRMED** |
| P5 sole READY and NOT_STARTED | READY set == `['P5']`; P5 `execution_state: NOT_STARTED`, `checkpoint_state: NO_CHECKPOINT`, **no** `acceptance_criteria`, **no** `landed_checkpoints`, `dependencies: ['P4']` | **CONFIRMED** |
| P6–P14 blocked | `BLOCKED` == `{P6,P7,P8,P9,P10,P11,P12,P13,P14}` — all nine | **CONFIRMED** |
| R-07 OPEN — NOT CONTAINED | `phase-0-baseline-manifest.yaml` blob `dd00f197f899fba0a28cd6752ee803fb442ae75c` — **byte-identical to `0891d1a`**; L229 reads `status: OPEN - NOT CONTAINED` | **CONFIRMED** |
| Canonical suite 1961 / 0 / 1 / 1962 | Disposable `--no-local` clone, detached at `42ea24c`, fresh venv, declared deps only, `PYTEST_ADDOPTS` cleared, `-c pytest-canonical.ini`: **1961 passed, 0 failed, 1 skipped, exit 0** (394.36 s); `--collect-only` → **1962 collected** | **CONFIRMED** |
| TEST-NODE-MANIFEST exact identity | recorded 1962 vs live 1962; **0 missing, 0 extra, exact set equality**; blob byte-identical to `0891d1a` and `86306d5` | **CONFIRMED** |
| 227 control guards passed | the ten control modules: **227 passed** | **CONFIRMED** |
| No finalizer receipt forged for `42ea24c` | `SUITE-RESULT.json` (`e74dd313…`) and `GATE-RESULT.json` (`2e7e12a5…`) are **blob-identical to `86306d5`** and still bind `commit 0891d1a` / `tree a3e70464`, `1961/0/1/1962`, `exit_status 0`, `passed: true`. A tree-wide `git grep` for `42ea24c` across `*.md`/`*.yaml`/`*.json`/`*.py` returns **zero hits** | **CONFIRMED** |
| No second finalizer run | no receipt, no metadata commit above the candidate, no branch advance, lock unheld, no process | **CONFIRMED** |
| No P5 implementation begun | `src/` and `scripts/` tree-identical to `0891d1a`; the closure delta contains **0** source paths | **CONFIRMED** |

### D.1 Derived status — recomputed through the repository's own composer

| Quantity | Committed | My recomputation | Verdict |
|---|---|---|---|
| `progress_status.derive(...)` (10 fields) | — | **zero divergent keys** | **EXACT MATCH** |
| `active_phase` · `single_ready_unit` | `P5` · `P5` | `P5` · `P5` | **PASS** |
| `overall_program_percent` | 22.0 | 22.0 | **PASS** |
| `current_phase_percent` | 0.0 | 0.0 | **PASS** (P5 has no contract — correct, it has not started) |
| `readiness_tier` | `SPECIFIED` | `SPECIFIED` | **PASS** |
| `phase_completion` P3 / P4 / P5 | — | 100.0 / 100.0 / 0.0 | **PASS** |
| `progress_status.build_status_errors(...)` | — | **`[]`** | **PASS** — no `PROGRESS-PROTOCOL.md` §8 rejection condition holds |

### D.2 Guard changes — independently located and hostilely probed

I located the four changed guards **mechanically**, not from the handoff (see F-TR-05).

| File | Assertions | Test fns | `def test_` name set |
|---|---|---|---|
| `test_status_reality.py` | 38 → **48** | 7 → 7 | **identical** |
| `test_docs_control_system.py` | 156 → **159** | 51 → 51 | **identical** |
| `test_rebaseline_invariants.py` | 69 → **74** | 19 → 19 | **identical** |
| `test_bootstrap_hermeticity.py` | 76 → **78** | 24 → 24 | **identical** |

Assertions rose in all four; no test was deleted, skipped or xfailed (`git diff` introduces no
`skip`/`xfail`); node identity is preserved, which is why `TEST-NODE-MANIFEST.json` is unchanged.

**My own anti-vacuity mutations**, run in a throwaway clone, each reverted byte-exactly:

| Mutation | Guards failing | Note |
|---|---|---|
| Baseline | 0 of 4 | 7 / 85 / 19 / 24 passed |
| P4 `acceptance_criteria` emptied to `[]` | **4 of 4 FAIL** | matches the review |
| P4 `canonical_finalizer` → `PENDING` | **4 of 4 FAIL**; `phase_completion("P4")` drops to **97.0** | matches the review |
| `phase-0-baseline-manifest.yaml` → `status: CONTAINED` | **2 of 4 FAIL** (`test_rebaseline_invariants`, `test_docs_control_system`) | review claimed 1 of 4 — the guards are **stronger** than claimed, not weaker |

The 97.0 figure is the mechanical proof of F-TR-06's premise: criterion 11's three points are
genuinely load-bearing, and 97/100 does not reach COMPLETE.

> **Correction to my own first probe.** An initial mutation attempt appeared to show only 2 of 4
> guards failing. It was mis-targeted: the registry contains **two** `canonical_finalizer` criteria
> (P3's and P4's) and my string search hit P3's. Re-run against the P4 unit block, the result is
> 4 of 4. The reviewer's table is correct.

## E. Explicit finding adjudication

### F-TR-01 — MEDIUM — `ARCHITECTURE.md` §28/§29 still asserts P4 incomplete

**Confirmed on the candidate tree.** `ARCHITECTURE.md:272` reads
`| **P4** | 🔄 READY *(selected)* — **IN PROGRESS, NOT COMPLETE** | … EP-1/EP-3/EP-8/EP-14 and
finding F2 remain, so **R-07 stays OPEN** |`; `:273` reads `| **P5+** | ⛔ NOT STARTED |`; `:280`
reads *"Nothing does, until P4."* Live text, not inside a `<details>` block. The file's header
banner defers only on **architecture** disagreements to the ADRs and specs — it carries no
status-defers-to-`CURRENT.md` clause. `git diff 0891d1a 42ea24c -- ARCHITECTURE.md` is empty.

**1. Authoritative canonical state, or descriptive architecture prose?**
**Descriptive architecture prose carrying a status table it holds no authority to set.**
`docs/CANONICAL-DOCUMENTS.md:63` classifies `ARCHITECTURE.md` **CANONICAL**, and CANONICAL's own
defined scope is *"Binding truth. **Product, architecture and specification**."* Status is a
**separate authority level** in the same table — `CURRENT_STATUS`, *"✅ Yes (**for status only**)"*
— and §8 states without qualification: *"**There is exactly ONE current-status authority:**
`docs/implementation/CURRENT.md`… **Any other file claiming to be 'the where-are-we doc' is stale
by definition.**"* §1 adds that `ARCHITECTURE.md` is an *"entry point into this chain, not a
replacement for it."* `ARCHITECTURE.md` is therefore canonical **for architecture** and carries
**no status authority whatsoever**.

**2. Does the contradiction make the candidate internally inconsistent?**
**Not in the authority sense, and not in any machine-checked sense.** There is no authority tie to
break: a document with no status authority cannot contradict the status authority. Every
machine-checked surface agrees — `derive()` matches the committed block with zero divergent keys,
`build_status_errors()` is `[]`, `repo_state()` is `PRODUCING`, the 227 control guards pass and the
canonical suite is green. What exists is a **documentation-accuracy defect**: a reader who
grep-lands on `ARCHITECTURE.md:272` is told something false about the repository.

**3. May the second finalizer legally certify while it remains?** **Yes.** `ARCHITECTURE.md` is not
a member of `finalize_status.STATUS_METADATA_FILES` (I read the 10-tuple in the source); the
finalizer neither reads nor writes it; and none of `PROGRESS-PROTOCOL.md` §8's ten rejection
conditions — implemented in `progress_status.build_status_errors()`, which I executed — reaches
non-status prose.

**4. Does it require narrowly scoped remediation *before* finalization?** **No — and this is where I
depart from the reviewer's recommendation, on sequencing rather than on substance.**

I did **not** accept "non-blocking" because the review table says so. I tested it, and I first made
the finding *stronger* than the review did:

- **The repository's own precedent for this exact act includes the correction.** The
  closure-topology determination §2.3 names `f579d92` *"Adjudicate P3 COMPLETE — all 14 weighted
  criteria PASS"* as the invariant P3 analogue. I read that commit: it is a content commit on a
  metadata parent, it authored `acceptance_criteria` into the registry, it changed the **same four
  guard files** — and it corrected **`ARCHITECTURE.md` and `AGENTS.md` alongside `CLAUDE.md` and
  `README.md` in the same commit**, rewriting exactly the phase-table row now at issue. The P4
  closure commit corrected `CLAUDE.md` and `README.md` and left their two peers. It is a **partial
  execution of the established precedent.**
- **A live guard states this invariant.** `test_switch_consistency.py`'s
  `test_..._completed_units_are_not_described_as_live_work` docstring reads: *"A COMPLETE unit may
  not still be described as READY / awaiting review / next work in any LIVE current-authority or
  auto-loaded surface."* I confirmed `ARCHITECTURE.md` and `AGENTS.md` **are** inside its scanned
  population. The candidate escapes it only on regex phrasing: the guard matches
  `the (?:single|one and only) READY unit`, while the files say `READY *(selected)*` and
  `the sole READY unit`. The population reaches these files; only the patterns fall short. This is
  a real gap and I record it as **ADJ-01** (§G).

That is the honest case *for* remediation. It is nevertheless **not a precondition of
finalization**, because remediating before finalization is mechanically impossible without a
strictly worse outcome — and I proved the mechanics rather than reasoning about them:

- **A second consecutive content commit is illegal. I executed it.** In a throwaway clone at
  `42ea24c` I appended one line to `ARCHITECTURE.md`, committed, and ran the real guard:

  ```
  repo_state() RAISED: AssertionError CURRENT.md records 0891d1a19 but HEAD is 29478c871 -
  the status authority is stale beyond every legal state.
  ```

  `eval/tests/test_status_reality.py` → **3 failed, 4 passed**. The cause is structural and
  independent of the delta's contents. The probe clone was deleted.
- **The only other pre-finalization route is amending or replacing `42ea24c`,** which would
  (a) orphan `refs/preserve/p4-closure-targeted-review-42ea24c`, whose parent is the exact
  candidate; (b) void the targeted review, which reviewed this exact commit and tree; (c) require
  a fresh targeted review **and** a fresh targeted adjudication — an entire cycle — to fix
  documentation prose; and (d) is precisely the act the closure-topology determination §3 refused,
  for the same reason.
- **The correct legal home already exists and is already scheduled.** The moment the second
  finalizer commits, state becomes `FINALIZED` and the next content slot opens. `CLAUDE.md` §11
  sequences the R-07 content commit exactly there. All four stale surfaces are content-surface
  edits — the same class the P3 precedent made in a content commit — so they belong in that commit.

**Resolution of the tension, explicitly.** The reviewer's recommendation is **right about the
requirement and wrong about the sequencing**. The correction is *required*; it cannot legally
precede finalization; making it a precondition would force either an illegal topology or a
destructive amend that discards a valid independent review. I therefore **carry it forward as a
BINDING precondition on the next content commit** (the R-07 commit), not as a bar to the finalizer.

**Verdict: does not block the second finalizer. Binding on the next content commit.**

### F-TR-02 — LOW — `AGENTS.md` stale, including *"only completing P4 closes R-07"*

**Confirmed** at `AGENTS.md:38–43`, untouched by the closure commit.

**Does it contradict the deliberately separate R-07 closure cycle?** **Yes, materially.** The
parenthetical *"only completing P4 closes R-07"* is the exact P4-COMPLETE ⇒ R-07-contained
conflation that `CLAUDE.md` §11, the adjudication §G.5, `BUILD-STATUS.yaml`,
`CAPABILITY-TRACEABILITY.yaml` and a **new guard assertion** in this very candidate exist to
prevent. P4 is now COMPLETE and R-07 is **not** closed, so the sentence is now false on its face.

**Must it be corrected before finalization?** **No.** `AGENTS.md` is classified **EVIDENCE**
(`CANONICAL-DOCUMENTS.md:66`) — *"⚠️ Supporting only. Records observations. **Cannot decide.**"* —
and `CLAUDE.md` is recorded as **superseding** *"agent status blocks in `AGENTS.md`"*
(`CANONICAL-DOCUMENTS.md:61`). `CLAUDE.md` **was** corrected by this candidate. The section
additionally self-disarms, opening *"Do not read status from this file… `CURRENT.md` is the single
authority"* and closing *"If this line and `CURRENT.md` ever disagree, `CURRENT.md` is right and
this line is stale."* It is outside the finalizer's write set and outside §8's rejection surface.

**Verdict: does not block. Binding on the next content commit** (P3 precedent corrected this file
in the analogous commit).

### F-TR-03 — LOW — `FREIGHT-CAPABILITY-MAP.md` states P4 not complete

**Confirmed** at `docs/product/FREIGHT-CAPABILITY-MAP.md:251`.

**Canonical, derived, descriptive or historical?** **Canonical (navigation) — i.e. derived and
descriptive, with no independent authority.** `CANONICAL-DOCUMENTS.md:79` classifies it
*"**CANONICAL (navigation)** — Defers classification/phase/tier to
`OPERATIONAL-USE-CASE-COVERAGE.yaml`; **states nothing as implemented**."* Its own header adds
*"current status → `CURRENT.md` … On any conflict the cited source wins."* Not machine-consumed for
status: the only code touching it (`test_roadmap_completeness_control.py:608`,
`mutate_roadmap_completeness.py`) counts its 18 capability areas.

**Correction required before finalization?** **No.**
**Verdict: does not block. Binding on the next content commit.**

### F-TR-04 — LOW — `EFFECT-PATH-INVENTORY.yaml` states *"P4 REMAINS NOT COMPLETE"*

**Confirmed** at `docs/implementation/EFFECT-PATH-INVENTORY.yaml:91`.

**Is it machine-consumed canonical evidence?** **It is machine-consumed — and I determined exactly
what is consumed, because the distinction decides the finding.** `test_bootstrap_hermeticity.py:326`
does `yaml.safe_load()` on it, and the guard consumes **only the structured `paths` list** —
`id`, `path`, `external_system`, `production_reachable`, `enablement`, `authority_bypass`,
`classification`, `containment_phase`, `disposition`, plus on-disk existence of removed paths and
set equality against the baseline manifest's import-probe candidates. Line 375 additionally asserts
the **literal** `R-07 OPEN`, which lives at `meta.risk` (L28, `R-07 OPEN - NOT CONTAINED`) and is
**still true**.

I located the stale sentence programmatically: it sits in the **free-text narrative field**
`paths[EP-1].p4_f01_governed_join`. **No guard parses that field.** Its authority classification is
`CURRENT_STATUS` scoped to *"the exact live-write adjudication (the six, the exclusions, EP-14)"* —
not to phase completion, for which §8 reserves sole authority to `CURRENT.md`.

**Does the stale statement make the candidate inconsistent?** **Not in the machine-checked sense** —
the consumed surface is correct and the whole suite is green. It is a prose defect in a
semi-canonical artifact, compounded because the same block still carries the provider-wiring
misstatement already recorded as **AD-01**.

**Verdict: does not block. Binding on the next content commit, folded into AD-01's already-scheduled
prose correction, with the block marked `HISTORICAL` as its sibling `p4_write_half_residual`
already is.**

### F-TR-05 — LOW — the builder handoff names a guard function that does not exist

**Confirmed and fully bounded.** `p4-closure-candidate-targeted-review-handoff-42ea24c.md:220`
names `test_the_dependency_graph_is_complete_consistent_and_acyclic`.

| Check | Result |
|---|---|
| Does that function exist anywhere in the candidate tree? | `git grep` over `HEAD` → **ZERO hits** |
| Is it referenced by any **committed** evidence artifact? | **ZERO hits** anywhere in the clone |
| Is the handoff itself tracked? | **No** — `git ls-tree HEAD` returns nothing for it; it is untracked, outside the candidate tree |
| The actual function | `test_the_implementation_graph_is_consistent_and_protects_the_safety_wall`, `eval/tests/test_bootstrap_hermeticity.py:382` — **present, and it is the one that changed** |
| Handoff sidecar | verifies (`9c5cc18793117c9d37f7014ed910e8a6ab34e806dd25b6b8bc0fd24559237e87`) |

**Is it limited to an untrusted handoff, or does committed evidence depend on it?** **Limited to the
untrusted, untracked handoff. No committed evidence depends on the nonexistent function.** As
instructed, I located all four guard changes **mechanically** rather than by name.

**Verdict: does not block. No remediation owed by the candidate.**

### F-TR-06 — ADJUDICATION QUESTION — `canonical_finalizer` authored by the closure builder

# DIRECT AUTHORIZATION CONCLUSION: **YES — the authorship is valid, and the second finalizer may consume the acceptance block.**

I did **not** rationalize this from the truth of the underlying evidence. I resolved it from role
assignment in repository authority first, and verified the evidence second.

**1. Which role does repository authority assign to transcribing the frozen acceptance criteria?**
**A later authorized content-authoring session — explicitly *not* an adjudicator.** The final
adjudication §F states it in its own words: *"**I set the following results from independent
evidence. A later authorized session must transcribe them into the registry; this document is their
source.**"* §H forecloses the alternative: the adjudication *"wrote no status metadata, marked no
phase complete."* The first-finalization report §7.1 names the same role and forecloses the
finalizer: *"`finalize_status.py` does not and cannot write it… **An authorized session must
transcribe adjudication §F verbatim.**"* The closure-topology determination fixes the surface: the
acceptance block lands in a **content** commit. Three independent authorities, one role, and the
adjudicator and the finalizer are each excluded by name.

**2. Was the builder authorized to transcribe a previously adjudicated, already-executed finalizer
result?** **Yes, by prior explicit instruction naming both the value and its trigger.** Adjudication
**§G.7.8**: *"The P4 `acceptance_criteria` block is present with the fourteen results of §F, **with
`canonical_finalizer` moved to `PASS` on the strength of the run that just completed**."* §F's
closing line: *"P4 computes to 97/100 now, and to **100/100 the moment `canonical_finalizer`
passes** — that is, on a successful finalizer run against `0891d1a`."* First-finalization report
§7.1 repeats it: *"13 PASS plus `canonical_finalizer` = **PASS on the strength of the run recorded
here**."* The builder was executing a written instruction, not improvising one.

**3. Is criterion 11 an attributable historical fact, or a new adjudicative decision?**
**An attributable historical fact.** The adjudicative decision — *"`canonical_finalizer` becomes
PASS iff a canonical finalizer run against `0891d1a` exits 0"* — was made by the adjudicator, which
recorded `PENDING` **solely by construction** (*"The finalizer has not run on this candidate. This
criterion cannot pass before finalization and legitimately completes last."*) and fixed the
successor value in advance. The builder evaluated a predicate that is objectively verifiable from
the object store and the first-finalizer execution record. It exercised **no discretion**: it could
not have chosen otherwise without contradicting §G.7.8. The **P3 precedent confirms this is a
sequencing difference, not an authority difference** — I read `f579d92`, where
`canonical_finalizer` is also `PASS`, set directly by the P3 adjudication (`p3-final-adjudication-review.md:75`)
because there the finalizer had *already* run. P4 inverted the order; the authority is identical.

**4. Is every evidence element true and bound?** **All six bindings independently CONFIRMED:**

| Element | My verification |
|---|---|
| implementation candidate `0891d1a` | `86306d5`'s **single parent** is `0891d1a`; tree `a3e70464` |
| first-finalizer metadata commit `86306d5` | present, single parent, `PRODUCING` recomputed through the real guard |
| exactly five `STATUS_METADATA_FILES` | `git diff --name-only 0891d1a 86306d5` returns **exactly** `SUITE-RESULT.json`, `GATE-RESULT.json`, `CURRENT.md`, `IMPLEMENTATION-REGISTRY.yaml`, `BUILD-STATUS.yaml` — five, **zero stray paths**, every one a member of the 10-entry `STATUS_METADATA_FILES` tuple |
| suite 1961 / 0 / 1 / 1962 | **reproduced exactly by me** in a disposable clone; `SUITE-RESULT.json` records the same, `exit_status 0`, bound to `0891d1a`/`a3e70464` |
| clean-clone PASS | `GATE-RESULT.json` `passed: true`, bound to `commit 0891d1a` / `tree a3e70464` |
| one finalizer owner · lock release | first-finalization report §5 (pid 79370, held throughout, released on exit, no second finalizer); lock **re-probed UNHELD today** by `flock` and `current_owner()` → `None` |
| exit code 0 | first-finalization report §5 |

Criterion 11's evidence is true in **every** element, and it is **self-disclosing**: its own
`evidence` field opens *"NOT the adjudication's result - the adjudication recorded PENDING because
the finalizer had not yet run."* The same disclosure appears in the commit message, the registry,
`CURRENT.md:143` and `BUILD-STATUS.yaml`. This is transparency, not laundering.

**5. May the second finalizer consume an acceptance block whose finalizer result was transcribed by
a content builder?** **Yes.**

- The finalizer's rejection surface is `PROGRESS-PROTOCOL.md` §8, implemented in
  `progress_status.build_status_errors()`. I read the source: its §8 completion check requires
  `independent_review` **and** `final_adjudication` to be `PASS`. **Both are — and both were set by
  independent sessions** (criteria 13 and 14, verified verbatim against adjudication §F). It
  contains no authorship test, because authorship of the *other* twelve results is not what the
  protocol polices.
- `CLAUDE.md` §11's prohibition is scoped precisely: *"Do not adjudicate any phase COMPLETE from
  within the session that implemented or remediated it. **`independent_review` and
  `final_adjudication` require a session that did neither**; certifying **your own fixes** is
  self-adjudication."* The closure builder implemented and remediated **nothing** — `src/` and
  `scripts/` are tree-object-identical to `0891d1a`, and the closure delta contains zero source
  paths. There are no own fixes to certify.
- The residual concern the review correctly refused to decide — that 3 of 100 weight points rest on
  a result no adjudicating session set — **is what this document exists to close. I ratify criterion
  11 and the resulting P4 COMPLETE**, on the role assignment in (1)–(3) and the evidence in (4).

**Verdict: AUTHORIZED. Does not block. No remediation required.**

### F-TR-07 — NON-BLOCKING RESIDUAL — AD-02, `finalizer_lock.py` untested

**Re-confirmed on the candidate tree today:** `scripts/finalizer_lock.py` is 188 lines with
**0** references anywhere under `eval/`, **0** nodes in `TEST-NODE-MANIFEST.json`, and **0**
mutation operators targeting it.

**Is it recorded?** **Yes** — present in P4's `residual_risks_carried_forward` under
`recorded_non_blocking`, alongside the full register.

**Does repository authority permit it as a carried residual for this finalization?** **Yes,
explicitly.** The final adjudication §E.3 adjudicated it *"**Not blocking for P4 or R-07**: the lock
protects status-record integrity, not effect containment, and P4's acceptance is adapter
containment,"* while recording it as *"directly load-bearing for the very next act"* and a **named
prerequisite** (§G.7.3). That is authority to run the finalizer with AD-02 standing, provided its
operating instruction travels with it: **treat a lock refusal as authoritative and never reclaim the
lock because a log file is missing.** The mechanism was independently re-derived 16/16 by the
adjudicator and behaved correctly throughout the first pass.

**Verdict: permitted as a carried residual. Carried forward undischarged, with its operating
instruction, and a hostile battery plus manifest regeneration still owed.**

## F. Cumulative consistency

Considered **together**, not one at a time.

**Classification: a DOCUMENTATION CONSISTENCY DEFECT REQUIRING REMEDIATION.** Not harmless stale
prose; **not** a repository-authority contradiction that blocks certification.

**Why not harmless.** Four surfaces — one CANONICAL, one CANONICAL (navigation), one
CURRENT_STATUS-classified, one EVIDENCE — still tell a reader P4 is incomplete. Two of them
(`ARCHITECTURE.md`, `AGENTS.md`) were corrected by the **P3 precedent commit in the analogous
content commit**, so the omission is a scope gap against the repository's own pattern, not an
accident of classification. One of them (`AGENTS.md`) additionally repeats the exact
P4-COMPLETE ⇒ R-07-closed conflation the candidate spent four other files and a new guard assertion
preventing. And an existing guard already **states** this invariant and already **scans** two of the
files, missing them only on regex phrasing (**ADJ-01**). Cumulatively this is a real defect and I
record it as binding.

**Why it does not block certification.** The authority question has a single, unambiguous answer
that no amount of stale prose disturbs:

> **`CANONICAL-DOCUMENTS.md` §8 — "There is exactly ONE current-status authority:
> `docs/implementation/CURRENT.md`." `IMPLEMENTATION-REGISTRY.yaml` is the machine authority for
> unit state; the two are guarded against each other. "Any other file claiming to be 'the
> where-are-we doc' is stale by definition."**

None of the four holds status authority: `ARCHITECTURE.md` is CANONICAL **for architecture** and an
entry point, not a replacement (§1); `AGENTS.md` is EVIDENCE and is explicitly **superseded** by
`CLAUDE.md` for agent status blocks; `FREIGHT-CAPABILITY-MAP.md` is navigation that *"states nothing
as implemented"*; `EFFECT-PATH-INVENTORY.yaml` is `CURRENT_STATUS` **scoped to the live-write
adjudication**, and its machine-consumed surface is correct. Three of the four self-disarm in text.
There is therefore **no authority-level contradiction to resolve** — the disagreement is between one
authority and four non-authorities, which repository authority already adjudicated in advance.

**And the cumulative defect cannot legally be fixed before finalization.** All four are content
surfaces; the candidate occupies the single content slot; a second consecutive content commit is
illegal (proved in §E, F-TR-01); and an amend would void a valid independent review. The defect's
only legal home is the next content commit. Cumulation therefore **raises the priority** of the
remediation without changing **when** it may occur.

**Authoritative source when documentation surfaces disagree:** `CURRENT.md` for status, with
`IMPLEMENTATION-REGISTRY.yaml` as the machine authority for unit state. Both record P4 **COMPLETE**
and P5 **READY / NOT_STARTED**. The four stale surfaces are wrong; the record is right.

## G. New findings from this adjudication

Neither is blocking. Both must be carried forward.

**ADJ-01 — LOW–MEDIUM — the switch-consistency guard states the invariant but its patterns do not
reach the stale phrasings.** `test_switch_consistency.py`'s completed-unit guard docstring reads
*"A COMPLETE unit may not still be described as READY / awaiting review / next work in any LIVE
current-authority or auto-loaded surface,"* and its population **does** include `ARCHITECTURE.md`
and `AGENTS.md` (augmented by the fixed five-root-document set). But it matches
`the (?:single|one and only) READY unit`, and the two files say `READY *(selected)*` and
`the sole READY unit` — so the defect the guard exists to catch passes it. This is why the closure
commit's correction set was, as the review put it, guard-driven rather than scope-driven.
**Remediation:** broaden the alternation (e.g. `sole`, `selected`, `IN PROGRESS, NOT COMPLETE`) and
re-run against the corrected files, in the same commit that fixes F-TR-01/F-TR-02. Not a false
green in the candidate: the guard is not evaded, it is under-specified, and it predates `42ea24c`.

**ADJ-02 — INFORMATIONAL — the P3 precedent's correction scope was not fully carried into P4.**
`f579d92` corrected `AGENTS.md`, `ARCHITECTURE.md`, `CLAUDE.md` and `README.md` in the P3 closure
content commit. `42ea24c` corrected `CLAUDE.md` and `README.md` only. Recorded so the next content
commit restores parity rather than repeating the omission at P5.

## H. R-07 boundary

| Requirement | Result |
|---|---|
| `phase-0-baseline-manifest.yaml` unchanged | **CONFIRMED** — blob `dd00f197f899fba0a28cd6752ee803fb442ae75c`, byte-identical to `0891d1a`; not in the closure delta |
| R-07 remains OPEN — NOT CONTAINED | **CONFIRMED** — L229 `status: OPEN - NOT CONTAINED`; stated across 12+ tracked files including `ARCHITECTURE.md`, `CLAUDE.md`, `README.md`, `CURRENT.md` (×6), `BUILD-STATUS.yaml`, the registry and `EFFECT-PATH-INVENTORY.yaml` |
| No closure text falsely states R-07 contained | **CONFIRMED** — a tree-wide sweep for containment claims returns only **NOT DONE / STILL OWED / procedural** statements about *who* may close it and *where*. Zero affirmative containment claims |
| P4 completion and R-07 containment are legally separate cycles | **CONFIRMED** — adjudication §G.5 (*"not by the finalizer's mechanical update, and not in one step"*), `CLAUDE.md` §11, closure-topology §? (R-07 record → a **content** commit **after** finalization), and P4's registry `completion_evidence` marks the R-07 record `### STILL OWED, NOT EVIDENCE OF COMPLETION` |
| P5 READY while R-07 open — permitted? | **YES, by adjudication §G.6**: once P4 is recorded COMPLETE at 100/100, P5 becomes eligible to move `BLOCKED → READY`, and P4 must leave READY in the same commit. Two cautions carried: `CLAUDE.md` §11 forbids **beginning** P5 (READY is a selection, never a claim of progress), and P5's independent **G2** transition/event blocker is present and undischarged — I confirmed it in the registry |

**R-07 was not closed here. The R-07 content cycle was not begun.**

## I. Report and residual attribution

| Requirement | Result |
|---|---|
| Historical reports retain original candidate attribution | **CONFIRMED** — the re-review and the adjudication both name `0891d1a` in their own headers; the first-finalization report names `86306d5`/`0891d1a` |
| No report claims to have reviewed `42ea24c` unless it did | **CONFIRMED** — tree-wide `git grep` for `42ea24c` across `*.md`/`*.yaml`/`*.json`/`*.py` returns **zero hits**; `CURRENT.md` states the negation outright: *"None of those four reports reviewed the closure commit itself."* The only artifact reviewing `42ea24c` is the targeted review, preserved outside the tree |
| Sidecars | final adjudication and first-finalization report **match**. The re-review's sidecar deliberately records the **original's** hash: tracked file 813 lines, preserve-ref blob 777; `tail -n 777` of the tracked file `cmp`s **byte-identical, zero differences** against the preserve blob and hashes to `181e1a37…b316` — the sidecar's value. The 36-line banner is the sole addition, required by `test_false_green_defenses.py`. **VERIFIED BY ME** |
| Targeted review durably preserved | **CONFIRMED** — §B |
| RR-01 remains a binding P12 precondition | **CONFIRMED** — under `binding_p12_preconditions`, `STATUS: NOT DISCHARGED - BINDING P12 PRECONDITION`, compounded by F-08 and F-09 |
| AD-01, AD-02 recorded | **CONFIRMED** |
| RR-02 … RR-06 recorded | **CONFIRMED** |
| F-03, F-06, F-07, F-08, F-09, F-10 recorded | **CONFIRMED** |
| Nothing discharged | **CONFIRMED** — the only occurrence of "DISCHARG" in the whole residual block is the negation `NOT DISCHARGED` |
| Production Action Class registration deferred to U8.1/P8 | **CONFIRMED** — under `founder_decision_preserved_unchanged`; `AC-CKPT-6-missing` unchanged |
| Production `GateRegistry` EMPTY | **CONFIRMED** — AST sweep, zero construction and zero registration sites (§D) |

## J. Second-finalizer authorization

### **The exact candidate is ELIGIBLE for EXACTLY ONE second finalizer.**

```
candidate commit          42ea24cfc76fac19406e7eaa44b695b8d032b3aa
candidate tree            1e2bba791a5c2c77194d1df9ce16e1d9df84315a
candidate parent          86306d5c4d866baf1a7fb6e4bd8220ce31017acd
branch                    p4/adapter-containment-completion (local, UNPUSHED)

accepted targeted review  docs/implementation/p4-closure-candidate-targeted-review-report-42ea24c.md
  sha256                  5547aa5e8d89ced661b4f6e415767f8259809bdf5d175615065158fa871a8ea5
  preservation ref        refs/preserve/p4-closure-targeted-review-42ea24c
  preservation commit     c30a43be5bf8d92a07a30136c94c0642c6792b12  (parent = the candidate)
  verdict                 ACCEPT FOR SEPARATE TARGETED ADJUDICATION

this adjudication         docs/implementation/p4-closure-candidate-targeted-adjudication-report-42ea24c.md
  preservation ref        refs/preserve/p4-closure-targeted-adjudication-42ea24c   (see §M)
```

**Exact finalizer prerequisites — re-verify each before running:**

1. `HEAD` is exactly `42ea24cfc76fac19406e7eaa44b695b8d032b3aa`, tree `1e2bba791a5c…`, on
   `p4/adapter-containment-completion`; `repo_state()` is still **`PRODUCING`** (recorded
   `0891d1a` == `HEAD^^`, `HEAD^` = `86306d5` and pure).
2. **The candidate has not moved** since this adjudication, and both
   `refs/preserve/p4-closure-targeted-review-42ea24c` and
   `refs/preserve/p4-closure-targeted-adjudication-42ea24c` still resolve to commits whose parent
   is the candidate.
3. **The working tree is clean.** `finalize_status.py` aborts on any dirty **tracked** file *before*
   it deletes receipts. Today no tracked file is dirty; four **untracked** review artifacts are
   present. If any must be moved, move them **out of band** (`cp`/`mv`) and **never** with
   `git checkout` / `restore` / `stash` / `clean` — `CLAUDE.md` §9 records that doing so once
   destroyed unrecoverable work here.
4. It holds `finalizer_lock` **exclusively**; `current_owner()` is `None` first. **AD-02 applies:**
   this lock has no committed test coverage — **treat a refusal as authoritative and never reclaim
   it because a log file is missing.**
5. No builder owns the worktree (`.git/neyma-builder-worktree.lock` unheld); no
   `mutate_phase4_boundary` or `clean_clone_gate` run is in flight.
6. `main` is untouched at `152574e4f4f2969468c9d31b1e705188896175b5`; nothing is pushed.
   Integration to `main` is fast-forward-only under **R-21** and is a separate founder-authorized
   act, **not** part of finalization.

**Expected `STATUS_METADATA_FILES` write set.** `finalize_status.STATUS_METADATA_FILES` is a
**10-entry** tuple (the five status artifacts plus five placeholder-substitution review documents).
The metadata commit is expected to touch **exactly these five**, as `86306d5` did:

```
docs/implementation/SUITE-RESULT.json
docs/implementation/GATE-RESULT.json
docs/implementation/CURRENT.md
docs/implementation/IMPLEMENTATION-REGISTRY.yaml
docs/implementation/BUILD-STATUS.yaml
```

`phase-0-baseline-manifest.yaml` **must not** appear. Any non-status path fails
`test_status_reality.py`. The receipts and the derived block will rebind from `0891d1a`/`a3e70464`
to `42ea24c`/`1e2bba79`; `build_status_errors()` must remain `[]` afterwards.

**Current state entering the pass:** P4 **COMPLETE**, 14/14, 100/100 · P5 **sole READY**,
`execution_state: NOT_STARTED`, no contract, G2 blocker undischarged · P6–P14 **BLOCKED** ·
R-07 **OPEN — NOT CONTAINED** · overall program **22.0 %**, current phase **0.0 %**, tier
**SPECIFIED**.

**Residuals carried forward, none discharged:** RR-01 (**binding P12 precondition**, compounded by
F-08 and F-09) · AD-01 · AD-02 · RR-02 … RR-06 · F-03 · F-06 · F-07 · F-10 · the U8.1/P8 founder
deferral with production `GateRegistry` EMPTY · **plus, from this adjudication:** F-TR-01, F-TR-02,
F-TR-03, F-TR-04 and **ADJ-01**, **ADJ-02**.

**Explicit authorization answers:**

| Question | Answer |
|---|---|
| Must stale canonical prose be remediated **first**? | **NO.** It is **required**, and it is **binding on the next content commit** — the R-07 commit — because a second consecutive content commit is illegal (proved) and an amend would void a valid independent review. It is **not** a precondition of the finalizer. |
| Is `canonical_finalizer` authorship valid? | **YES.** §E, F-TR-06. |
| May exactly one finalizer run? | **YES — exactly one.** No second run, no re-run, no forged receipt. |
| May P5 implementation begin? | **NO.** READY is a selection, never a claim of progress. Stop at the control boundary (`PROGRESS-PROTOCOL.md` §9, `CLAUDE.md` §11). P5's G2 blocker is separately undischarged. |
| Does R-07 remain open after this pass? | **YES.** R-07 stays **OPEN — NOT CONTAINED** through and after finalization. It closes only in the separate content commit that writes `phase-0-baseline-manifest.yaml`, afterwards. |

**Required sequence from here:** this targeted adjudication → **exactly one** second finalizer →
the next **content** commit carrying the R-07 CONTAINED record **and** the F-TR-01 … F-TR-04 /
ADJ-01 documentation remediation → its own review, adjudication and finalization.

## K. Verdict

# ACCEPT CLOSURE CANDIDATE FOR SECOND FINALIZATION

The candidate is exactly the act repository authority named, and nothing else. Identity, tree,
parent, single-parent shape, the one-content-commit-above-`86306d5` topology and the `PRODUCING`
state all verify from the object store and from the repository's own guard, executed. No protected
ref moved, nothing was pushed, no builder or finalizer owns the primary repository, the finalizer
lock is unheld, and the candidate has not moved since the review that accepted it. The targeted
review is durably preserved on a commit parented at the exact candidate, and its bytes hash to the
expected value three ways.

**No P4 runtime implementation byte changed** — `src/`, `scripts/`, `configs/` and `data/` are
tree-object-identical to accepted candidate `0891d1a`, and the production `GateRegistry` population
is **EMPTY** by AST sweep. The fourteen criteria match the frozen template exactly in name, weight,
order and count, sum to 100, are fully PASS with attributable evidence, and thirteen match the
adjudication §F verbatim. P4 100.0 / P5 sole READY and NOT_STARTED / P6–P14 BLOCKED are what the
repository's own composer computes; `derive()` matches the committed block with zero divergent keys;
`build_status_errors()` is `[]`. The four guard changes are narrow name-frozen replacements that
gained assertions and **failed every anti-vacuity mutation I ran**. The canonical suite reproduces
**1961 / 0 / 1 over 1962 collected**, the node manifest is identical by identity, and 227 control
guards pass. R-07 remains OPEN — NOT CONTAINED on a byte-identical manifest, the full residual
register is carried with RR-01 binding and undischarged, no receipt was forged for `42ea24c`, and
every historical report keeps its original `0891d1a` attribution.

**Why each finding is non-blocking:**

**F-TR-01** is the one that had to be earned rather than assumed, and I made it stronger before
clearing it: the P3 precedent commit corrected `ARCHITECTURE.md` in the analogous closure content
commit, and a live guard states the very invariant the file now violates (**ADJ-01**). It is a real
documentation defect. It is nevertheless not a bar to the finalizer, because `ARCHITECTURE.md` holds
**no status authority** — `CANONICAL-DOCUMENTS.md` §8 gives that solely to `CURRENT.md` — it is
outside the finalizer's write set and outside every §8 rejection condition, and remediating it
*before* finalization is **mechanically illegal**: I executed a second consecutive content commit at
`42ea24c` and `repo_state()` raised *"stale beyond every legal state"* with three status-reality
tests failing. The only pre-finalization alternative is an amend that would orphan the review
preservation commit and void the review of this exact tree. So the correction is **required and
binding on the next content commit**, which is the first legal slot — and which is already scheduled
for R-07.

**F-TR-02 … F-TR-04** are the same defect on documents that hold no status authority — EVIDENCE,
navigation, and a `CURRENT_STATUS` artifact whose **machine-consumed surface is correct** (the stale
sentence lives in a free-text field no guard parses). Three self-disarm. All four are bound to the
same next content commit. **Cumulatively** they are a documentation consistency defect requiring
remediation, not a repository-authority contradiction: the disagreement is between one authority and
four non-authorities, which repository authority resolved in advance.

**F-TR-05** is confined to an untracked handoff; the named function exists nowhere, no committed
evidence depends on it, and I located every guard change mechanically instead.

**F-TR-06** is answered **YES** on role assignment, not on the comfort of true evidence: repository
authority assigns transcription to a later authorized content session — expressly not the
adjudicator, expressly not the finalizer — and adjudication §G.7.8 pre-set `canonical_finalizer` to
`PASS` *"on the strength of the run that just completed."* The builder evaluated a predicate with no
discretion, disclosed it in six places, and implemented or remediated nothing. Every one of the six
evidence bindings is independently confirmed. **This document is the separate adjudication the
review said must ratify criterion 11, and it ratifies it.**

**F-TR-07 / AD-02** is permitted as a carried residual by the final adjudication's own
classification, with its operating instruction carried alongside it.

**No finding is a false green. Exactly one second finalizer is authorized on this exact candidate.
P5 must not begin. R-07 remains OPEN — NOT CONTAINED.**

## L. Scope of this document

This is an adjudication and nothing else. It ran no finalizer, wrote no status metadata, marked no
phase complete, closed no risk, awarded no weight it did not verify, modified no product code, no
test, no status file, no report, no index and no branch, remediated no finding, amended no
candidate, moved no protected ref, pushed nothing, merged nothing, deployed nothing, contacted no
external system and enabled no effect. It did not begin P5, did not close R-07 and did not begin the
R-07 content cycle. No previous report was overwritten. The candidate's tree
`1e2bba791a5c2c77194d1df9ce16e1d9df84315a` is unchanged and still verifies.

**Stop at the control boundary.**

## M. Preservation

```
report        docs/implementation/p4-closure-candidate-targeted-adjudication-report-42ea24c.md
sidecar       docs/implementation/p4-closure-candidate-targeted-adjudication-report-42ea24c.md.sha256
preservation  refs/preserve/p4-closure-targeted-adjudication-42ea24c
parent        42ea24cfc76fac19406e7eaa44b695b8d032b3aa   (the exact adjudicated candidate)
```

The preservation commit adds **only** this report and its `.sha256`, leaving the candidate's tree
otherwise untouched — the same mechanism already used by
`refs/preserve/p4-independent-rereview-0891d1a`, `refs/preserve/p4-final-adjudication-0891d1a` and
`refs/preserve/p4-closure-targeted-review-42ea24c`. It was built through a temporary
`GIT_INDEX_FILE` outside `.git/index`, so the product branch and the repository index were never
touched. The adjudicated candidate was not modified and the product branch was not moved.
