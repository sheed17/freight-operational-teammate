# ⛔ R-07 CLOSURE BUILDER HANDOFF — NOT A REVIEW, NOT AN ADJUDICATION, NOT A FINALIZATION

> **This is the builder's handoff for the R-07 CONTAINMENT + DOCUMENTATION-CONSISTENCY content
> commit.** It certifies nothing and adjudicates nothing. The session that wrote it did **not**
> implement P4, did not remediate it, did not author the P4 acceptance closure candidate, did not
> conduct either targeted review, did not conduct either adjudication, did not run either finalizer,
> and did not author the reconstructed second-finalization report. It resumed no prior session.
>
> It ran **no** finalizer, wrote **no** finalizer receipt, performed **no** independent review and
> **no** adjudication, began **no** P5 work, pushed / merged / deployed nothing, enabled no effect,
> amended nothing, and used no `checkout` / `restore` / `stash` / `clean` / `gc` / `prune`.
>
> **A builder's handoff is untrusted input to the reviewer.** Verify every claim below against the
> object store and the repository's own guards. The previous cycle's handoff contained a finding
> (F-TR-05: it named a guard function that does not exist), which is exactly why nothing here may be
> taken on trust.

---

## A. The candidate

```
parent (second-finalizer metadata commit)   06ebfdb35a544df8e9cf36d739cc54a0b6877e1f
branch                                      p4/adapter-containment-completion   (local, UNPUSHED)
commit                                      the SOLE commit above 06ebfdb3 on this branch
                                            (git rev-list --first-parent 06ebfdb3..HEAD  ->  exactly 1)
```

This document is committed **inside** the candidate, so it cannot contain its own hash. Derive it:
`git rev-parse HEAD`, and confirm `git rev-list --count --first-parent 06ebfdb3..HEAD` is **1**.

**Prior chain, re-derivable from the object store:**

| Object | Value |
|---|---|
| Accepted implementation candidate | `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e` (tree `a3e704645b8a06561d90cdb5f81288309ae51850`) |
| First-finalizer metadata commit | `86306d5c4d866baf1a7fb6e4bd8220ce31017acd` |
| P4 acceptance closure candidate | `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` (tree `1e2bba791a5c2c77194d1df9ce16e1d9df84315a`) |
| Second-finalizer metadata commit | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (tree `e3f0c59e36269d541b27d8be8dac8de68234e4fb`) |

## B. Verified starting state (Step 1 — re-derived, not inherited)

Every row was recomputed in this session before any file was modified.

| Check | Result |
|---|---|
| Branch · HEAD · tree · parent | `p4/adapter-containment-completion` · `06ebfdb3…` · `e3f0c59e…` · `42ea24cf…` — **all match** |
| `HEAD^..HEAD` changed paths | **exactly 5**, every one a `STATUS_METADATA_FILES` member: `BUILD-STATUS.yaml`, `CURRENT.md`, `GATE-RESULT.json`, `IMPLEMENTATION-REGISTRY.yaml`, `SUITE-RESULT.json`. The declared tuple has **ten** entries; five differed. The declared-ownership tuple and the changed-path set are **not** the same thing |
| `test_status_reality.repo_state()` | **`FINALIZED`** — executed, not assumed |
| P4 | `status: COMPLETE`, `execution_state: COMPLETE`, `checkpoint_state: PHASE_ACCEPTANCE_COMPLETE` |
| P5 | sole `READY`; `execution_state: NOT_STARTED`, `checkpoint_state: NO_CHECKPOINT` |
| P6–P14 | all nine `BLOCKED` |
| R-07 before this commit | `OPEN - NOT CONTAINED` |
| `phase-0-baseline-manifest.yaml` vs `0891d1a` | blob `dd00f197f899fba0a28cd6752ee803fb442ae75c` — **byte-identical**, as repository authority expects |
| Production `GateRegistry` | **EMPTY** — AST sweep of **152** modules across `src/` and `scripts/`: **0** constructions, **0** `register_gate` calls |
| Phase-8 Action Class gate deferral | unchanged (`AC-CKPT-6-missing`, `DEFERRED_BY_DEPENDENCY`, U8.1 / P8) |
| Active builder / finalizer / suite / mutation process | **none** |
| `.git/neyma-finalizer.lock` · `.git/neyma-builder-worktree.lock` | both **UNHELD** by `flock(LOCK_EX\|LOCK_NB)`; `finalizer_lock.current_owner()` → `None` |
| Targeted review + adjudication preservation refs | `refs/preserve/p4-closure-targeted-review-42ea24c` → `c30a43be…`, `refs/preserve/p4-closure-targeted-adjudication-42ea24c` → `d3cf1de9…` — reports and sidecars **verify** |
| Reconstructed second-finalization report | exists · SHA-256 **`96ef5fe85016f2de5d5840814d95dd170947474a3259ac8bb902df9f485a1fa0`** — matches exactly · sidecar valid · preserved at `refs/preserve/p4-second-finalization-report-06ebfdb3` = `99f0e59d06684625606d789604256dc11cf9d5d8`, parent **exactly `06ebfdb3`**, adding **only** the report and its `.sha256` |
| The report's evidence-source distinctions | **accurate** — five explicit classes (`[GIT]`, `[RECEIPT]`, `[RUN-ARTIFACT]`, `[SCRATCHPAD]`, `[UNAVAILABLE]`), and its §C.1 correction of the "five declared `STATUS_METADATA_FILES`" phrasing is right |
| `main` · `origin/main` · protected refs | `152574e4f4f2969468c9d31b1e705188896175b5`, unchanged |
| Pushed | **nothing** |

