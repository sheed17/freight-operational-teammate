# P4 R-07 CLOSURE — SUCCESSOR CANDIDATE `3874d4a`, FRESH TARGETED INDEPENDENT REVIEW

**Exact candidate reviewed:** `3874d4a1bd02cdf81525aba52268e7aa44343457`
**Tree:** `82bd3da480f4f1320bd1a9cff076bb8f99827efc`
**Parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (certified second-finalizer metadata commit)
**Branch:** `p4/adapter-containment-completion`

**Reviewer standing.** This session did not implement P4, did not author rejected candidate
`11c9112`, did not author rejected replacement candidate `4d12b0e`, did not author successor
candidate `3874d4a`, conducted no prior review or adjudication, ran neither finalizer, and
reconstructed no finalization evidence. No previous session was resumed. All implementation
behaviour was measured in disposable `--no-local` clones; the primary worktree, index and branch
were never written.

---

## VERDICT

# REJECT — TARGETED REMEDIATION REQUIRED

Three **confirmed blocking defects** are recorded below (**S-01**, **S-02**, **S-03**). Each one
independently reproduces, on this successor, the exact defect class the candidate exists to close:
a canonical document asserting **R-07 OPEN — NOT CONTAINED** in rendered, readable text while the
**entire canonical suite is green**.

The strongest single proof: with **S-01** and **S-03** applied together, `ARCHITECTURE.md` contains
the row `| **R-07** | … | **OPEN — NOT CONTAINED** |` and `CURRENT.md` — the designated status
authority — contains `The four violation residuals keep R-07 OPEN and the write half is NOT
CONTAINED.` inside an **unlabelled** `<details>` block, and the full canonical suite reports
**2041 passed · 0 failed · 3 skipped** — zero failures.

This is *not* a rejection of the candidate's core design. The row-aware claim unit (R-01) and the
label-gated details classification (R-02) are **correct, well-built and genuinely remediate the
adjudicated defects for the direct attack**. R-03, R-04 and R-05 are correctly closed. Containment,
F-01, F-03, runtime byte-equality, corpus counts, both mutation batteries and every receipt
reproduce exactly. The defect is narrow and localized: **R-01 widened the claim unit from the cell
to the row, but the three exemption rules were left scoped to the widened unit**, so an ordinary
word in an unrelated descriptive column now launders the status column. The remediation is
correspondingly narrow — see §9.

---

## 1. MECHANICAL VERIFICATION OF THE CANDIDATE

Every value below was re-derived from the object store, not read from the handoff.

