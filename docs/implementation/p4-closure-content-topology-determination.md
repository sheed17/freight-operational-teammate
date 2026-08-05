# P4 CLOSURE-CONTENT — LEGAL-TOPOLOGY DETERMINATION AND BLOCKED-CANDIDATE REPORT

**Author:** fresh closure-content builder. Did not implement P4, did not perform the independent
re-review, did not perform the final adjudication, did not author any prior handoff.

**Date:** 2026-07-29.

**Result: NO CLOSURE-CONTENT CANDIDATE WAS CREATED.** The requested delta cannot be expressed as a
legal content commit before finalization. This is a mechanical determination, proved against the
repository's own guards, not a judgement call. §3 states the exact authorization that would be
required to proceed anyway, and §4 states why this builder recommends against it.

Nothing was pushed. The finalizer was not run. P4 is NOT COMPLETE. R-07 remains OPEN — NOT
CONTAINED. No implementation byte, production gate, test, mutation operator or policy changed. No
protected ref moved. No history was rewritten.

---

## 1. Authority read and independently verified

Every value below was read from the object store or the file, never from the handoff.

### 1.1 Candidate identity — **MATCH**

| Property | Expected | Verified |
|---|---|---|
| Commit | `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e` | identical |
| Tree | `a3e704645b8a06561d90cdb5f81288309ae51850` | identical |
| Parent | `f1e8e1893eff2460d68f3f168f18fd29635b250d` | identical |
| Branch | `p4/adapter-containment-completion` | `HEAD` is the branch tip |

### 1.2 Report hashes — **MATCH ×2, three-sided each**

| Report | Expected SHA-256 | Worktree file | Committed sidecar |
|---|---|---|---|
| Final adjudication | `078cfea8…997e` | match | match |
| Accepted re-review | `181e1a37…316` | match | match |

### 1.3 Preservation refs — **MATCH, both parented on the candidate**

```
refs/preserve/p4-final-adjudication-0891d1a   420e5b2d0b3b6af280d8a8d0f3d80ad9f6cb9ebc
    parent 0891d1a19a9c…   tree 434f47aa8d70…
refs/preserve/p4-independent-rereview-0891d1a 5ca6d2e95896336f447cf693da04282a0d53bdbf
    parent 0891d1a19a9c…   tree e90e2580a016…
```

### 1.4 Protected refs — **UNMOVED**

`main` and `origin/main` both `152574e4f4f2969468c9d31b1e705188896175b5` — the value
`PROGRESS-PROTOCOL.md` §10 records. Every pre-existing `refs/preserve/*` holds its prior value.

### 1.5 Ownership — **FREE**

`finalizer_lock.current_owner(Path('.'))` → `None`. Both `.git/neyma-finalizer.lock` and
`.git/neyma-builder-worktree.lock` are 0-byte with **no** `lsof` holder (the lock is `flock`-based,
so an unheld file is not a wedge). No `finalize_status`, `clean_clone_gate` or
`mutate_phase4_boundary` process is running. One live worktree plus one prunable stale entry on an
unrelated docs branch.

### 1.6 Index and working tree — **INDEX CLEAN, 7 DIRTY LINES**

`git diff --cached --stat` is empty: the index is identical to `HEAD`. `git status --porcelain`
reports 7 lines — 2 modified tracked files and 5 untracked. See §5.

---

## 2. The legal-topology determination (Step 3) — decided mechanically, not assumed

### 2.1 The governing rule

`PROGRESS-PROTOCOL.md` §10 and `eval/tests/test_status_reality.py::repo_state` permit exactly three
states, resolved through **first-parent** lookups against the `content_commit` recorded in the
**working-tree** `CURRENT.md` (`test_status_reality.py:57`, read from disk — not from git):

| State | Condition |
|---|---|
| `BASELINE` | recorded == `HEAD` |
| `FINALIZED` | recorded == `HEAD^`, and `HEAD` touches only `STATUS_METADATA_FILES` |
| `PRODUCING` | recorded == `HEAD^^`, and `HEAD^` touches only `STATUS_METADATA_FILES` |

Anything else raises *"stale beyond every legal state."*