**No identity or authority condition differed, so this session proceeded.**

## C. Preservation (Step 3)

```
preservation ref     refs/preserve/p4-r07-closure-prestate-06ebfdb3
preservation commit  3cac4d0e17b569b7d9c6c78d394593051e55face
preservation tree    e4dd3417c3527b055471f0c57405dd6ef41eebed
preservation parent  06ebfdb35a544df8e9cf36d739cc54a0b6877e1f
```

Built through a **HEAD-seeded** temporary `GIT_INDEX_FILE` outside `.git/index` (`git read-tree HEAD`
— *not* an empty index), **before any file was modified**. The product branch was not moved and the
repository index was not touched.

| Class | Count | How captured |
|---|---|---|
| Tracked files | **622** | content, by object identity from HEAD |
| Untracked reports + sidecars | **8** | content |
| Tracked-but-ignored `.playwright-mcp/*` | **7** | content (inside the 622; listed separately) |
| Dirty tracked files · index-vs-HEAD differences | **0** · **0** | worktree tree **==** HEAD tree `e3f0c59e…` |
| Ignored-untracked | **18 878** | **inventory only** — path · class · size/symlink target · SHA-256 |
| Preservation evidence blobs | **9** | content |
| **Total tree entries** | **639** | |

**Why ignored-untracked content is inventoried, not committed.** The set is `.venv` (14 445),
gitignored `data/` corpora (3 394), a **real Chrome profile with cookies and login data** (761),
caches, and **`.env`**. Committing it would put secret and environment material into Git objects,
which `CLAUDE.md` §10 and the closure tasking both forbid. Every one of the 18 878 is recorded by
path, class, size and SHA-256; `.env` alone is recorded `SECRET-CLASS / CONTENT-NOT-CAPTURED /
OMITTED`. **The omission is itself recorded — nothing was silently dropped.**

**Verified in a disposable `git clone --no-local`:** 630 content paths compared — **0 missing,
0 byte-mismatched**; reverse sweep over live tracked + untracked-non-ignored — **0 uncaptured**;
ignored-untracked **18 878 live / 18 878 inventoried / 0 uninventoried**; **all 7 sidecars verify**
inside the clone.

> The re-review sidecar verifies under its **documented** semantics, re-derived here rather than
> inherited: the tracked file is 813 lines (a 36-line disarming banner prepended), the sidecar
> records the **original's** hash, and `tail -n 777` of the tracked file `cmp`s **byte-identical,
> zero differences** against the preserved blob, hashing to `181e1a37…b316`.

## D. The R-07 containment record (Step 4)

**Location:** `docs/implementation/phase-0-baseline-manifest.yaml`, `expected_legacy_paths`.

**Exact repository-authorized state — no new spelling, no new schema:**

```yaml
risk_id: R-07
status: CONTAINED          # exactly the spelling the guards detect and PHASE-OUTPUTS.md names
contained_at: >-
  P4 - recorded by the R-07 closure content commit whose parent is the second-finalizer
  metadata commit 06ebfdb35a544df8e9cf36d739cc54a0b6877e1f. …
```

`removed_by_phase: P4` and `accountable_unit` are unchanged. `deletion_condition` now records
**MET** with the conditions enumerated. `reason` is retained as the **historical premise**, labelled
as such — a finding whose premise vanishes when it closes is a finding nobody can audit.

### D.1 The containment MECHANISM, stated as a mechanism — not as "tests passed"

An external effect can be produced **only** by an effect-capable adapter. An effect-capable adapter
can be imported **only** by the containment boundary, another adapter, or a recorded quarantine
importer — and the CI import gate (`eval/tests/test_import_gate.py` over
`eval/phase0/import_probe.py`) fails the build if any other importer exists, **live and recorded,
both-sided**, so an unrecorded cut and an unperformed recorded cut each fail. The single
application-layer route into an effect-capable adapter is therefore
`src/freight_recon/effect_boundary.py`, and inside it the only external-write construction and
execution path is `execute_invoice_write`: a narrowly typed `InvoiceWriteOperation` that must pass
the seven-step atomic checkpoint, a fresh Checkpoint Witness, an Effect Grant and an atomic claim
before an adapter is called. **Anything that cannot present that chain REFUSES — it does not fall
back.** The deployed authenticated Slack callback reaches this boundary and the governed-kernel seam
through `governed_write_route.py`; with no kernel registered it answers a recorded
`ROUTE_NOT_CONFIGURED` refusal. There is **no reachable legacy callback-to-actuator path**:
`run_action_callback_server.py` imports no effect-capable adapter, constructs no live-write driver,
and passes `operation_router=None` unconditionally.