| Property | Required | Observed | |
|---|---|---|---|
| Commit | `3874d4a1bd02…3457` | `3874d4a1bd02cdf81525aba52268e7aa44343457` | ✅ |
| Tree | `82bd3da4…827efc` | `82bd3da480f4f1320bd1a9cff076bb8f99827efc` | ✅ |
| Parent | `06ebfdb3…6877e1f` | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` | ✅ |
| Parent count | exactly 1 | 1 — not a merge | ✅ |
| Child of `4d12b0e`? | must be NO | `merge-base --is-ancestor` non-zero | ✅ |
| Child of `11c9112`? | must be NO | `merge-base --is-ancestor` non-zero | ✅ |
| Commits above `06ebfdb3` | exactly 1 | `rev-list --count` = 1 — no second consecutive content commit | ✅ |
| Topology | legal PRODUCING | one content commit above certified metadata | ✅ |
| Branch | `p4/adapter-containment-completion` | unchanged since creation (reflog `@{0}` = candidate) | ✅ |
| `main` / `origin/main` | `152574e4…175b5` | both `152574e4f4f2969468c9d31b1e705188896175b5`, equal | ✅ |
| Pushed? | nothing | `git branch -r --contains HEAD` empty; 7 unpushed vs `origin/main` | ✅ |
| Primary worktree | clean | 0 modified paths, before and after this review | ✅ |
| `.git/neyma-finalizer.lock` | unheld | `flock(LOCK_EX\|LOCK_NB)` acquired and released; `lsof` no holder | ✅ |
| `.git/neyma-builder-worktree.lock` | unheld | same probe, same result | ✅ |
| Residual processes | none | no `pytest` / `mutate_*` / `finalize_status` / `clean_clone_gate` at review start | ✅ |

Both lock files exist as 0-byte artifacts. The lock is `flock`-based
(`neyma_product_driver/ownership.py:45,155,205`), so **file presence is not ownership** — liveness
was decided by probe, never inferred from the artifact.

**Changed paths — 54 vs `06ebfdb3`** (52 modified/added tracked surfaces plus the successor handoff
and its sidecar). **No path under `src/`, `configs/` or `data/` is touched.** Verified by
`git diff --name-status`.

---

## 2. RUNTIME BYTE-EQUALITY TO ACCEPTED IMPLEMENTATION CANDIDATE `0891d1a`

Tree-object comparison, `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e` versus `3874d4a`:

| Path | `0891d1a` | `3874d4a` | |
|---|---|---|---|
| `src/` | `0204261b17ba…` | `0204261b17ba…` | **IDENTICAL** ✅ |
| `configs/` | `124ae4bcbbec…` | `124ae4bcbbec…` | **IDENTICAL** ✅ |
| `data/` | `8d0210227727…` | `8d0210227727…` | **IDENTICAL** ✅ |
| `scripts/` | `ca99a45efb7a…` | `851f5331ab01…` | differs — **one file only** |

`git diff --name-status 0891d1a 3874d4a -- scripts/` returns exactly
`M scripts/mutate_roadmap_completeness.py`. `git diff --name-only … -- src configs data` is empty.

**Import reachability.** `eval/control/status_claims.py` imports only `re`, `dataclasses`,
`functools` and (lazily, inside `live_authority_documents`) `control.inventory`.
`scripts/mutate_roadmap_completeness.py` imports only `argparse`, `shutil`, `subprocess`, `pathlib`.
`git grep` over `src scripts configs data` at the candidate finds **no** import of either module
(the single hit is a usage line in the mutation script's own docstring). Neither parser nor mutation
code can enter a freight runtime path. ✅

**Governed machinery unchanged.** Adapters, approval/write machinery, checkpoint/witness/grant/claim
machinery, browser boundaries, origin policy and the production `GateRegistry` implementation are
all inside the byte-identical `src/` tree. ✅

**Receipts.** `docs/implementation/SUITE-RESULT.json` (`a16cb1fc1574…`) and
`docs/implementation/GATE-RESULT.json` (`8201ca745af0…`) are **identical blobs** to `06ebfdb3`.
No receipt was forged. The committed `SUITE-RESULT.json` still describes commit `42ea24c` at
1961/1962 — correctly, since no finalizer has run for this candidate and none may be fabricated. ✅

---

## 3. R-07 TECHNICAL CONTAINMENT — RETAINED

| Property | Observed | |
|---|---|---|
| R-07 canonical status | `expected_legacy_paths.status: CONTAINED` | ✅ |
| Recorded violation edges | `effect_adapter_import_gate.violation_edges: []` | ✅ |
| Gate status | `EMPTY (mechanical close met)` | ✅ |
| Live/recorded equality | both empty, agreeing both-sided | ✅ |
| Detection edges | `detection_edges: 13` | ✅ |
| Production `GateRegistry` | **0 constructions**, **0 `register_gate` calls** in `src/` | ✅ |
| Phase-8 gate deferral | intact (`governed_write_registry.py:394-403` — construction REMOVED, deliberately not relocated, `DEFERRED_BY_DEPENDENCY — REQUIRED AT PHASE 8`) | ✅ |
| `CdpActuator` construction | none in `src/` or `scripts/` (all hits are mutant string literals inside `mutate_phase4_boundary.py`) | ✅ |
| `cdp_actuator` import | none, same qualification | ✅ |
| Legacy live-operation router | `_build_live_operation_router` / `_build_agent` exist nowhere in `src/` or `scripts/` (one comment in the mutation script) | ✅ |
| Production default | `ROUTE_NOT_CONFIGURED` (`action_callback.py:662`) | ✅ |
| P4 | `COMPLETE` / `COMPLETE` | ✅ |
| P5 | `READY` + `NOT_STARTED`, **sole** READY unit | ✅ |
| P6–P14 | all `BLOCKED` / `NOT_STARTED` | ✅ |
| P5 implementation | none begun | ✅ |

**Containment remains containment, not enablement.** No production write is enabled, the production
gate population stays EMPTY, and no autonomy was granted. ✅

---

## 4. WHAT IS CORRECT — R-01, R-02, R-03, R-04, R-05

I want to be precise about this, because the rejection below is narrow and the work it rests on is
sound.

### 4.1 R-01 — the row-aware parser is correct for the direct attack

The claim unit is genuinely the bounded row. `TableRow`, `ClaimUnit` and `StatusClaim` carry every
one of the six required identities: document (caller), `line`, `table_id`, `row_index`, ordered
`cells`, `subject_cell`, `status_cell`, plus a `where` property naming the deciding cell.

All six required forms parse as specified:

| Form | Parsed |
|---|---|
| `\| R-07 \| OPEN — NOT CONTAINED \|` | OPEN, live ✅ |
| `\| R-07 \| CONTAINED \|` | CONTAINED, live ✅ |
| `\| Risk \| R-07 \| Status \| OPEN — NOT CONTAINED \|` | OPEN, live ✅ |
| `\| Risk \| R-07 \| Status \| CONTAINED \| Evidence \| … \|` | CONTAINED, live ✅ |
| `\| P4 \| COMPLETE \|` | correctly **not** an R-07 claim ✅ |
| `\| P5 \| READY \| NOT_STARTED \|` | correctly **not** an R-07 claim ✅ |

Syntax handling verified individually: leading/trailing pipes present **and** omitted (a delimiter
row establishes the table), header rows, separator/alignment rows (`---`, `:---`, `---:`, `:---:`),
escaped pipes (`\|` is content — `_split_cells` skips escaped characters), inline code, emphasis,
links, descriptive columns before/between/after, empty cells, and prose containing a literal pipe
(correctly **not** a row: `table_rows()` returns empty, `claim_units()` yields only `sentence`). ✅

**The three formerly invisible canonical rows are positively anchored and parsed**, located
mechanically rather than by line number:

| Document | Line | subject → status cell | Parsed |
|---|---|---|---|
| `docs/implementation/CURRENT.md` | 105 | cell 0 → cell 2 | CONTAINED, live ✅ |
| `CLAUDE.md` | 73 | cell 0 → cell 1 | CONTAINED, live ✅ |
| `README.md` | 63 | cell 0 → cell 1 | CONTAINED, live ✅ |

A plain status flip on each of the three is **CAUGHT**. The prior ARCHITECTURE.md cross-cell
mutation (M25) is **CAUGHT**.

**Over-association — the risk this design introduces — is genuinely bounded.** Verified refused:
cross-row association, cross-table association, row-versus-surrounding-prose, header rows,
separator rows, a list rendered with pipes, a wrapped/multi-line cell, and a nested-looking table
written inside a cell. Conflicting statuses in one row resolve **OPEN-first** in both orders, and
`not contained | CONTAINED` resolves OPEN — all fail-closed. Malformed table syntax
(`| R-07 | OPEN`, `R-07 | OPEN |`, `|||R-07|||OPEN|||`, `| R-07 || OPEN |`) still yields the claim
rather than losing it. ✅

The `_CELL_JOIN = " | "` device works as documented: `\w+`, `\s+` and `[-\s]+` cannot consume a
pipe, so multi-word token sequences stay per-cell while association spans the row.

### 4.2 R-02 — details-aware parsing is correct in its own terms

Independently verified against the source, not the handoff. The authorized vocabulary is the closed
pair `HISTORICAL` / `SUPERSEDED` (`_HISTORICAL_MARKER`, `status_claims.py:171`), and the marker
position is the block's own `<summary>`, or absent one its own first non-blank body line
(`_build_block`, `:392-420`). Confirmed behaviour:

| Case | Result | |
|---|---|---|
| unlabelled details containing OPEN | **LIVE** and scanned | ✅ |
| unlabelled details containing CONTAINED | parsed live, no OPEN | ✅ |
| `HISTORICAL` `<summary>` containing OPEN | `historical-details`, exempt **and visible** | ✅ |
| `SUPERSEDED` `<summary>` containing OPEN | exempt and visible | ✅ |
| `REJECTED EVIDENCE` label | **not** exempt — read, fail-closed | ✅ |
| `ARCHIVED` label | **not** exempt — read, fail-closed | ✅ |
| first-body-line marker | exempt | ✅ |
| nested live inside historical | **LIVE** — no downward inheritance | ✅ |
| nested historical inside live | exempt — no upward inheritance | ✅ |
| missing `</details>` | **LIVE**, fails closed | ✅ |
| malformed `<summary>` (never closed) | **LIVE**, yields no marker | ✅ |
| stray `</details>` | ignored | ✅ |
| markdown table inside details | parsed | ✅ |
| cross-cell R-07 row inside unlabelled details | **LIVE** (R-01 × R-02 composed) | ✅ |
| cross-cell R-07 row inside labelled details | exempt | ✅ |

`details_structure_defects()` reports unterminated blocks, stray closers and unclosed summaries, and
returns empty on well-formed input — so a guard can fail loudly rather than widen silently. ✅

**Excluded content is exempt and visible, never deleted.** `parse_status_claims` returns exempt
claims carrying their reason; `strip_historical_blocks` blanks in place preserving every offset, so
reported line numbers are the document's real line numbers. ✅

**No guard module strips all details content before invoking the shared parser.** Verified
exhaustively: the two live-OPEN guards
(`test_roadmap_completeness_control.py:465`, `test_docs_control_system.py:298`) call
`parse_status_claims(text)` on **raw** text. The five delegating modules call
`strip_historical_blocks`, which now blanks **only self-labelling** blocks. `grep` for the raw
`re.sub(r"<details>.*?</details>", …)` across `eval/` and `scripts/` returns **one** hit, inside a
docstring documenting what was replaced. ✅

### 4.3 The five additional guard-module changes — justified defect propagation

Reviewed individually. Each is a **one-line** replacement of the identical defective regex
`re.sub(r"<details>.*?</details>", "", text, flags=re.S)` with
`status_claims.strip_historical_blocks(text)`, plus a docstring recording why.

| Module | Duplicated the adjudicated defect? | Mechanically required? | Delegates? | Narrow? | Runtime effect? | Second model? |
|---|---|---|---|---|---|---|
| `test_docs_control_system.py:65` | **Yes — verbatim** | not named in §9, but same defect | yes | 1 line | none (eval/) | no — removes one |
| `test_switch_consistency.py:53` | **Yes — verbatim** | same | yes | 1 line | none | no |
| `test_status_reality.py:221` | **Yes — verbatim** | same | yes | 1 line | none | no |
| `test_false_green_defenses.py:48` | **Yes — verbatim** | same | yes | 1 line | none | no |
| `test_bootstrap_hermeticity.py:460` | **Yes — verbatim** | same | yes | 1 line | none | no |

Each carried a docstring asserting a label check none of them performed. Fixing only the parser
would have left five copies of the adjudicated defect open — including the channel of the incident
`CURRENT.md` actually records (a false **phase transition** claim, which the R-07 parser never
guarded). The adjudication's §9 item 2 is "details-block historical/live classification
correction"; confining that to one of six identical copies would be a partial fix, not a narrower
one.

**Assessment: necessary defect propagation, not scope expansion. Accepted.** The change strictly
narrows duplication, strictly strengthens the control, creates **one** historical-classification
model rather than six drifting ones, and touches no runtime surface. It is behaviour-neutral on the
current tree (every `<details>` block in the corpus is already labelled), and the full suite
confirms it.

Focused regression coverage exists for the shared definition (the R-02 node family in
`test_roadmap_completeness_control.py`), though see **S-05** for a residual anti-drift gap.

### 4.4 R-03 — the three historical label moves are legitimate

I inspected all three at byte level (`git diff 4d12b0e 3874d4a`).

| Document | Claim | Verified |
|---|---|---|
| `PHASE-OUTPUTS.md:109` | "R-07 stays OPEN through P3" | genuinely historical — the row states the state **after P3**; label `*(HISTORICAL — …)*` moved before the claim; wording unchanged ✅ |
| `pr-sequence.md:33` | "R-07 stays OPEN at P0" | genuinely historical — a **frozen Phase-0 sequence** recording the P0 state; label moved before the claim; wording unchanged ✅ |
| `phase-0-baseline-manifest.yaml:874` | "…kept R-07 OPEN" | genuinely historical — the paragraph is explicitly the record of a superseded checkpoint state; `HISTORICAL, SUPERSEDED -` moved to sentence start; wording unchanged ✅ |

In every case the marker is attached to the exact governed claim, does not exempt neighbouring live
content, the claim remains readable and discoverable in place, and **no document-level exemption was
introduced**. All three were *already* labelled `HISTORICAL`; only the label's **position** changed.
This is the opposite of relabelling to make the corpus green. **No unjustified historical
relabelling found.** ✅

The one genuinely reclassified claim — `LEGACY-DISPOSITION.md:436`, `marked-historical` → live
CONTAINED — is correct. I read the surrounding text: the blockquote quotes the superseded wording
(which parses `quoted`, exempt) and then states the author's **live** correction, *"It is **not** a
live statement: R-07 is recorded `CONTAINED` in `phase-0-baseline-manifest.yaml`."* That sentence
genuinely reads CONTAINED and is genuinely live. Counting it is right; it is **not**
over-association. ✅

### 4.5 R-04 — quote parity is row-bounded

The exact R-04 authority (adjudication §5): `| a | he said "hello |` followed by
`| b | R-07 remains OPEN |` parsed the second row `exemption='quoted'`, because `_quoted()` counted
parity from the preceding blank line and a markdown table has no blank lines between rows.

