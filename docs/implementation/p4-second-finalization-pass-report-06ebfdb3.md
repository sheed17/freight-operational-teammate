# RECONSTRUCTED SECOND-FINALIZATION EVIDENCE REPORT — metadata commit `06ebfdb3`

> ### **THIS IS A RECONSTRUCTION, NOT AN EXECUTION RECORD.**
> This report was authored **after** the second finalizer had already completed, by a **fresh
> designated attestation session** that did **not** run it. The session that wrote this document
> did not implement P4, did not remediate it, did not author the closure candidate `42ea24c`, did
> not conduct the targeted review or the targeted adjudication, and **did not execute
> `scripts/finalize_status.py`**. It ran no finalizer, no canonical suite and no clean-clone gate.
> Every statement below is reconstructed from durable machine-verifiable evidence that already
> existed on disk, and every fact carries an explicit evidence class.

---

## A. Attestation-session independence statement

This session's entire mandate was to **reconstruct and attest to an already-completed run**. It was
prohibited from, and did not: modify product implementation, tests, status facts, manifests,
canonical documentation, commits, branches, the index or tracked worktree files; run
`finalize_status.py`; rerun or simulate the second finalizer; begin the R-07 closure cycle or P5;
push, merge, deploy or enable effects; or use `checkout`, `restore`, `stash`, `clean`, `gc` or
`prune`.

The original second-finalizer run was executed by a **different, earlier session**, identified
below from its surviving run artifacts. This attestation session is not that session and inherits
none of its claims: every value reproduced here was **independently recomputed or re-derived** from
Git objects, canonical receipts and on-disk run artifacts. Where a value could only be recovered
from a scratchpad or session artifact, it is labelled as such and reconciled against Git before
being reported. Where nothing durable survives, this report says so rather than guessing.

**Evidence classes used throughout:**

| Class | Meaning |
|---|---|
| **[GIT]** | Directly proven by Git object identity — recomputed in this session |
| **[RECEIPT]** | Directly proven by a canonical receipt whose payload hash this session recomputed |
| **[RUN-ARTIFACT]** | Directly proven by a surviving lock/run artifact written during the run |
| **[SCRATCHPAD]** | Corroborated by surviving scratchpad/session evidence, reconciled with Git |
| **[UNAVAILABLE]** | Not durably recoverable — explicitly stated as such |

---

## B. Exact candidate and metadata identities

| Fact | Value | Class |
|---|---|---|
| Product branch | `p4/adapter-containment-completion` | **[GIT]** |
| Metadata commit (HEAD) | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` | **[GIT]** |
| Metadata tree | `e3f0c59e36269d541b27d8be8dac8de68234e4fb` | **[GIT]** |
| Metadata parent | `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` | **[GIT]** |
| Parent count | **1 — not a merge** (`git cat-file -p HEAD` yields exactly one `parent` line) | **[GIT]** |
| Candidate commit | `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` | **[GIT]** |
| Candidate tree | `1e2bba791a5c2c77194d1df9ce16e1d9df84315a` | **[GIT]** |
| Candidate parent | `86306d5c4d866baf1a7fb6e4bd8220ce31017acd` (the first-pass metadata commit) | **[GIT]** |
| Candidate subject | `Record P4 COMPLETE at 14/14 and hand the selector to P5` | **[GIT]** |
| Candidate author date | `2026-08-04T18:01:31-07:00` | **[GIT]** |
| Metadata commit date | `2026-08-04 20:08:57 -0700` (`1785899337 -0700`) | **[GIT]** |
| Author / committer | `sheed17 <rsamady2@gmail.com>` | **[GIT]** |

**Proof candidate `42ea24c` was not amended** — **[GIT]** + **[RUN-ARTIFACT]**. The pre-run ref
snapshot `refs-before.txt`, captured by the executing session before the finalizer launched,
records `refs/heads/p4/adapter-containment-completion 42ea24cfc76fac19406e7eaa44b695b8d032b3aa`.
The current `HEAD^` is that **same object hash**. A commit hash covers the whole commit object, so
an amend would necessarily have produced a different hash and orphaned the original. The candidate
is byte-identical before and after the run. Independently, `refs/preserve/p4-second-finalization-prestate-42ea24c`
(`d2ae8f474d1238d6e9f9e69c84d1f17d20afa0c7`) has parent exactly `42ea24cfc76fac19406e7eaa44b695b8d032b3aa`,
pinning that object into the graph from a second direction.

---

## C. Exact finalizer-generated changed paths

`git diff --name-status HEAD^ HEAD` — **[GIT]**, recomputed in this session:

```
M	docs/implementation/BUILD-STATUS.yaml
M	docs/implementation/CURRENT.md
M	docs/implementation/GATE-RESULT.json
M	docs/implementation/IMPLEMENTATION-REGISTRY.yaml
M	docs/implementation/SUITE-RESULT.json
```

```
 docs/implementation/BUILD-STATUS.yaml            |  4 ++--
 docs/implementation/CURRENT.md                   |  4 ++--
 docs/implementation/GATE-RESULT.json             |  8 ++++----
 docs/implementation/IMPLEMENTATION-REGISTRY.yaml |  4 ++--
 docs/implementation/SUITE-RESULT.json            | 10 +++++-----
 5 files changed, 15 insertions(+), 15 deletions(-)