Today: recorded `3d231731b8b0…` == `HEAD^^`; `HEAD^` is `f1e8e18` (pure metadata); `HEAD` is the
candidate. State is **`PRODUCING` — legal**.

### 2.2 Both options were executed and classified in a disposable `--no-local` clone

The primary worktree was **never** used for these probes. The real guard was run, not a
reimplementation of it.

| Option | Resulting state | Real guard `test_status_reality.py` |
|---|---|---|
| **(1)** `HEAD` = `0891d1a`, untouched | recorded == `HEAD^^` → `PRODUCING` | **1 passed** |
| **(A)** new content commit **on top of** `0891d1a` | recorded == `HEAD^^^` → none | ### **FAILED** |
| **(B)** **amend** `0891d1a` in place | recorded == `HEAD^^` → `PRODUCING` | **7 passed** |

Option A's exact failure:

```
E  AssertionError: CURRENT.md records 3d231731b but HEAD is 7705da0d5 - the status authority is
   stale beyond every legal state. Run the finalization cycle (run_canonical_suite.py, then
   update_current_status.py, then the metadata commit).
```

> ### **Option A — an additional consecutive content commit — is ILLEGAL. Proved, not assumed.**

The cause is structural and independent of the delta's contents: `0891d1a` is already a content
commit, so anything stacked on it is the second unfinalized content commit, which the two-commit
convention forbids. **No choice of file contents can rescue Option A.**

### 2.3 The precedent confirms the shape

`f579d92` *"Adjudicate P3 COMPLETE — all 14 weighted criteria PASS"* is the exact P3 analogue of the
requested delta. It **is** a content commit, and it **did** author `acceptance_criteria` into
`IMPLEMENTATION-REGISTRY.yaml`. But its parent `a7006c6` is a **status-metadata commit** — so
recorded == `HEAD^^` held and the state stayed `PRODUCING`. It was followed by `c8f25f9`, the
metadata commit. The pattern is invariant across the whole history: **metadata → content → metadata**.

`0891d1a` sits at the *content* position of that cycle. The next legal commit is a **metadata**
commit, not another content commit.

---

## 3. Why Option B was not executed either

Option B is topologically legal and would require an amend. It was **not** performed, because it
directly contradicts the authority that authorized this work at all.

The final adjudication's own finalizer prerequisites (§G.7):

> 1. **`HEAD` is exactly `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e`**, tree `a3e704645b8a…` …
> 5. **The candidate has not moved** since this adjudication …

An amend replaces the commit and the tree, and would therefore break, in one act:

| Broken by an amend | Why it matters |
|---|---|
| Adjudication prerequisites §G.7.1 and §G.7.5 | The verdict is `ACCEPT P4 FOR FINALIZATION` for **`0891d1a`**, not for a successor. |
| Criterion 13 `independent_review` = PASS | The accepted re-review's preservation commit is a **child of `0891d1a`**. A new candidate would carry **no** independent review. |
| Criterion 12 `clean_clone_execution` = PASS | `GATE-RESULT.json` binds `commit 0891d1a` / `tree a3e70464`. The gate would have to be fully re-run against the new tree. |
| Criteria 9 / 10 evidence | The 61/61 mutation battery and the 1961/1/1962 suite are bound to tree `a3e70464…`, including the byte-exact restoration proof. |

So Option B does not *deliver* the adjudicated state — it **destroys** it and would demand a fresh
independent review and a fresh adjudication of a commit nobody has reviewed.

> ### No amend was performed and no founder authorization is requested, because the delta that would justify one is not required. See §4.

Had an amend been the right answer, it would have required an exact live founder authorization
naming: old commit `0891d1a19a9c…`; the new intended tree; certified parent `f1e8e1893eff…`; branch
`p4/adapter-containment-completion`; the archive ref for `0891d1a`; the protected refs
(`main`/`origin/main` at `152574e4…`); and the worktree/index preservation hashes in §5. That
authorization is **not** being sought.

---

## 4. The premise itself does not hold — the closure content is not content

The brief states that the adjudication *"determined that the frozen 14-criterion P4 acceptance block
must exist in content before finalization."* **The adjudication determines the opposite,** and the
code agrees. This is the substantive finding of this session.