### D.2 What containment is NOT — recorded in the manifest itself

Not "the tests passed". **Not production writes enabled** — the default bounded writer performs a
proven non-occurrence and a non-sandbox operation is refused before any claim. **Not a registered
production policy gate** — the production `GateRegistry` population is EMPTY and stays empty until
U8.1 / P8 by founder decision. **Not autonomy of any kind, bounded or otherwise.** Live supervised
writes remain P12, behind the undischarged **RR-01**.

### D.3 The bound evidence chain (`containment_evidence`)

| Element | Value |
|---|---|
| implementation candidate | `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e` |
| accepted independent re-review | `p4-independent-rereview-report-0891d1a.md`, sha256 `181e1a37…b316`, `refs/preserve/p4-independent-rereview-0891d1a` |
| final adjudication | `p4-final-adjudication-report-0891d1a.md`, sha256 `078cfea8…997e`, `refs/preserve/p4-final-adjudication-0891d1a` |
| first-finalizer metadata commit | `86306d5c4d866baf1a7fb6e4bd8220ce31017acd` |
| P4 acceptance closure candidate | `42ea24cfc76fac19406e7eaa44b695b8d032b3aa` |
| accepted targeted independent review | `p4-closure-candidate-targeted-review-report-42ea24c.md`, sha256 `5547aa5e…8ea5`, `refs/preserve/p4-closure-targeted-review-42ea24c` |
| accepted targeted adjudication | `p4-closure-candidate-targeted-adjudication-report-42ea24c.md`, sha256 `23496e6c…9567`, `refs/preserve/p4-closure-targeted-adjudication-42ea24c` |
| second-finalizer metadata commit | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` |
| reconstructed second-finalization report | sha256 `96ef5fe85016f2de5d5840814d95dd170947474a3259ac8bb902df9f485a1fa0` |
| canonical suite | 1961 passed / 0 failed / 1 skipped / 1962 collected |
| clean-clone | PASS |
| mutation battery | 61/61 caught, 0 MISS, 0 SETUP-FAIL, 0 RESTORE-RED |
| violation edges | 0 live / 0 recorded, agreeing both-sided |
| detection edges | 13 |
| callback socket tests | 34 passed |
| finalizer lock | one owner per pass, held throughout, released on exit; re-probed UNHELD |
| authenticated callback → bounded provider + governed-kernel seam | proved through the production entry point |
| production default | `ROUTE_NOT_CONFIGURED` refusal, zero grants minted |
| production `GateRegistry` | EMPTY, must stay empty until U8.1 / P8 |
| Phase-8 gate registration | DEFERRED — unchanged by this record |
| reachable legacy callback→actuator path | NONE |
| P5 implementation | NOT BEGUN |

### D.4 Attribution constraint honoured

The `second_finalization_report` entry states **in the manifest** that the report is a
**RECONSTRUCTION** authored after the run by an independent attestation session that did not execute
the finalizer; that it may be cited only for facts independently established by Git objects,
canonical receipts, lock/run artifacts and preserved scratchpad evidence; that it is **not**
contemporaneous finalizer testimony; and that the process PID and the Product Driver run/session IDs
are `[UNAVAILABLE]` — **documented limitations, not blanks to be filled in.** Nothing in the
containment record rests on any `[UNAVAILABLE]` item.

## E. F-TR-01 … F-TR-04 remediation mapping (Step 5)

| Finding | File | Was | Now |
|---|---|---|---|
| **F-TR-01** | `ARCHITECTURE.md` §28/§29 | `P4 \| 🔄 READY *(selected)* — IN PROGRESS, NOT COMPLETE`, `P5+ ⛔ NOT STARTED`, "Nothing does, until P4", "R-07 remains OPEN — NOT CONTAINED" | P4 **COMPLETE — ADJUDICATED**; a distinct **P5 READY *(selected)* — NOT STARTED, NOT COMPLETE** row; **P6+ BLOCKED**; §29 restated as the wall that now exists, with **CONTAINED ≠ ENABLED**. Architectural history is **not** rewritten: the superseded "discipline, not a mechanism … may never be recorded as containment" paragraph is retained, labelled **HISTORICAL**, with the permanent rule restated |
| **F-TR-02** | `AGENTS.md` §Status | "P4 … sole READY unit AND is executing — NOT COMPLETE; R-07 OPEN — NOT CONTAINED (**only completing P4 closes R-07**)" | Current state, plus an explicit four-act sequence: P4 implementation and acceptance completed → **that did NOT close R-07** → R-07 required a separate evidence-backed closure cycle → **both** P4 finalization passes ran → **only then** did the canonical containment record close it |
| **F-TR-03** | `docs/product/FREIGHT-CAPABILITY-MAP.md` (header + §16) | "in-progress P4 … READY, not COMPLETE; R-07 remains OPEN — NOT CONTAINED" | P4 **COMPLETE — ADJUDICATED**, R-07 **CONTAINED** with the bound stated. **P5 is stated as READY and NOT STARTED** — no implication that P5 work has begun |
| **F-TR-04** | `docs/implementation/EFFECT-PATH-INVENTORY.yaml` | free-text `paths[EP-1].p4_f01_governed_join`: "R-07 REMAINS OPEN - NOT CONTAINED, and P4 REMAINS NOT COMPLETE"; `meta.risk: R-07 OPEN - NOT CONTAINED`; header paragraph | Corrected with the superseded sentence **quoted in place**; `meta.risk` now restates the canonical CONTAINED record **with its bound**; the mid-cutover header paragraph carries an explicit `### [HISTORICAL AS WRITTEN …]` marker naming where the live status lives |