Reproduced directly against the successor: an unbalanced `"` in an earlier row of the same table
**no longer** exempts a later row — the later row parses **live OPEN**. `_row_unit` sets
`block_start=row.offset`, so a table row is its own parity block (`status_claims.py:584,630-633`).
The fix is **row-bounded semantics**, not cross-row matching, not global-document matching, not a
loose regex, and not a one-off exception for the current documents. ✅

### 4.6 R-05 — the commit message is accurate

The rejected candidate's false line was `2014 passed / 0 failed / 3 skipped / 2017 collected`. The
successor's message does **not** repeat it. It states its own figures —
`2043 passed / 0 failed / 1 skipped / 2044 collected` — and explicitly names the `4d12b0e` line as
inaccurate and superseded, recording the true reproduced result on that tree as `2017 / 0 / 1 /
2018` (which is what §9 item 10 required).

**I independently reproduced the canonical result before accepting the figure:**
**2043 passed · 0 failed · 1 skipped · 2044 collected** — exact match. ✅

**The message is not consumed as a canonical receipt.** Verified: authority is `SUITE-RESULT.json`
(written only by `run_canonical_suite.py` from a real run) and `TEST-NODE-MANIFEST.json`; no guard
reads a commit message as state. ✅

---

## 5. CORPUS COUNTS — INDEPENDENTLY RECOMPUTED

