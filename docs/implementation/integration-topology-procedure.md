# Integration Topology — how a finalized pair reaches `main`

> ### **This document records a STANDING OBLIGATION, not a completed state.** The obligation is
> discharged for a given unit only when that unit reaches `main` by the procedure below. It does
> **not** block local implementation; it blocks **integration**.

*Recorded during P4 (adapter containment), after the P4 working branch was found sitting on a
commit the repository's own status guard rejects.*

---

## 1. The conflict

Two rules are in force, and off-the-shelf GitHub integration violates one of them.

**The two-commit convention** (`IMPLEMENTATION-REGISTRY.yaml` `meta.status_convention`,
[`CURRENT.md`](CURRENT.md), enforced by
[`eval/tests/test_status_reality.py`](../../eval/tests/test_status_reality.py)): a commit cannot
contain its own hash, so the recorded status names the **content commit**, and the record lands in
**exactly one status-metadata commit directly on top**. `HEAD` is therefore permitted to be only:

1. the certified content commit itself (state `BASELINE`), or
2. the single finalizer-generated metadata commit directly above it (state `FINALIZED`).

`repo_state()` reaches those states through `HEAD^` and `HEAD^^` — **first-parent** lookups.

**A standard GitHub pull-request merge** ("Create a merge commit") appends a merge commit *on top
of* the finalized pair. Its first parent is the base branch, not the certified content commit. So
`HEAD^` is no longer the content commit, and the repository lands in the state the guard names
*"stale beyond every legal state."*

### This already happened