**The machine-consumed effect-path inventory is preserved.** `git diff` on the `paths` list shows
**no classification change**: `PRODUCTION_LIVE_WRITE` is still exactly `{EP-1}`, `REMOVED_AT_P4` is
still exactly `{EP-6, EP-7, EP-9, EP-10}`, EP-3/EP-8/EP-14 keep their read-only classifications, and
`test_bootstrap_hermeticity.py` still holds every one by exact set. The only structured field
changed is `meta.production_reachable_live_write_remaining: 2 → 1`, which no guard consumes and
which corrects a stale count (EP-3 left the live set at P4) rather than a classification.

**Historical blocks are mechanically distinguishable.** Two conventions, both narrow and both
enforced: a superseded claim survives in place only if it is **inside a double-quoted span** (it is
being reported, not asserted) or the **same line** carries a `HISTORICAL` / `SUPERSEDED` token. A
marker several lines away does **not** count — that is how a "historical" block silently grows to
cover live text. Implemented as `_is_superseded_in_place()` in
`eval/tests/test_roadmap_completeness_control.py`.

**AD-01 folded in as the adjudication directed.** Both artifacts that carried the stale
provider-`None` prose — `EFFECT-PATH-INVENTORY.yaml` and `LEGACY-DISPOSITION.md` — now state the
deployed wiring exactly: the **lookup boundary is WIRED** (a bounded `provider` closure resolving an
already-authorized pending write via `WorkflowStorePendingWrites`, `writer=None`, failing **closed**
on any lookup error) and the **execution kernel remains `None`** (`kernel_factory = None`) pending
U8.1 / P8. **AD-01 itself is carried, not discharged.**

## F. ADJ-01 remediation and hostile-test mapping (Step 6)

### F.1 The gap, proved mechanically

Run in this session against the **pre-remediation** guard and the **pre-remediation** documents
(`git show 06ebfdb3:<file>`):

```
population size: 49        ARCHITECTURE.md in population: True     AGENTS.md in population: True
ARCHITECTURE.md   old-pattern hits = 0   actual stale constructions = 1
                  -> 'P4** | 🔄 READY *(selected)* — **IN PROGRESS, NOT COMPLETE'
AGENTS.md         old-pattern hits = 0
```

**The population was never the problem; the alternation was.** The guard matched only
`the (?:single|one and only) READY unit` while the corpus said `READY *(selected)*` and
`the sole READY unit`. A **second** dimension surfaced during remediation: the stale `AGENTS.md`
sentence read `P4 (adapter\ncontainment) is the sole READY unit` — unit token and claim on different
lines — so every `[^\n]{0,N}` window walked straight past it. A guard a line wrap defeats is not a
guard, and the corpus is hard-wrapped prose.

### F.2 The remediation

1. **`test_no_completed_unit_is_described_as_ready_or_pending_in_live_guidance`** — all four
   original patterns retained **verbatim in meaning**; alternation broadened to
   `sole|single|selected|one and only|only|next` and to the `READY *(selected)*` and
   `IN PROGRESS, NOT COMPLETE` forms; matching now runs over **whitespace-normalised** text.
   **Nothing was narrowed.**
