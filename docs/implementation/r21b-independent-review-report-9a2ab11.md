> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **Preserved as received.** The body below this banner is byte-identical to the artifact as
> delivered — blob `b268077e07b99689aa06109de5516791c0523cf2`, sha256
> `85f3c6873ff8ca57738ac8d31a961ff3eee06bee35ac838301417ed51ec0ccb1` — kept off-branch at
> `refs/preserve/r21b-independent-review-9a2ab11`. Adding this banner necessarily changes the
> worktree file's bytes; the preserved blob is the original. This is evidence of a past moment,
> not status.
>
> It is an **INDEPENDENT REVIEW, not an adjudication**: it scored no acceptance criterion, marked
> no phase complete, closed no risk and authorized no finalization.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** It reviewed candidate
> `9a2ab11b2228acbd2e3fef3b15d053bb77c7e7eb` (tree `a63a24975e2de710a4ac628ea01252052bc21a3f`) and
> returned **ACCEPT FOR SEPARATE TARGETED ADJUDICATION** with 8 nonblocking findings. That
> candidate **no longer exists**: it was amended in place — it had never been pushed to any remote
> ref — to carry the remediation this review asked for. Read its findings against the commit that
> carries this file, not against `9a2ab11`.
>
> ### **What changed after it was written.** **F-2** and **F-3**, which the reviewer recommended as
> hard landing conditions, are **APPLIED**, and each is now mutation-proved by a guard assertion
> that did not exist when this was written. **F-1** — the octopus content commit — is **CLOSED
> rather than recorded**: `topology_errors()` now bounds the content commit at **two** parents.
> **F-6** is closed as a side effect of that bound. **F-4**, **F-5** and **F-7** remain open as
> debt rows and are non-blocking (CLAUDE.md §13.3). **F-8**'s decoration test is replaced by one
> that can fail for its own property. The suite counts and the node manifest this review verified
> (3060 nodes) are therefore **superseded**: the tree it reviewed is not the tree that landed.
>
> ### **STILL OWED, and this document does not discharge it:** a separate targeted adjudication by
> a session outside every lineage, then exactly **one** canonical finalizer run.

---

# R-21b — FRESH INDEPENDENT REVIEW

**Verdict: ACCEPT FOR SEPARATE TARGETED ADJUDICATION.**

- **Candidate:** `9a2ab11b2228acbd2e3fef3b15d053bb77c7e7eb` · **tree `a63a24975e2de710a4ac628ea01252052bc21a3f`** (matches the reported tree; verified by `git rev-parse HEAD^{tree}`)
- **Baseline:** `d1b47c2` (status-metadata commit for `15a0fe5`) — single parent, verified
- **Reviewer lineage:** neither implemented, remediated, adjudicated nor landed this change or any prior P6 unit. This is an INDEPENDENT REVIEW, **not** an adjudication: it scores no acceptance criterion, marks no phase complete, closes no risk and authorizes no finalization.
- **Tier:** 3 by blast radius (test guard + governance documents; nothing under `src/` or `migrations/`), executed at Tier-2 rigor because the artifact under repair is the gate that decides whether the repository can ever reach `main`. Taking the higher tier once, and saying so (§13.2).
- **Working tree:** left byte-for-byte unchanged. `git status --porcelain` empty at start and at end; `HEAD^{tree}` still `a63a2497`. Every destructive experiment ran in disposable `git clone --no-hardlinks` copies under the session scratchpad. Nothing was committed, staged, amended, pushed; no finalizer was run; `refs/preserve/*` untouched.

**Findings: 8, all NONBLOCKING.** Two of them (F-2, F-3) I recommend the adjudicator convert into hard landing conditions; both are one-line document edits and neither requires touching the guard.

---

## 1. Root cause — re-derived independently, not read

The commit asserts the previous procedure was *literally unexecutable*. I did not take that on the commit message's word. I reproduced it twice, and I also proved the premise it rests on.

### 1.1 `origin/main`'s actual topology (verified, not assumed)

```
$ git log --first-parent --format='%h %p | %s' origin/main | head -5
152574e 97c311d 180fdcc | Merge pull request #3 from sheed17/p3/checkpoint-witness
97c311d 7ae4401 9cac877 | Merge pull request #2 from sheed17/p3/checkpoint-witness
7ae4401 1c7cecc c6e59c6 | Merge pull request #1 from sheed17/add-claude-github-actions-...
1c7cecc a8c6fde | yessir
a8c6fde  | first commit

$ git merge-base --is-ancestor 857cdc1 main && echo YES          -> YES
$ git rev-list --first-parent main | grep '^857cdc1'             -> (no match)
```

