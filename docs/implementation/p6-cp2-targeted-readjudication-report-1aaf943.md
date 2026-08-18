# P6-CP-2 — TARGETED RE-ADJUDICATION AGAINST THE INDEPENDENT REVIEW — candidate `1aaf943`

> ### **VERDICT: ACCEPT — M2 MAY PROCEED TOWARD LANDING.**
> Machine **M2 — the Pipeline Instance**. Candidate content commit `1aaf9439e89f`, tree
> `1d859547798c`, parent `cc986dd`. **No blocking defect survives.** F-01 and F-02 are CLOSED and I
> re-derived both myself. All seven independent-review findings R-1…R-7 are **NONBLOCKING**, and
> **one of them (R-3) is materially wrong** — I disproved it by mutation. The remaining landing
> conditions are **procedural and environmental, not defects in the candidate.**
> ### **This is an adjudication, not a landing and not a finalization.** No P6 criterion is scored,
> no product code was modified, the finalizer was not run, and M3 was not begun.

| | |
|---|---|
| **Adjudicator lineage** | A session that did **not** implement, remediate, or independently review this candidate, and authored none of `3d4046a`, `8bb4cb0`, `1aaf943`, the independent review, or the prior (pre-review) adjudication. |
| **Supersedes** | `refs/preserve/p6-cp2-targeted-adjudication-1aaf943` (verdict *BLOCKED ON EVIDENCE*, created **before** any independent review existed). See **§4 — the R-4 ruling**. |
| **Independence discipline** | Every load-bearing claim re-derived here with probes I wrote. I read both prior reports **only to adjudicate them**, and re-executed every claim I rely on. |
| **Tree state** | Verified byte-identical to `HEAD` after every probe and mutation, by `git hash-object` blob identity. `git checkout` / `restore` / `stash` / `clean` were **never** used to undo a mutation. |

---

## 1. ADJUDICATION VERDICT

### **ACCEPT.**

The two defects that rejected predecessor `3d4046a` are closed **structurally** — in the derivation
of a population and in the first executable statement of a guard, not at a call site. I confirmed
both with probes of my own that fire on their positive controls. The candidate does not overclaim:
`landed_checkpoints` names exactly `['P6-CP-1']`, `criteria_scored` is `[]`, zero P6 acceptance
criteria are scored, and `P6-CP-2` sits under `candidate_awaiting_review`.

**ACCEPT is not a landing.** §7 lists the exact conditions that remain, all of them procedural or
environmental.

---

## 2. F-01 and F-02

### F-01 — `CLAIMED` reachable without the CAS: **CLOSED**

Re-derived here, not inherited:

| What I checked | Result |
|---|---|
| The derivation is genuine, not a hand list | `CONSEQUENTIAL_ROW_IDS` (seeds) = `{PL-8, PL-9}`; `KERNEL_OWNED_ROW_IDS` = `{PL-8, PL-8f, PL-9}` — **`PL-8f` enters the population without being named**, via the `(from_state, trigger)` closure |
| The refusal cannot be pre-empted by a row branch | **AST-verified**: the `row.id in KERNEL_OWNED_ROW_IDS` refusal is the **first executable statement** of `_guard_problem` (line 2095), ahead of the trigger-type authority check and ahead of every row branch |
| Only the kernel reaches the dangerous states | Rows reaching `GRANTED`: `['PL-8']`; reaching `CLAIMED`: `['PL-9']` — **both kernel-owned** |
| Population is non-vacuous | Asserted non-empty before believing the sweep |
| P3's claim CAS was not weakened | Extracted the `GRANTED→CLAIMED` CAS blocks from `cc986dd` and `1aaf943`: **byte-identical**, predicates intact. `checkpoint.py` grew 66,876 → 75,622 bytes and **the CAS is untouched** |

> **Disclosure of my own harness error.** My first CAS comparison used an unbraced `$rev:path` in
> zsh, where `:s` is a history modifier — both `git show` calls failed, both block lists were
> **empty**, and my script printed *"BYTE-IDENTICAL"* over a zero-size population. That is the exact
> §9 false-green it exists to catch. I added a `len(a)>0 and len(b)>0` population guard and re-ran;
> the 2-block comparison above is the trustworthy result.

**Adjudicated: CLOSED.**

### F-02 — the "ships dark" guard was false-green: **CLOSED**

I did not re-run the candidate's walker. I wrote my own AST closure over all seven import
spellings plus `importlib`/`__import__`:

- M2's roots (`pipeline_instance`, `migrations.phase6_pipeline_instances`): closure **24 modules**,
  **effect-capable adapters reached: NONE**
- **Positive controls FIRE** — `effect_boundary` (39 modules) and `governed_write_route` (41) each
  reach `['browser_use_write', 'tms_write']`. My walker is not blind.
- **Production importers of `pipeline_instance`: NONE**

**Adjudicated: CLOSED.** M2 ships dark.

---

## 3. RULING ON EACH FINDING R-1 … R-7

| # | Independent review's class | **My ruling** | Landing-blocking? |
|---|---|---|---|
| **R-1** | MEDIUM · occurrence-key escape hatch | **UPHELD — accurate** | **NO** |
| **R-2** | MEDIUM · NEW · PL-1b concurrency | **UPHELD — reproduced independently** | **NO** |
| **R-3** | LOW · landing gate never checks report exists | ### **OVERTURNED IN PART — the headline is FALSE** | **NO** |
| **R-4** | LOW · PROCESS · adjudication predates review | **UPHELD — and acted on.** See §4 | **NO** (resolved by this report) |
| **R-5** | LOW · "byte-identical" imprecise | **UPHELD — confirmed exactly** | **NO** |
| **R-6** | LOW · F-02 narrative overstates the miss | **UPHELD — confirmed exactly** | **NO** |
| **R-7** | LOW · docstring claims derivation | **UPHELD — confirmed exactly** | **NO** |

### R-1 — UPHELD. Real §8 gap, unexploited on this tree.

`test_no_free_form_occurrence_key_is_readable_from_the_request_payload` exempts any
`occurrence_key` read carrying `CANONICAL-ROW-READ:` within ten lines above, and asserts only
`assert annotated` — *some* annotated site exists. That **pins no exact set**, which is what
CLAUDE.md §8 requires ("membership, not counts — a same-count substitution must fail").

I enumerated the real population myself: **exactly one** annotated site,
`src/freight_recon/pipeline_instance.py:2541`, and **zero** unannotated offenders. That site reads
`row["occurrence_key"]` — **a database column off this system's own persisted row**, which is the
opposite of the caller-authored-payload defect P1 closed.

**Nonblocking:** no invariant is violated on this tree, and the hatch is opt-in, self-naming and
visible in review. **Recorded as debt; the recommendation to pin the exact set is correct.**

### R-2 — UPHELD. I reproduced it independently, and the safety invariant holds.

I wrote my own 8-thread / 8-connection probe against a sequential control:

| | live attempts persisted | `absorbed_count` | `DuplicateProposalAbsorbed` |
|---|---|---|---|
| **sequential** 1 + 7 duplicates | **1** | **7** | **7** |
| **concurrent** 1 + 7 duplicates | **1** | **0** | **0** |

Concurrent outcomes: `{started: 1, ReservationHeld: 7}`.

**The safety invariant holds in both modes — one attempt, one effect, no double bill.** The Layer-1
UNIQUE index is the enforcer and it works under genuine contention. `propose()` reads-then-writes;
a racer that loses the index gets a **typed** `ReservationHeld` whose message names the correct
remedy ("should be absorbed onto it (PL-1b), not retried"). **The failure is loud, not silent.**

What does not hold is the **record**: raced duplicates appear in no operator count. I confirmed the
reviewer's companion claims — `ReservationHeld` appears in the battery **only as an import**
(line 96, never asserted), there is **no `threading` anywhere** in the M2 battery, and
`test_two_attempts_racing_one_effect_produce_exactly_one_live_reservation` is **sequential on one
connection**. The implementation record (line 185) describes that sequential test as
*"five proposals racing one effect"*.

**Adjudicated NONBLOCKING TECHNICAL DEBT, not a required M2 remediation.** Against §13.3's test:
(a) no wrong customer outcome — verified under contention; (b) no invariant violated — the absorb
*count* is an operational metric, and §14 PL-1b's "one card" is satisfied; (c) a later phase is not
made unsafe — the refusal is typed and actionable, M2 ships dark with **zero** production importers,
and the fix is local to `propose()`'s `except` branch, not a rewrite of certified code (§13.4).

**Landing condition attached (documentation only, §7.3):** the debt row must be recorded, and the
implementation record must stop calling the sequential test "racing". **Must be resolved before the
first concurrent proposer — M9's billing sweep — arrives.**

### R-3 — OVERTURNED IN PART. The landing gate *does* check existence.