2. **NEW — `test_the_selected_ready_unit_construction_is_present_singular_and_matches_the_registry`.**
   The old guard was purely **negative**: it can only fire on a unit that is already COMPLETE. Had
   `ARCHITECTURE.md` simply *deleted* its P4 row instead of leaving it stale, the guard would have
   gone quiet and the repository would carry **no live statement of which unit is READY at all** —
   silence reading as compliance. The new guard requires the construction to be **reached** and
   **correct**: exactly one READY unit in the registry; the discovered corpus non-empty; the
   selected-READY construction **present** (absence FAILS) in at least 3 documents; every attributed
   unit equal to the registry's; two distinct attributed units FAIL; and
   `BUILD-STATUS.derived.single_ready_unit` agreeing.
3. **No brittle P5-only shortcut.** Everything derives from the registry, so the guard keeps working
   — and keeps failing correctly — at the next transition.
4. **No substring-only matching.** Attribution is anchored on a **unit token** (`P\d{1,2}`,
   `U-…`, `U\d+(\.\d+)?`) near a whole-construction match. Program ranges (`P0-P14`) are blanked
   length-preservingly before attribution — a false positive this guard's own first run produced,
   attributing "the single READY unit" in an agent description to `P14`.
5. **Also de-vacuumed:** `test_an_executing_phase_is_never_described_as_not_begun` scoped itself to
   `execution_state == IN_PROGRESS` and, finding none, did `return` — a **silent PASS over an empty
   population**, the M-9 false-green pattern. It went vacuous when P4 moved IN_PROGRESS → COMPLETE,
   and mutation case **M1 proved it** (the mutant went undetected). Its population is now every unit
   with **landed checkpoints**, which cannot be empty while any phase is done.

### F.3 Regression coverage and manifest identity

`TEST-NODE-MANIFEST.json` regenerated through `scripts/regenerate_test_manifest.py` — the canonical
mechanism, never automatic:

```
1962 -> 1964 nodes
  +3  test_phase0_baseline_manifest.py::test_r07_containment_record_holds_only_while_its_mechanical_conditions_hold
      test_phase0_baseline_manifest.py::test_no_allowance_section_may_be_read_as_containment
      test_switch_consistency.py::test_the_selected_ready_unit_construction_is_present_singular_and_matches_the_registry
  -1  test_phase0_baseline_manifest.py::test_r07_is_never_described_as_contained   (renamed — see §J)
```

Collection identity re-verified after regeneration: live collection == recorded manifest, **0
missing, 0 extra**.

## G. ADJ-02 canonical-document parity proof (Step 7)

The P3 precedent `f579d92` corrected `AGENTS.md`, `ARCHITECTURE.md`, `CLAUDE.md` and `README.md`;
`42ea24c` corrected only the latter two. **All four now agree**, and the sweep went wider than the
four. Every occurrence of `P4 IN PROGRESS` / `P4 NOT COMPLETE` / `P4 remains incomplete` /
`P4 alone closes R-07` / `R-07 OPEN` / `P5 BLOCKED` was classified:

| Classification | Surfaces |
|---|---|
| **Current live status — CORRECTED** | `ARCHITECTURE.md`, `AGENTS.md`, `CLAUDE.md` (§3 rows, §11, closing block), `README.md`, `PRODUCT.md`, `CURRENT.md`, `BUILD-STATUS.yaml` (**authored `snapshot:` only**), `IMPLEMENTATION-REGISTRY.yaml` (residual register only), `CAPABILITY-TRACEABILITY.yaml`, `IMPLEMENTATION-SURFACE.yaml`, `PHASE-OUTPUTS.md`, `EFFECT-PATH-INVENTORY.yaml`, `LEGACY-DISPOSITION.md`, `docs/product/FREIGHT-CAPABILITY-MAP.md`, `docs/product/FREIGHT-OPERATING-VISION.md`, `docs/CANONICAL-DOCUMENTS.md`, `.claude/agents/roadmap-steward.md` |
| **Legitimate historical record — LABELLED, NOT REWRITTEN** | `PHASE-OUTPUTS.md` P3 row ("R-07 stays OPEN **through P3** *(HISTORICAL…)*"); `pr-sequence.md` U0.10 row (the frozen Phase-0 sequence); the `phase-0-baseline-manifest.yaml` staged-cutover comments; the `EFFECT-PATH-INVENTORY.yaml` mid-cutover header |
| **Preserved review evidence — UNTOUCHED** | every `docs/implementation/*review*.md`, the P3/P4 adjudications, both finalization reports, the closure-topology determination, `U-*-ACCEPTANCE.yaml`. **No historical report body was altered to make it look current** |
| **Unrelated text** | occurrences of "open" not referring to R-07's state; guard source that must *name* the forbidden string in order to hunt it |

**No historical report was edited to appear current.** The only additions to a historical report are
the disarming banners in §J, required by `test_false_green_defenses.py` for a tracked
review-family document — the same mechanism the accepted re-review already carries.

## H. Residual-risk register (Step 8) — nothing discharged

**R-07 is the only item this cycle closed, and it closed because a record was WRITTEN, never because
a residual was waived.**

