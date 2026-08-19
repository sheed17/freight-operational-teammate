# Integration Topology — how a finalized pair reaches `main`

> ### **This document records a STANDING OBLIGATION, not a completed state.** The obligation is
> discharged for a given unit only when that unit reaches `main` by the procedure below. It does
> **not** block local implementation; it blocks **integration**.

*Recorded during P4 (adapter containment), after the P4 working branch was found sitting on a
commit the repository's own status guard rejects.*
*Corrected as **R-21b** (procedure repair), after the procedure in §3 was proved unexecutable.*

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

**A standard GitHub pull-request merge** ("Create a merge commit") appends a merge commit whose
**first parent is the base branch** and whose second parent is the feature branch. The certified
pair ends up on the *second-parent* side, so `HEAD^` is no longer the content commit and the
repository lands in the state the guard names *"stale beyond every legal state."*

### This already happened

`main` reached `152574e` through three PR merge commits (`7ae4401` PR#1, `97c311d` PR#2,
`152574e` PR#3). Its **first-parent spine is a throwaway history** — `a8c6fde` *"first commit"* →
`1c7cecc` *"yessir"* → the three merges. Every piece of real work, including the certified content
commit `857cdc1cd`, arrived as a **second parent**. `857cdc1cd` is an ancestor of `main` but sits
at no first-parent depth, which is exactly why the guard cannot bind there.

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

> ### **The guards are correct in substance and stay in force.** `test_status_reality` and the
> Product Driver's receipt-freshness rule both detected this independently, through unrelated
> mechanisms. Neither may be weakened, suppressed, or exempted to accommodate a merge button.
> §5 records the one place the *expression* of the rule was wrong, how it was corrected, and
> ### **exactly what that correction relaxed** — the content commit is no longer required to have
> exactly one parent; it may have at most two. Nothing else was relaxed, and §5's table names every
> shape that is still rejected.

---

## 2. The invariant

> ### **The first-parent chain from `HEAD` must bind to the certified pair, and BETWEEN the content
> commit and `HEAD` there is exactly one commit** — the finalizer-generated **metadata commit** —
> **and it has exactly one parent.**

The invariant constrains what sits **between the content commit and `HEAD`**. It does not reach
further up or down the graph. It does not require the content commit to be a non-merge — that
requirement is what made integration unreachable — but it does **bound** how many lineages that
commit may join. Two things follow, and the second is the one that was previously got wrong:

- **The metadata commit may never be a merge.** This is not implied by anything else: `repo_state()`
  checks that commit's *diff* for purity but never its *parent count*, so a merge whose first parent
  is the recorded content commit and whose second parent touches only `STATUS_METADATA_FILES`
  passes `repo_state()` cleanly. Only the topology guard rejects it.
- ### **The content commit MAY be a merge**, provided its **first** parent is the previous metadata
  commit and it has ### **at most TWO parents**. Requiring it to have exactly one made integration
  unreachable — see §5. Two is the integrating merge this procedure prescribes: the branch and
  `origin/main`. ### **An octopus content commit (three or more parents) is REJECTED** — it carries
  a lineage that `git show` renders as an empty patch, so the independent review this relaxation
  leans on would never see it.

> ### **How the FIRST-PARENT proviso is actually enforced — it is NOT `topology_errors()`.** The
> predicate reads the content commit's parent count only to bound it at two; it never inspects
> *first-parentage* itself. That half of the
> requirement bites through **`repo_state()`**, which resolves `HEAD^` and `HEAD^^` by *first-parent*
> lookup: a merge whose first parent is anything other than the previous metadata commit leaves the
> recorded pair off the chain, so `repo_state()` reports no legal state and `topology_errors()`
> rejects on that `state` input. The practical consequence is that the proviso is enforced **at
> finalizer time** — an integrating merge is legal only because it lands in `PRODUCING` with a
> finalizer owed on it, and a mis-parented one is stale or invalid there instead. It is **not** a
> parent-shape check performed at rest.

Equivalently: `main` advances by **fast-forward only**. Integration adds no commit that the
integrating branch did not already contain, and removes none that `main` already had.

---

## 3. The procedure

Run when a unit is implemented and about to be integrated — **before** the final independent review,
so that the tree reviewed is the tree that lands.

```
    main tip  (152574e — a merge; its first-parent spine is not ours)
        │
        │  ... the branch's own finalized pairs ...
        │
   <metadata commit>          the branch's certified pair tip
        │
        ▼
   <content commit>           ONE commit; MAY be the merge that integrates main's tip,
        │                     whose FIRST parent is the metadata commit above
        ▼
   <metadata commit>          written by scripts/finalize_status.py, exactly ONE parent,
        │                     touching ONLY STATUS_METADATA_FILES
        ▼
      main                    fast-forwarded — no new commit created
```

**Step 1 — check whether integration is even needed.**

```
git fetch origin
git merge-base --is-ancestor origin/main HEAD && echo "already contains main — skip to step 3"
```

**Step 2 — if `origin/main` is NOT an ancestor, merge it INTO the branch as the content commit.**

```
git merge --no-ff -m "<unit>: integrate origin/main (content commit)" origin/main
```

The merge's **first** parent is your branch, so `HEAD^` remains the metadata commit and `HEAD^^`
remains the recorded content commit: `repo_state()` returns `PRODUCING` and the chain still binds.
`main`'s tree already carries `.github/workflows/*`, so those files are inherited — never re-added,
never dropped.

> ### **Do NOT rebase.** A rebase rewrites every commit SHA, including the one `CURRENT.md` records.
> The recorded commit then appears at no first-parent depth, `repo_state()` is stale at every
> position, and **no finalizer can repair it** — the finalizer executes the suite that is failing.
> This is not a style preference; it is a one-way door. See §5.

**Step 3 — independent review, remediation, re-review, adjudication** against *this* content
commit. Any remediation is folded into the content commit or lands as a further pair.

> ### **If the content commit is the integrating merge, review it with `git diff HEAD^ HEAD`.**
> `git show HEAD` prints a *combined* diff, which on a merge is empty for every file that matches
> either parent — an integrating merge typically renders as a ~170-byte header and **no content at
> all**. The first-parent diff shows the whole delta the merge brings onto the branch. Independent
> review is the control this procedure leans on for the class the topology guard cannot detect
> (see §3 Forbidden), so reviewing a merge with the wrong command silently removes that control.

**Step 4 — finalize.** `.venv/bin/python scripts/finalize_status.py` (no arguments; it executes the
full canonical suite and the clean-clone gate and refuses a dirty tree), then commit exactly the
files it names:

```
git add <STATUS_METADATA_FILES as printed by the finalizer>
git commit -m "Record executed status for <unit> (status-metadata commit)"
```

**Step 5 — verify before integrating.** All must pass:

```
.venv/bin/python -m pytest eval/tests/test_status_reality.py -q          # FINALIZED
.venv/bin/python -m pytest eval/tests/test_integration_topology.py -q    # chain binds
.venv/bin/python scripts/clean_clone_gate.py                             # passed (also run by step 4)
neyma-product-driver protocol --repo .      # CONSISTENT — advisory only, see PD-02
neyma-product-driver doctor   --repo .      # 0 failures — advisory only, see PD-02
```

The Product Driver lives outside this repository and carries the recorded **PD-02** parsing defect;
it is **not** authoritative on commit topology. Take topology from this document and
[`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md) §10 only.

**Step 6 — integrate by fast-forward only.** ### **Requires explicit founder authorization: this
is a push.**

```
git merge-base --is-ancestor origin/main <unit-branch>   # MUST succeed, or stop
git push origin <unit-branch>:main                       # fast-forward; no merge commit
```

### Forbidden

- ### **GitHub's "Create a merge commit"** — this is the defect. On GitHub, set
  *Settings → Pull Requests* to allow **only** rebase merging.
  ### **After R-21b the topology guard no longer detects this class on its own, and the repository
  setting is the primary control for it.** The button's *usual* shape merges the feature INTO the
  base, which puts the certified pair on the second-parent side so the chain does not bind — that
  shape is still rejected. But a merge the button creates whose **first** parent happens to be the
  branch's metadata commit is **topologically indistinguishable** from a legitimate integrating
  merge: both bind the chain, both leave the metadata commit single-parent, and `topology_errors()`
  accepts both. For that remainder the controls are the **allow-only-rebase-merging repository
  configuration**, and the fact that any content commit must still pass independent review and a
  real `finalize_status.py` run before it can land.
  ### **Do NOT enable "Require linear history" on `main`.** It would reject the integrating merge
  this procedure depends on, and `main` cannot satisfy it anyway — it already contains three merge
  commits that cannot be rewritten.
- An **octopus content commit** (three or more parents). The integrating merge joins the branch
  and `origin/main` and nothing else; a third parent smuggles a lineage past both `git show` and
  the topology guard's chain-binding check. Rejected by the content-parent bound in §2.
- Any **rebase** of a branch that already carries a metadata commit, at any time.
- Any merge or squash performed **above** the metadata commit.
- Force-pushing `main`, or any rewrite of a pushed commit.

### A note on `main`'s current state

`main` at `152574e` is itself in the illegal state described in §1, and it is pushed, so it cannot
be repaired by rewriting. Fast-forwarding it to a metadata commit produced by this procedure
**repairs it**: the recorded content commit becomes `HEAD^` again and `repo_state()` returns
`FINALIZED`. The illegal merge commits stay in history as ancestors, which is harmless — the
convention constrains the top of the branch, not the whole graph. ### **No rewrite of `main` is
required, and none is authorized.**

---

## 4. Validation

The procedure is re-executed every canonical suite by
[`eval/tests/test_integration_topology.py`](../../eval/tests/test_integration_topology.py), which
builds the real divergence hermetically — a throwaway `main` spine, work arriving as second parents
of PR merges, and a working branch ahead by its own finalized pair — and drives it through the
**real** `repo_state()` rather than a reimplementation. It asserts, at minimum:

| Requirement | Where |
|---|---|
| the historical merge-button shape — feature merged INTO base, so the chain does not bind — is REJECTED (a button merge that *preserves* first-parentage is indistinguishable from a legitimate integration; see §3 Forbidden) | `test_the_scenario_reproduces_the_historical_defect_before_it_repairs_it` |
| the superseded rebase-and-collapse state is REJECTED | `test_the_documented_rebase_and_collapse_state_is_illegal` |
| ### the **finalizer-time** state is legal | `test_the_corrected_procedure_is_legal_at_the_finalizer_time_state` |
| the integrated pair is legal, keeps every file, and fast-forwards losing nothing | `test_the_corrected_procedure_produces_a_legal_integrable_pair` |
| a merge used as the **metadata** commit is REJECTED (and `repo_state()` alone accepts it) | `test_the_predicate_and_the_real_guards_reject_a_merge_used_as_the_metadata_commit` |
| a finalizer position exists at or above the integrating merge | `test_a_finalizer_position_exists_above_a_merge_on_the_first_parent_chain` |
| stacking unfinalized content commits is still REJECTED | same test, final clause |
| an **octopus** content commit carrying a third lineage is REJECTED (and `repo_state()` alone accepts it) | `test_the_real_guards_reject_an_octopus_content_commit_carrying_a_third_lineage` |
| the content commit's parent count is bounded at two, not unconstrained | `test_the_predicate_bounds_the_content_commits_parent_count_at_two` |

> ### **Correct topology cannot launder a forged receipt.** Receipt values edited by hand rather
> than produced by a finalizer run are rejected: *"payload hash mismatch — the record was edited
> after it was produced."* Correct topology is necessary for integration; it is **not** sufficient,
> and it grants no evidentiary credit whatsoever. Only a real `finalize_status.py` run produces an
> acceptable receipt.

---

## 5. R-21b — the procedure repair

The procedure recorded in §3 **could not be executed**, and the guard that was supposed to prove it
did not look at the state where it failed.

**What was wrong.** The topology guard expressed the invariant as a **parent count**: neither
`HEAD` nor `HEAD^` may be a merge. The second half is stricter than §2 — in the `FINALIZED` state
`HEAD^` is the *content* commit, whose parent count §2 never constrained. Because any history in
which `origin/main` becomes an ancestor without rewriting the certified pair **must** contain a
merge on the first-parent chain, the recorded anchor was **trapped below that merge**: every
position where `repo_state()` bound was rejected on parent count, and every position accepted on
parent count was stale. Since `finalize_status.py` validates *before* it writes, it could never be
run at the one position that would have produced a legal pair.

The old §3 made this concrete: *"rebase onto `main`'s tip, collapse to ONE content commit, then
finalize."* With `main`'s tip a merge, that intermediate state fails **both** guards, so Step 4 was
unreachable.

**Why nobody noticed.** The previous rehearsal hand-wrote its metadata commit, never invoked the
finalizer or `repo_state()`, and evaluated the predicate **only on the final pair**. It constructed
the illegal intermediate state and never asserted on it. It also built its "defective" base by
merging a side branch *onto* the certified pair, which leaves the first-parent chain intact — so it
never reproduced the real defect either.

**What changed, stated exactly.** The predicate now asserts the three properties that matter — the
chain binds, the metadata commit has exactly one parent, and the content commit has at most two —
and the scenarios evaluate them at the finalizer-time state against the real `repo_state()`.
The third was added after the first independent review constructed an octopus content commit that
the other two accepted; see the Forbidden note in §3.

### **The relaxation is confined to ONE thing: the CONTENT commit is no longer required to have
exactly ONE parent.** Its parent count is still read, and still bounded — at **two**. Everything
else is retained:

| Shape | After R-21b |
|---|---|
| a merge used as the **metadata** commit | ### **still REJECTED** |
| an octopus metadata commit | ### **still REJECTED** |
| a chain that does not bind the recorded pair (the usual merge-button shape) | ### **still REJECTED** |
| stacked unfinalized content commits | ### **still REJECTED** |
| an **octopus content** commit (three or more parents) | ### **REJECTED** — the bound is two |
| a two-parent merge used as the **content** commit | ### **MAY be ACCEPTED** — and only where the certified chain binds, the state is `PRODUCING`, and a finalizer is owed on it |

Each retained rejection is covered by a test that fails when its rule is removed. The one accepted
case is not a blanket permission: it is accepted *because* the chain still resolves to the certified
pair, which is what distinguishes a legitimate integration from a lost anchor. See the Forbidden
note in §3 for the class this no longer detects on its own.

**What it does not change.** No history was rewritten, `main` was not touched, and no receipt
gained or lost evidentiary weight.

---

## 6. Status

| | |
|---|---|
| **Obligation** | ### **OPEN** — discharged per unit, at integration |
| **Risk register** | ### **R-21** (defect), **R-21b** (procedure repair) |
| **Blocks** | pushing or integrating any unit into `main` |
| **Does not block** | local implementation, review, remediation or finalization |
| **Owner** | the owner (the push itself is a founder-authorized act) |