### 4.1 The acceptance block is finalizer-owned metadata, not content

`acceptance_criteria` lives in `docs/implementation/IMPLEMENTATION-REGISTRY.yaml`, which is member
4 of `finalize_status.STATUS_METADATA_FILES` (`finalize_status.py:70–81`). The adjudication §G.5:

> The P4 `acceptance_criteria` block (§F), P4 `status: COMPLETE`, and the R-07 lines in `CURRENT.md`
> and `BUILD-STATUS.yaml` are all in `STATUS_METADATA_FILES`, **so they may legally land in the one
> metadata commit** — but they must be authored, not derived.

And §G.7, under *"After it runs, and before committing"*:

> 8. **The P4 `acceptance_criteria` block is present with the fourteen results of §F**, with
>    `canonical_finalizer` moved to `PASS` on the strength of the run that just completed.

That is an instruction to the **finalizing session**, placing the block in the **metadata commit** —
*after* the finalizer runs. It is not an instruction to a content builder.

### 4.2 Nothing refuses a missing acceptance block

`scripts/progress_status.py:105–117`:

```python
def phase_completion(phase_id, w, registry_units) -> float:
    """A phase whose criteria are not yet instantiated (the normal pre-start case) is 0.0 …"""
    crits = unit.get("acceptance_criteria")
    if not crits:
        return 0.0
```

It **returns 0.0**; it does not refuse. No step in `finalize_status.py` requires the block to
pre-exist. The finalizer runs cleanly on `0891d1a` with no acceptance block and records P4 at 0% —
which the finalizing session then corrects by authoring the block and regenerating
`BUILD-STATUS.yaml`'s derived block, exactly as §G.7.8 warns must happen in that order.

**There is therefore no mechanism that needs the block early, and no legal commit that could carry
it early.**

### 4.3 R-07 must NOT be marked CONTAINED now — and its content commit belongs *after* finalization

Adjudication §G.5, stated as its own heading:

> ### **No — not by the finalizer's mechanical update, and not in one step.**
>
> … P4's own `completion_evidence` requires *"R-07 marked CONTAINED with the mechanism named, in
> `phase-0-baseline-manifest.yaml`"*. That file is **not** in `STATUS_METADATA_FILES`, and
> `test_status_reality.py:78–83` fails any metadata commit that touches a non-status file. **R-07
> therefore cannot be fully closed within the commit that finalizes this candidate. It requires one
> further content commit afterwards.**
>
> Until both occur, **R-07 remains OPEN — NOT CONTAINED**.

`phase-0-baseline-manifest.yaml` itself agrees, in its own words at the violation-surface block:

> Recording R-07 CONTAINED / P4 COMPLETE is the ADJUDICATION step and requires a session that did
> not implement this cut (CLAUDE.md §11) — **PENDING**.

The mechanical close condition is met and independently verified; the **recording** is not
authorized until after finalization. Marking R-07 CONTAINED in a pre-finalization content commit
would be precisely the drift `PROGRAM-WEIGHTS.yaml` names for P4: *"R-07 marked contained without
the six paths actually gone"* — here, marked contained before the act that earns it.

**And the topology works perfectly for the prescribed order.** After the metadata commit, recorded
== `HEAD^` (`FINALIZED`); a content commit then makes recorded == `HEAD^^` (`PRODUCING`) — legal.
The R-07 manifest edit has a legal home. It is simply **not this one**.

### 4.4 Consequence for every item in the requested delta

| Requested item | Correct owner | Correct commit |
|---|---|---|
| 14-criterion acceptance block, 13 PASS + `canonical_finalizer` PENDING→PASS | finalizing session | the **metadata** commit |
| P4 `status: COMPLETE` | finalizing session | the **metadata** commit |
| R-07 CONTAINED in `CURRENT.md` / `BUILD-STATUS.yaml` | finalizing session | the **metadata** commit |
| R-07 CONTAINED + mechanism in `phase-0-baseline-manifest.yaml` | a later session | a **content** commit **after** finalization |
| RR-01 as a binding P12 precondition; AD-01, AD-02, F-08/F-09 and the other retained residuals | finalizing session | the status/risk record in the **metadata** commit (§G.4, §G.7.10) |
| Phase-8 gate-registration deferral | already recorded; unchanged | — |