Measured over the unified population (`live_authority_documents()` ∪ the four landing documents),
which is what the guards assert over. **I did not treat equality with the handoff as proof:** I ran
the superseded instrument on its own tree and the corrected instrument on this tree.

| Metric | Superseded (`4d12b0e` parser on `4d12b0e` tree) | Corrected (`3874d4a`) | Δ |
|---|---|---|---|
| documents | **58** | **58** | 0 |
| parsed claims | **81** | **84** | **+3** |
| live CONTAINED | **45** | **49** | **+4** |
| **live OPEN** | **0** | **0** | **0** |
| exempt | **36** | **35** | **−1** |

Both baselines reproduced **exactly**. Every difference is accounted for:

* **+3 claims** — precisely the three canonical cross-cell rows that were invisible
  (`CURRENT.md:105`, `CLAUDE.md:73`, `README.md:63`). Confirmed by direct parse.
* **+4 live CONTAINED** — those three, plus `LEGACY-DISPOSITION.md:436` (§4.4 above). **Not**
  created through over-association: each was individually inspected and each is a real
  subject-and-status assertion in one bounded unit.
* **−1 exempt** — the same `LEGACY-DISPOSITION.md` claim leaving the exempt set.
* Two exemption **relabels**, both still exempt, both confirmed by differential parse:
  `LEGACY-DISPOSITION.md` `hypothetical` → `marked-historical`;
  `phase-0-baseline-manifest.yaml` `marked-historical` → `hypothetical`.

Exemption breakdown at the candidate: `quoted` 20, `hypothetical` 8, `marked-historical` 7.

**Zero live OPEN is not produced by historical overclassification.** `historical-details` accounts
for **0** exemptions in the live corpus — no claim currently relies on the details-exemption path at
all. The remaining 35 exemptions were reviewed by reason; the F-01 sweep (§6) found no live stale
claim.

**Corpus membership is positively anchored.** `live_authority_documents()` asserts
`len(out) >= 15`; both guards assert `len(population) >= 15`, assert `contained_claims >= 5` (so the
guard cannot pass over a corpus that stopped saying anything), and
`test_roadmap_completeness_control.py` asserts every `REQUIRED_R07_REACH` document is in the scanned
set. `test_docs_control_system.py` explicitly requires `CURRENT`, `CLAUDE`, `ARCHITECTURE`, `README`
and `LEGACY` to be present. **A missing document fails; an empty claim set fails.** ✅

---

## 6. F-01 STALE-CLAIM CLEANUP — RETAINED

Swept every document in the unified population, plus agent instructions, for live claims equivalent
to the ten corrected ones:

| Pattern | Live hits |
|---|---|
| `R-07 remains open` | 0 live — 1 `quoted` (`EFFECT-PATH-INVENTORY.yaml:141`) |
| `R-07 is open` | 0 |
| `keeps R-07 open` | 0 live OPEN — 1 `quoted` (`effect-entry-point-cutover-plan.md:18`), 1 `hypothetical` (`phase-0-baseline-manifest.yaml:367`), 1 live **CONTAINED** (`LEGACY-DISPOSITION.md:436`, §4.4) |
| `leaves R-07 open` | 0 |
| `does not contain R-07` | 0 |
| `R-07 not contained` | 0 |
| `EP-1 write path remains present` | 0 |
| `direct actuator route remains present` | 0 |
| `four violation residuals remain` | 0 |

**Zero false live OPEN claims** across the unified population. Historical claims are explicitly
marked through valid attached markers. **No historical report was rewritten** — the three R-03
changes move a label's position and change no claim's wording (§4.4). **No stale claim was moved
into an unparsed format** — the parser reads details content, fenced code and inline code, so there
is no format to hide in. ✅

*(Caveat: this retention holds for the tree as committed. **S-01** and **S-03** below make it
trivially defeatable going forward, which is why they block.)*

---

## 7. F-03 IMMUTABLE EVIDENCE BINDING — RETAINED, RE-RUN IN FULL

`test_evidence_binding.py` is byte-unchanged from `4d12b0e`. I re-ran the full load-bearing battery
myself rather than inheriting a result, in a `--no-local` clone, restoring byte-exactly between
cases (baseline **26 passed** before and after every case).

Six load-bearing reports are derived from
`expected_legacy_paths.containment_evidence` (not hand-listed): the accepted re-review and final
adjudication for `0891d1a`, the first-finalization report, the accepted targeted review and
adjudication for `42ea24c`, and the second-finalization report. Each is bound to expected SHA-256,
sidecar, authenticated body, preservation ref, preservation commit, preservation parent, candidate
attribution and verdict.

### 7.1 Hostile battery — every case bites

| Case | Result | |
|---|---|---|
| **`ACCEPT` → `REJECT` in the load-bearing adjudication** (the exact tamper attack) | **1 failed** | ✅ |
| sidecar content changed | **1 failed** | ✅ |
| sidecar missing | **1 failed** | ✅ |
| report missing | **5 failed** | ✅ |
| required banner removed (corrected probe — see 7.3) | **5 failed** | ✅ |
| body substituted under a valid banner | **15 failed** | ✅ |
| **recorded verdict flipped in the manifest** (body still says ACCEPT) | **1 failed** | ✅ |
| **recorded digest flipped in the manifest** | **1 failed** | ✅ |

The last two are my own additions; the record itself cannot be edited to match a tampered report.

### 7.2 Two-tier design — verified on both sides