```

**Five paths changed. All five are members of `STATUS_METADATA_FILES`.** — **[GIT]**

### C.1 A precision correction on "the five declared `STATUS_METADATA_FILES`"

The tasking for this report, and the metadata commit message itself, both describe the commit as
containing "the five authorized `STATUS_METADATA_FILES`". That phrasing is **imprecise**, and this
attestation will not copy it forward unverified. The actual declaration at
`scripts/finalize_status.py:70-81` contains **ten** paths — **[GIT]**:

```python
STATUS_METADATA_FILES = (
    "docs/implementation/SUITE-RESULT.json",
    "docs/implementation/GATE-RESULT.json",
    "docs/implementation/CURRENT.md",
    "docs/implementation/IMPLEMENTATION-REGISTRY.yaml",
    "docs/implementation/u-handoff-1a-control-correction-review.md",
    "docs/implementation/u-handoff-1b-clean-clone-correction-review.md",
    "docs/implementation/u-handoff-1c-false-green-and-discovery-correction-review.md",
    "docs/implementation/u-handoff-1d-final-adjudication-review.md",
    "docs/implementation/u-rebaseline-1-product-production-review.md",
    "docs/implementation/BUILD-STATUS.yaml",
)
```

The finalizer's own closing instruction, preserved verbatim in the run log, staged **all ten**
— **[RUN-ARTIFACT]**:

```
next: commit ONLY the status files as the single status-metadata commit:
  git add docs/implementation/SUITE-RESULT.json docs/implementation/GATE-RESULT.json
  docs/implementation/CURRENT.md docs/implementation/IMPLEMENTATION-REGISTRY.yaml
  docs/implementation/u-handoff-1a-control-correction-review.md
  docs/implementation/u-handoff-1b-clean-clone-correction-review.md
  docs/implementation/u-handoff-1c-false-green-and-discovery-correction-review.md
  docs/implementation/u-handoff-1d-final-adjudication-review.md
  docs/implementation/u-rebaseline-1-product-production-review.md
  docs/implementation/BUILD-STATUS.yaml
```

**Why only five appear in the diff, proven mechanically.** The five review documents are touched by
`_write_status()` only through placeholder substitution — it replaces the literal tokens
`CONTENT_COMMIT_INSERTED_BY_FINALIZER`, `CONTENT_TREE_INSERTED_BY_FINALIZER` and
`SUITE_INSERTED_BY_FINALIZER`. Those tokens were already consumed by the **first** finalization
pass. This session confirms **zero** occurrences of `INSERTED_BY_FINALIZER` remain in any of the
five review files — **[GIT]**. The substitution was therefore a no-op, the files were rewritten
byte-identically, and Git recorded no change: `git diff --name-only HEAD^ HEAD --` restricted to
those five paths returns **0** entries — **[GIT]**.

So the accurate statement, which this report adopts, is: **the commit's changed paths are a strict
subset of the ten declared `STATUS_METADATA_FILES`; exactly five of the ten differed, and the other
five were staged but byte-unchanged for a mechanically demonstrable reason.** The commit is
correctly scoped either way — nothing outside `STATUS_METADATA_FILES` was touched.

### C.2 Proof no source, test, script, adapter, policy, manifest or production gate changed

**[GIT]** — The complete `HEAD^..HEAD` change set is the five paths above. Every one lives under
`docs/implementation/`. There is no path under `src/`, `eval/`, `tests/`, `scripts/`, no ADR, no
policy document and no acceptance-criteria file in the diff.

Specifically verified:

- **`docs/implementation/phase-0-baseline-manifest.yaml`** — tracked, and **not** in the change set
  (`git diff --name-only HEAD^ HEAD -- <path>` returns 0 entries) — **[GIT]**. It is present on disk
  (50,589 bytes). It is deliberately absent from the commit because it is **not** a
  `STATUS_METADATA_FILE`; the R-07 `CONTAINED` record belongs there and requires its own separate
  content commit.
- **Production `GateRegistry`** — unchanged, because no source file changed at all — **[GIT]**. Its
  state is examined in §G.
- **P4 acceptance block** — unchanged in substance: `finalize_status.py` contains no code path that
  writes `acceptance_criteria`; it writes only the `CURRENT.md` status-block, the registry
  `baseline_commit` / `validated_tree` / `suite` meta fields, and the `BUILD-STATUS.yaml`
  derived-block — **[GIT]**, by reading the script. The 14/14 PASS block summing to 100 is verified
  independently in §G.

---

## D. Canonical-suite and clean-clone evidence

### D.1 The finalizer's own recovered stdout — **[RUN-ARTIFACT]**

The complete original standard output of the second-finalizer process survives on disk at
`…/ebca17df-78cb-4dcc-bcc5-67a456950818/scratchpad/sf/finalizer.log` (21 lines, mtime
`2026-08-04 20:07 -0700`), written by the shell redirection that launched the run. Reproduced
verbatim:

```
clean-clone gate: /var/folders/b0/6h_5p8v179n_z4v6ngf9n_540000gn/T/neyma-clean-clone-a050fg09/clone (committed 42ea24cfc)
--- clone committed state (exit 0)
--- no active_workspace in clone: OK
--- python floor (host) (exit 0)
--- fresh venv (exit 0)
--- python floor (venv) (exit 0)
--- install declared deps only (exit 0)
--- complete canonical suite (clean clone) (exit 0)
    clean-clone: {'passed': 1961, 'failed': 0, 'skipped': 1, 'collected': 1962}
--- control guards (clean clone) (exit 0)
--- AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001 (exit 0)

CLEAN-CLONE GATE: PASS
OK: Python 3.14 satisfies >= 3.11
finalizing 42ea24cfc - executing the complete canonical suite ...
  suite: 1961/0/1 - executing clean-clone gate ...
  gate: PASS - executing control guards and AC gates ...
  progress: BUILD-STATUS.yaml derived and validated