Every row is either metadata or post-finalization. **None is pre-finalization content.** That is why
no candidate was built.

---

## 5. Exact dirty-file preservation mechanism (Step 2 — completed in full)

Preservation was executed **before** any other action, and no forbidden command was used at any
point: no `git checkout`, `restore`, `stash`, `clean`, `gc` or `prune`.

### 5.1 The artifact

```
ref     refs/preserve/p4-closure-prestate-0891d1a
commit  4cd467a2840d9ab631d5b4bbb4a615f7c1abbbb7
tree    8c1fee16ca3b9ee38c98b5f073d803a7aed381ba
parent  0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e   (the candidate — attributable, not part of it)
paths   619  =  614 tracked + 5 untracked
```

### 5.2 Method, and the proof it was necessary

The already-proven HEAD-seeded temporary-index method, in a throwaway index outside `.git/index`:

```
GIT_INDEX_FILE=<tmp> git read-tree HEAD      # seed
GIT_INDEX_FILE=<tmp> git add -A              # overlay the working tree
GIT_INDEX_FILE=<tmp> git write-tree
```

The seeding is what preserves the **ignored-but-tracked** `.playwright-mcp/` paths (`.gitignore`
lists `.playwright-mcp/`, yet 7 paths are tracked). Proved rather than assumed, both ways:

| Index seeding | Tree | `.playwright-mcp/` paths captured |
|---|---|---|
| **empty** | `6a481020e2f8e6db4ba0f2ed688466a69a6fb32f` | **0 of 7** |
| **HEAD-seeded** | `8c1fee16ca3b9ee38c98b5f073d803a7aed381ba` | ### **7 of 7** |

### 5.3 Hand-authored / finalizer-owned content preserved — verified inside the artifact

| Path | SHA-256 in the preserve tree | vs `HEAD` |
|---|---|---|
| `CURRENT.md` | `b37ccea814daf20ef8fd98c8bde81118e9cc98e89f1f9fb63ed326d077ff0a6f` | differs (`HEAD`: `2d631dc4…`) |
| `GATE-RESULT.json` | `f16c85b8a3792137d3c2fed97d64e57216662be8de6a5ef1ed3d636969ba6249` | differs (`HEAD`: `63ef8366…`) |
| `p4-final-adjudication-report-0891d1a.md` | `078cfea8…997e` | untracked |
| `p4-independent-rereview-report-0891d1a.md` | `181e1a37…b316` | untracked |
| `p4-remediation-handoff.md` | `1295399b5224dd2e55e605c7ee0ce32a1425246ecb34cba82a3bab447a432a7c` | untracked |

**The 167 hand-authored `CURRENT.md` lines are intact.** `git diff --numstat` reports `160 7` for
`CURRENT.md` (167 changed lines); the working file is **476 lines** against `HEAD`'s **323**, and
the preserved blob is **476 lines** and hashes to `b37ccea8…`. The prose is the P4 EP-cut narrative
(items 4–8: F2/EP-8, EP-3, EP-3 provenance hardening, EP-14, EP-1 read-half) plus the EP-1
write-path design note. The finalizer rewrites only the fenced status-block and would **not**
regenerate any of it.

### 5.4 Restoration

```
git show refs/preserve/p4-closure-prestate-0891d1a:docs/implementation/CURRENT.md > docs/implementation/CURRENT.md
```

— or materialize the whole state from tree `8c1fee16…`. Restoration needs no network and no branch
movement.

---

## 6. State of the repository at handoff — unchanged except for two additive artifacts

```
HEAD    0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e     (unchanged)
tree    a3e704645b8a06561d90cdb5f81288309ae51850     (unchanged)
branch  p4/adapter-containment-completion            (unchanged)
index   identical to HEAD                            (unchanged)
main / origin/main  152574e4…                        (unchanged)
```

`git status --porcelain` is byte-for-byte what it was at session start, plus this report. The two
tracked dirty files still hash to `b37ccea8…` and `f16c85b8…`.