Confirmed exactly as described: the first-parent spine is a throwaway history (`a8c6fde` → `1c7cecc`), all real work — including the certified content commit `857cdc1cd` — arrived as a **second** parent, and the certified pair is an ancestor of `main` at **no first-parent depth**. The guard's `_build_defective_main` models this faithfully (it builds two spine merges where the real history has three; its assertion `parent_count(main_tip^) == 2` holds on the real tip, so the modelled shape is the real shape).

### 1.2 The premise: `finalize_status.py` validates before it writes

Read `scripts/finalize_status.py::finalize()`. Order is `_step_dirty_tree` → floor → deps → `_step_population` → `_step_run_suite` (refuses unless the **complete** canonical suite passes cleanly, and the complete suite contains both `test_status_reality.py` and `test_integration_topology.py`) → `_step_run_gate` → `_step_run_guards_and_gates` → **only then** `_write_status`. There is no `--trust`, no skip-suite and no filtered mode. The premise is true.

### 1.3 The trap, reproduced on the real repository

I proved the general claim first, by hand rather than by citation. Let `B` be the branch tip, `P` the recorded pair tip, and suppose `origin/main` is an ancestor of `B` but not of `P`, with `P` on `B`'s first-parent chain. Walk `B = c0 → c1 → … → ck = P`. There is an `i` where `main` is an ancestor of `c_i` but not of `c_{i+1}`; `c_i` therefore reaches `main` through a parent other than its first, so **`c_i` is a merge on the first-parent chain, strictly above the recorded commit.** The old predicate read the parent counts at first-parent depths 0 and 1, and `repo_state()` binds only when the recorded commit is at depth 0, 1 or 2 — so every position where the anchor bound put that merge at a depth the old predicate inspected. The claim is not rhetorical; it is forced.

Then I executed it against the live history in a disposable clone, merging `origin/main` into the branch at the real `FINALIZED` position `d1b47c2` and evaluating **both** predicates plus the real `repo_state()` at every first-parent position:

```
  5d099ab14 Integrate main (content commit)     state=PRODUCING  OLD=fail  NEW=PASS
  d1b47c200 Status metadata for the R-07 ...    state=FINALIZED  OLD=PASS  NEW=PASS
  15a0fe5c7 Disambiguate R-07's closure cell    state=PRODUCING  OLD=PASS  NEW=PASS
  dd9808e23 Status metadata for the P6-D11 ...  state=FINALIZED  OLD=PASS  NEW=PASS
  ...
  finalizer position AT/ABOVE integrating merge: OLD=False  NEW=True
```

Under the superseded predicate there is **no** position at or above the integrating merge where both guards pass — the anchor is trapped below it, exactly as claimed. Under the corrected predicate the integrating merge itself is a finalizer position.

I also executed the *other* documented route, the rebase-and-collapse of the old §3, on the real history:

```
$ git rebase --onto origin/main $(git merge-base d1b47c2 origin/main) reb
$ repo_state()
AssertionError: CURRENT.md records 15a0fe5c7 but HEAD is 93c3eec9d - the status
authority is stale beyond every legal state.
```

The recorded SHA is rewritten and the anchor is stale at every position, permanently. **Both halves of the diagnosis are real. Section A is confirmed.**

---

## 2. Is the corrected predicate sound?

### 2.1 It rejects the shapes the old one rejected that were genuinely defective

I constructed each shape rather than reading the tests.

| Shape | Old | New | How I verified |
|---|---|---|---|
| the real merge-button defect (`main` @ `152574e`, certified pair off the first-parent chain) | reject | **reject** | ran the real `repo_state()` + `topology_errors()` against a clone detached at the real `origin/main`; got `state='STALE'` and the chain-binding error |
| a **merge used as the metadata commit** | reject | **reject** | forged with `git commit-tree`, below |
| an **octopus metadata commit** | reject | **reject** | predicate unit test, mutation-proved (MU-A) |
| stacked unfinalized content commits | reject | **reject** | reproduced when I merged `origin/main` into the *unfinalized* content commit `9a2ab11`: `state=STALE`, both predicates fail |