status finalized from EXECUTED results: 1961/0/1 on 42ea24cfc (1e2bba791)
next: commit ONLY the status files as the single status-metadata commit:
  [ten STATUS_METADATA_FILES, quoted in full in §C.1]
```

### D.2 Canonical suite — `SUITE-RESULT.json` — **[RECEIPT]**

| Field | Value |
|---|---|
| `command` | `.venv/bin/python -m pytest -c pytest-canonical.ini -v` |
| `collected` | **1962** |
| `passed` | **1961** |
| `failed` | **0** |
| `skipped` | **1** |
| `deselected` | 0 |
| `exit_status` | **0** |
| `commit` | `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` |
| `tree` | `1e2bba791a5c2c77194d1df9ce16e1d9df84315a` |
| `completed_at` | `2026-08-05T03:00:36.270642+00:00` |
| `duration_seconds` | 387.1 |
| `platform` | `macOS-15.1.1-arm64-arm-64bit-Mach-O` |
| `python_version` | `3.14.4` |
| `rogue_nodes` | `[]` |
| `unexecuted_nodes` | `[]` |
| `xfail_nodes` | `[]` |
| `skipped_nodes` | `["eval/tests/test_phase0_guard_integrity.py::test_the_red_by_design_cases_are_strict_xfails"]` |

The single skip is named and node-identified — it is the one conditionally justified skip, not an
anonymous count. `rogue_nodes` and `unexecuted_nodes` are both empty, so the executed population
matched `TEST-NODE-MANIFEST.json` by identity.

**The suite receipt is bound to the candidate, not to the metadata commit** — `commit` /
`tree` are `42ea24c` / `1e2bba79`, exactly the content commit the finalizer ran against. This is
the two-commit convention working correctly: a commit cannot contain its own hash.

### D.3 Clean-clone gate — `GATE-RESULT.json` — **[RECEIPT]**

| Field | Value |
|---|---|
| `gate` | `clean_clone_gate` |
| `passed` | **`true`** |
| `reason` | `""` (empty — no qualification) |
| `clean_clone_counts` | `{passed: 1961, failed: 0, skipped: 1, collected: 1962}` |
| `commit` | `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` |
| `tree` | `1e2bba791a5c2c77194d1df9ce16e1d9df84315a` |
| `completed_at` | `2026-08-05T03:07:44.647067+00:00` |

All **nine** steps recorded `exit_status: 0` — **[RECEIPT]**:

1. clone committed state · 2. python floor (host) · 3. fresh venv · 4. python floor (venv) ·
5. install declared deps only · 6. complete canonical suite (clean clone) · 7. control guards
(clean clone) · 8. `AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001` · 9. clone tree still clean

**Cross-corroboration:** the clean-clone counts in the receipt (`1961/0/1/1962`) match the counts
independently printed into `finalizer.log` during the run (`{'passed': 1961, 'failed': 0,
'skipped': 1, 'collected': 1962}`) — two independently-written artifacts agreeing exactly.

### D.4 Shared integrity anchors

Both receipts carry **identical** anchors, proving they describe the same tree under the same
harness — **[RECEIPT]**:

| Anchor | Value |
|---|---|
| `config_sha256` | `22f4294195baec814e441c94ed34d5e20fd2f3975bcece35fd0a65962f255a2e` |
| node manifest sha256 | `44b5457125e79e3dee21768684823f2ab7ab03c362a11577974ccd38d39dfd40` |
| `runner_sha256` | `75b924e9f39821eaf4a9796ea81b24c8240ef4d228e781c95f627230586295eb` |

*(the manifest anchor is keyed `manifest_sha256` in the suite receipt and `node_manifest_sha256`
in the gate receipt; the values are identical.)*

---

## E. Receipt verification and payload hashes

This session **independently recomputed** both payload hashes using the repository's own
`scripts/suite_result.py:payload_hash()` — `sha256(json.dumps({k:v for k,v in data.items() if k !=
"payload_sha256"}, sort_keys=True))` — and compared against the stored values. **[RECEIPT]**

| Receipt | Stored `payload_sha256` | Recomputed | Verdict |
|---|---|---|---|
| `SUITE-RESULT.json` | `309b7ea07ef6fa24aff04dd63ced9924724a6bc8d9d02527c79715d94d6a834e` | `309b7ea07ef6fa24aff04dd63ced9924724a6bc8d9d02527c79715d94d6a834e` | **MATCH** |
| `GATE-RESULT.json` | `fddf651c138073c01086b2b48c06db5025a27b566e0a87ac1268d049c60e762f` | `fddf651c138073c01086b2b48c06db5025a27b566e0a87ac1268d049c60e762f` | **MATCH** |

Neither receipt has been edited since the finalizer wrote it.

**Trust model, restated honestly.** Per `scripts/finalize_status.py`'s own module docstring, these
receipts are **generated evidence of the finalizer process's own observations, not independent
cryptographic proof**. No in-repository secret exists, so a local forger with write access could in
principle produce a consistent set. This report does not claim otherwise. What raises confidence
above a bare receipt is the **architecture**: the finalizer *deletes* any pre-existing
`SUITE-RESULT.json` and `GATE-RESULT.json` before running, so a pre-planted receipt is never read
and never consumed; evidence files are strictly **outputs** of the run. That property is verified
by reading the script, and it is corroborated here by a fully independent artifact — the run log in
§D.1, written by shell redirection outside the finalizer's control, which reports the same counts.

---

## F. Lock and single-finalizer evidence

### F.1 Exact invocation — **[SCRATCHPAD]**, reconciled with **[RUN-ARTIFACT]** and **[GIT]**

The launching command survives verbatim in the executing session's transcript:

| Fact | Value |
|---|---|
| **Finalizer command** | `.venv/bin/python scripts/finalize_status.py` |
| **Working directory** | `/Users/sammyfammy/Desktop/freight-logistics-operational-teammate` |
| **Arguments** | none — the script accepts none beyond `--help`; everything runs, every time |
| **Launch mode** | backgrounded shell job, stdout+stderr redirected to `sf/finalizer.log`, `$?` captured to `sf/finalizer-rc.txt` |
| **Executing session** | `ebca17df-78cb-4dcc-bcc5-67a456950818` (product-driver project) |

This reconciles with Git and the run artifacts: the log it produced names candidate `42ea24cfc`
and tree `1e2bba791`, which are exactly `HEAD^` and its tree.

### F.2 Timing — **[RUN-ARTIFACT]**

| Fact | Value | Source |
|---|---|---|
| **Start time** | `2026-08-05T02:54:05Z` (= `2026-08-04 19:54:05 -0700`) | `sf/finalizer-start.txt` |
| **End time** | `2026-08-05T03:07:58Z` (= `2026-08-04 20:07:58 -0700`) | `sf/finalizer-end.txt` |
| **Duration** | **833 s = 13 m 53 s** | computed from the two above |
| **Exit code** | **0** | `sf/finalizer-rc.txt` (contents: `0`) |

**Internal consistency of the timeline** — every independent clock agrees:

| Time (UTC) | Event | Source |
|---|---|---|
| `02:54:05` | finalizer start; lock acquired | `finalizer-start.txt`; lock record `started_at_iso` |
| `03:00:36` | canonical suite completed (387.1 s run) | `SUITE-RESULT.json` **[RECEIPT]** |
| `03:07:44` | clean-clone gate completed | `GATE-RESULT.json` **[RECEIPT]** |
| `03:07:57` | **lock file truncated → lock released** | `.git/neyma-finalizer.lock` mtime **[RUN-ARTIFACT]** |
| `03:07:58` | finalizer process exited, rc captured | `finalizer-end.txt` **[RUN-ARTIFACT]** |
| `03:08:57` | metadata commit `06ebfdb3` created | commit timestamp `1785899337` **[GIT]** |

The suite's own `duration_seconds` (387.1) places its start at ≈`02:54:09Z`, four seconds after
lock acquisition — consistent with the pre-suite steps (dirty-tree refusal, HEAD resolution, Python
floor, dependency import check, population identity check, receipt deletion).

### F.3 Lock path, owner and exclusivity

| Fact | Value | Class |
|---|---|---|
| **Lock path** | `/Users/sammyfammy/Desktop/freight-logistics-operational-teammate/.git/neyma-finalizer.lock` | **[RUN-ARTIFACT]** — confirmed by calling `finalizer_lock.lock_path()` in this session |
| **Lock mechanism** | non-blocking `fcntl.flock(LOCK_EX \| LOCK_NB)` | **[GIT]** — read from `scripts/finalizer_lock.py` |
| **Lock-owner PID** | **16381** | **[SCRATCHPAD]** — see F.4 |
| `started_at` | `1785898445.574404` → `2026-08-04T19:54:05-0700` | **[SCRATCHPAD]** |
| `repository` | `/Users/sammyfammy/Desktop/freight-logistics-operational-teammate` | **[SCRATCHPAD]** |
| `target_commit` | `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` | **[SCRATCHPAD]** |
| `host` | `Sammys-MacBook-Air.local` | **[SCRATCHPAD]** |
| `run_id` / `session_id` | **empty strings** — neither `NEYMA_RUN_ID` nor `NEYMA_SESSION_ID` was set | **[SCRATCHPAD]** |

### F.4 Why the PID is [SCRATCHPAD] and not [RUN-ARTIFACT] — stated plainly

**The lock file on disk is 0 bytes and contains no PID.** This is not damage; it is the designed
release behaviour. `finalizer_lock()`'s `finally` block runs `os.ftruncate(fd, 0)` before
`flock(LOCK_UN)`, so a cleanly-released lock *always* leaves an empty file. The owner record is
therefore **destroyed by a correct release** and is **not durably recoverable from the lock file**.

PID **16381** was recovered instead from a **live capture** of the lock record taken by the
executing session *while the finalizer was running*, preserved in that session's transcript. It
reconciles with Git and the run artifacts on four independent points, which is why it is reported
rather than withheld:

- its `started_at_iso` (`2026-08-04T19:54:05-0700`) equals `finalizer-start.txt` (`02:54:05Z`) to
  the second;
- its `target_commit` equals `HEAD^` exactly;
- its `repository` equals the verified product repository path;
- the captured `ps` line shows that PID running `scripts/finalize_status.py` under Python 3.14.4,
  matching `SUITE-RESULT.json`'s `python_version`.

**A reader who rejects scratchpad evidence entirely loses only the PID and hostname.** Every
load-bearing fact in this report — identity, scope, counts, gate result, exit code, final state —
stands on **[GIT]**, **[RECEIPT]** and **[RUN-ARTIFACT]** alone.

### F.5 Proof exactly one finalizer owned the lock

Four independent arguments, none relying on a log file's presence:

1. **Architectural** — **[GIT]**. `main()` wraps the *entire* `finalize()` call in
   `finalizer_lock(ROOT, …)`. Acquisition is `LOCK_EX | LOCK_NB`: a second finalizer fails
   *immediately*, before it can delete a receipt, run a suite or write a status file, and exits `2`
   having modified nothing. The lock is acquired **before** any receipt deletion or suite run.
2. **Observed** — **[SCRATCHPAD]**. A live `ps` capture during the run shows exactly **one**
   `finalize_status.py` process — PID `16381`. The capture's raw count was `2`, but the second
   entry is PID `16376`, the `/bin/zsh -c` wrapper that launched it (its command line is the
   launching script itself, containing the string `finalize_status.py`). **One finalizer, one
   shell parent.**
3. **Receipt coherence** — **[RECEIPT]**. Two concurrent finalizers delete each other's receipts
   and certify a moving tree; the surviving record then describes a state neither run certified.
   Here both receipts carry the **same** `commit`, `tree`, `config_sha256`, node-manifest hash and
   `runner_sha256`, and their timestamps are strictly ordered (`03:00:36` → `03:07:44`) inside a
   single lock hold (`02:54:05` → `03:07:57`). No interleaving is present.
4. **Exit status** — **[RUN-ARTIFACT]**. `finalizer-rc.txt` contains `0`. A finalizer that lost the
   lock race returns `2` and prints `REFUSED:`. The log contains no `REFUSED` line.

### F.6 Proof the lock was released, and that zero finalizers remain

- **Released** — **[RUN-ARTIFACT]**. `.git/neyma-finalizer.lock` is **0 bytes** with mtime
  `2026-08-04 20:07:57 -0700` (`03:07:57Z`). Truncation to zero is performed *only* in the release
  path. The mtime sits one second before the recorded process end and fifty-nine seconds before the
  metadata commit — the lock was released by its owner, in order, before the commit was made.
- **Unheld now** — **[RUN-ARTIFACT]**. This session called the repository's own authoritative probe,
  `finalizer_lock.current_owner(repo)`, which attempts `flock(LOCK_EX | LOCK_NB)` and returns the
  owner record only if the lock is held. It returned **`None`** — the lock is free. This is the
  probe the module itself designates as authoritative; it does not infer liveness from a log file.
- **Zero finalizer processes remain** — **[RUN-ARTIFACT]**. A process listing taken in this session
  for `finalize_status`, `pytest`, `clean_clone`, `canonical`, `builder` and `finalizer` returned
  **no matches**. No builder, finalizer, canonical-suite, mutation or repository-changing process is
  active.
- **Builder/worktree lock unheld** — **[RUN-ARTIFACT]**. `.git/neyma-builder-worktree.lock` is
  0 bytes, mtime `2026-07-28 14:17:53 -0700` — released, and untouched for a week before this run.
- **No stray Git locks** — **[GIT]**. Neither `.git/index.lock` nor `.git/HEAD.lock` exists.

---

## G. Final P4 / P5 / R-07 state

All values below were **computed in this session** by loading the repository's own
`scripts/progress_status.py` against the finalized tree — not read out of prose. **[GIT]**

### G.1 P4 — COMPLETE at 100%

| Field | Value |
|---|---|
| `unit_id` | `P4` |
| `status` | **`COMPLETE`** |
| `execution_state` | `COMPLETE` |
| `checkpoint_state` | `PHASE_ACCEPTANCE_COMPLETE` |
| Weighted acceptance criteria | **14** |
| Criteria at PASS | **14 / 14** |
| Weighted sum | **100** |

### G.2 P5 — sole READY unit, NOT_STARTED

| Field | Value |
|---|---|
| `unit_id` | `P5` |
| `status` | **`READY`** |
| `execution_state` | **`NOT_STARTED`** |
| `checkpoint_state` | `NO_CHECKPOINT` |
| READY units across all 18 registry units | **`['P5']` — P5 is the sole READY unit** |

### G.3 Derived block written by the finalizer — `BUILD-STATUS.yaml`

```yaml
content_commit: 42ea24cfc76fac19406e7eaa44b695b8d032b3aa
content_tree: 1e2bba791a5c2c77194d1df9ce16e1d9df84315a
active_phase: P5
single_ready_unit: P5
cli_switch_readiness_percent: 100.0
overall_program_percent: 22.0
current_phase_percent: 0.0
user_visible_maturity_percent: 0.0
production_readiness_percent: 0.0
readiness_tier: SPECIFIED
```

`current_phase_percent: 0.0` is correct and important: P5 is *selected*, not *started*. READY is a
selection, never a claim of progress.

The `CURRENT.md` status-block and the registry meta agree with the receipts exactly — **[GIT]**:

```yaml
recorded_authoring_branch: p4/adapter-containment-completion
content_commit: 42ea24cfc76fac19406e7eaa44b695b8d032b3aa
content_tree: 1e2bba791a5c2c77194d1df9ce16e1d9df84315a
suite_passed: 1961
suite_failed: 0
suite_skipped: 1
```

```yaml
baseline_commit: 42ea24cfc76fac19406e7eaa44b695b8d032b3aa
validated_tree: 1e2bba791a5c2c77194d1df9ce16e1d9df84315a
suite: "1961 passed, 0 failed, 1 conditionally justified skip"
```

The finalizer rebound the record from `0891d1a` / `a3e70464` (the first pass) to `42ea24c` /
`1e2bba79`. That rebinding **is** the substance of this commit's 15 insertions / 15 deletions.

### G.4 R-07 — OPEN, NOT CONTAINED

**[GIT]** — `docs/implementation/phase-0-baseline-manifest.yaml` line 229 still reads:

```yaml
  status: OPEN - NOT CONTAINED