`main` reached `152574e` through three PR merge commits (`7ae4401` PR#1, `97c311d` PR#2,
`152574e` PR#3). At that commit:

| Check | Result |
|---|---|
| `test_status_reality.py::test_recorded_commit_and_tree_match_a_legal_repository_state` | ### **FAILS** — *"CURRENT.md records 857cdc1cd but HEAD is 152574e4f — the status authority is stale beyond every legal state"* |
| Product Driver `protocol` | ### **VIOLATION** — stale receipt, `receipt-freshness:scripts/finalize_status.py:L12` |
| Product Driver `doctor` | 6 warnings, topology VIOLATION |

The certified content tree `df2509f52d43` was **not** corrupted — the only delta between the
finalized pair tip `180fdcc` and `152574e` is two CI files
(`.github/workflows/claude.yml`, `.github/workflows/claude-code-review.yml`) introduced by PR #1.
The defect is **topological**, not substantive. That is precisely why it is dangerous: nothing
about the content looks wrong, and only the topology guard notices.

> ### **The guards are correct and stay as they are.** `test_status_reality` and the Product
> Driver's receipt-freshness rule both detected this independently, through unrelated mechanisms.
> Neither may be weakened, suppressed, or exempted to accommodate a merge button.

---

## 2. The invariant

> ### **No merge commit may sit above a certified content commit.** Between the content commit and
> `HEAD` there is exactly one commit — the finalizer-generated metadata commit — and it has exactly
> one parent.

Equivalently: `main` advances by **fast-forward only**. Integration adds no commit that the
integrating branch did not already contain.

---

## 3. The procedure

Run when a unit is implemented and about to be integrated — **before** the final independent review,
so that the tree reviewed is the tree that lands.

```
                 152574e  ← main (its tree already carries .github/workflows/*)
                    │
                    ▼
              <content commit>       one commit, one parent, all unit work
                    │
                    ▼
             <metadata commit>       written by scripts/finalize_status.py, one parent,
                    │                touching ONLY STATUS_METADATA_FILES
                    ▼
                  main               fast-forwarded — no new commit created
```

**Step 1 — replay the unit's work onto `main`'s tip.** The working branch is based on the previous
finalized pair, which is an ancestor of `main`, so only the unit's own commits replay.

```
git fetch origin
git rebase --onto origin/main <previous-pair-tip> <unit-branch>
```

**Step 2 — collapse to exactly ONE content commit.**

```
git reset --soft origin/main
git commit -m "<unit>: <summary> (content commit)"
```

The unit branch is local and unpushed, so this rewrites nothing shared. `main`'s tree already
carries `.github/workflows/*`, so those files are inherited — never re-added, never dropped.

**Step 3 — independent review, remediation, re-review, adjudication** against *this* content
commit. Any remediation is folded back into the single content commit (repeat step 2).

**Step 4 — finalize.** `.venv/bin/python scripts/finalize_status.py` (no arguments; it executes the
full canonical suite and the clean-clone gate and refuses a dirty tree), then commit exactly the
files it names:

```
git add <STATUS_METADATA_FILES as printed by the finalizer>
git commit -m "Record executed status for <unit> (status-metadata commit)"
```

**Step 5 — verify before integrating.** All four must pass:

```
.venv/bin/python -m pytest eval/tests/test_status_reality.py -q      # FINALIZED
neyma-product-driver protocol --repo .                               # CONSISTENT
neyma-product-driver doctor   --repo .                               # 0 failures
.venv/bin/python scripts/clean_clone_gate.py                         # passed (also run by step 4)
```

**Step 6 — integrate by fast-forward only.** ### **Requires explicit founder authorization: this
is a push.**

```
git merge-base --is-ancestor origin/main <unit-branch>   # MUST succeed, or stop
git push origin <unit-branch>:main                       # fast-forward; no merge commit
```

### Forbidden

- ### **GitHub's "Create a merge commit"** — this is the defect. On GitHub, set
  *Settings → Pull Requests* to allow **only** rebase merging, and enable **Require linear
  history** on `main`.
- Any merge, squash or rebase performed **after** the metadata commit.
- Force-pushing `main`, or any rewrite of a pushed commit.

### A note on `main`'s current state

`main` at `152574e` is itself in the illegal state described in §1, and it is pushed, so it cannot
be repaired by rewriting. Fast-forwarding it to a metadata commit produced by this procedure
**repairs it**: the recorded content commit becomes `HEAD^` again and `repo_state()` returns
`FINALIZED`. The illegal merge commits stay in history as ancestors, which is harmless — the
convention constrains the top of the branch, not the whole graph.

---

## 4. Validation

The procedure was rehearsed end-to-end in a disposable local clone (never pushed; shared history
untouched), simulating a two-commit unit on top of the certified pair `180fdcc`:

| Requirement | Observed |
|---|---|
| preserves the GitHub workflow files | ### **2/2 present** in the content commit's tree |
| preserves the unit's reviewed content | ### **2/2 present** |
| content commit + one metadata commit | both have ### **exactly 1 parent** |
| metadata commit touches only status files | diff ⊆ `STATUS_METADATA_FILES` |
| introduces no post-finalizer merge commit | `git rev-list --count --merges <old-main>..HEAD` = ### **0** |
| does not rewrite shared history | old `main` tip is still an ancestor; `merge --ff-only` succeeded |
| `test_status_reality` | ### **PASS** — state `FINALIZED` |
| Product Driver `protocol` | ### **CONSISTENT** — `<old main> BASELINE → CONTENT → FINALIZER_GENERATED` |

> ### **The rehearsal also proved the procedure cannot launder a forged receipt.** Receipt values
> edited by hand rather than produced by a finalizer run were rejected:
> *"payload hash mismatch — the record was edited after it was produced."* Correct topology is
> necessary for integration; it is **not** sufficient, and it grants no evidentiary credit
> whatsoever. Only a real `finalize_status.py` run produces an acceptable receipt.

The rehearsal is not a document. It is re-executed every canonical suite by
[`eval/tests/test_integration_topology.py`](../../eval/tests/test_integration_topology.py), which
builds the topology hermetically and asserts each property above, and which additionally checks
the **live** repository's `HEAD` and `HEAD^` for merge parents.

---

## 5. Status

| | |
|---|---|
| **Obligation** | ### **OPEN** — discharged per unit, at integration |
| **Risk register** | ### **R-21** |
| **Blocks** | pushing or integrating any unit into `main` |
| **Does not block** | local implementation, review, remediation or finalization |
| **Owner** | the owner (the push itself is a founder-authorized act) |