The reviewer's headline — *"the landing gate never checks that the cited review report exists"* —
is **false at repository level**, and the prior adjudication's contradicting mutant (L1: CAUGHT)
was right. I settled it by mutation, repointing P6-CP-1's citation at a nonexistent file:

| Guard | Result under the mutant |
|---|---|
| `test_status_reality.py` | **GREEN** (exit 0) — the reviewer is correct **about this guard**, which tests truthiness only |
| `test_roadmap_completeness_control.py:240` | ### **RED** — `AssertionError: P6-CP-1: cited report docs/implementation/THIS-FILE-DOES-NOT-EXIST.md missing` |

Baseline and post-restore: **118 passed, exit 0**; registry restored byte-exact
(sha256 `080afd92…`, unchanged).

**The existence check exists; it lives in a different guard file than the reviewer probed.** No
repository gap, and **no remediation is owed.** R-3 is downgraded to an accuracy defect *in the
review*, recorded here so a later session does not act on a false premise.

### R-5 / R-6 / R-7 — UPHELD, all accuracy-class, none blocking.

- **R-5:** `8bb4cb0 → 1aaf943` is **+52 / −1 across three documentation files**
  (`CURRENT.md`, `IMPLEMENTATION-REGISTRY.yaml`, the implementation record) and **zero difference
  under `src/`, `eval/` or `scripts/`**. "byte-identical" is imprecise; the substantive claim — no
  runtime delta — **holds exactly**.
- **R-6:** `EFFECT_CAPABLE_ADAPTERS` has 8 names; **6 exist on disk**; `browser_agent` and
  `browser_tms_adapter` are **absent** (historical, deleted EP paths). So exactly **one** real leak
  vector (`discovered_write`) was missing from the old hand list — enough, as F-02 shows, to defeat
  every spelling. Confirmed.
- **R-7:** `test_phase6_work_item.py:2553` says the permitted set "is derived from the P6 modules on
  disk rather than typed out"; line **2555** is the literal `{"work_item.py", "pipeline_instance.py"}`,
  guarded by an existence check. **The guard is sound; the sentence is not.** The `path.name`
  collision the reviewer notes is confirmed at lines 2571/2575.

---

## 4. THE R-4 RULING — the prior adjudication is SUPERSEDED

**R-4 is UPHELD, and this report is the remedy.**

The facts, verified from the object store:

| Artifact | Commit | Timestamp | Verdict |
|---|---|---|---|
| Prior targeted adjudication | `3e0acd67` | **2026-08-17 17:54:01** | BLOCKED ON EVIDENCE |
| Fresh independent review | `06ab01f7` | **2026-08-17 18:38:42** | ACCEPT |

### **RULING: the pre-review adjudication does NOT satisfy the route's third step, and targeted adjudication MUST be — and now HAS been — re-performed against the independent review.**

The canonical route is *candidate → fresh independent review → **separate adjudication** → exactly
one finalizer*. An adjudication that **could not have read the review it is supposed to follow** is
not that third step; it inverted the order. This is not a technicality:

- The prior adjudication's **own blocking condition was the missing review artifact** — it recorded
  *"Independent review report artifact — MISSING. This is what blocks the landing"* and named the
  exact next act as the reviewer writing and preserving it. **That act has now occurred.**
- The review it never saw returned **seven findings, two of them new and material** (R-1, R-2).
  **Neither R-1 nor R-2 appears anywhere in the prior adjudication**, so no session had ever weighed
  them until this one.

**Disposition of the prior adjudication:** it is **retained, not discarded**. Its F-01/F-02
re-derivations are sound and I independently corroborate them; its **N-01 preservation act**
(`refs/preserve/p6-cp2-product-driver-bypass-evidence-1aaf943`) was correct and durable, and it
resolved a real evidence gap. It stands as preserved evidence of the route's first attempt. **It is
superseded as the adjudication of record by this report**, which is why this artifact is named a
*re-adjudication* — the same convention `p5-u51-targeted-readjudication-d59b740` established.

**Its `P6-D14` assignment does not survive** — see §5.

---

## 5. TWO FINDINGS OF MY OWN

### A-01 — a three-way `P6-D14` collision · **MUST be resolved in the landing commit**

Three artifacts assign the same debt ID to three different findings:

| Source | What it calls `P6-D14` |
|---|---|
| `p6-cp2-pipeline-instance-implementation-record.md:217` | the co-commit partner halves owed by M3/M4 |
| Prior adjudication §B / §E | the unpreserved `3d4046a` rejection review |
| Independent review R-2 | the PL-1b concurrency absorption gap |