```

and `CURRENT.md`'s open-risks table records `R-07 | Ungated live-write paths | OPEN — NOT
CONTAINED`, discharged only by *"a separate content commit that records CONTAINED in
phase-0-baseline-manifest.yaml"*.

**The second finalizer did not and could not close R-07.** `phase-0-baseline-manifest.yaml` is not
a member of `STATUS_METADATA_FILES`, so the CONTAINED record cannot ride in a status-metadata
commit — and it did not: the manifest is verifiably absent from this commit's change set (§C.2).
The *mechanical* close condition is met and independently verified; the *recording* is not made.
Until that separate content commit lands, **R-07 is OPEN**.

### G.5 Production `GateRegistry` — EMPTY, Phase-8 deferral intact

**[GIT]** — `src/freight_recon/governed_write_registry.py:394` carries the named, blocked seam:

```
# ------------------------------------------------------------------ THE GATE REGISTRY IS BLOCKED
#
# A `GateRegistry` construction belonged here. It is REMOVED, and deliberately not relocated.
```

The deferral's four anchors are intact in that comment: `phase-0-baseline-manifest.yaml` records
`AC-CKPT-6-missing` as `DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8` (`green_at_phase P8`,
`accountable_unit U8.1`); `pr-sequence.md` assigns gate registration to U8.1; `test_phase0_null_gate.py`
proves the production registration population is EMPTY and requires re-adjudication if it stops
being empty; `PROGRESS-PROTOCOL.md` sec 3 requires founder approval to change a frozen acceptance
case. The only `GateRegistry` definition and uses are in `src/freight_recon/checkpoint.py` (the
class, and the kernel's requirement that one be supplied) — **no production registration site
exists**. The seam is left BLOCKED and named, which is the fail-closed direction.

Since **no source file changed in this commit at all** (§C.2), the second finalizer left this
deferral untouched by construction.

---

## H. Worktree and report preservation evidence

The executing session captured a pre-run baseline of the untracked review artifacts. This session
**re-verified every one against that baseline** — **[RUN-ARTIFACT]** + **[GIT]**:

```
docs/implementation/p4-closure-candidate-targeted-adjudication-report-42ea24c.md: OK
docs/implementation/p4-closure-candidate-targeted-adjudication-report-42ea24c.md.sha256: OK
docs/implementation/p4-closure-candidate-targeted-review-handoff-42ea24c.md: OK
docs/implementation/p4-closure-candidate-targeted-review-handoff-42ea24c.md.sha256: OK
docs/implementation/p4-closure-candidate-targeted-review-report-42ea24c.md: OK
docs/implementation/p4-closure-candidate-targeted-review-report-42ea24c.md.sha256: OK
```

All six are **byte-unchanged since before the finalizer launched**. Each `.md` additionally
verifies against its own sidecar from the repository root.

Independently, every one is preserved as a Git blob under
`refs/preserve/p4-second-finalization-prestate-42ea24c` (`d2ae8f47…`, parent exactly `42ea24c`),
and this session compared `git hash-object` of each worktree file against the blob in that ref —
**all six IDENTICAL** — **[GIT]**:

| File | Blob (preserved == worktree) |
|---|---|
| targeted-adjudication-report `.md` | `d0e4644554ac1b197d15121b0d735a37bad78664` |
| targeted-adjudication-report `.md.sha256` | `1d2900e95c61ecb27ccf43f1bf77a3fe5c6e4d0c` |
| targeted-review-handoff `.md` | `d33a28b945efef20b39207dfc9379fbfe76cc8f8` |
| targeted-review-handoff `.md.sha256` | `be4587c1ee77496bdcebe24a214227a27e477040` |
| targeted-review-report `.md` | `b1c71b82a7027f2efc48ccbe3147c760db93b59a` |
| targeted-review-report `.md.sha256` | `9e6070425dae118b590903f7e647120ddc6fbef2` |

The targeted review and targeted adjudication reports for `42ea24c` are therefore present,
unmodified, sidecar-verified and durably preserved in the object database.

---

## I. Protected-ref and push verification

### I.1 Exactly two ref changes, both authorized — **[RUN-ARTIFACT]**

The executing session snapshotted `git for-each-ref` before and after. The **complete** difference
between `refs-before.txt` and `refs-after.txt` is:

```
12c12
< refs/heads/p4/adapter-containment-completion 42ea24cfc76fac19406e7eaa44b695b8d032b3aa
---
> refs/heads/p4/adapter-containment-completion 06ebfdb35a544df8e9cf36d739cc54a0b6877e1f
34a35
> refs/preserve/p4-second-finalization-prestate-42ea24c d2ae8f474d1238d6e9f9e69c84d1f17d20afa0c7
```

1. The **authorized local P4 branch transition** `42ea24c → 06ebfdb3` — the metadata commit itself.
2. The **addition** of a `refs/preserve/*` safety ref. Nothing was overwritten.

**No protected ref moved.** `refs/heads/main`, every `refs/remotes/origin/*`, every tag, every
archive branch and every pre-existing `refs/preserve/*` entry is byte-identical across the run.

### I.2 `main` and `origin/main` unchanged — **[GIT]**

```
refs/heads/main          152574e4f4f2969468c9d31b1e705188896175b5
refs/remotes/origin/main 152574e4f4f2969468c9d31b1e705188896175b5
```

Identical to each other and unchanged across the run.

### I.3 Nothing was pushed — **[GIT]**

- `git ls-remote origin refs/heads/p4/adapter-containment-completion` **exits 2 (absent)** — the P4
  branch **does not exist on the remote**. Neither `42ea24c` nor `06ebfdb3` was ever published.
- The remote-tracking reflog for `origin/main` shows its most recent event as a **`fetch`** on
  `2026-07-26`; the last `update by push` was `2026-06-11`, long before any P4 finalization work.
- No `refs/remotes/origin/*` entry changed across the run (§I.1).

Nothing was pushed, merged, deployed or enabled.

---

## J. Evidence-source table

| # | Evidence source | Location | What it proves | Class |
|---|---|---|---|---|
| 1 | Metadata commit object | `06ebfdb35a54…` | tree, single parent, non-merge, author, timestamp, message | **[GIT]** |
| 2 | Candidate commit object | `42ea24cfc76f…` | candidate tree `1e2bba79`, not amended | **[GIT]** |
| 3 | `git diff HEAD^..HEAD` | product repo | exactly 5 changed paths, all `STATUS_METADATA_FILES` | **[GIT]** |
| 4 | `scripts/finalize_status.py` | lines 70-81, 200-340 | the 10-path declaration; what the finalizer writes; lock-wrapped `main()` | **[GIT]** |
| 5 | `scripts/finalizer_lock.py` | whole module | `flock` semantics; truncate-on-release; authoritative `current_owner()` | **[GIT]** |
| 6 | `SUITE-RESULT.json` | `docs/implementation/` | 1961/0/1, 1962 collected, exit 0, bound to `42ea24c`/`1e2bba79` | **[RECEIPT]** |
| 7 | `GATE-RESULT.json` | `docs/implementation/` | clean-clone `passed: true`, nine steps exit 0 | **[RECEIPT]** |
| 8 | Recomputed payload hashes | via `suite_result.payload_hash()` | both receipts unmodified since written | **[RECEIPT]** |
| 9 | `sf/finalizer.log` | executing session scratchpad | complete original finalizer stdout; all ten staged paths | **[RUN-ARTIFACT]** |
| 10 | `sf/finalizer-rc.txt` | executing session scratchpad | **exit code 0** | **[RUN-ARTIFACT]** |
| 11 | `sf/finalizer-start.txt` / `-end.txt` | executing session scratchpad | start `02:54:05Z`, end `03:07:58Z`, duration 833 s | **[RUN-ARTIFACT]** |
| 12 | `sf/refs-before.txt` / `refs-after.txt` | executing session scratchpad | exactly two authorized ref changes; no protected ref moved | **[RUN-ARTIFACT]** |
| 13 | `sf/untracked-before.sha256` | executing session scratchpad | six review artifacts byte-unchanged across the run | **[RUN-ARTIFACT]** |
| 14 | `.git/neyma-finalizer.lock` | product repo | 0 bytes + mtime `03:07:57Z` ⇒ released by its owner | **[RUN-ARTIFACT]** |
| 15 | `finalizer_lock.current_owner()` probe | run in this session | lock is **not held** now | **[RUN-ARTIFACT]** |
| 16 | Process listing | run in this session | zero finalizer/suite/builder processes remain | **[RUN-ARTIFACT]** |
| 17 | `progress_status` computation | run in this session | P4 COMPLETE 14/14=100; P5 sole READY, NOT_STARTED | **[GIT]** |
| 18 | `phase-0-baseline-manifest.yaml` | line 229 | R-07 `OPEN - NOT CONTAINED`; file absent from the commit | **[GIT]** |
| 19 | `governed_write_registry.py:394` | product source | production `GateRegistry` EMPTY; P8/U8.1 deferral intact | **[GIT]** |
| 20 | `refs/preserve/p4-…-prestate-42ea24c` | `d2ae8f47…` | pre-state worktree preserved; parent exactly `42ea24c` | **[GIT]** |
| 21 | `git ls-remote origin` + remote reflogs | product repo | P4 branch absent on remote; nothing pushed | **[GIT]** |
| 22 | Live lock-record capture | executing session transcript | PID 16381, host, `target_commit`, `started_at` | **[SCRATCHPAD]** |
| 23 | Live `ps` capture during run | executing session transcript | exactly one finalizer process | **[SCRATCHPAD]** |
| 24 | Launch command capture | executing session transcript | exact command and working directory | **[SCRATCHPAD]** |

---

## K. Unrecoverable details and limitations

Stated explicitly rather than invented:

1. **The lock record's PID is not recoverable from the lock file. [UNAVAILABLE→corroborated]**
   `.git/neyma-finalizer.lock` is 0 bytes because a correct release truncates it. PID `16381` comes
   only from a live capture preserved in the executing session's transcript (**[SCRATCHPAD]**),
   reconciled against Git on four points (§F.4). A reader rejecting scratchpad evidence loses the
   PID and hostname and nothing else.
2. **`run_id` and `session_id` were empty. [UNAVAILABLE]** Neither `NEYMA_RUN_ID` nor
   `NEYMA_SESSION_ID` was set, so the lock record carried `""` for both. There is no
   finalizer-assigned run identifier for this pass. This is the environment's state at run time, not
   a lost artifact.
3. **No Product Driver run journal exists for this pass. [UNAVAILABLE]** The newest directory under
   `neyma-product-driver/runs/` is `20260728-205113` (2026-07-28). The second finalizer was launched
   directly from an interactive session, not through the driver's run-journal harness, so no
   `state.json` / `protocol-resolution.json` records it. The scratchpad `sf/` artifact set is the
   run's durable journal.
4. **Per-test suite output is not durably retained. [UNAVAILABLE]** `SUITE-RESULT.json`'s
   `stdout_tail` is `""`, and `finalizer.log` is summary-level. What survives is stronger in kind
   though narrower: exact counts, the named skipped node, empty `rogue_nodes` / `unexecuted_nodes` /
   `xfail_nodes`, and the node-manifest identity hash — which together prove the executed population
   matched the declared canonical population exactly.
5. **The clean-clone workspace is gone. [UNAVAILABLE]** The gate cloned to
   `/var/folders/…/T/neyma-clean-clone-a050fg09/clone`, a temporary directory that no longer exists.
   Its nine per-step exit statuses and counts survive in `GATE-RESULT.json` and `finalizer.log`.
6. **The metadata commit message was authored by the executing session, not by the finalizer.**
   `finalize_status.py` contains no commit-message generation and does not commit at all — it writes
   files and *prints* the `git add` line (§C.1). So the commit message's narrative claims (including
   "pid 16381" and "the five authorized `STATUS_METADATA_FILES`") are **testimony recorded in a
   durable Git object**, not finalizer-generated output. This report re-derived every such claim
   independently and corrected the "five declared" phrasing in §C.1.
7. **Receipts are generated evidence, not independent cryptographic proof.** Restated from §E; this
   is the repository's own declared trust model, and this report makes no stronger claim.
8. **Scope of this attestation.** This report attests to *what the second finalizer did*. It does
   **not** re-adjudicate P4's acceptance criteria, re-review candidate `42ea24c`, or independently
   re-run the canonical suite. Those are separate acts by separate sessions, recorded elsewhere.

---

## L. Conclusion — sufficiency for the R-07 closure candidate

**The evidence is SUFFICIENT for the fresh R-07 closure candidate to cite this second-finalizer
pass.**

Every fact an R-07 closure builder needs to rely on is proven by **[GIT]**, **[RECEIPT]** or
**[RUN-ARTIFACT]** — the three classes that do not depend on any session's testimony:

| Required fact | Established | Class |
|---|---|---|
| A finalizer ran to completion on candidate `42ea24c` | exit code `0`, `02:54:05Z`→`03:07:58Z` | **[RUN-ARTIFACT]** |
| Exactly one finalizer owned the lock, and released it | architectural + receipt coherence + 0-byte lock + free-lock probe | **[GIT]** + **[RECEIPT]** + **[RUN-ARTIFACT]** |
| The complete canonical suite passed | 1961 passed / 0 failed / 1 named skip / 1962 collected | **[RECEIPT]** |
| The clean-clone gate passed | `passed: true`, nine steps exit 0 | **[RECEIPT]** |
| Receipts are unedited | both `payload_sha256` recomputed and matched | **[RECEIPT]** |
| Receipts bind to the candidate | `commit`/`tree` = `42ea24c`/`1e2bba79` in both | **[RECEIPT]** |
| The metadata commit is correctly scoped | 5 changed paths, all `STATUS_METADATA_FILES`; no source/test/script/adapter/policy/manifest/gate | **[GIT]** |
| The candidate was not amended | same object hash before and after the run | **[GIT]** + **[RUN-ARTIFACT]** |
| P4 is COMPLETE at 14/14 = 100 | recomputed from `progress_status` | **[GIT]** |
| P5 is the sole READY unit and NOT_STARTED | recomputed from `progress_status` | **[GIT]** |
| **R-07 is OPEN — NOT CONTAINED** | manifest line 229; manifest absent from the commit | **[GIT]** |
| Production `GateRegistry` is EMPTY, P8 deferral intact | `governed_write_registry.py:394`; no source changed | **[GIT]** |
| No protected ref moved | complete before/after ref diff = 2 authorized changes | **[RUN-ARTIFACT]** |
| Nothing was pushed | P4 branch absent on remote; no remote-ref change | **[GIT]** |

**The single gap — the lock-owner PID — is not load-bearing.** Single-finalizer exclusivity is
established without it, by the non-blocking `flock` architecture, the internal coherence of two
receipts written inside one lock hold, the `0` exit code (a loser returns `2`), and the 0-byte
released lock. The PID is a convenience identifier, not the proof.

**What an R-07 closure builder may cite from this report:**

- that candidate `42ea24c` / tree `1e2bba79` is finalized, with a green canonical suite and a green
  clean-clone gate, recorded in metadata commit `06ebfdb3`;
- that P4 is mechanically COMPLETE and P5 is the sole READY, NOT_STARTED unit;
- that the repository is in a clean FINALIZED state with no held locks and no active processes.

**What it must NOT cite this pass as:** any form of R-07 closure. This finalizer pass explicitly did
**not** close R-07 and could not have. The CONTAINED record belongs in
`phase-0-baseline-manifest.yaml`, which is not a `STATUS_METADATA_FILE`, is verifiably absent from
this commit, and requires **its own separate content commit** — which has not been made. R-07
remains **OPEN — NOT CONTAINED**. Citing this pass as evidence that R-07 is contained would be
exactly the drift `PROGRAM-WEIGHTS.yaml` names as P4's characteristic failure mode: *"R-07 marked
contained without the six paths actually gone."*

---

*Reconstructed and attested by a fresh finalization-evidence attestation session that did not
execute the finalizer. No product implementation, test, status fact, manifest, canonical document,
commit, branch, index or tracked worktree file was modified in producing this report.*