### 2.2 The metadata-parent rule is genuinely not redundant with `repo_state()` — verified by my own forgery

I built the forgery myself on the repository's own history rather than trusting the shipped scenario: a side commit off the recorded content commit `15a0fe5` touching only `GATE-RESULT.json`, then

```
$ git commit-tree $(git rev-parse d1b47c2^{tree}) -p 15a0fe5 -p $SIDE -m "FORGED AS A MERGE"
$ repo_state()             -> FINALIZED          # accepted, cleanly
$ topology_errors(...)     -> ["the status-metadata commit (HEAD) is a merge (2 parents) ..."]
```

`repo_state()` alone **accepts** a merge occupying the metadata position; only the topology guard rejects it. The claim is true and the rule is load-bearing.

### 2.3 The relaxation — I attacked it, and it does admit something

This was the most important attack, and it partially succeeds. Constructed on the real history:

```
$ git checkout -B attack d1b47c2
$ git merge --no-ff evil2          # evil2 branches off 15a0fe5 and adds src/neyma_evil/backdoor.py
repo_state:             PRODUCING
NEW topology_errors:    []                      <- ACCEPTED
OLD linearity_errors:   ['HEAD is a merge']     <- was REJECTED
backdoor present in tree: yes
```

and the octopus variant, which also satisfies §3 Step 6's precondition:

```
$ git merge --no-ff origin/main evil2
HEAD parents:                    d1b47c2 152574e 29fbbf2   (three)
origin/main ancestor of HEAD?    YES
repo_state:                      PRODUCING
NEW topology_errors:             []             <- ACCEPTED
```

So an arbitrary third lineage can ride into the content commit while every mechanical precondition in the procedure passes. On top of that, the reviewer's most natural command is blind on this shape:

```
$ git show HEAD | wc -c              170     # combined diff: EMPTY patch
$ git show HEAD | grep -c backdoor   0
$ git diff HEAD^ HEAD | grep -c backdoor  2   # the first-parent diff DOES show it
```

**How I weigh this.** The topology guard was never the control for a content commit's *content*; a content commit is arbitrary code by definition, and the tree is re-certified by a full suite plus the clean-clone gate at finalizer time. What actually changed is the **reviewability** of the content commit: the old rule incidentally guaranteed a single-parent commit, so `git show` displayed its whole delta. That incidental guarantee is gone, and the procedure — which leans explicitly on "any content commit must still pass independent review" — never tells the reviewer to use the first-parent diff. It also never states that an **octopus** content commit is accepted, while it does state that an octopus *metadata* commit is rejected. That asymmetry is real and unrecorded.

I do **not** classify this blocking: no money, effect, authority, tenant, kernel or replay invariant is touched; the shape it admits was previously "rejected" only in a world where integration was impossible, so the old rule was a deadlock rather than a control; and the residual class is already named in §3 Forbidden and in R-21. See F-2 and F-3 for the two one-line corrections I recommend.

### 2.4 States

- **PRODUCING** — the live state at `9a2ab11`; the live guard passes and I reproduced the verdict independently.
- **FINALIZED** — exercised by my forgery and by the hermetic pair; correct.
- **STALE** — exercised against the real `origin/main`; correct.
- **BASELINE** — the predicate returns `[]` unconditionally and reads no parent count, where the old one still read `HEAD` and `HEAD^`. This is a real (if theoretical) widening. It is unreachable in practice: `BASELINE` requires `recorded == HEAD`, i.e. a commit whose own tree names its own hash. Recorded as F-6, non-blocking.

### 2.5 The exception handling in `_state_and_errors`

`except (AssertionError, FileNotFoundError, subprocess.CalledProcessError): state = "STALE"` is **safe for the live guard** — the live check `test_the_chain_binds_and_the_status_metadata_commit_is_not_a_merge` does *not* use this helper; it calls `repo_state()` directly and re-raises. The swallow is confined to the hermetic scenarios, and it cannot turn a rejection into an acceptance (every positive control asserts a *specific* state — `PRODUCING`, `FINALIZED` — which a swallowed exception cannot produce). It **can** make a negative control pass for the wrong reason; I proved that, see F-5.

---

## 3. Are the tests real? — my own mutations