| ID | Standing after this commit |
|---|---|
| **RR-01** | **NOT DISCHARGED — BINDING P12 PRECONDITION.** `base_url` remains outside `payload_hash()`'s canonical set and outside `approval_operation_mismatch`; compounded by **F-08** and **F-09**. Must be discharged before any live writer is injected |
| **AD-01** | **CARRIED.** Provider is **WIRED**; production kernel remains `None` pending Phase 8. Prose corrected in both artifacts; the **stale provider-`None` prose must not reappear**. The finding stays on the register so a reintroduction reads as a regression |
| **AD-02** | **CARRIED.** `finalizer_lock.py` remains safety-critical with **zero committed test coverage** — no `eval/` references, no manifest nodes, no mutant. Operating instruction travels with it: **treat a lock refusal as authoritative; never reclaim the lock because a log file is missing** |
| **RR-02 · RR-03 · RR-04 · RR-05 · RR-06 · F-03 · F-06 · F-07 · F-08 · F-09 · F-10** | all **CARRIED**, unchanged, in `IMPLEMENTATION-REGISTRY.yaml` → P4 → `residual_risks_carried_forward` |
| **PD-01** *(newly recorded)* | The Product Driver `BLOCKED_AUTHORITY` observation reported during the second finalization. Classified as a **pre-existing prose-extraction ambiguity in that external tool's protocol resolver**, **not** a failed repository guard: no repository guard reported it, `build_status_errors()` was `[]`, `repo_state()` was legal, the suite was green. **OPEN, recorded, not discharged** — the driver's finding to close |
| **CB-01** *(newly recorded)* | Two roadmap mutation cases SKIP-INVALID because their anchors no longer exist: **M4** and **M11**. Both anchors were **already absent at `06ebfdb3`** (`git show HEAD:<path>`) — pre-existing, **not** introduced here. **Deliberately not fixed**: choosing replacement anchors decides what those guards should assert, which belongs to the guard owner. See §I |
| **Phase-8 Action Class gate registration** | **DEFERRED to U8.1 / P8 — unchanged.** Production `GateRegistry` population **EMPTY** and must stay empty |
| **G2 transition/event completeness** | `COUNT NEEDS ADJUDICATION`, undischarged, P5's own blocker |

## I. The one `scripts/` change — disclosed plainly

`git diff --stat 0891d1a HEAD -- src configs data` is **empty**: `src/`, `configs/` and `data/` are
**byte-identical** to the accepted implementation candidate.

`scripts/` is **not** byte-identical, and that is a deliberate, disclosed change:

```
scripts/mutate_roadmap_completeness.py | 17 ++++++++++++-----   (1 file, +12 / -5)
```

**Why it was unavoidable.** That file is the roadmap-completeness **mutation battery** — evidence
infrastructure, never imported by runtime, adjudicating nothing (`LEGACY-DISPOSITION.md` classifies
it exactly so). A mutation case is bound to the **exact text** it reintroduces its defect into. Two
of its anchors are documents this commit legitimately corrects:

* **M1** anchored `## P4 — Adapter containment 🔄 IN PROGRESS — NOT COMPLETE` in `PHASE-OUTPUTS.md`
  — an F-TR-class stale live claim that ADJ-02 parity required correcting.
* **M3** anchored `| **R-07** | … OPEN — NOT CONTAINED |` in `CURRENT.md` and mutated it *into* a
  containment claim — the exact state the R-07 record now legitimately holds.

Left alone, both would SETUP-FAIL and prove nothing. They were **re-pointed**, not weakened: M1
reintroduces the same defect (a phase with landed evidence described as not started); M3 now
reintroduces the same defect from the other side (the status authority contradicting the manifest).
**The alternative — leaving stale live claims in canonical documents so a mutation anchor keeps
matching — would have been the tail wagging the dog.**

**Battery result after re-pointing: 9/11 CAUGHT, 0 MISS, 2 SKIP-INVALID (M4, M11 — CB-01,
pre-existing).** Byte-for-byte restoration verified; `__pycache__` purged; no `git checkout` /
`restore` / `stash` / `clean` used.

## J. Report attribution and preservation (Step 10)

This commit **tracks** the cycle's evidence so future reviewers can durably read it rather than
depending on untracked files that a clean clone will not contain:

| Document | SHA-256 (as committed) | Note |
|---|---|---|
| `p4-closure-candidate-targeted-review-report-42ea24c.md` | see §J.1 | banner prepended; sidecar keeps the **original** hash `5547aa5e…8ea5` |
| `p4-closure-candidate-targeted-review-handoff-42ea24c.md` | see §J.1 | banner prepended; sidecar keeps the **original** hash `9c5cc187…9e87` |
| `p4-closure-candidate-targeted-adjudication-report-42ea24c.md` | `23496e6cb895c3ceb591947b9828de1e248ca4ed0f46c82282c1a1c256499567` | **unmodified** |
| `p4-second-finalization-pass-report-06ebfdb3.md` | `96ef5fe85016f2de5d5840814d95dd170947474a3259ac8bb902df9f485a1fa0` | **unmodified** |
| `p4-r07-closure-handoff.md` (this file) | see §J.1 | this cycle's handoff |