`P6-D15` and `P6-D16` are also already taken by the implementation record. **The next free ID is
`P6-D17`** (`P6-D10` is unused but reusing a skipped ID is worse for an audit). **Nonblocking**, but
a landed history carrying one ID for three findings is not resolvable later, so the landing commit
must assign distinct IDs.

### A-02 — the untracked review report makes the tree dirty, and the finalizer refuses dirty trees

I measured the suite as **3007 passed · 20 failed · 3 skipped = 3030**, where both prior sessions
measured **3009 · 20 · 1 = 3030**. **This is not a discrepancy and not a regression** — the
denominator is identical and reconciles exactly with `TEST-NODE-MANIFEST.json` (`node_count: 3030`).
The delta is two tests that **skip on a dirty working tree**:

```
SKIPPED eval/tests/test_status_reality.py:126  NOT-RUN: dirty working tree — committed-state
                                               consistency cannot be measured here
SKIPPED eval/tests/test_status_reality.py:170  NOT-RUN: dirty working tree — ... canonical
                                               finalization refuses dirty trees and TREATS THIS
                                               SKIP AS FAILURE
```

The tree is dirty for exactly one reason: `p6-cp2-independent-review-report-1aaf943.md` is
**untracked**. **This is a concrete landing condition** — the landing content commit must
*materialize* the review report and this adjudication report on disk, which is precisely the
sequence P6-CP-1 followed. Recorded here because it would otherwise surface as a mysterious
finalizer refusal.

---

## 6. THE INDEPENDENT-REVIEW ARTIFACT, AND THE CLEAN-CLONE GATE

### The review artifact — **EXISTS, CORRECTLY PRESERVED AND CORRECTLY PARENTED**

| Check | Result |
|---|---|
| Ref exists | `refs/preserve/p6-cp2-independent-review-1aaf943` → `06ab01f79cbd` |
| **Parentage** | parent = **`1aaf9439e89f`** — bound to the candidate it describes ✅ |
| Contents | adds **only** the 363-line report; **no** runtime, test, fixture or status file touched ✅ |
| In-tree copy | **byte-identical** to the preserved copy (sha256 `1bcd37d5ab38…f2fdb0`) ✅ |
| Verdict | ACCEPT FOR SEPARATE TARGETED ADJUDICATION ✅ |

### The clean-clone gate — **FAILS HERE, AND THE FAILURE IS ENVIRONMENTAL**

I executed it. Steps 1–5 pass; step 6, *install declared deps only*, fails:

```
SSLError(SSLCertVerificationError('OSStatus -26276')) — https://pypi.org/simple/hatchling/
CLEAN-CLONE GATE FAILED at: install declared deps only (exit 1)
```

**Proven candidate-independent, not asserted:**

1. The candidate touched **no** dependency declaration — `git diff cc986dd..1aaf943 -- pyproject.toml
   setup.py setup.cfg requirements*.txt scripts/clean_clone_gate.py` is **empty**.
2. The failing step fetches a **build backend** (`hatchling`) from pypi.org before any repository
   code is exercised.
3. `pypi.org` is unreachable from this host at the socket layer (`gaierror`), and via pip the
   certificate chain is intercepted.
4. The committed receipt `GATE-RESULT.json` records **`passed: true`** at commit `da84806` (the
   P6-CP-1 landing) with **`failed: 0`**, 2870 collected — **a capable host exists and the gate is
   achievable**.

> **Disclosure — I dirtied a tracked file and repaired it.** Running the gate **overwrote the
> committed `docs/implementation/GATE-RESULT.json`** with a `passed:false` receipt bound to
> `1aaf943`. I restored it from the object store with `git cat-file blob`
> (**never** `checkout`/`restore`/`stash`/`clean`), purged `__pycache__`, and verified restoration
> by blob identity: `git hash-object` = `46019832d1c1a69217dad9d7698bdcff8b3d8fcb`, matching
> `HEAD`'s blob exactly. The working tree is back to its session-start state.

### **Is a clean-clone PASS from a capable host still a mandatory landing condition? — YES.**

**It is enforced mechanically and is not within my discretion to waive.**
`scripts/finalize_status.py` **executes the gate itself** and refuses on failure:

```
158  rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "clean_clone_gate.py")], ...)
162  raise _refuse(f"the clean-clone gate failed (exit {rc})")
164  raise _refuse("the clean-clone gate wrote no result - a PASS with no record is not a PASS")
```