Added by this session, both additive and neither in the candidate's tree:

1. `refs/preserve/p4-closure-prestate-0891d1a` — the preservation artifact (§5).
2. `docs/implementation/p4-closure-content-topology-determination.md` — this report, untracked,
   following the precedent of `p4-remediation-handoff.md`.

Removed by this session: the disposable `--no-local` clone and the throwaway index used for the §2.2
probes and the §5 capture. Nothing in the primary worktree was written by any probe.

---

## 7. Validation results (Step 6)

| Check | Result |
|---|---|
| Legal repository topology | `PRODUCING` — real guard, **1 passed** at `0891d1a` |
| Option A (stacked content commit) | ### **ILLEGAL** — real guard **FAILED**, *"stale beyond every legal state"* |
| Option B (amend) topologically legal | confirmed, **7 passed** — but authority-blocked (§3) |
| P4 remains NOT COMPLETE | `status: READY`, `execution_state: IN_PROGRESS`, **no** `acceptance_criteria` → contributes 0% |
| `canonical_finalizer` | **PENDING** — the finalizer has not run on this candidate |
| Acceptance block has exactly 14 criteria / 13 PASS | **not instantiated** — correctly, per §4; the frozen template in `PROGRAM-WEIGHTS.yaml` has 14 criteria totalling 100, and adjudication §F sets 13 PASS + `canonical_finalizer` PENDING = **97/100** |
| R-07 status | **OPEN — NOT CONTAINED**, mechanically consistent with `phase-0-baseline-manifest.yaml` (*"PENDING"*) and adjudication §G.5 |
| No implementation byte changed | tree `a3e70464…` unchanged; **zero** files written in the primary worktree |
| No production gate appeared | no change made; the empty `GateRegistry` population is untouched |
| Reports remain attributable to `0891d1a` | both preservation commits are children of `0891d1a`; both hashes re-verified |
| Residual risks remain recorded | unchanged in the candidate and in the reports; carried forward in §8 |
| No finalizer-owned file hand-edited | **none** — `CURRENT.md`, `SUITE-RESULT.json`, `BUILD-STATUS.yaml`, `IMPLEMENTATION-REGISTRY.yaml`, `GATE-RESULT.json` all untouched by this session |
| Protected refs unchanged | `main` / `origin/main` at `152574e4…`; all pre-existing `refs/preserve/*` unchanged |

Broader suites were **not** run: no content candidate exists to validate, and the candidate's own
evidence is already bound and independently reproduced by the adjudication.

**This session's probes are not an independent review of anything.** The accepted independent
re-review reviewed **`0891d1a`** and nothing else. No new candidate was created, so no new review
is owed — but equally, nothing here may be cited as a review.

---

## 8. Carry-forward register (unchanged, recorded, not discharged)

**Binding P12 precondition — RR-01.** `base_url` is **outside** `freight_operations.payload_hash()`'s
canonical set and **outside** `governed_write_route.approval_operation_mismatch`. Two docstrings
(`governed_write_registry._rebuild`'s integrity anchor and `governed_write_route`'s module
docstring) overclaim that every consequential value is covered by the signed hash. **Not
discharged.** Compounded by **F-09** (`_refuse_if_not_dark` reads
`if base_url and not _is_loopback_base_url(base_url)`, so an empty `base_url` skips the loopback
refusal entirely) and **F-08** (approved-field *values* unconstrained and interpolated into an LLM
task at P12). Must be discharged before any live writer is injected.

**AD-01** — `EFFECT-PATH-INVENTORY.yaml:86` and `LEGACY-DISPOSITION.md:156`, both **committed in the
candidate tree**, state that `run_action_callback_server.py` leaves `governed_write_provider`/
`governed_write_kernel` as `None`. Mechanically false for the **provider**: the real builder returns
provider **WIRED**, kernel `None`. The operative conclusion (route unreachable) is true. Prose fix
only, no code change. **Recorded and carried — deliberately not fixed here.**

**AD-02** — `scripts/finalizer_lock.py` is a new 188-line safety-critical module with **zero**
committed test coverage: no references under `eval/`, no nodes in `TEST-NODE-MANIFEST.json`, no
mutant in the 61-case battery. Verified sound 16/16 by both the reviewer and the adjudicator, but
only ad hoc. Directly load-bearing for the very next act. **Recorded and carried — deliberately not
fixed here.**

