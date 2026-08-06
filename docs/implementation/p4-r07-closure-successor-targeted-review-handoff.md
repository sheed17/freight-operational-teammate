> # ⛔ HANDOFF — NOT CURRENT AUTHORITY, AND NOT A REVIEW
> **This is a builder's handoff to a fresh targeted independent reviewer.** It certifies nothing,
> adjudicates nothing, sets no acceptance criterion, closes no risk and authorizes no finalization.
> The status authority is [`CURRENT.md`](CURRENT.md) and the registry; the operating guide is
> [`../../CLAUDE.md`](../../CLAUDE.md).
>
> ### **DO NOT TREAT ANY CLAIM BELOW AS EVIDENCE.** Re-derive every one from the object store and
> from execution. The P4 remediation handoff was wrong about two numbers (RR-02); the handoff for
> `42ea24c` named a guard function that does not exist (F-TR-05); and `4d12b0e`'s own commit
> message misstated its suite population (R-05). A reviewer who trusted any of them would have
> reported a false result. That is exactly why a handoff is never review evidence — including
> this one, and including its §7 disclosure of a probe of mine that returned green without biting.

# P4 R-07 CLOSURE — SUCCESSOR REPLACEMENT CANDIDATE, TARGETED REVIEW HANDOFF

**Certified parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (second-finalizer metadata commit)
**Branch:** `p4/adapter-containment-completion`
**Replaces rejected replacement candidate:** `4d12b0e41cfa722fa74338903526c4bbc52cf65a`
**Which itself replaced rejected candidate:** `11c911244304d56737913db41b458d5f3278bc80`

This candidate's own commit and tree hashes are not embedded here — this file is *inside* the tree
it would describe. Verify them mechanically:

```
git rev-parse p4/adapter-containment-completion            # the candidate
git rev-parse p4/adapter-containment-completion^{tree}     # its tree
git rev-list --parents -n 1 p4/adapter-containment-completion   # exactly one parent, = 06ebfdb3
```

**Builder standing.** This session did not implement P4, did not author `11c9112`, did not author
`4d12b0e`, did not conduct either candidate's targeted review or targeted adjudication, and did not
run either finalizer. No previous session was resumed. It reviewed nothing, adjudicated nothing,
ran no finalizer, began no P5 work, enabled no effect, moved no protected ref and pushed nothing.

**This document is a HANDOFF. It certifies nothing, reviews nothing and adjudicates nothing.**

---

## 1. WHAT WAS AUTHORIZED, AND WHAT WAS BUILT

The targeted adjudication of `4d12b0e` returned **REJECT — TARGETED REMEDIATION REQUIRED** and
authorized exactly one path (§8.3 Option A): replace `4d12b0e` in place against certified parent
`06ebfdb3`, preserving it first the way `11c9112` was preserved. A second consecutive content
commit is mechanically forbidden by `repo_state()`; no metadata path can carry a parser fix; no
merge is permitted. That is the path taken.

R-07's **technical containment**, **F-01** and **F-03** were ratified by that adjudication and are
**not reopened**. They are carried forward unchanged and re-verified (§7, §8).

| Finding | Adjudicated status | Disposition here |
|---|---|---|
| **R-01** cross-cell table claims | **BLOCKING** | Remediated — the claim unit is now the ROW (§3) |
| **R-02** `<details>` stripped unlabelled | **BLOCKING** | Remediated — live by default, label-gated (§4) |
| **R-03** ungoverned historical marker | non-blocking, in scope | Remediated — the marker must GOVERN (§5) |
| **R-04** quote parity bounded by paragraph | non-blocking, in scope | Remediated — bounded by the row (§5) |
| **R-05** stale suite figures in the message | non-blocking, mandatory | Corrected, and the false line named as superseded (§6) |

---

## 2. EXACT CHANGED PATHS

**Versus `4d12b0e` — 12 paths, all modifications. No additions, no deletions, no renames**
(this handoff and its sidecar make 14 in the final tree):