Baseline in a disposable clone at `9a2ab11`: **19 passed**. Every mutation used in-memory save/restore, purged `__pycache__` before and after, and asserted byte-for-byte restoration (no `git checkout`/`restore`/`stash`/`clean`). All restores verified; clone left clean.

| # | Mutation (mine, not the candidate's table) | Result | Nodes that caught it |
|---|---|---|---|
| MU-A | `elif metadata_parents > 1` → `> 99` (drop the metadata-parent rule) | **CAUGHT** 4 failed | both `..._merge_used_as_the_metadata_commit_when_{finalized,producing}`, `..._octopus_metadata_commit`, `..._the_real_guards_reject_a_merge_used_as_the_metadata_commit` |
| MU-B | `if state not in METADATA_COMMIT_REV` → `if False` (drop chain binding) | **CAUGHT** 4 failed | `..._a_chain_that_does_not_bind`, `..._historical_defect...`, `..._rebase_and_collapse_state_is_illegal`, `..._finalizer_position_exists_above_a_merge...` |
| MU-C | `METADATA_COMMIT_REV["PRODUCING"] = "HEAD"` — my version of "restore the superseded content-parent read" | **CAUGHT** 2 failed | `..._legal_at_the_finalizer_time_state`, `..._finalizer_position_exists_above_a_merge...` |
| MU-D | drop the parentless-metadata rule | **CAUGHT** 1 failed | `..._a_parentless_metadata_commit` |
| MU-E | `topology_errors` returns `[]` unconditionally | **CAUGHT** 9 failed | all nine discriminating nodes |
| MU-F | R-21b row reverts to "NOTHING WAS RELAXED" | **CAUGHT** | `test_r21_is_recorded_with_a_mechanism_and_an_owner` |
| MU-G | R-21 drops "indistinguishable" | **CAUGHT** | same |
| MU-H | R-21 drops "allow ONLY rebase merging" | **CAUGHT** | same |
| MU-I | procedure drops the "Do NOT enable Require linear history" paragraph | **CAUGHT** | `test_the_procedure_records_the_executable_invariant` |
| MU-J | procedure flips to "the content commit may not be a merge" | **CAUGHT** | same |
| MU-K | procedure §2 drops "…and it has exactly one parent" | ***MISS*** | — |
| MU-K2 | §2 **and** §5 both drop it | **CAUGHT** | `test_the_procedure_records_the_executable_invariant` |
| VAC-1 | the hermetic `_finalize_like` stops writing the status block | **CAUGHT** 4 failed | the four positive controls — but see F-5 |

**On the MU-K MISS: my probe was defective, not the guard** (§9). I checked before concluding, and found the assertion is satisfied at two independent sites:

```
line  64: 'metadata commit** —\n> **and it has exactly one parent'
line 254: 'metadata commit has exactly one parent'
```

Removing only one leaves the other. Removing both is caught (MU-K2). No guard was weakened; I report the MISS and its resolution rather than deleting it.

**Faithfulness of the scenarios:** verified in §1.1. The hermetic `_build_defective_main` reproduces the real defect and its own docstring records that an earlier draft merged the side branch *onto* the certified pair — which leaves the chain intact and reproduces nothing. I confirmed that trap is real: when I merged `origin/main` into the branch's *unfinalized* content commit rather than its metadata commit, the state was `STALE` rather than `PRODUCING`, i.e. the shape of the merge matters and the scenario is sensitive to it.

---

## 4. Documentation accuracy

The corrected §2 invariant, the §3 procedure, the §5 relaxation table and PROGRESS-PROTOCOL §10 all describe the predicate the guard actually implements, including the honest and unusual admission in §2 that the first-parent proviso is **not** enforced by `topology_errors()` at all but bites through `repo_state()` at finalizer time — I verified that statement is exactly right. A repo-wide grep found **no** surviving live statement of the superseded rule (`no merge commit may sit above a certified content commit`, `neither HEAD nor HEAD^`, `linearity_errors`) outside the guard's own historical docstring, and no dangling reference to any deleted test name.

The prior round's two corrections (R-21 must not present the guard as a complete control; R-21b must not claim nothing was relaxed) are present, and each is mutation-proved (MU-F, MU-G, MU-H). **But one equivalent overstatement was newly introduced elsewhere** — see F-2 — and two pre-existing inaccuracies are now load-bearing — see F-3, F-4.