Each is classified in `docs/CANONICAL-DOCUMENTS.md` as **HISTORICAL (evidence)**, and the
second-finalization report's row carries its **reconstruction / `[UNAVAILABLE]`** caveat in the
authority map itself.

**Candidate attribution is exact and unchanged.** The re-review and the final adjudication name
`0891d1a` in their own headers; the first-finalization report names `86306d5`/`0891d1a`; the
targeted review and targeted adjudication name `42ea24c`; the second-finalization report names
`06ebfdb3`. **No report claims to have reviewed a commit it did not.** Nothing here reviewed the
R-07 closure commit — that is the next session's job.

**No secret or environment material is in any Git object.** `.env`, `.venv` and the Chrome profile
are outside every commit and every preservation tree; `.env` is recorded by path only.

### J.1 Hashes computed on the final tree

Computed after the last edit and recorded in the session output alongside the commit hash; each
tracked report has a `.sha256` sidecar beside it, and the two bannered documents follow the accepted
re-review's precedent (sidecar records the pre-banner original; `tail -n <original-lines>` of the
tracked file `cmp`s byte-identical to the preserved blob).

## K. Guard changes in this commit — what changed and why

| Guard | Change |
|---|---|
| `test_phase0_baseline_manifest.py` | `test_r07_is_never_described_as_contained` **replaced** (rule 20) by `test_r07_containment_record_holds_only_while_its_mechanical_conditions_hold` — a **state** check, not a flipped literal: it fails if any live/recorded violation edge exists, if the two surfaces disagree, if the production `GateRegistry` is populated, if the callback regains an actuator route, or if any evidence element is missing/mismatched. Plus a new `test_no_allowance_section_may_be_read_as_containment` carrying forward the permanent rule the old name protected. **Renamed** because the old name would have become an outright falsehood |
| `test_phase0_entry_points.py` | `test_r07_exposure_is_recorded_as_open_and_uncontained` — **name frozen**, body re-pointed; additionally pins the effect-capable-by-import set to exactly the two recorded, **test-only** quarantine importers |
| `test_docs_control_system.py` | `test_10_…` — name frozen, body re-pointed; requires exactly **one** bare `status: CONTAINED` in the manifest, every control document to record CONTAINED, none to describe it as OPEN, and **each to state the bound** |
| `test_roadmap_completeness_control.py` | R-07 guard **direction flipped, invariant unchanged** (consistency with the manifest, not a particular value); `_is_superseded_in_place()` added; `test_an_executing_phase_is_never_described_as_not_begun` de-vacuumed |
| `test_rebaseline_invariants.py` | both R-07 guards re-pointed; the record may read CONTAINED **only** inside the control state that authorizes it (P4 COMPLETE on a full fully-PASS contract, P5 sole READY) |
| `test_status_reality.py` | must record CONTAINED, must **not** describe R-07 as OPEN, must say completing P4 did **not** close it, must state the bound |
| `test_bootstrap_hermeticity.py` | inventory `meta.risk` must agree with the canonical record and carry the bound |
| `test_switch_consistency.py` | ADJ-01 — see §F |

**No guard was weakened to achieve a green result.** Every re-pointed guard gained assertions.

## L. Validation results (Step 12)

| Check | Result |
|---|---|
| Canonical suite (`pytest -c pytest-canonical.ini`) | see §L.1 |
| Clean-clone gate | see §L.1 |
| `TEST-NODE-MANIFEST` collection identity | live == recorded, 0 missing, 0 extra (**1964**) |
| Focused R-07 / status-reality / integration-topology / switch-consistency / documentation-control guards | see §L.1 |
| Hostile probes | see §L.1 |
| Repository topology | `PRODUCING` — recorded `42ea24c` == `HEAD^^`, `HEAD^` (`06ebfdb3`) pure status-metadata |
| Exactly one new content commit above `06ebfdb3` | yes |
| P4 / P5 / P6–P14 | COMPLETE / sole READY + NOT_STARTED / all nine BLOCKED |
| R-07 | mechanically **CONTAINED** |
| P5 implementation | none — `src/`, `configs/`, `data/` byte-identical to `0891d1a` |
| Production `GateRegistry` | EMPTY |
| Phase-8 deferral | intact |
| Residuals | all recorded; none discharged |
| Finalizer receipts | **not forged** — `SUITE-RESULT.json` and `GATE-RESULT.json` are byte-identical to `06ebfdb3` and still bind `42ea24c` / `1e2bba79` |
| Protected refs | unchanged; nothing pushed |

### L.1 Exact figures