| Path | Δ | Why |
|---|---|---|
| `eval/control/status_claims.py` | +614 | R-01, R-02, R-03, R-04 — the whole parser correction |
| `eval/tests/test_roadmap_completeness_control.py` | +295 | 26 new regression tests; one `claim_units` caller adapted |
| `scripts/mutate_roadmap_completeness.py` | +271 | M22–M40, negative cases, failure-reason verification |
| `docs/implementation/TEST-NODE-MANIFEST.json` | 30 | regenerated: 2018 → 2044 nodes |
| `eval/tests/test_status_reality.py` | 12 | delegate to the one label-aware details definition |
| `eval/tests/test_docs_control_system.py` | 11 | same delegation |
| `eval/tests/test_false_green_defenses.py` | 11 | same delegation |
| `eval/tests/test_switch_consistency.py` | 9 | same delegation |
| `eval/tests/test_bootstrap_hermeticity.py` | 8 | same delegation |
| `docs/implementation/phase-0-baseline-manifest.yaml` | 4 | R-03: move a trailing historical label into governing position |
| `docs/implementation/PHASE-OUTPUTS.md` | 2 | R-03: same |
| `docs/implementation/pr-sequence.md` | 2 | R-03: same |

**Versus `06ebfdb3` — 52 paths** (`4d12b0e`'s 51, plus `eval/tests/test_false_green_defenses.py`).

**No path under `src/`, `configs/` or `data/` is touched, at either comparison.**

---

## 3. R-01 — ROW-AWARE PARSING

### 3.1 The defect, reproduced

`claim_units()` split a table row on `|` and yielded each **cell** as an independent claim unit,
never re-associating them. A row naming the risk in one column and its status in another produced
two units — one with the subject and no polarity, one with the polarity and no subject — and both
were discarded. That is not a narrower F-02; it is the same defect class displaced by one column.

The three live rows this made invisible, located **mechanically** (not by line number):

| Document | Line | Subject cell → status cell |
|---|---|---|
| `docs/implementation/CURRENT.md` | 105 | 1 → 3 |
| `CLAUDE.md` | 73 | 1 → 2 |
| `README.md` | 63 | 1 → 2 |

### 3.2 The design

A markdown table row is **one record**; its cells are that record's **fields**. The claim unit is
now the whole row. Association is bounded to **exactly one row**:

* **within** a row — across any cells, in any column order, with any number of descriptive columns
  before, between or after subject and status;
* **never** across rows, **never** across tables, **never** between a row and surrounding prose.

Cells are joined by a literal `` | `` for the polarity decision. That is what keeps the *token
sequences* per-cell while the *association* spans the row: `\w+` and `[-\s]+` cannot consume a
pipe, so `… is not | contained …` never reads as negated containment and `| OPEN | risks |` never
reads as the register noun *open risks*.

Structured provenance retained on every claim: document, line, `table_id`, `row_index`, ordered
`cells`, `subject_cell`, `status_cell`, plus a `where` property — so a failure names **which cell**
asserted the polarity, not merely which file.

Handled: header rows and separator/alignment rows (structure, never claims) · leading and trailing
pipes present or omitted (a delimiter row establishes the table) · escaped pipes (`\|` is content) ·
inline code, emphasis and links inside cells · empty cells · a prose line that merely *contains* a
pipe (not a row).

### 3.3 Structural decisions ignore code

`<details>` and table pipes inside a fenced block or inline code span are **literal mentions**, not
markup. `CURRENT.md` discusses `` `<details>` `` in backticks *inside* a `<details>` block; a depth
tracker that counted it would mis-pair every later block. The mask governs **structure only** — it
never removes text from a claim, so nothing gains an exemption by being written in backticks, and a
fenced sample is still **read**. Creating a blanket fence exemption would have repeated exactly the
mistake R-02 exists to close.

---

## 4. R-02 — DETAILS-AWARE PARSING

### 4.1 The defect

`strip_historical_blocks()` deleted **every** `<details>…</details>` region before parsing, under a
docstring asserting *"Explicitly-labelled"* and code that checked for no label at all.

This is not a docstring mismatch. `docs/implementation/CURRENT.md` preserves an incident in which a
**false transition claim** was planted inside a `<details>` block, and states the derived control
requirement in its own words: the drift guard *"requires historical blocks to be self-labelling
rather than silently trusted."* The parser silently trusted all of them.

### 4.2 The design — parse by default, exclude only on proof

* Details content is **parsed as LIVE**.
* It is excluded from live counts only when **that exact block is self-labelling**.
* The marker is read from **the block's own `<summary>`**, or — absent one — **its own first
  non-blank body line**. It is found by *parsing the block*, never by proximity search.
* The vocabulary is **CLOSED**: `HISTORICAL` / `SUPERSEDED` (`_HISTORICAL_MARKER`), which is what
  every labelled block in this corpus already uses. It was **deliberately not widened**. The
  adjudication called `ARCHIVED` and `REJECTED EVIDENCE` *reasonable additions that must be added
  explicitly, never matched loosely*; until that deliberate act happens, a block labelled only
  "Rejected evidence" is **read**, which is the fail-closed direction.
* A label in the prose **above** a block exempts nothing.
* Nesting is **depth-tracked**, and a block **never inherits** its parent's label — an unlabelled
  block inside a labelled one is **LIVE**.
* Malformed structure **fails closed**: an unterminated `<details>` grants no exemption at all; a
  `<summary>` that is never closed yields no marker; a stray `</details>` is ignored.
  `details_structure_defects()` reports all three so a guard can fail loudly.
* Excluded content is **exempt and visible**, never deleted — an excluded claim stays auditable
  *as* excluded, and reported line numbers are now the document's **real** line numbers.

### 4.3 One semantics, not six

The identical unlabelled-`<details>` hole existed in **six** copies across the guard modules, each
with a docstring asserting a check none performed. All six now delegate to the one label-aware
definition:

`test_docs_control_system.py` · `test_roadmap_completeness_control.py` ·
`test_switch_consistency.py` · `test_status_reality.py` · `test_bootstrap_hermeticity.py` ·
`test_false_green_defenses.py`

This matters **beyond R-07**: the incident actually recorded in `CURRENT.md` was a false **phase
transition** claim, which the R-07 parser never guarded. Fixing only `status_claims` would have
left the real incident channel open while citing that incident as the reason it was blocking.

**Reviewer note — a deliberate scope judgement.** The adjudication's §9 scope names the parser.
Delegating the other five is a one-line change each that strictly *narrows* duplication and
strictly *strengthens* the control, and it is the same anti-drift principle the adjudication itself
applied to the unified corpus definition. Every `<details>` block in the corpus today is already
labelled, so the change is behaviour-neutral on the current tree — verified by the full suite. If a
reviewer judges this outside scope, it is separable: it is confined to those five one-line
delegations.

---

## 5. R-03 AND R-04

### R-03 — the historical marker must GOVERN the claim

Matched anywhere on the risk id's source line, so
`R-07 remains OPEN and NOT CONTAINED today; nothing here is SUPERSEDED.` exempted itself with a
trailing clause. It is now scoped **exactly as `_CONDITIONAL` is** — it must appear **before the
risk id, within the claim unit**. One marker discipline now governs the module instead of two
contradictory ones.

**Consequence, disclosed.** Three genuinely historical claims carried their label *after* the claim
it labelled and therefore became live under the corrected rule. Each label was **moved into the
governing position**; no claim's wording, meaning or historical status changed:

| Document | Claim | Change |
|---|---|---|
| `docs/implementation/PHASE-OUTPUTS.md` | "R-07 stays OPEN through P3" | `*(HISTORICAL — …)*` moved before the claim |
| `docs/implementation/pr-sequence.md` | "R-07 stays OPEN at P0" | `*(HISTORICAL — …)*` moved before the claim |
| `docs/implementation/phase-0-baseline-manifest.yaml` | "…kept R-07 OPEN" | `HISTORICAL, SUPERSEDED -` moved to sentence start |

This is the opposite of laundering: each historical claim is now **structurally bound** to its
label rather than merely adjacent to it.

### R-04 — quote parity is bounded by the claim unit's own block

F-05's fix counted parity from the preceding blank line. A markdown table has **no blank lines
between rows**, so the whole table was one parity window and an unbalanced `"` in an early row
exempted every later row. Parity is now counted from the block `_blocks()` already computes, and a
table row **is** its own block.

---

## 6. R-05 — THE COMMIT MESSAGE

`4d12b0e`'s message stated *"2014 passed / 0 failed / 3 skipped / 2017 collected"*. That was
inaccurate: `2014 + 3 = 2017` cannot be reconciled with `TEST-NODE-MANIFEST`'s `node_count: 2018`,
and the reproduced result on that tree was **2017 / 0 / 1 / 2018**.

This candidate's message states its **own independently reproduced** figures and **names the
`4d12b0e` line as inaccurate and superseded**.

**Verified: no guard reads a commit message as authoritative state.** Authority is
`SUITE-RESULT.json` — written only by `run_canonical_suite.py` from a real run — and
`TEST-NODE-MANIFEST.json`. A commit message is narrative testimony accompanying them, never a
receipt.

---

## 7. WHAT WAS RETAINED — F-01, F-03, CONTAINMENT

### F-01 — retained

All ten stale false claims stay corrected with superseded wording quoted in place under explicit
markers. **Zero live OPEN claims** across the unified population — and this is now the stronger
statement, because it is measured by a parser that can see the constructions the corpus actually
uses. The three R-03 label moves are the only documentation edits, and none touches a corrected
claim's wording.

### F-03 — retained, hostile battery re-run against the new parser

Re-run in a **distribution clone carrying ZERO `refs/preserve/*`** (tier 1 only), restoring between
cases; baseline **26 passed** before and after:

| Hostile case | Result |
|---|---|
| `ACCEPT` → `REJECT` in the load-bearing adjudication | **1 failed** ✅ |
| sidecar content changed | **2 failed** ✅ |
| sidecar missing | **1 failed** ✅ |
| report missing | **5 failed** ✅ |
| required banner removed | **5 failed** ✅ |
| body substituted under a valid banner | **15 failed** ✅ |

The two-tier clean-clone/ref-backed model is **unchanged and not weakened** — no code in
`test_evidence_binding.py` was modified.

> **Disclosed harness note.** A first attempt at the banner-substitution case replaced only the
> phrase `ACCEPT FOR SEPARATE FINAL ADJUDICATION` and left the suite green. That was a defect in
> *my probe*, not in the control: that phrase is not the verdict line the record binds. Replacing
> every `ACCEPT` token reproduces the reviewer's recorded **15 failed** exactly. Recorded because a
> green result from a probe that did not bite is precisely the false-green class this repository
> exists to catch.

### Technical containment — retained

| Property | Observed |
|---|---|
| `src` / `configs` / `data` trees vs `0891d1a` | `0204261b…` / `124ae4bc…` / `8d021022…` — **IDENTICAL** |
| P4 boundary mutation battery | **61/61 caught**, byte-exact restoration |
| R-07 canonical status | `CONTAINED` |
| P4 | COMPLETE, 100/100 |
| P5 | **sole READY**, `NOT_STARTED` |
| P6–P14 | BLOCKED |
| Production `GateRegistry` | EMPTY |
| Phase-8 gate deferral | intact |
| `SUITE-RESULT.json` / `GATE-RESULT.json` | byte-identical blobs to `06ebfdb3` — no receipt forged |

`eval/control/status_claims.py` is imported by **no runtime module** (only `eval/tests/*`).
`scripts/mutate_roadmap_completeness.py` is imported by **nothing**. Parser, control and test
changes did not become runtime imports.

**Secret hygiene.** `.env` is untracked and enters no git or preservation object; its digest
`220534bc39dbcb0f4698b530ad740674381e1e046c6b52373ed62f1b181d60ab` is unchanged across this
remediation. A credential-pattern sweep over all changed paths surfaces nothing. The only
`.env`-family path in the tree is `.env.example`.

---

## 8. CORPUS COUNTS — RECOMPUTED, NOT CARRIED FORWARD

Measured over the **unified** population (`live_authority_documents()` ∪ the four landing
documents), which is what the guards assert over.

| Metric | Superseded instrument | Corrected parser | Δ |
|---|---|---|---|
| documents | 58 | **58** | 0 |
| parsed claims | 81 | **84** | **+3** |
| live CONTAINED | 45 | **49** | **+4** |
| **live OPEN** | 0 | **0** | **0** |
| exempt | 36 | **35** | −1 |

**Every difference is accounted for. A changed count is not a defect; an unexplained one is.**

* **+3 claims** — exactly the three canonical cross-cell rows that were invisible
  (`CURRENT.md:105`, `CLAUDE.md:73`, `README.md:63`).
* **+4 live CONTAINED** — those three, plus one `LEGACY-DISPOSITION.md:436` sentence that R-03
  correctly reclassified from `marked-historical` to live. That sentence is the author's **live
  correction** of a superseded quotation — *"It is **not** a live statement: R-07 is recorded
  `CONTAINED`…"* — so counting it as a live CONTAINED claim is right.
* **−1 exempt** — the same claim.
* Two exemption **relabels**, both still exempt: `LEGACY-DISPOSITION.md:53`
  `hypothetical` → `marked-historical`; `phase-0-baseline-manifest.yaml:367`
  `marked-historical` → `hypothetical`.
* Claims inside self-labelling `<details>` blocks are now **parsed and returned as exempt** rather
  than deleted, and line numbers after a details block are now the document's **real** ones
  (`CURRENT.md` claims shifted by exactly the 29-line length of its first details block).

**The corpus figures `58 / 81 / 45 / 0` were NOT reused.** They were re-derived from the corrected
instrument and differ where they should.

---

## 9. HOSTILE MATRICES

### 9.1 Parser-level proof (47 probes, all passing)

Cross-cell: `| R-07 | OPEN — NOT CONTAINED |` · `| R-07 | CONTAINED |` ·
`| Risk | R-07 | Status | OPEN |` · `| Risk | R-07 | Status | CONTAINED | Evidence | … |` ·
status-before-subject · descriptive columns both sides · empty cells · inline code · emphasis and
links · escaped pipe · omitted outer pipes.
Refused: cross-row · cross-table · row-versus-prose · header rows · separator rows ·
`| P4 | COMPLETE |` · `| P5 | READY | NOT_STARTED |`.
Details: unlabelled/OPEN · unlabelled/CONTAINED · `HISTORICAL` summary · `SUPERSEDED` summary ·
first-body-line marker · "Rejected evidence" (**not** exempt) · label outside the block · cross-cell
row inside unlabelled details · live-inside-historical · historical-inside-live · missing
`</details>` · malformed `<summary>` · stray `</details>` · literal `` `<details>` `` in code.
R-03: trailing marker does not exempt · leading marker does · earlier cell governs · later cell does
not. R-04: stray quote bounded to its own row and its own block.

### 9.2 Mutation battery — 40/40 correct, 0 defective, **0 SKIP-INVALID**

M1–M21 retained and re-verified. **M22–M40 added:**

| Case | Attacks |
|---|---|
| **M22** | `CURRENT.md` canonical row, **cross-cell**, verbatim (contrast M3, the same-cell control) |
| **M23** | `CLAUDE.md` canonical row, cross-cell, verbatim |
| **M24** | `README.md` canonical row, cross-cell, verbatim — pointed at the **unified** guard |
| **M25** | a **new** cross-cell row introduced into `ARCHITECTURE.md` |
| **M26** | status in a leading cell, subject later |
| **M27** | extra descriptive columns |
| **M28** | escaped-pipe cell content |
| **M29** | inline-code subject and status cells |
| **M30** | cross-**row** false association — **must stay GREEN** |
| **M31** | cross-**table** false association — **must stay GREEN** |
| **M32** | unlabelled `<details>` containing OPEN |
| **M33** | correctly labelled `<details>` containing OPEN — **must stay GREEN** |
| **M34** | historical marker moved **outside** the block |
| **M35** | historical marker **removed** |
| **M36** | malformed block — `</details>` deleted |
| **M37** | nested unlabelled block inside a labelled one |
| **M38** | cross-cell row **inside** an unlabelled block (R-01 × R-02 composed) |
| **M39** | **zero** READY rows |
| **M40** | **duplicate** READY rows |

Three battery-mechanism improvements, each closing a way the previous battery could report a
result it had not earned:

1. **`expect: GREEN` cases.** A battery in which every mutation fails cannot distinguish a parser
   that reads rows correctly from one that fires on anything nearby — and **over-association is
   exactly the new risk a row-aware parser introduces**. M30, M31 and M33 assert negative
   invariants and are battery defects if they *fail*.
2. **Failure-reason verification.** A case counts as CAUGHT only if the guard failed with an
   `AssertionError`. A mutation that kills a guard with a `TypeError` is evidence the guard broke,
   not that the invariant is enforced.
3. **Per-case guard targeting.** M24 runs against `test_docs_control_system.py` and M39/M40 against
   `test_switch_consistency.py`, so each case is scored by the guard that actually asserts over its
   population.

> **M24 is a finding in itself.** `README.md` is **not** in the discovered
> `live_authority_documents()` population — it is reached only through the union with the four
> landing documents. Pointed at the roadmap node, M24 scored a MISS that said nothing about the
> parser and everything about which corpus each guard asserts over. Recorded so no future reader
> mistakes the population boundary for a parser hole.

---

## 10. TESTS AND RECEIPTS

| Check | Result |
|---|---|
| Canonical suite (clean tree, disposable clone) | **2043 passed · 0 failed · 1 skipped · 2044 collected** |
| Approved skips | exactly one — `test_the_red_by_design_cases_are_strict_xfails` |
| `TEST-NODE-MANIFEST.json` | regenerated via `scripts/regenerate_test_manifest.py`; **2044 == 2044, 0 missing, 0 extra**; `config_sha256` `22f42941…` **unchanged** |
| New test nodes | **+26**, all of them R-01/R-02/R-03/R-04 regression tests |
| Roadmap/documentation mutation battery | **40/40 correct, 0 defective, 0 SKIP-INVALID** |
| P4 boundary battery | **61/61 caught** |
| Corpus sweep | **58 / 84 / 49 / 0** (recomputed) |
| Runtime equality vs `0891d1a` | `src`/`configs`/`data` tree-identical |
| Receipts vs `06ebfdb3` | `SUITE-RESULT.json`, `GATE-RESULT.json` identical blobs |
| Clean-clone gate | **PASS**, from its own fresh virtualenv built from declared dependencies only, independently reproducing **2043 / 0 / 1 / 2044**. Run ONLY in a disposable clone, because it writes `GATE-RESULT.json` — the primary tree's receipt was never touched. Re-run it yourself per §14 |

**No test was weakened to obtain a green result.** One new failure appeared during validation —
`test_no_control_guard_hand_enumerates_a_file_population` fired on the new `_CROSS_CELL_ANCHORS`
tuple. The guard was **correct**; the tuple is a genuine fixed specification for the same reason
`REQUIRED_R07_REACH` is, and it was annotated `FIXED-SPECIFICATION` **with a reason**, which is the
mechanism the guard itself sanctions. The guard was not touched.

---

## 11. PRESERVATION — NOTHING WAS DELETED

| Artifact | Ref | Value |
|---|---|---|
| Rejected replacement candidate | `refs/preserve/p4-r07-closure-rejected-replacement-candidate-4d12b0e` | `4d12b0e4…cf65a` |
| — archive branch | `refs/heads/archive/p4/r07-rejected-replacement-4d12b0e` | `4d12b0e4…cf65a` |
| — its rejected tree | | `35f6755c5ce90dc64c96bb5f4be4236a170fff83` |
| — complete worktree | `refs/preserve/p4-r07-rejected-replacement-worktree-4d12b0e` | `6b88dd090ae985756d2ec15d1a9f1b53dfde7a39` (tree `3145b3a6…`, **645 paths**) |
| Its targeted **review** | `refs/preserve/p4-r07-closure-replacement-targeted-review-4d12b0e` | `62df39dd…`, parent **`4d12b0e`** |
| — report SHA-256 | | `8c26a311cb80d26715624f43ad5b062fece3ca9319f21948cd242651f95a6d42` |
| Its targeted **adjudication** | `refs/preserve/p4-r07-closure-replacement-targeted-adjudication-4d12b0e` | `ce5dbb30…`, parent **`4d12b0e`** |
| — report SHA-256 | | `62d2d26771194e1d9fc2fcd193d2a4c8fd73f74d90ed4410275748c65435990f` |
| Rejected predecessor `11c9112` | `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` · `refs/heads/archive/p4/r07-rejected-11c9112` | `11c91124…bc80` |
| — its worktree | `refs/preserve/p4-r07-rejected-worktree-11c9112` | `6224b36e…` |
| — its review / adjudication | `…-targeted-review-11c9112` · `…-targeted-adjudication-11c9112` | `fa4c459b…` · `030c5954…`, both parented to **`11c9112`** |

**Preservation verification**, performed in a disposable `--no-local` clone:

* forward: **645/645 paths present, 0 missing, 0 mismatches** against the source worktree;
* reverse sweep: **zero uncaptured paths** other than `.env`;
* sidecars: **9/9 verify** (6 direct, 3 debannered at 27/34/35 banner lines — the disclosed
  banner convention);
* `.env` deliberately **not stored**, digest-only, matching the `11c9112` precedent and unchanged.

**Attribution is mechanically exclusive.** No report of `11c9112` or `4d12b0e` appears in this
candidate's tree; each exists only at its preservation commit, parented to the candidate it
actually reviewed. Nothing here may be read as reviewing this successor.

---

## 12. RESIDUAL RISKS

| # | Residual |
|---|---|
| **RC-01 (recurrence, recorded again)** | A battery drawn from the instrument's own field of view measures that field of view. M12–M21 reported 21/21 while never testing the corpus's canonical construction. The `expect: GREEN` cases and the positive cross-cell anchors narrow this — they do not abolish it. **The next blind spot will also be invisible to the battery that shares its assumptions.** |
| **RR-01** | The closed historical vocabulary is `HISTORICAL` / `SUPERSEDED` only. A block labelled solely "Archived" or "Rejected evidence" is **read as live** — fail-closed, but it will surprise an author. Widening the vocabulary is a deliberate act owing its own hostile cases. |
| **RR-02** | Content inside a fenced code block is **read**. A document that legitimately *illustrates* a bad status row must mark, quote or self-label it. Zero such cases exist in the live corpus today; the alternative — exempting fences — would recreate R-02's hiding place. |
| **RR-03** | `README.md` is outside the discovered `live_authority_documents()` population and is protected only through the union in `test_docs_control_system.py`. Two guards, two populations; M24 depends on which. Unifying the population is out of this scope. |
| **RR-04** | The R-03 governance rule is *marker precedes the risk id within the unit*. A historical claim labelled only **after** its claim is now live. Three were corrected here; a fourth written tomorrow will fail the guard until its label is moved — the intended behaviour, but it is a new authoring constraint. |
| **F-06, AD-01, AD-02, RC-02, RC-03** | Carried from prior adjudications, **not discharged** here and not reopened. |

---

## 13. WHAT THIS SESSION DID NOT DO

Did not review this candidate · did not adjudicate it · did not run `finalize_status.py` · did not
begin P5 · did not deploy or enable any effect · did not modify P4 runtime behaviour · did not
weaken R-07 technical containment · did not create a second consecutive content commit · did not
move `main`, `origin/main` or any protected ref · did not delete, move or reinterpret any
preservation ref · did not alter the review or adjudication of `11c9112` or `4d12b0e` · did not
resume any previous session · pushed nothing. All implementation behaviour was measured in
disposable `--no-local` clones; the primary worktree and index were written only to carry the
final delta.

---

## 14. PREREQUISITES FOR A COMPLETELY FRESH TARGETED REVIEWER

The reviewer must be a session that **authored neither candidate and conducted neither prior review
nor adjudication**, and must resume no previous session.

**Verify first, from the primary repository:**

1. Branch is `p4/adapter-containment-completion`; HEAD has **exactly one parent**, `06ebfdb3`; it is
   **not** a child of `4d12b0e` or `11c9112` (`git merge-base --is-ancestor` returns non-zero for
   both); `git rev-list --count 06ebfdb3..HEAD` is **1**; state is **PRODUCING**.
2. All preservation refs in §11 resolve, with the parents stated there.
3. `main` = `origin/main` = `152574e4f4f2969468c9d31b1e705188896175b5`; nothing pushed
   (`git branch -r --contains HEAD` empty).

**Then measure independently — do not accept these figures:**

4. Recompute the corpus over the unified population and reconcile every delta in §8.
5. Re-run the parser matrix in §9.1 and the battery in §9.2; confirm **0 SKIP-INVALID** and that
   the three `expect: GREEN` cases stay green.
6. **Attack the new parser on its own terms**, not the old one's. Specifically hunt for
   **over-association** (the risk this design introduces): try to make a row claim attach to a
   neighbouring row, a nested table, a list rendered with pipes, or a wrapped cell.
7. Re-run the F-03 hostile battery (§7) and confirm each case bites — verify your probe actually
   modified the file before trusting a green.
8. Confirm runtime tree-identity to `0891d1a` and that `SUITE-RESULT.json` / `GATE-RESULT.json` are
   unchanged blobs.
9. Run the clean-clone gate **only in a disposable clone** — it writes `GATE-RESULT.json`.
10. Form an independent view on the §4.3 scope judgement (the five delegated `strip_historical`
    call sites) and on the three R-03 label moves in §5.

**Environment artifacts to expect** (reproduce on the unmodified parent before recording either as
a regression): a clone with a symlinked `.venv` is reported dirty and raises two extra NOT-RUN
skips; a `.venv`-less clone fails four CLI smoke tests that shell out to `ROOT/.venv/bin/python`.

## 15. PREREQUISITES FOR LATER THIRD-FINALIZER AUTHORIZATION

`scripts/finalize_status.py` **must not run** until **all** of:

1. A completely fresh **targeted independent review** of this candidate returns acceptance.
2. A **separate targeted adjudication** — by a different session again — returns acceptance.
3. Both are preserved under `refs/preserve/*`, parented to **this** candidate, with sidecars.
4. R-01 and R-02 are confirmed remediated **by measurement, not by this document**.
5. Corpus and mutation counts are independently reproduced and every delta reconciled.
6. Technical containment, F-01 and F-03 are confirmed still closed.
7. Runtime byte-equality to `0891d1a` is confirmed.
8. `TEST-NODE-MANIFEST` is confirmed at exact set equality against a real collection.

Only then may **exactly one** third finalizer run. No finalizer receipt exists for this candidate
and none may be fabricated.

---

**This document is a handoff. It certifies nothing, adjudicates nothing and authorizes no
finalization.**