| Requirement | Verified |
|---|---|
| Unconditional content binding in a clean clone with **no** local preserve refs | tier 1 runs, 26 passed, and catches every case above ✅ |
| All-or-nothing ref verification when preservation refs are present | fetched all 32 `refs/preserve/*`; baseline 26 passed ✅ |
| **One missing ref fails rather than downgrading silently** | deleted one ref → **2 failed**, including the explicit `test_the_tier_two_condition_is_all_or_nothing` ✅ |
| Preservation-parent mismatch fails | re-pointed a ref to another commit → **1 failed** ✅ |
| Banner-aware body verification | corrected banner probe → 5 failed ✅ |
| Mutable worktree substitution failure | body substitution → 15 failed ✅ |
| Candidate-attribution mismatch failure | covered by the re-pointed-ref case ✅ |

### 7.3 Adjudication of the builder's disclosed green probe — **F-S-06**

The handoff §7 discloses that a first attempt at the banner-substitution case "replaced only the
phrase `ACCEPT FOR SEPARATE FINAL ADJUDICATION` and left the suite green", and attributes this to
"that phrase is not the verdict line the record binds".

**I do not accept that explanation, and the disclosure is inaccurate — but in the candidate's
favour.** Measured:

1. **What the probe intended to mutate:** the authenticated body of a load-bearing report, to prove
   a substituted body under a valid banner fails.
2. **Did it modify a load-bearing authenticated source?** The phrase occurs **3×** in
   `p4-independent-rereview-report-0891d1a.md` and **2×** in `p4-final-adjudication-report-0891d1a.md`
   — **both load-bearing**. So a probe that actually wrote to either did modify one.
3. **Was the guard expected to fail?** Yes.
4. **What the green result indicates:** I reproduced the probe exactly — replacing only that phrase
   in the load-bearing re-review report — and got **15 failed**, identical to the "replace every
   `ACCEPT` token" result. The phrase **is** bound. Therefore the builder's green result is **not**
   explicable as a non-load-bearing mutation and is **not** an evidence-binding gap; it is
   consistent only with an **invalid probe** that did not write to a load-bearing authenticated
   source (the phrase also occurs in four non-authenticated files: `CLAUDE.md`, `BUILD-STATUS.yaml`,
   `CURRENT.md`, `phase-0-baseline-manifest.yaml`, and in the handoff itself).

**Classification: invalid probe. No remaining evidence-binding gap on this vector.** The corrected
probe is supplied above and bites. The handoff's stated *reason* for the green is wrong and should
be corrected in the record, but the control is sound. **Non-blocking.**

*(For completeness and against my own convenience: my first banner-removal probe also returned green
because I pointed it at `p4-final-adjudication-report-0891d1a.md`, which is **not** bannered — it
stripped 0 lines and modified nothing. I record this as my own invalid probe. The corrected probe,
against the bannered re-review report, strips 36 banner lines and yields 5 failed. My
sidecar-mutation case yielded 1 failed where the handoff reports 2; that is probe-shape dependent
and immaterial — it bites either way.)*

---

## 8. THE BLOCKING FINDINGS

### S-01 · **CONFIRMED DEFECT** · **BLOCKING** — a conditional word in any preceding cell launders the status cell

**Exact requirement.** Adjudication §3.4(4)–(5) and §9(1): subject and status associate *within a
single table row and no wider*; the row is the bound. The module's own governing rule
(`status_claims.py:126-135`, `_CONDITIONAL` note at `:174-190`): *"A conditional marker exempts a
claim only when it INTRODUCES it."*

**Exact file and range.** `eval/control/status_claims.py:704`

```python
elif _CONDITIONAL.search(unit.norm[:token_end]):
    exemption = "hypothetical"
```

where `unit.norm` for a table row is the **whole row's cells joined by `" | "`** (`_row_unit`,
`:576-587`). The exemption window is therefore the entire row prefix, not the clause introducing the
claim.

**Mechanical proof.**

```
| R-07 | plain descriptive text | OPEN |                 -> ('OPEN', None)          LIVE, caught
| R-07 | note: before P5       | OPEN |                  -> ('OPEN','hypothetical') EXEMPT, evaded
| note: before P5 | R-07       | OPEN |                  -> ('OPEN','hypothetical') EXEMPT, evaded
```

Any of `if · unless · until · once · when · whenever · while · before · after · should · would ·
could · cannot · …` in **any cell preceding the polarity token** suffices. These are ordinary words
in descriptive columns — and descriptive columns in any position are an *explicitly authorized*
arrangement.

**End-to-end reproduction** (disposable clone at `3874d4a`, single row appended to a real table in
`ARCHITECTURE.md`, a document the unified guard explicitly requires to be scanned):

```
| **R-07** | ungated live-write paths, to be re-read before P5 | **OPEN — NOT CONTAINED** |
```

→ `test_roadmap_completeness_control.py` + `test_docs_control_system.py` + `test_status_reality.py`
+ `test_switch_consistency.py`: **181 passed, 0 failed.**

**Control**, proving the laundering phrase is the sole cause — the identical row without
`, to be re-read before P5`:

```
| **R-07** | ungated live-write paths | **OPEN — NOT CONTAINED** |
```

→ **2 failed**: `test_r07_is_never_represented_as_contained_anywhere_live` and
`test_10_r07_is_recorded_open_and_never_contained`.

**Consequence.** Any canonical or control document in the unified population can assert
**R-07 OPEN — NOT CONTAINED** in rendered, readable table text with the entire guard set green. This
is exactly the R-01/F-01 defect class the candidate exists to close, displaced from the cell
boundary to the exemption scope. The three anchored documents (`CURRENT.md`, `CLAUDE.md`,
`README.md`) are partially protected by `_CROSS_CELL_ANCHORS`
(`test_roadmap_completeness_control.py:679`), which catches the exempted-canonical-row case — but
that tuple covers **three documents** and no other, and does not constrain **new** rows anywhere.

**Blocks third-finalizer authorization: YES.**