---

## 5. Scope and safety

| Check | Result |
|---|---|
| files under `src/` or `migrations/` | **none** |
| product / kernel / effect-boundary / P6-D11 implementation touched | **none**; the eight changed files are 5 documents + 3 test modules |
| status block in `CURRENT.md` hand-edited | **no** — the diff touches no `content_commit` / `content_tree` / `suite_*` line; the block is still the finalizer's |
| `SUITE-RESULT.json` / `GATE-RESULT.json` / `BUILD-STATUS.yaml` touched | **no** |
| `main` / `origin/main` | both still `152574e4f4f2969468c9d31b1e705188896175b5` |
| `refs/preserve/*` | 88 refs, all resolve (`git cat-file -e` on each) |
| commit shape | single-parent: `9a2ab11 parents=[d1b47c2]` |
| resulting `repo_state()` | `PRODUCING` — legal; recorded `15a0fe5` at `HEAD^^`, `d1b47c2` a pure metadata commit at `HEAD^` |
| `M3` begun | **no** |

---

## 6. Test results — verified, not accepted

I ran the canonical suite myself on the clean tree at `9a2ab11`:

```
$ .venv/bin/python -m pytest -c pytest-canonical.ini -q
20 failed, 3039 passed, 1 skipped, 5 warnings in 421.75s (0:07:01)
```

**3039 / 20 / 1 = 3060.** This reconciles the commit message's `3037 / 20 / 3`: the two extra skips are `test_status_reality`'s dirty-tree skips, which the authoring session incurred on a dirty tree and which `APPROVED-SKIPS.yaml` explicitly forbids in a canonical run; on the clean committed tree they execute and pass. The single remaining skip is the one approved skip, `test_phase0_guard_integrity.py::test_the_red_by_design_cases_are_strict_xfails`.

**The 20 failures.** All 20 are in `test_action_callback.py` (19) and `test_p4_deployed_governed_route.py` (1). I reproduced them on a **pristine clone detached at the parent commit `d1b47c2`**, with none of this change present:

```
$ git checkout --detach d1b47c2 && pytest test_action_callback.py test_p4_deployed_governed_route.py -q
20 failed, 41 passed
$ diff <(sorted failures @ 9a2ab11) <(sorted failures @ d1b47c2)   ->  IDENTICAL SETS (20/20)
```

Cause confirmed as environmental, not asserted: the traceback bottoms out in `socketserver.TCPServer.server_bind` — this host forbids `socket.bind`. **Pre-existing and environmental: verified.**

**Node manifest.** Verified by identity, not by count:

```
node_count 3060, len(node_ids) 3060, unique 3060
manifest_sha256 recomputes: True
config_sha256 matches pytest-canonical.ini: True
live collected: 3060 ; in-manifest-not-live: 0 ; live-not-in-manifest: 0
EXACT SET MATCH: True
```

The manifest moved `3052 → 3060` (+16 / −8), every changed node in `test_integration_topology.py`. Matches the claim.

**Consequence worth stating plainly:** because the suite is red on this host, `finalize_status.py` will refuse here. The one canonical finalizer this commit owes must run from a host that permits `socket.bind` — which is the standing condition `CURRENT.md` already records, not a new one.

---

## 7. Did the change do anything beyond its stated scope?

**(a) The `CURRENT.md` "a P6-D11 finalizer is owed" correction — factually CORRECT, and I verified it rather than reading it.** `dd9808e` has a single parent `fa6481e`, touches exactly five `STATUS_METADATA_FILES` and nothing else, and its receipts bind `fa6481eb2e47f6f4` / tree `bd3aa1b500c9ff6c` at 3051/0/1 with `clean_clone_gate passed: true`. I recomputed `payload_sha256` for both receipts at `dd9808e`, `d1b47c2` and `9a2ab11`: **all six recompute exactly**, so none was hand-edited. The superseded claim was therefore an active false instruction that would have sent a fresh session to run a finalizer nobody owes — the same defect class the P6-D11 landing itself corrected (its F-1 / A-2). The superseded wording is retained per §5 rule 20. **In scope and correct.**