Recorded in the session output that produced this commit, and reproducible by any reviewer with the
commands in §M.

## M. Prerequisites for the FRESH TARGETED INDEPENDENT REVIEWER

**You must not have** implemented P4, remediated it, authored the acceptance closure candidate,
conducted either earlier review or adjudication, run either finalizer, authored the reconstructed
second-finalization report, or authored **this** commit. Do not resume a prior session.

1. Verify identity from the object store, not from this document: `HEAD`, its tree, its single
   parent `06ebfdb3`, and `git rev-list --count --first-parent 06ebfdb3..HEAD == 1`.
2. Execute `test_status_reality.repo_state()` — expect **`PRODUCING`**.
3. Re-derive the changed-path set yourself (`git diff --name-status 06ebfdb3 HEAD`) and check it
   against §D–§K. **Locate every guard change mechanically, never by name from this handoff** —
   F-TR-05 is why.
4. Prove `src/`, `configs/`, `data/` tree-object equality against `0891d1a`, and audit the **single**
   `scripts/` change (§I) on its merits.
5. Re-run the canonical suite and the clean-clone gate in a disposable `git clone --no-local`,
   detached at the candidate, fresh venv, declared dependencies only, `PYTEST_ADDOPTS` cleared.
6. Re-run the hostile probes and the roadmap mutation battery yourself. **Confirm CB-01
   independently** — that M4 and M11 were already broken at `06ebfdb3`.
7. Adjudicate the questions this builder could not: was renaming
   `test_r07_is_never_described_as_contained` correct, or should the node name have been frozen?
   Is the `scripts/` mutation-battery change within an authorized content commit's scope? Is the
   `_is_superseded_in_place()` exemption narrow enough? Is CB-01 correctly deferred?
8. Re-probe both locks; confirm no builder or finalizer owns the repository.
9. Confirm `main`/`origin/main` at `152574e4…`, nothing pushed, no protected ref moved.

## N. Prerequisites for the THIRD FINALIZER

**Only after** a fresh targeted independent review **and** a separate targeted adjudication both
accept this candidate.

1. `HEAD` is exactly the accepted candidate and has **not moved** since the adjudication; both new
   preservation refs still parent to it.
2. `repo_state()` is **`PRODUCING`**.
3. **The working tree is clean.** `finalize_status.py` aborts on any dirty tracked file *before* it
   deletes receipts. Move untracked artifacts **out of band** (`cp`/`mv`) — **never** with
   `git checkout` / `restore` / `stash` / `clean`; `CLAUDE.md` §9 records that doing so once
   destroyed unrecoverable work here.
4. Hold `finalizer_lock` **exclusively**; `current_owner()` is `None` first. **AD-02 applies: treat
   a refusal as authoritative and never reclaim the lock because a log file is missing.**
5. No builder owns the worktree; no `mutate_*` or `clean_clone_gate` run is in flight.
6. Expect the metadata commit to touch **only** members of `STATUS_METADATA_FILES`.
   `phase-0-baseline-manifest.yaml` **must not** appear. `build_status_errors()` must remain `[]`.
7. Exactly **one** finalizer. No re-run. No forged receipt.
8. `main` untouched; nothing pushed. Integration is fast-forward-only under **R-21** and is a
   separate founder-authorized act.

## O. Required sequence after this session

```
fresh targeted independent review
  -> separate targeted adjudication
    -> exactly ONE third finalizer
      -> P4 / R-07 campaign closure verification
        -> only then may P5 begin
```

**Do not begin P5.** `READY` is a selection, never a claim of progress, and P5's own **G2**
transition/event blocker is separately undischarged.

## P. Contradictions and remaining blockers

| Item | Standing |
|---|---|
| **CB-01** | Two roadmap mutation cases (M4, M11) prove nothing. Pre-existing at `06ebfdb3`; deliberately not fixed here; recorded for the next cycle |
| **AD-02** | `finalizer_lock.py` still has zero committed coverage and is load-bearing for the **third** finalizer |
| **RR-01** | Binding P12 precondition, undischarged, compounded by F-08 and F-09 |
| **G2** | Undischarged; blocks P5's event content independently of everything above |
| **PD-01** | External-tool ambiguity; will recur at the next finalization until the driver's resolver is corrected |
| **The one `scripts/` change** | Disclosed in §I; a reviewer may legitimately conclude it belonged in a separate commit. This builder judged that leaving a knowingly broken mutation anchor was worse |
| Otherwise | **No contradiction found between repository authority and this candidate.** |

## Q. Scope of this document

A handoff and nothing else. It ran no finalizer, wrote no status metadata beyond the authored
content described above, marked no phase complete, awarded no criterion, performed no review and no
adjudication, amended nothing, moved no protected ref, pushed nothing, merged nothing, deployed
nothing, contacted no external system and enabled no effect. It did not begin P5.

**Stop at the control boundary.**