**Narrowly scoped remediation.** Scope the conditional exemption to the claim's **own cell** for
table-row units — i.e. search `_CONDITIONAL` within `[cell_start(status_cell), token_end)` (or the
subject cell's span), not over the joined row prefix — leaving prose-unit behaviour unchanged. Add
mutation operators for a conditional token in a preceding descriptive cell, in each of the
subject-before-status and status-before-subject arrangements.

---

### S-02 · **CONFIRMED DEFECT** · **BLOCKING** — a historical marker in any cell preceding the risk id launders the row

**Exact requirement.** Adjudication §4.3(5): *"attachment is the whole requirement… A marker
inferred from surrounding prose is exactly the ungoverned-marker defect R-03 names, and it is
trivially forgeable."* R-03's fix was to require the marker to **govern** the claim.

**Exact file and range.** `eval/control/status_claims.py:701`

```python
elif _HISTORICAL_MARKER.search(unit.norm[:risk_in_norm.start()]):
    exemption = "marked-historical"
```

Same defect shape as S-01: the search window is the joined-row prefix.

**Mechanical proof.**

```
| R-07 | OPEN — NOT CONTAINED |                              -> ('OPEN', None)               LIVE
| nothing here is superseded | R-07 | OPEN — NOT CONTAINED | -> ('OPEN','marked-historical') EXEMPT
| ⛔ HISTORICAL | R-07 | OPEN — NOT CONTAINED |               -> ('OPEN','marked-historical') EXEMPT
```

Applied to the real `CLAUDE.md:73` canonical row with a leading cell added and the status flipped:
live OPEN = **0**.

The repository's own R-03 authority sentence — *"R-07 remains OPEN and NOT CONTAINED today; nothing
here is SUPERSEDED."* — is correctly caught **in prose**, but its row-shaped equivalent
(`| nothing here is superseded | R-07 | OPEN |`) is **not**. R-03 was closed for sentences and
re-opened for rows by the same widening that closed R-01.

**Consequence.** Identical to S-01: a live OPEN claim renders visibly while the guard set is green.
Additionally, a single leading "Status"/"Notes" column whose text legitimately mentions *superseded*
or *historical* would silently exempt an entire row's status — a false-negative authors would never
suspect.

**Blocks third-finalizer authorization: YES.**

**Narrowly scoped remediation.** For table-row units, require the historical marker to be in the
**subject cell** (preceding the risk id within that cell) or in a designated status/marker column —
not anywhere in the row prefix. Add mutation operators for a marker word in a preceding descriptive
cell.

---

### S-03 · **CONFIRMED DEFECT** · **BLOCKING** — a prose marker immediately above a `<details>` opener launders the whole block

**Exact requirement.** Adjudication §4.3(4)–(5): the marker must be **attached to the block itself**
— its own `<summary>` or its own first body line — *"found by parsing the block, never by proximity
search"*; *"A label in the prose ABOVE a block exempts nothing: one sentence placed before a block
would otherwise launder everything inside it."* The candidate's own docstring
(`status_claims.py:78-80`) states this rule verbatim.

**Exact file and range.** `eval/control/status_claims.py:590-608` (`_prose_blocks`) together with
`:701`. `_prose_blocks` breaks a prose run on a **blank line** or a **table line** only — it does
**not** treat `<details>` / `</details>` tag lines as unit boundaries. So a marker sentence
immediately above the opener merges with the block's first content line into **one claim unit**, and
the `marked-historical` rule at `:701` then exempts a claim that sits inside an **unlabelled** block.

The block-level logic is correct — `details_blocks()` assigns `marker=None`, and the exemption
reported is `marked-historical`, **not** `historical-details`. The leak is entirely through prose
unit boundaries.

**Mechanical proof.**

```
HISTORICAL section follows.
<details>
R-07 remains OPEN.
</details>
                       -> ('OPEN','marked-historical')   EXEMPT   (must be LIVE)
```

Removing one blank line is the entire attack. With a blank line after the marker sentence, the same
input is correctly **LIVE** — which is why **M34 does not catch this**: M34
(`mutate_roadmap_completeness.py:298-304`) injects
`"⛔ HISTORICAL — the superseded notes below.\n\n<details>\n…"` — **with** the blank line. The
battery tests only the separated variant. This is precisely the **RC-01** recurrence the handoff
itself records: a battery drawn from the instrument's field of view measures that field of view.

**End-to-end reproduction** (disposable clone at `3874d4a`, injected into real `CURRENT.md` at the
`## Documents required before proceeding` anchor — the same anchor M32–M38 use):

```
⛔ HISTORICAL — the superseded notes below.
<details>
<summary>Notes</summary>
The four violation residuals keep R-07 OPEN and the write half is NOT CONTAINED.
</details>
```

→ `test_roadmap_completeness_control.py` + `test_docs_control_system.py` + `test_status_reality.py`
+ `test_switch_consistency.py` + `test_false_green_defenses.py` + `test_bootstrap_hermeticity.py`:
**227 passed, 0 failed.**

The claim text deliberately reinstates **two** of F-01's corrected stale claims — *"four violation
residuals remain"* and *"keeps R-07 open"* — in a construction the legacy copula regex in
`test_status_reality.py:240` cannot see. (An earlier probe using the literal phrase
`R-07 remains OPEN` **was** caught, but only by that legacy word-order substring regex — the very
instrument the new parser was built to replace — not by the parser.)

**Consequence.** The R-02 attachment invariant — the blocking finding this candidate exists to
remediate — is defeated by deleting one blank line. `CURRENT.md`, the designated status authority,
can carry a live OPEN claim inside an unlabelled `<details>` block with every guard green. This is
the same channel as the incident `CURRENT.md` itself records.

**Blocks third-finalizer authorization: YES.**

**Narrowly scoped remediation.** Make `_prose_blocks` break a prose run at any structural
`<details>` / `</details>` tag line (i.e. a tag line not inside code), exactly as it already breaks
at a table line. That confines a prose marker to its own side of the boundary and restores
"attachment is the whole requirement". Re-point M34 to the **adjacent** (no blank line) variant, and
add the separated variant as a second case so both are covered.

---

### FULL EXEMPTION-REACHABILITY MAP (S-01 + S-02, measured)

| Row shape | Parsed |
|---|---|
| `\| R-07 \| OPEN \|` | `('OPEN', None)` — live ✅ |
| `\| note: before P5 \| R-07 \| OPEN \|` | `('OPEN','hypothetical')` — **evaded** |
| `\| R-07 \| note: before P5 \| OPEN \|` | `('OPEN','hypothetical')` — **evaded** |
| `\| R-07 \| OPEN \| note: before P5 \|` | `('OPEN', None)` — live ✅ |
| `\| HISTORICAL \| R-07 \| OPEN \|` | `('OPEN','marked-historical')` — **evaded** |
| `\| R-07 \| HISTORICAL \| OPEN \|` | `('OPEN', None)` — live ✅ |
| `\| R-07 \| OPEN \| HISTORICAL \|` | `('OPEN', None)` — live ✅ |

---

## 9. NON-BLOCKING FINDINGS

### S-04 · **NON-BLOCKING RESIDUAL RISK** — a header row is rendered text but is never a claim

`| R-07 | OPEN — NOT CONTAINED |` written as a table **header** (with a delimiter row beneath)
parses to **zero** claims. This is *specified* behaviour — the adjudication requires header and
separator rows not be parsed as claims, and the parser is compliant. But a header row renders as
visible document text, so it is a structurally sanctioned place to write a status claim that no
guard reads. No such case exists in the corpus today.

**Does not block.** Remediation, if taken later: treat a header row carrying the risk id **and** a
polarity token as a claim, or add a guard asserting no header row mentions the risk id.

### S-05 · **NON-BLOCKING RESIDUAL RISK** — no anti-drift guard prevents reintroducing the raw details regex

All six copies of `re.sub(r"<details>.*?</details>", …)` are now delegated, but nothing prevents a
seventh from being written. Given the defect recurred in six independent copies, a guard asserting
that no module under `eval/` performs its own unconditional `<details>` stripping would make the
unification durable rather than conventional.

**Does not block.**

### S-06 · **EVIDENCE DEFICIENCY** — the handoff's stated reason for its green F-03 probe is wrong

Adjudicated in full at §7.3. The control is sound; the *explanation* in handoff §7 ("that phrase is
not the verdict line the record binds") is factually incorrect — the phrase **is** bound in two
load-bearing reports and mutating it yields 15 failed. The green result indicates an **invalid
probe**, not a non-load-bearing mutation and not a binding gap.

**Does not block**, but the record should be corrected so no later reader infers a real gap where
none exists, or infers that the phrase is unbound.

### S-07 · **TEST-ENVIRONMENT LIMITATION** — reproduced and disclosed

The handoff's §14 environment note is accurate. A clone with a **symlinked** `.venv` is reported
dirty and raises **two extra NOT-RUN skips** — I reproduced this exactly (2043 passed/1 skipped with
a copied venv; 2041 passed/3 skipped with a symlinked one; 2044 collected in both, zero failures in
both). Not a candidate defect.

### Carried residuals — confirmed accurate, not discharged

**RR-01** (closed vocabulary `HISTORICAL`/`SUPERSEDED`; `ARCHIVED` and `REJECTED EVIDENCE` read as
live — verified fail-closed) · **RR-02** (fenced content is read — verified) · **RR-03**
(`README.md` outside the discovered population, reached only through the union — verified; the
handoff's M24 note is correct and is a genuine finding) · **RR-04** (marker-precedes-claim is a new
authoring constraint) · **RC-01** (recurrence — **and S-03 is a live instance of it**) ·
**F-06, AD-01, AD-02, RC-02, RC-03** carried from prior adjudications, not reopened here.

---

## 10. TESTS AND REPRODUCTION — INDEPENDENTLY REPRODUCED

| Check | Claimed | Reproduced | |
|---|---|---|---|
| Canonical suite | 2043 / 0 / 1 / 2044 | **2043 passed · 0 failed · 1 skipped · 2044 collected** (387.2s) | ✅ |
| Disposable clean clone | same | **2043 / 0 / 1 / 2044** from a fresh venv, declared deps only | ✅ |
| Clean-clone gate | PASS | **`CLEAN-CLONE GATE: PASS`** (exit 0) — fresh venv, declared deps only, independently reproducing **2043 / 0 / 1 / 2044**; control guards and AC-SAFE-012/013 + AC-SEC-001 all exit 0. Run **only** in a disposable clone, since it writes `GATE-RESULT.json`; the primary tree's receipt was never touched | ✅ |
| `TEST-NODE-MANIFEST` | 2044, exact set equality | `node_count: 2044`; runner enforces exact node-identity equality and aborts on any divergence — it ran to completion | ✅ |
| `config_sha256` | `22f42941…` unchanged | `22f4294195baec814e441c94ed34d5e20fd2f3975bcece35fd0a65962f255a2e` | ✅ |
| Approved skips | exactly one | 1 skipped | ✅ |
| Roadmap/status mutation battery | 40/40, 0 defective, 0 SKIP-INVALID | **40/40 correct (37 CAUGHT + 3 must-stay-GREEN), 0 defective, 0 SKIP-INVALID** | ✅ |
| P4 boundary mutation battery | 61/61 | **61/61 mutants caught** | ✅ |
| Corpus counts | 58 / 84 / 49 / 0 | **58 / 84 / 49 / 0**, exempt 35 | ✅ |
| Production `GateRegistry` | EMPTY | 0 constructions, 0 `register_gate` calls | ✅ |
| Detection count | 13 | `detection_edges: 13` | ✅ |
| Receipts vs `06ebfdb3` | identical | `SUITE-RESULT.json` and `GATE-RESULT.json` identical blobs | ✅ |
| Locks | unheld | both `flock`-probed unheld | ✅ |
| Protected refs | unchanged | `main` = `origin/main` = `152574e4…`; all 32 `refs/preserve/*` and both archive branches intact | ✅ |
| Pushed | nothing | `git branch -r --contains HEAD` empty | ✅ |

`scripts/finalize_status.py` was **not** run. No targeted adjudication was performed. P5 was not
begun. No effect was deployed or enabled.

### 10.1 Mutation battery integrity — reviewed, not inherited

Each new operator (M22–M40) was read individually against its target text. Every case targets a
**real, non-empty** structure — the battery SETUP-FAILs otherwise, and reported **0 SKIP-INVALID**
and **0 defective**, which I reproduced. Restoration is byte-exact: `git status` was clean after the
run (only the untracked `.venv`). The battery verifies the failure was an `AssertionError` rather
than an unrelated exception, so no case passes because parsing crashed for an unrelated reason. The
three `expect: GREEN` negative cases (M30 cross-row, M31 cross-table, M33 correctly-labelled block)
all stayed green, which is what distinguishes a row-aware parser from one that fires on anything
nearby. The M24 population note is a genuine finding and is correctly recorded.

**The required mutation classes are present and caught** — subject/status in separate cells (M22–M24),
reversed cell order (M26), extra columns (M27), escaped pipes (M28), inline code (M29), cross-row
(M30) and cross-table (M31) false association, unlabelled details with OPEN (M32), removed marker
(M35), marker moved outside the block (M34), malformed details (M36), nested details (M37), and the
R-01 × R-02 composition (M38).

**The gap is coverage, not integrity:** no operator tests a conditional or historical token in a
**preceding descriptive cell** (S-01, S-02), and M34 tests only the blank-line-separated
marker-outside variant (S-03).

---

## 11. PRESERVATION AND ATTRIBUTION — BOTH REJECTED CANDIDATES INTACT

All ten refs resolve, with the parents required:

| Artifact | Ref | Object | Parent |
|---|---|---|---|
| Rejected candidate | `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` | `11c911244304…` | `06ebfdb3` |
| — archive branch | `refs/heads/archive/p4/r07-rejected-11c9112` | `11c911244304…` | `06ebfdb3` |
| — complete worktree | `refs/preserve/p4-r07-rejected-worktree-11c9112` | `6224b36e1961…` | **`11c9112`** |
| — targeted review | `refs/preserve/p4-r07-closure-targeted-review-11c9112` | `fa4c459b0507…` | **`11c9112`** |
| — targeted adjudication | `refs/preserve/p4-r07-closure-targeted-adjudication-11c9112` | `030c5954ba26…` | **`11c9112`** |
| Rejected replacement | `refs/preserve/p4-r07-closure-rejected-replacement-candidate-4d12b0e` | `4d12b0e41cfa…` | `06ebfdb3` |
| — archive branch | `refs/heads/archive/p4/r07-rejected-replacement-4d12b0e` | `4d12b0e41cfa…` | `06ebfdb3` |
| — complete worktree | `refs/preserve/p4-r07-rejected-replacement-worktree-4d12b0e` | `6b88dd090ae9…` | **`4d12b0e`** |
| — targeted review | `refs/preserve/p4-r07-closure-replacement-targeted-review-4d12b0e` | `62df39dd531e…` | **`4d12b0e`** |
| — targeted adjudication | `refs/preserve/p4-r07-closure-replacement-targeted-adjudication-4d12b0e` | `ce5dbb30b8d9…` | **`4d12b0e`** |

**Report sidecars verified by recomputation:**

| Report | Recomputed SHA-256 | Sidecar |
|---|---|---|
| review `11c9112` | `1659338af1389ec1c4c77c3fc38bffcff296332556a7beeca50ec92ccd4e9222` | **match** ✅ |
| adjudication `11c9112` | `a8cb27684e0b6bd108de2260be1eb9809af8c392a5ead7a6e4c81e6847d00335` | **match** ✅ |
| review `4d12b0e` | `8c26a311cb80d26715624f43ad5b062fece3ca9319f21948cd242651f95a6d42` | **match** ✅ |
| adjudication `4d12b0e` | `62d2d26771194e1d9fc2fcd193d2a4c8fd73f74d90ed4410275748c65435990f` | **match** ✅ |

**Attribution is mechanically exclusive.** No report of `11c9112` or `4d12b0e` appears anywhere in
`3874d4a`'s tree. **No prior report mentions `3874d4a` at all** (0 occurrences in all four). Each
report names and is parented to the candidate it actually reviewed. **No prior review or
adjudication can be read as reviewing this successor.** ✅

---

## 12. SECRET AND OBJECT HYGIENE — VERIFIED, NOT TRUSTED

Swept the candidate tree and every preservation tree (`3874d4a`, both worktree preservations, all
four report preservations) for `.env`, credentials, tokens, keys, caches, virtualenv content and
session scratchpad data.

The **only** matches in any tree are `.env.example` (a placeholder template — every secret field is
empty: `ANTHROPIC_API_KEY=`, `OPENAI_API_KEY=`) and
`docs/architecture/decisions/ADR-014-credential-and-machine-identity.md` (a design document, matched
on the word "credential"). **No `.env`, no credential material, no token, no `__pycache__`, no
`.venv/`, no `.pytest_cache`, no scratchpad path entered any candidate or preservation Git object.** ✅

---

## 13. FINDING SUMMARY

| ID | Severity | Class | Blocks third finalizer |
|---|---|---|---|
| **S-01** | **BLOCKING** | confirmed defect — conditional exemption spans the whole row | **YES** |
| **S-02** | **BLOCKING** | confirmed defect — historical marker exemption spans the row prefix | **YES** |
| **S-03** | **BLOCKING** | confirmed defect — prose marker adjacent to a `<details>` opener launders the block | **YES** |
| S-04 | LOW | non-blocking residual risk — header rows are visible but unparsed | no |
| S-05 | LOW | non-blocking residual risk — no anti-drift guard on the details regex | no |
| S-06 | LOW | evidence deficiency — handoff's F-03 probe explanation is incorrect | no |
| S-07 | INFO | test-environment limitation — symlinked-venv skips, reproduced | no |

**Minimum remediation for a fourth candidate:** three narrowly scoped parser corrections (S-01
exemption window → the claim's own cell; S-02 marker window → the subject cell; S-03 `_prose_blocks`
breaks at structural `<details>` tag lines), plus mutation operators for each of the three evasions
and re-pointing M34 to the adjacent variant. No change to `src/`, `configs/` or `data/`; no change to
the containment mechanism; no re-litigation of F-01, F-03, R-03, R-04 or R-05, all of which are
correctly closed and must be retained unchanged.

---

## 14. WHAT THIS REVIEW DID NOT DO

Did not remediate · did not modify the candidate · did not adjudicate · did not finalize · did not
run `finalize_status.py` · did not begin P5 · did not deploy or enable any effect · did not amend,
commit to the product branch, reset, restore, rebase, merge, checkout, stash, clean, update any
branch ref or push · did not modify, move or reinterpret any preservation ref · did not alter the
review or adjudication of `11c9112` or `4d12b0e` · did not resume any previous session. All
implementation behaviour was measured in disposable `--no-local` clones; the primary worktree,
index and branch were never written.

---

**VERDICT: REJECT — TARGETED REMEDIATION REQUIRED.**

**This document is a review. It certifies nothing beyond its findings, adjudicates nothing and
authorizes no finalization. This candidate owes its own separate targeted adjudication; no third
finalizer may run.**