**(b) The `test_status_reality.py` remediation-hint change — CORRECT.** The old message named `scripts/update_current_status.py`; I read that file and it is a **refusing shim** superseded at U-HANDOFF-1C (`REFUSED: scripts/update_current_status.py is superseded`). Pointing an operator at it was actively wrong. The replacement names `finalize_status.py` and the R-21b one-way-door. Small, in-scope, and it changes no behaviour — only the message. It is, however, **incomplete**: see F-7.

Both edits share the surface and the risk story of the R-21b repair (finalizer topology, the same guard file, the same false-instruction class), so batching them here is consistent with §13.5 rather than a scope leak.

---

## 8. Findings

### F-1 — the relaxation admits a merge, and an **octopus**, content commit carrying an arbitrary lineage. **NONBLOCKING.**
Constructed and reproduced (§2.3): a content commit with parents `(metadata, origin/main, arbitrary)` binds as `PRODUCING`, returns no topology error, satisfies §3 Step 6's `--is-ancestor` precondition, and renders as an **empty patch** under `git show`. The old predicate rejected it. **Non-blocking** because no safety invariant is touched, the tree is still re-certified by the full suite and the clean-clone gate at finalizer time, and the rule it replaces was a deadlock rather than a usable control. Recorded, with F-2 and F-3 as the cheap mitigations.

### F-2 — a NEW overstatement of exactly the class the prior round removed. **NONBLOCKING; recommend as a landing condition.**
`integration-topology-procedure.md` line 57 (added by this commit) says the rule was corrected *"**without** relaxing anything it protects"*. §5 of the same document says *"**The relaxation is confined to ONE thing:** the CONTENT commit's parent count is no longer read"* and its table moves a shape from `REJECTED` to `MAY be ACCEPTED`. `test_r21_is_recorded_with_a_mechanism_and_an_owner` forbids the equivalent sentence in the **register** but nothing forbids it in the **procedure**, and I confirmed by grep that this is the only surviving instance. It is a one-line edit; the phrase should scope itself the way §5 does. Non-blocking because §2 immediately below states the opposite in bold, so a reader is corrected within twenty lines.

### F-3 — the procedure never tells a reviewer how to review a merge content commit. **NONBLOCKING; recommend as a landing condition.**
§3 Step 3 says *"independent review … against **this** content commit"*, and §3 Forbidden leans on *"any content commit must still pass independent review"* as the control for the class the guard can no longer detect. On a merge content commit the default review command shows nothing (`git show HEAD` → 170 bytes, zero content; `git diff HEAD^ HEAD` → the full delta). One sentence in Step 3 naming the first-parent diff restores the control the relaxation leans on. Non-blocking because integration has not occurred and is a separate founder-authorized act.

### F-4 — §1's enumeration of legal `HEAD` positions omits `PRODUCING` and mislabels the content commit's state. **NONBLOCKING.**
Lines 21–24 (pre-existing, untouched) say `HEAD` may be *"the certified content commit itself (state `BASELINE`)"* or *"the metadata commit (state `FINALIZED`)"*, then reference `HEAD^^` — which only `PRODUCING` uses. After R-21b this is load-bearing: Step 2 deliberately leaves `HEAD` a **new content commit in `PRODUCING`**, a position §1 does not list and names wrongly. Inherited rather than introduced, hence non-blocking, but it now contradicts the procedure's own step.

### F-5 — two negative controls can pass for the wrong reason. **NONBLOCKING; proved, not theorised.**
Under VAC-1 (the scenario builder stops writing the status block) `test_the_scenario_reproduces_the_historical_defect_before_it_repairs_it` and `test_the_documented_rebase_and_collapse_state_is_illegal` **still passed** — `_state_and_errors` maps `FileNotFoundError` to `"STALE"`, which is the string they assert. Neither can distinguish *"correctly rejected"* from *"the scenario was never built"*. Non-blocking because the module's four positive controls failed loudly on the same mutant, so a broken builder cannot pass the file; the sharper form would assert on the rejection **reason**, as `..._merge_used_as_the_metadata_commit` already does with its `any("merge" in e …)` check.

### F-6 — `BASELINE` is now wholly unconstrained. **NONBLOCKING.**
`METADATA_COMMIT_REV["BASELINE"] = None` makes `topology_errors` return `[]` without reading any parent count; the old predicate still read `HEAD` and `HEAD^` there. Unreachable in practice (`recorded == HEAD` requires a commit whose tree contains its own hash), so it is a widening with no constructible instance.