The P6-CP-1 landing record states the same rule in words: **"The finalizer executing this landing
re-runs both in full."** The precedent is therefore *not* that a landing may proceed without the
gate — it is that the **review and adjudication sessions may record an environmental limitation
honestly, and the finalizer, on a capable host, is what actually discharges it.** That is exactly
the posture of this report.

---

## 7. EXACT REMAINING LANDING CONDITIONS

1. **This adjudication report on disk and preserved** — done by this session (§9).
2. **ONE landing content commit**, by a session that is not this one, which:
   - materialises `p6-cp2-independent-review-report-1aaf943.md` **and** this report under
     `docs/implementation/` (A-02: this is what clears the dirty tree);
   - moves `P6-CP-2` from `candidate_awaiting_review` into `landed_checkpoints`, citing both reports,
     with **`criteria_scored` unset**;
   - records the nonblocking residuals **R-1, R-2, R-5, R-6, R-7, A-01, A-02** with **distinct debt
     IDs from `P6-D17` upward** (A-01), and corrects the implementation record's line 185
     description of the sequential test as "racing" (R-2).
3. **EXACTLY ONE canonical finalizer run**, under an exclusively-held `finalizer_lock`, by a session
   in **none** of the build, review or adjudication lineages — producing one status-metadata commit
   touching only `STATUS_METADATA_FILES`.
4. **From a host that reaches pypi.org over untampered TLS and permits `socket.bind`**, so the
   finalizer's clean-clone gate returns a genuine PASS and the 20 environmental failures resolve.

**Not owed, and must not happen:** no P6 criterion may be scored; P6 is **not** COMPLETE; M3 may not
begin; and nothing here lands anything.

---

## 8. THE DIRECT ANSWERS

| Question | Answer |
|---|---|
| **May M2 land now?** | **No — but no defect blocks it.** Conditions §7.2–§7.4 remain, all procedural/environmental. |
| **May the P6 finalizer run now?** | ### **No.** Two independent reasons: **role separation** — I am the adjudicator, and the P6-CP-1 precedent requires "a session that is not this one"; and it **would refuse anyway** — the clean-clone gate fails here and the tree is dirty. |
| **May M3 begin?** | ### **No.** P6-CP-2 has not landed. Separately, **P6-D11 is a hard boundary**: eight of M2's 25 rows are `CONSUMES` and emit nothing on a **strict-order** aggregate, so the F2 stream has gaps that would **permanently park** the first real consumer. That consumer is M3. It must be resolved before M3, and it is **not** discharged by M2 landing. |
| **May any P6 criterion be scored?** | ### **No.** `criteria_scored` stays `[]` until all 13 machines and 134 transitions land and a **separate final adjudication** sets the fourteen weighted criteria. |
| **Is further remediation or review required?** | ### **No.** No blocking defect survives. All seven findings plus my two are recorded, not actioned (§13.3) — **the debt row is the complete deliverable.** |

---

## 9. WHAT THIS ADJUDICATION CHANGED, AND ROLE SEPARATION

**Nothing in the product, and no status field.** No file under `src/`, `eval/` or `scripts/` was
modified; no registry field was edited; `criteria_scored` remains `[]`; `landed_checkpoints` still
names exactly one entry; no branch was moved and **nothing was pushed**.

Implementer, reviewer and adjudicator remain three distinct sessions, and a **fourth** must
finalize. Every mutation used in-memory save/restore with `__pycache__` purging and blob-identity
verification; `git checkout` / `restore` / `stash` / `clean` were never used to undo one. The one
tracked file this session dirtied (`GATE-RESULT.json`, by executing the gate) was restored from the
object store and verified byte-exact.

**Evidence I executed myself:** the full canonical suite on the final tree (3007/20/3 = 3030,
reconciling with the manifest) · the 55-mutant M2 battery (**55/55 caught**, tree byte-exact after)
· the clean-clone gate · my own kernel-population and `_guard_problem` AST probes · my own dual
import-closure walker with live positive controls · the CAS byte comparison across `cc986dd`/`1aaf943`
· my own 8-thread PL-1b concurrency probe with a sequential control · the M-LAND landing-gate
mutation that overturned R-3 · the occurrence-key population enumeration · registry reconciliation.

---

*Targeted re-adjudication performed by a session that neither implemented, remediated, nor
independently reviewed this candidate, and did not author the prior pre-review adjudication it
supersedes. It is an adjudication — not a review, not a landing, and not a finalization. Preserved
at `refs/preserve/p6-cp2-targeted-readjudication-1aaf943`, parented on `1aaf943`. The branch was not
moved and nothing was pushed.*