**Also retained:** RR-02 (stale handoff gate-result numbers), RR-03 (null-gate probe scans only
`src/`), RR-04 (mutant B34's label), RR-05 / F-07 (numeric self-contradictions in narrative), RR-06
(two guards use substring not AST), F-03 (`ReadOnlyBrowserUseRunner` `base_url` unvalidated), F-06
(route family is a denylist), F-10 (conditional workspace / message-ts binding, partially mitigated).

**Founder decision preserved unchanged:** production Action Class gate registration remains
**deferred to U8.1/P8**. `AC-CKPT-6-missing` stays `DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8`.
The production `GateRegistry` population is empty and must stay empty until P8.

---

## 9. What the finalizing session must do — and one correction to §G.7.2

The adjudication's §G.7 prerequisites stand unchanged. **One is understated and should be corrected
before it is relied on:**

> §G.7.2 says *"Two tracked files are dirty today."*

`finalize_status._step_dirty_tree` (`finalize_status.py:97–101`) runs plain
`git status --porcelain`, which in its default mode **includes untracked files**. It reports **7**
lines today, not 2:

```
 M docs/implementation/CURRENT.md
 M docs/implementation/GATE-RESULT.json
?? docs/implementation/p4-final-adjudication-report-0891d1a.md
?? docs/implementation/p4-final-adjudication-report-0891d1a.md.sha256
?? docs/implementation/p4-independent-rereview-report-0891d1a.md
?? docs/implementation/p4-independent-rereview-report-0891d1a.md.sha256
?? docs/implementation/p4-remediation-handoff.md
```

Plus this report, making 8. **The finalizer will refuse until the untracked files are dealt with
too** — clearing only the two tracked files is not sufficient. Both reports are already durably
preserved (their own `refs/preserve/*` commits, hashes re-verified in §1.2) and all 8 paths are
inside `refs/preserve/p4-closure-prestate-0891d1a`, so moving them aside is safe — **out of band,
never with `checkout` / `restore` / `stash` / `clean`.**

The ordered path to 100/100, from here:

1. Preserve the working-tree `CURRENT.md` prose out of band (or restore it from §5.4 afterwards);
   move the untracked reports aside. Leave `HEAD` at `0891d1a`.
2. Acquire `finalizer_lock` exclusively; confirm `current_owner()` was `None` first (**AD-02**: treat
   a refusal as authoritative; never reclaim on a missing log).
3. Run `finalize_status.py` against `0891d1a` / `a3e70464`.
4. Author, into the **one metadata commit**: the 14-criterion `acceptance_criteria` block from
   adjudication §F with `canonical_finalizer` = **PASS**; P4 `status: COMPLETE`; the R-07 lines in
   `CURRENT.md` and `BUILD-STATUS.yaml`; the residual register of §8; the restored `CURRENT.md`
   prose. Regenerate `BUILD-STATUS.yaml`'s derived block **after** the criteria are in place, or it
   records P4 at 0%.
5. Verify the metadata commit contains **only** `STATUS_METADATA_FILES` —
   `phase-0-baseline-manifest.yaml` **must not** be in it.
6. **Then, and only then**, a separate content commit marks R-07 CONTAINED with the mechanism named
   in `phase-0-baseline-manifest.yaml`. Until it lands, R-07 is not closed.
7. Print the full `NEYMA BUILD STATUS` block and **stop at the control boundary**. Do not begin P5.
   Integration to `main` is fast-forward-only under R-21 and is a separate founder-authorized act.

---

## 10. Scope of this document

This is a topology determination and a preservation record. It created no content candidate, ran no
finalizer, wrote no status metadata, marked no phase complete, marked R-07 neither contained nor
closed, modified no product code, no test, no mutation operator, no adapter and no policy,
remediated no finding, amended no candidate, moved no protected ref, pushed nothing, contacted no
external system and enabled no effect. The candidate's tree
`a3e704645b8a06561d90cdb5f81288309ae51850` is unchanged and still verifies.