### F-7 — the superseded-shim correction is incomplete within its own file. **NONBLOCKING.**
`test_status_reality.py` line 14 still reads *"`scripts/update_current_status.py` records status ONLY from a valid artifact"* — the same stale claim the commit corrected 78 lines below, in the same module docstring that describes the corrected design. Cosmetic; record and move on (§13.3), or fix in the same breath as F-2.

### F-8 — one test cannot fail for the property it names. **NONBLOCKING.**
`test_the_predicate_no_longer_constrains_the_content_commits_parent_count` asserts only `topology_errors("FINALIZED", 1) == []`, which is byte-identical in effect to `test_the_predicate_accepts_a_single_parent_metadata_commit`. `topology_errors` has no content-parent parameter, so no reintroduction of that rule can make this node red — and MU-C, which *did* effectively reintroduce it, left this test **passing** while two others failed. It is documentation with a test's name (§9: "a guard never seen to fail is a decoration"). Non-blocking: the property it names is genuinely covered, by the hermetic finalizer-time and anchor-reachability tests.

---

## 9. What could have failed, and what I could not verify

**Could have failed and did not:** the root-cause claim (I tried to find a finalizer position at or above the integrating merge under the old predicate on the real history, and there is none); the non-redundancy of the metadata-parent rule (I forged the merge metadata commit myself with `commit-tree` and `repo_state()` accepted it); the claim that the new guard still rejects the real `main` (it does, against the actual `152574e`); every one of my thirteen mutations (twelve caught, one MISS traced to my own probe and then caught when corrected); the 3039/20/1 counts; the identity of the 20 failures at the parent commit; the exact-set node-manifest match; the `payload_sha256` of all six receipts; and every scope and safety check in §5.

**What I did not verify:**
- **I did not run `scripts/finalize_status.py`, and no finalizer has run on this commit.** It cannot run on this host — the suite is red on 20 socket-bound tests. I therefore verified the finalizer's *ordering* by reading it, not by executing it, and I take the "validates before it writes" premise from that read plus the receipt hashes.
- **I did not run the clean-clone gate.** Same reason; it executes the same suite.
- The pristine-clone reproduction of the 20 failures used the real repository's `.venv`. `pytest-canonical.ini`'s `pythonpath = src` puts the *clone's* `src` first, and no `src/` file differs between `d1b47c2` and `9a2ab11`, so I consider the reproduction sound — but it is not a from-scratch venv.
- I did not assess the GitHub repository settings (`allow only rebase merging`, `Require linear history`). Those are the named control for the class F-1 describes and they live outside this repository; I can neither confirm nor set them.
- I did not attempt to determine whether the full canonical suite would *catch* the smuggled `src/neyma_evil/backdoor.py` of §2.3; my judgement in F-1 assumes it would not, which is the conservative assumption.
- I reviewed the commit message's claims but treated none as evidence; where my numbers differ from it (3037/20/3 vs 3039/20/1) I reconciled the difference in §6 rather than adopting either.

**Reviewer limitations.** I am a single session with no conversation history; I read the canon named in the task and the eight changed files, and I re-derived every material claim mechanically. I did not review the repository's prior R-21 history beyond what the changed documents assert, and I did not evaluate whether integration to `main` should proceed — that is a founder-authorized act and remains OPEN.

---

## 10. Recommendation

**ACCEPT FOR SEPARATE TARGETED ADJUDICATION.** The diagnosed defect is real and I reproduced it two ways on the real history; the corrected predicate is a genuine strengthening on the class that actually broke `main` (it rejects `152574e` on a property the old parent-count rule only ever caught by proxy) and its retained rules are mutation-proved by my own battery, not the candidate's. The one real weakening is bounded, reproducible, and already partly recorded by the change itself.

I recommend the adjudicator consider **F-2** and **F-3** as hard landing conditions — together they are two sentences in `integration-topology-procedure.md`, they require no guard change and no re-review of the predicate, and they close the gap between what the document claims and what the guard can do. **F-1 and F-4 through F-8 are debt rows and the debt row is the complete deliverable (§13.3).**

This commit still owes, in order: a separate targeted adjudication by a session outside every lineage, and then **exactly one** canonical finalizer run from a host that permits `socket.bind`. Until that finalizer runs, the repository is in `PRODUCING` and `M3` may not begin.
