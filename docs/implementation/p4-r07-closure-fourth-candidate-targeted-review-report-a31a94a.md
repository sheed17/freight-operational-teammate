> # ⛔ INDEPENDENT REVIEW — NOT CURRENT AUTHORITY
> **This is a completely fresh targeted independent review of one candidate.** It certifies nothing,
> adjudicates nothing, closes no risk, sets no acceptance criterion and authorizes no finalization.
> The status authority is [`CURRENT.md`](CURRENT.md) and the registry; the operating guide is
> [`../../CLAUDE.md`](../../CLAUDE.md).
>
> It reviews **exactly** `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24` and nothing else. No earlier
> review or adjudication in this family may be read as reviewing this candidate, and this report may
> not be read as reviewing `11c9112`, `4d12b0e` or `3874d4a`.

# P4 R-07 CLOSURE — FOURTH CANDIDATE `a31a94a`, FRESH TARGETED INDEPENDENT REVIEW

**Candidate:** `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24`
**Tree:** `637580b64ca666695d0811c4119e866de6100ce9`
**Parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (certified second-finalizer metadata commit)
**Branch:** `p4/adapter-containment-completion`
**Replaces rejected successor:** `3874d4a1bd02cdf81525aba52268e7aa44343457`

---

## VERDICT

# ACCEPT FOR SEPARATE TARGETED ADJUDICATION

All three blocking findings the controlling adjudication of `3874d4a` raised — **S-01**, **S-02**
and **S-03** — are completely remediated, by the narrow delta that adjudication authorized and by
nothing wider. Every figure the builder's handoff asserts was independently re-derived on this tree
and every one reproduced exactly. Five non-blocking residuals are recorded in §12; none asserts a
false status, none conceals a live claim, and none compounds with another to do so.

**Reviewer standing.** This session did not implement P4; did not author `11c9112`, `4d12b0e`,
`3874d4a` or `a31a94a`; conducted no prior review or adjudication in this family; ran neither
finalizer and reconstructed no finalization evidence. No previous session was resumed. All runtime
behaviour was measured in disposable `--no-local` clones, never from the primary worktree. The
primary repository's branch, worktree and index were byte-exactly unchanged throughout (§14).

---

## 1. IDENTITY, TOPOLOGY AND ENVIRONMENT — MECHANICALLY VERIFIED

| Property | Required | Observed | |
|---|---|---|---|
| commit | `a31a94aa…` | `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24` | ✅ |
| tree | `637580b6…` | `637580b64ca666695d0811c4119e866de6100ce9` | ✅ |
| parent | `06ebfdb3…` | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` | ✅ |
| parent count | 1 (not a merge) | `1` | ✅ |
| descendant of `3874d4a` | no | `git merge-base --is-ancestor` → false | ✅ |
| descendant of `4d12b0e` | no | false | ✅ |
| descendant of `11c9112` | no | false | ✅ |
| branch | `p4/adapter-containment-completion` | same, HEAD = candidate | ✅ |
| branch moved since creation | no | reflog `@{0}` is `a31a94a` | ✅ |
| working tree / index | clean | 0 modified, 0 staged | ✅ |
| finalizer lock | unheld | `lsof` → 0 holders (0-byte file, `flock`-based) | ✅ |
| builder-worktree lock | unheld | `lsof` → 0 holders | ✅ |
| pytest / mutation processes | none | `ps` → none | ✅ |
| `main` = `origin/main` | yes | both `152574e4f4f2969468c9d31b1e705188896175b5` | ✅ |
| remote P4 branch | none | `git ls-remote --heads origin` → 0 matches | ✅ |
| pushed | nothing | no remote ref advanced | ✅ |

### 1.1 PRODUCING topology is real, not asserted

Evaluated by executing `repo_state()` from `eval/tests/test_status_reality.py` against this tree:

```
recorded content_commit : 42ea24cfc76fac19406e7eaa44b695b8d032b3aa
HEAD                    : a31a94aa…      HEAD^ : 06ebfdb3…      HEAD^^ : 42ea24cf…
HEAD^^..HEAD^ changed   : BUILD-STATUS.yaml, CURRENT.md, GATE-RESULT.json,
                          IMPLEMENTATION-REGISTRY.yaml, SUITE-RESULT.json   (all 5 declared)
REPO STATE              : PRODUCING
```

`recorded == HEAD^^`, `HEAD^` is a pure status-metadata commit, `HEAD` is the next content commit.
**Legal PRODUCING.** The builder's topology claim is also correct: a second content commit stacked
on `3874d4a` would leave `recorded` matching neither `HEAD`, `HEAD^` nor `HEAD^^`, which
`repo_state()` raises on — replacement in place against `06ebfdb3` was the only legal shape.

### 1.2 The six-path delta

Against the rejected successor `3874d4a` (which shares this candidate's parent), the delta is
**exactly six paths**, verified by `git diff --name-status`:

```
M  docs/implementation/TEST-NODE-MANIFEST.json
A  docs/implementation/p4-r07-closure-fourth-targeted-review-handoff.md
A  docs/implementation/p4-r07-closure-fourth-targeted-review-handoff.md.sha256
M  eval/control/status_claims.py
M  eval/tests/test_roadmap_completeness_control.py
M  scripts/mutate_roadmap_completeness.py
```

Note for the adjudicator: against the **certified parent** `06ebfdb3` the delta is 56 paths — that
is the whole R-07 closure content commit, which this candidate carries in place of `3874d4a`. The
"six paths" figure is the *remediation* delta and is correct in that sense only. Both were measured.

### 1.3 Review environment

A disposable `git clone --no-local --no-checkout` of the product repository, detached at
`a31a94aa8239113ec8ea3c02b5ef6fad922a1b24`, with a freshly built venv (`pip install -e ".[dev]"`).
Four such clones were used (review, mutation battery, anti-vacuity at `3874d4a`, evidence binding).
The primary worktree was never executed from and never written to.

---

## 2. S-01 — CLAIM-LOCAL CONDITIONAL CLASSIFICATION · **COMPLETELY REMEDIATED**

### 2.1 The implementation, read structurally

Rows are parsed by `table_rows()` into `TableRow`s; `_row_unit()` joins each body row's normalized
cells with a literal `" | "` and records each cell's `[start, end)` span in `cell_spans`. Subject
and status associate across the **whole row** (`_polarity()` searches `unit.norm`), which is R-01
and is untouched. Exemption is decided separately:

```python
elif _CONDITIONAL.search(unit.norm[_governing_window_start(unit, token_start):token_end]):
    exemption = "hypothetical"
```

`_governing_window_start` (`eval/control/status_claims.py:784-818`) returns `0` for prose (whole
unit, unchanged), the **start of the cell containing the position** for a table row, and — when the
offset resolves to no cell at all, i.e. it fell in the `" | "` join — the position itself, admitting
no preceding text. That last branch is the fail-closed direction and is correct: it cannot silently
restore the row-wide search.

So the governing window for a conditional is `[start of the STATUS TOKEN's own cell, token_end)`.
Ordering (R-03) is retained by the window's upper bound; cell-locality (S-01) by its lower bound.

### 2.2 Hostile reproduction — my own cases, not the builder's

Run against the candidate parser and, for anti-vacuity, against `3874d4a`'s parser over identical
inputs:

| Case | Required | Candidate | `3874d4a` |
|---|---|---|---|
| `\| Conditional \| if X happens \| R-07 \| OPEN — NOT CONTAINED \|` | LIVE | **LIVE** ✅ | exempt ❌ |
| `\| Evidence \| recorded when the gate ran \| R-07 \| OPEN — NOT CONTAINED \|` | LIVE | **LIVE** ✅ | exempt ❌ |
| `\| Before remediation \| evidence \| R-07 \| OPEN — NOT CONTAINED \|` | LIVE | **LIVE** ✅ | exempt ❌ |
| `\| R-07 \| OPEN — NOT CONTAINED \| verified after the run \|` | LIVE | **LIVE** ✅ | LIVE |
| `\| R-07 \| OPEN — NOT CONTAINED \| while collecting evidence \|` | LIVE | **LIVE** ✅ | LIVE |
| `\| R-07 \| measured when the run finished \| OPEN — NOT CONTAINED \|` | LIVE | **LIVE** ✅ | exempt ❌ |
| `\| R-07 \| may not be recorded CONTAINED until the gate asserts empty \|` | **EXEMPT** | **exempt** ✅ | exempt |

### 2.3 Marker-position matrix — every position required by the review scope

Conditional placed in each structural position, claim `| R-07 | OPEN — NOT CONTAINED |`:

| Position | Result |
|---|---|
| before the subject (separate cell) | **LIVE** ✅ |
| between subject and status (separate cell) | **LIVE** ✅ |
| after the status (separate cell) | **LIVE** ✅ |
| in the table **header** row | **LIVE** ✅ |
| in a **neighbouring row** | **LIVE** ✅ |
| in a **neighbouring table** | **LIVE** ✅ |
| in **prose outside** the table (blank line and adjacent) | **LIVE** ✅ |
| inside the **status cell**, before the token | exempt — *by design*, see FR-01 |
| inside **inline code** in the status cell | exempt — code mask is structure-only, documented |

**Association was not destroyed.** Cross-cell subject→status association still resolves in every
case above (`subject_cell` and `status_cell` are populated and differ), and the three canonical
cross-cell anchors (`CURRENT.md`, `CLAUDE.md`, `README.md`) still parse cross-cell and read
CONTAINED — confirmed by the corpus recomputation in §6.

**No unrelated cell can launder a claim.** S-01 is closed.

---

## 3. S-02 — CLAIM-LOCAL HISTORICAL CLASSIFICATION · **COMPLETELY REMEDIATED**

### 3.1 The implementation

```python
elif _HISTORICAL_MARKER.search(
        unit.norm[_governing_window_start(unit, risk_in_norm.start()):risk_in_norm.start()]):
    exemption = "marked-historical"
```

Window = `[start of the SUBJECT's own cell, start of the risk id)`. Same function, same two axes.

### 3.2 Hostile reproduction

| Case | Required | Candidate | `3874d4a` |
|---|---|---|---|
| `\| Historical example \| unrelated text \| R-07 \| OPEN — NOT CONTAINED \|` | LIVE | **LIVE** ✅ | exempt ❌ |
| `\| Evidence from superseded test \| R-07 \| OPEN — NOT CONTAINED \|` | LIVE | **LIVE** ✅ | exempt ❌ |
| `\| R-07 \| OPEN — NOT CONTAINED \| historical note about another field \|` | LIVE | **LIVE** ✅ | LIVE |
| `\| Historical \| R-07 \| OPEN — NOT CONTAINED \|` | LIVE | **LIVE** ✅ | exempt ❌ |
| `\| R-07 \| superseded evidence column \| OPEN — NOT CONTAINED \|` | LIVE | **LIVE** ✅ | LIVE |
| `\| HISTORICAL R-07 \| OPEN — NOT CONTAINED \|` | **EXEMPT** | **exempt** ✅ | exempt |

Marker positions: header · neighbouring row · neighbouring table · prose above (blank-line and
adjacent) — **all LIVE**. In-cell before the subject — exempt, which is the form the live corpus
actually uses.

### 3.3 The closed vocabulary was not broadened, and no row-level construct was invented

`_HISTORICAL_MARKER` is byte-unchanged: `r"\bHISTORICAL\b|\bSUPERSEDED\b"`. `ARCHIVED` and
`REJECTED EVIDENCE` still read as **live**, which is the fail-closed direction. No whole-row marker
construct exists — I searched for one and there is none; adjudication §5.3 forbade inventing one.
Exempt claims remain **visible** (`parse_status_claims` returns them with their reason), not deleted:
35 exempt claims are enumerable in the union corpus (§6).

### 3.4 The corrected pre-existing assertion — a genuine correction, not test weakening

`test_the_historical_marker_must_govern_the_claim_it_exempts`. The old body contained:

```python
assert not status_claims.live_open_claims("| ⛔ HISTORICAL | R-07 | OPEN — NOT CONTAINED |"), (
    "a marker in an EARLIER cell of the same row must govern the row")
```

That is the S-02 defect written down as required behaviour. The replacement **flips** it to assert
the row is LIVE, and **adds** a new must-stay-exempt assertion for the in-cell form the corpus
actually uses. The test went from **4 assertions to 5**; the two R-03 negatives (trailing marker,
later-cell marker) and the prose governing case are all retained verbatim.

**Verified independently that replacement was required, not convenient:** the old assertion is
mechanically incompatible with the adjudicated S-02 requirement — the exact string it asserted must
be exempt is the exact string the adjudication requires to be live. It could not have been kept.

**Verified the new must-stay-exempt form is real:** `PHASE-OUTPUTS.md:109` and `pr-sequence.md:33`
both carry `marked-historical` exemptions with the marker in the subject's own cell (§7). Deleting
the marker rule would now fail M58 and this assertion.

---

## 4. S-03 — DETAILS STRUCTURAL BOUNDARIES · **COMPLETELY REMEDIATED**

`_prose_blocks` now terminates a prose run at every structural `<details>`, `</details>`,
`<summary>`, `</summary>` tag (`_STRUCTURAL_TAGS`, `_structural_tag_spans`), in addition to blank
lines and table lines. The boundary is the **tag**, not the line carrying it. Tags inside code are
literal mentions and are not boundaries, by the same `_code_mask` rule `details_blocks()` uses.

### 4.1 All fourteen required arrangements, reproduced

| # | Arrangement | Required | Candidate | `3874d4a` |
|---|---|---|---|---|
| 1 | external marker **adjacent** to `<details>` (no blank line) | LIVE | **LIVE** ✅ | exempt ❌ |
| 2 | external marker separated by a **blank line** | LIVE | **LIVE** ✅ | LIVE |
| 3 | **valid** marker attached (first body line) | EXEMPT | exempt ✅ | exempt |
| 3b | **valid** marker in the block's own `<summary>` | EXEMPT | exempt ✅ | exempt |
| 4 | historical marker **inside the summary** | EXEMPT | exempt ✅ | exempt |
| 5 | **live R-07 claim inside the summary** | LIVE, visible | **LIVE** ✅ | LIVE |
| 6 | live R-07 **table row inside details content** | LIVE | **LIVE** ✅ | LIVE |
| 7 | **unlabelled** nested inside **labelled historical** | LIVE | **LIVE** ✅ | exempt ❌ |
| 8 | **labelled historical** nested inside **live** | EXEMPT | exempt ✅ | exempt |
| 9 | **unterminated `<details>`**, no blank lines | LIVE | **LIVE** ✅ | exempt ❌ |
| 10 | **unterminated `<summary>`** (no closing tag) | LIVE | **LIVE** ✅ | exempt ❌ |
| 11 | malformed summary `</summary  >` | (well-formed to the parser) | exempt ✅ | exempt |
| 11b | stray `</summary>` with no opener | EXEMPT (own first body line *is* the marker) | exempt ✅ | exempt |
| 12 | **missing `</details>`** after a labelled summary | LIVE | **LIVE** ✅ | exempt ❌ |
| 13 | **multiple adjacent** details blocks (1st labelled, 2nd not) | LIVE | **LIVE** ✅ | exempt ❌ |
| 14 | details tags **embedded on lines with extra text** | LIVE | **LIVE** ✅ | exempt ❌ |
| 14b | marker text then `<details>` on the **same line** | LIVE | **LIVE** ✅ | exempt ❌ |

Cases 9, 10 and 12 also confirm `details_structure_defects()` **reports** the malformation, so the
failure is loud as well as closed.

**Eight laundering arrangements that the rejected parser accepted are closed.** Classification is now
identical with and without blank lines — the divergence that was the defect signature is gone.

### 4.2 The unterminated-summary end-of-line boundary — reviewed closely

The builder added one boundary beyond the adjudication's literal wording
(`_structural_tag_spans`, `eval/control/status_claims.py:638-651`): an unterminated `<summary>`
installs a synthetic boundary at the end of its own line.

| Question | Determination |
|---|---|
| Mechanically required? | **Yes.** Case 10 above escapes without it: `_build_block` correctly reads *no* marker from a malformed summary, but with no closing tag there is no boundary either, so the void label's text ran into the block body and the prose marker rule granted `marked-historical` from a label the module had just declared void. Confirmed by direct reproduction on `3874d4a`. |
| Narrow? | **Yes.** It fires only when the next structural tag after a `<summary>` opener is not a `</summary>`. A properly closed summary — including one spanning multiple lines — installs no synthetic boundary (verified). |
| Fails closed? | **Yes.** More boundaries mean smaller units, which can only *remove* exemption reach, never grant it. |
| Creates unrelated parser behaviour? | **No.** Prose regressions preserved: `HISTORICAL note: R-07 remains OPEN…` still exempt; `This is HISTORICAL. R-07 remains OPEN…` still LIVE (R-03 ordering across sentences). |
| Preserves claims inside valid summary content? | **Yes.** Case 5 and a live claim inside an *unterminated* summary both parse and stay **LIVE** — they do not vanish. |
| Classifies all malformed markup as historical? | **No** — the opposite. Every malformed form in §4.1 resolves **LIVE**. |

### 4.3 No live claim disappears — fuzz

300 arrangements of a live R-07 claim surrounded by every combination of `<details>`, `</details>`,
`<summary>`, `</summary>`, a paired summary, a nested opener, a bare `HISTORICAL`, a table fragment
and plain text, at three separator widths:

```
arrangements tested                              : 300
arrangements where the claim PARSED TO NOTHING   :   0
live 280 / exempt 20   — identical to 3874d4a on this population
```

**Parsing failure cannot silently remove a live claim.** Confirmed.

---

## 5. MUTATION COVERAGE — REPRODUCED, INCLUDING ANTI-VACUITY

### 5.1 Battery integrity, reviewed before its result was believed

`scripts/mutate_roadmap_completeness.py` refuses to start unless every guard is green; treats a
**missing anchor as a battery defect, never a skip**; asserts the mutation changed bytes; requires
the guard to fail with an **`AssertionError`** (an unrelated exception is scored *WRONG REASON*, not
a catch); restores byte-exactly and asserts the restoration; and restores in a `finally`.

### 5.2 Result on this candidate — reproduced in a disposable clone

```
battery: 58/58 correct (52 must-be-CAUGHT, 6 must-stay-GREEN), 0 defective
```

Zero `MISS`, zero `SKIP-INVALID`, zero `WRONG REASON`, zero `FALSE POSITIVE`. Worktree clean and
byte-exact afterwards. **Zero SKIP-INVALID is real** — every case's anchor was positively found.

### 5.3 Operator coverage against the review's required list

| Required family | Operators present | Verified |
|---|---|---|
| S-01 `if` unrelated preceding cell | **M47** | CAUGHT |
| S-01 `when` evidence cell | **M48** | CAUGHT |
| S-01 `before` between subject and status | **M49** | CAUGHT |
| S-01 `after` after status | **M50** | CAUGHT (regression bound) |
| S-01 `while` description cell | **M51** | CAUGHT |
| S-01 legitimate attached conditional | **M52** | **stays GREEN** |
| S-02 `HISTORICAL` unrelated preceding cell | **M53** | CAUGHT |
| S-02 `SUPERSEDED` unrelated cell | **M54** | CAUGHT |
| S-02 marker in a header | **M55** | CAUGHT |
| S-02 marker in a neighbouring row | **M56** | CAUGHT |
| S-02 marker after status in notes | **M57** | CAUGHT |
| S-02 legitimate attached marker | **M58** | **stays GREEN** |
| S-03 adjacent external marker | **M34** (retargeted) | CAUGHT |
| S-03 blank-line external marker | **M41** | CAUGHT |
| S-03 unterminated details, no blank lines | **M42** | CAUGHT |
| S-03 unterminated summary | **M45** | CAUGHT |
| S-03 nested unlabelled | **M43** | CAUGHT |
| S-03 nested labelled (in live) | **M44** | **stays GREEN** |
| S-03 conditional twin | **M46** | CAUGHT |
| S-03 marker moved outside the block | **M34 / M41** | CAUGHT |

Every required operator exists, and each family carries its own must-stay-GREEN negative — so a
"remediation" that deleted the exemption rules outright would **not** score full marks.

**M34 retargeting confirmed legitimate.** Its old fixture used a blank line before `<details>`, an
arrangement a blank line already bounded — so it certified "proximity is not attachment" on a tree
where the adjacent form escaped entirely. The blank-line form is retained separately as **M41**;
nothing was lost.

### 5.4 Anti-vacuity — reproduced independently

The candidate's `mutate_roadmap_completeness.py` copied onto the **`3874d4a` tree** (that tree's own
parser, guards and tests), fresh clone, fresh venv:

```
battery: 47/58 correct (52 must-be-CAUGHT, 6 must-stay-GREEN), 11 defective
```

The eleven MISSES are **exactly**:

```
M34 M42 M43 M45 M46 M47 M48 M49 M51 M53 M54
```

identical to the set the handoff claims. Each miss is a real defect the new operator attacks; the
five already-CAUGHT operators (M41, M50, M55, M56, M57) are regression bounds and the three
must-stay-GREEN negatives (M44, M52, M58) stayed green on both trees. **The new battery is evidence,
not fixtures.**

### 5.5 P4 boundary battery

```
61/61 mutants caught
```
Byte-exact restoration; worktree clean afterwards.

---

## 6. CORPUS COUNTS — RECOMPUTED WITH AN INDEPENDENT INSTRUMENT

Both views recomputed on this tree with my own script, not the handoff's:

| Population | Documents | Claims | live CONTAINED | **live OPEN** | quoted | hypothetical | marked-historical |
|---|---|---|---|---|---|---|---|
| **discovered** (`live_authority_documents`) | **57** | **82** | **47** | **0** | 20 | 8 | 7 |
| **union** (+ `CURRENT`/`CLAUDE`/`ARCHITECTURE`/`README`) | **58** | **84** | **49** | **0** | 20 | 8 | 7 |

Both match the handoff exactly, and were not accepted because they match.

### 6.1 Why the two views differ

The discovered population is derived by `status_claims.live_authority_documents()` — current-authority
documents plus root control docs and agent lenses, minus the review family, historical documents,
frozen `U-*-ACCEPTANCE.yaml` contracts and the registry itself. `test_docs_control_system.py`
additionally **unions** the four landing documents so none can drop out silently. The only document
the union adds is **`README.md`** (+1 document, +2 claims, +2 live CONTAINED). `CURRENT.md`,
`CLAUDE.md` and `ARCHITECTURE.md` are already discovered. The difference is therefore fully
explained and is exactly 1 document / 2 claims.

### 6.2 The counts are not an artefact of over-exemption

* **Per-claim comparison against the rejected parser**, run over the *same* 58 documents so only
  parser behaviour varies: **84 claims compared, 0 documents differing — classification is
  byte-identical** on `(line, polarity, exemption, kind, subject_cell, status_cell, excerpt)`.
  Zero claims changed state. The narrowing removes only capability the corpus never uses.
* **Zero live OPEN is not over-exemption:** all 23 OPEN-polarity claims in the union population are
  individually enumerated in §7 with a valid *attached* exemption. 47/49 live CONTAINED claims remain
  live and visible — the construction did not disappear.
* **No document disappears for carrying capability rather than status:** 23 of 57 discovered
  documents carry an R-07 claim; the other 34 are in the population and simply assert nothing about
  R-07. `live_authority_documents` asserts `len(out) >= 15` and the guards assert
  `contained_claims >= 5`, so an empty or collapsed corpus fails rather than passing silently.
* **Required documents positively anchored:** `CURRENT.md`, `CLAUDE.md`, `ARCHITECTURE.md`,
  `LEGACY-DISPOSITION.md`, `BUILD-STATUS.yaml`, `phase-0-baseline-manifest.yaml` all present in the
  discovered population; `README.md` reached through the union, and `test_docs_control_system.py`
  asserts each of `CURRENT`, `CLAUDE`, `ARCHITECTURE`, `README`, `LEGACY` is in it.
* **Counts do not rely on malformed parser output:** `details_structure_defects()` returns empty
  across the population.

---

## 7. F-01 STALE-CLAIM CLEANUP — RETAINED IN FULL

Every OPEN-polarity claim in the union population, with its exemption:

| Exemption | Count | Examples |
|---|---|---|
| `quoted` | 14 | `principal-architect-supervisor.md:61,92`, `EFFECT-PATH-INVENTORY.yaml:28,64,141`, `LEGACY-DISPOSITION.md:436`, `phase-0-baseline-manifest.yaml:368,670`, `AUTONOMY-MATRIX.md:98`, `NEYMA-OPERATOR.md:384`, `OPERATIONAL-USE-CASE-COVERAGE.yaml:20`, `QUOTE-TO-CASH-LIFECYCLE.md:108`, `BUILD-STATUS.yaml:48`, `PROGRAM-WEIGHTS.yaml:212`, `effect-entry-point-cutover-plan.md:18` |
| `marked-historical` | 7 | `EFFECT-PATH-INVENTORY.yaml:18`, `LEGACY-DISPOSITION.md:53`, `PHASE-OUTPUTS.md:109`, `phase-0-baseline-manifest.yaml:714,875`, `pr-sequence.md:33` |
| `hypothetical` | 2 | `PHASE-OUTPUTS.md:127`, `phase-0-baseline-manifest.yaml:367` |
| **`LIVE`** | **0** | — |

* **Zero false live OPEN claims.** ✅
* **Historical claims use valid *attached* classification** — every `marked-historical` exemption has
  its marker in the subject's own cell or its own prose unit; every `quoted` exemption is
  row/block-bounded parity. Verified per claim, not by total.
* **No historical report was rewritten** — all corpus documents are byte-identical to `3874d4a`
  (the six-path delta touches none of them).
* **No stale claim was moved into an unparsed format** — no header row in the population mentions
  R-07 (0 of 57), and `details_structure_defects()` is empty, so nothing was hidden in malformed
  markup.
* Agent instruction files: 6 in population, 5 claims total, **0 live OPEN**.
* The candidate's own new handoff is excluded from the population by authority classification
  (`implementation_review_documents`), and **would contribute 0 live OPEN even if parsed** — so the
  exclusion is not doing load-bearing work.

Raw phrase sweep over all tracked `.md`/`.yaml` for "R-07 remains open", "keeps R-07 open",
"R-07 not contained", "EP-1 write path remains present", "direct actuator route remains present",
"violation residuals remain" returns hits **only** in review/historical documents outside the live
population, or at the exempt lines enumerated above.

---

## 8. F-03 IMMUTABLE EVIDENCE BINDING — RE-RUN IN FULL, RETAINED

`eval/tests/test_evidence_binding.py` is **byte-identical** to `3874d4a`
(`d2a09a7d09c9d1a77d5bf4432203c8ef58b59a8e`). Six load-bearing reports; all bindings hold.

Baseline: **26 passed** in a clone carrying **zero** `refs/preserve/*` (tier 1 only).

### 8.1 Hostile battery — every attack fails as required

| Attack | Result |
|---|---|
| verdict **ACCEPT → REJECT** in the authenticated body | **FAILS** (15 / 2 / 1 / 3 failures depending on report) ✅ |
| report **body changed** (one byte appended) | **FAILS** ✅ |
| **candidate attribution changed** (`0891d1a`/`42ea24c`/`06ebfdb3` → `deadbee`) | **FAILS** ✅ |
| **sidecar changed** (digest zeroed) | **FAILS** ✅ |
| **sidecar missing** | **FAILS** ✅ |
| **report missing** | **FAILS** ✅ |
| **banner removed** from a banner-required report | **FAILS** ✅ |
| **banner-body substitution** (valid banner over a substituted body) | **FAILS** ✅ |
| **one preservation ref missing** (real `update-ref -d`) | **FAILS — 16 failed** ✅ |
| **preservation ref re-pointed** to the wrong commit | **FAILS — 15 failed** ✅ |
| **wrong preservation parent** / **wrong preserved blob** / **mutable worktree substitution** | **FAILS** (in-suite hostile nodes, each anchored on the real report set and asserted green before tampering) ✅ |
| **reconstructed report cited as contemporaneous testimony** | **FAILS** — the record must contain `RECONSTRUCTION`, `NOT contemporaneous` and `UNAVAILABLE`; the report itself opens with a reconstruction banner ✅ |

### 8.2 Two-tier model — verified on both sides

| Condition | Required | Observed |
|---|---|---|
| **no** `refs/preserve/*` present | tier 1 only, green | **26 passed** ✅ |
| **all** `refs/preserve/*` present | tier 1 + tier 2, green | **26 passed** ✅ |
| **one** ref missing (partial availability) | hard failure, **no silent downgrade** | **16 failed** ✅ |

Unconditional content binding in clean clones ✅ · all-or-nothing ref verification when preserve refs
are available ✅ · **no silent downgrade** ✅.

---

## 9. S-06 — THE CORRECTED PROBE EXPLANATION IS ACCURATE · **DISCHARGED**

I reproduced the exact mutation independently, inheriting neither account, in a clone carrying zero
`refs/preserve/*`, restoring byte-exactly between cases.

**Phrase changed:** `ACCEPT FOR SEPARATE FINAL ADJUDICATION` → `REJECT FOR SEPARATE FINAL ADJUDICATION`.

| Target | Occurrences (file / **authenticated body**) | Result |
|---|---|---|
| `p4-independent-rereview-report-0891d1a.md` — load-bearing, **bannered** | 3 / **2** | **15 failed** |
| `p4-final-adjudication-report-0891d1a.md` — load-bearing, unbannered | 2 / **2** | **1 failed** |
| `CLAUDE.md` — not authenticated evidence | 1 / n/a | **26 passed (green)** |

Every figure matches the builder's corrected §9 exactly.

**Why the earlier probe was green — established, not assumed.** I initially reproduced the *same
false green* myself: replacing the **first** occurrence in the two bannered reports mutates bytes
inside the **banner**, which `strip_banner()` deliberately excludes from the authenticated body
(2489 and 2490 bytes, 35 and 34 blockquote lines respectively). `body.count(b"ACCEPT")` is 2 in the
rereview report while `raw.count` is 3 — the extra occurrence is banner-only. Re-aimed at the first
occurrence **inside the body**, the same attack fails immediately. So:

1. The phrase **is** load-bearing and **is** bound — in **both** load-bearing reports. ✅
2. Changing it **does** fail the evidence guard, in both. ✅
3. The prior green result is explicable **only** as an invalid probe that did not mutate the
   authenticated bytes. ✅
4. It was **not** an evidence-binding gap and **not** "a phrase the record does not bind". ✅

**F-03 is not reopened and is not weakened.** The corrected attack does **not** remain green.
The handoff's §9 explanation is accurate as written.

---

## 10. TECHNICAL R-07 CONTAINMENT — RETAINED

| Property | Required | Observed |
|---|---|---|
| R-07 canonical status | CONTAINED | `phase-0-baseline-manifest.yaml` records CONTAINED with the bound |
| live violation edges | 0 | `import_probe.effect_adapter_import_violations()` → **0**, `[]` |
| recorded violation edges | 0 | manifest `violation_edges: []` — **len 0** |
| live == recorded | exact | **0 == 0**, both-sided ✅ |
| detection count | 13 | `adapter_import_sites()` → **13** ✅ |
| production `GateRegistry` | EMPTY | **0** `GateRegistry(` constructions, **0** `register_gate` calls in `src/` ✅ |
| Phase-8 Action Class gate registration | deferred | intact ✅ |
| `CdpActuator` **construction** | none | **0** `CdpActuator(` sites in `src/` ✅ |
| legacy live-operation router | none | `_build_live_operation_router` absent from `src/` ✅ |
| production default | `ROUTE_NOT_CONFIGURED` | `src/freight_recon/action_callback.py:662` ✅ |
| P4 | COMPLETE | `status=COMPLETE`, `execution_state=COMPLETE` ✅ |
| P5 | sole READY, NOT_STARTED | `status=READY`, `execution_state=NOT_STARTED`; the only READY unit ✅ |
| P6 – P14 | BLOCKED | all nine `BLOCKED` / `NOT_STARTED` ✅ |
| P5 implementation | none | none begun ✅ |

Remaining `cdp_actuator` / `CdpActuator` textual hits in `src/` are the module's own definition and
docstrings **stating** that the governed path imports no actuator — not construction sites.

**Containment remains containment, not enablement.** No production write is enabled; no bounded
autonomy is claimed. The record states the bound and the guards enforce that it is stated.

---

## 11. RUNTIME BYTE EQUALITY TO `0891d1a` — PROVEN

| Subtree | `0891d1a` | `a31a94a` | |
|---|---|---|---|
| `src/` | `0204261b17baecd2bab3dc1b7d25a7494eb3b22d` | identical | ✅ |
| `configs/` | `124ae4bcbbec96cc0ff9282d183d7c97aa1914f5` | identical | ✅ |
| `data/` | `8d02102277273f6858ce15d3753002e7875bb9df` | identical | ✅ |
| `scripts/` | one file differs: `scripts/mutate_roadmap_completeness.py` | | ✅ |

Tree-hash equality is a stronger proof than a file diff: it covers adapters, governed approval/write
machinery, checkpoint/witness/grant/claim machinery, browser-use boundaries, origin policy and the
production `GateRegistry` implementation and population in one comparison.

**Nothing enters freight runtime.** `grep` over `src/`, `configs/`, `data/` for `status_claims` and
`mutate_roadmap` returns **zero** hits, and no module under `src/` imports from `eval/` or `control`
at all. `status_claims` itself imports only `re`, `dataclasses`, `functools` and — lazily, inside one
function — `control.inventory`. `scripts/mutate_roadmap_completeness.py` is a test instrument
executed manually and imported by nothing.

**Receipts are byte-identical to the certified parent `06ebfdb3`:**

```
docs/implementation/SUITE-RESULT.json  a16cb1fc1574e72d351391568fc8808e7e7d0b49  IDENTICAL
docs/implementation/GATE-RESULT.json   8201ca745af0a093d2c69e90e203af1b7f7facde  IDENTICAL
```

No finalizer ran for this candidate and no receipt was forged.

---

## 12. FINDINGS

Severity key: **BLOCKING** = blocks third-finalizer authorization. All findings below are
**non-blocking**.

### FR-01 · NON-BLOCKING RESIDUAL RISK — the accidental-firing class is narrowed to the status cell, not eliminated

**Requirement.** Review scope: "Verify legitimate conditional claims remain supportable when the
conditional expression belongs to the actual claim cell"; adjudication §5.3(1): window → "the claim's
own cell / bounded claim unit."

**Location.** `eval/control/status_claims.py:860-864` with `_governing_window_start` at `:784-818`.

**Mechanical proof.**

```
| R-07 | Verified after the audit: OPEN - NOT CONTAINED |     -> EXEMPT: hypothetical
| R-07 | Recorded when the gate ran: OPEN - NOT CONTAINED |   -> EXEMPT: hypothetical
| R-07 | Status before remediation: OPEN - NOT CONTAINED |    -> EXEMPT: hypothetical
| R-07 | OPEN - NOT CONTAINED (checked after the run) |       -> LIVE   (ordering still holds)
```

**Consequence.** `after`, `when`, `before`, `while` are ordinary English words. The handoff's framing
— "S-01 fires **accidentally**, not only adversarially" — is correct, and the fix removes the
cross-cell half of that class entirely; but the same accidental firing survives when the ordinary
word happens to precede the polarity token **within the status cell itself**. Zero live corpus
claims are affected (§6.2), and the failure requires prose to be written into the canonical status
cell ahead of the status word.

**Classification.** **Non-blocking residual risk**, and partly an **evidence deficiency**: the
handoff discloses a new authoring constraint for *markers* (§12) but does not disclose that the
*conditional* accidental class remains open inside the status cell.

**Does it block third-finalizer authorization?** **No.** The candidate implements exactly the window
the adjudication authorized. Narrowing further (e.g. requiring a clause-initial modal) is a design
change the adjudication did not require and explicitly bounded against.

**Narrowly scoped remediation (for a future authorization, not this one).** Record the residual in
the carried-residual list, and — if ever authorized — consider requiring the conditional to govern
the token syntactically rather than merely precede it in-cell.

### FR-02 · NON-BLOCKING RESIDUAL — S-04, header rows are rendered text but are never claims

**Requirement.** Review scope: "For S-04, verify whether repository authority permits canonical live
status to exist in table headers."

**Location.** `eval/control/status_claims.py:731` — `claim_units()` admits only `role == "body"`.

**Mechanical proof.** `| R-07 | OPEN - NOT CONTAINED |` written as a header row (delimiter beneath)
parses to **0 claims** — absent, not exempt. Independently measured: **0 header or separator rows in
the 58-document union population mention R-07.**

**Repository authority.** Header and separator rows are *required* not to be parsed as claims by the
prior adjudication, and the parser is compliant; the corpus convention places status in body cells.
Authority therefore does not *permit* live status in a header so much as it *does not forbid* one —
a header renders as visible text, so it remains a structurally sanctioned place to write a status no
guard reads.

**Classification.** **Non-blocking residual risk.** Genuine (a real, uncovered authoring location),
but no live instance exists and changing claim-parsing semantics is explicitly out of scope.
**Does not block.** Correctly and accurately disclosed by the handoff.

### FR-03 · NON-BLOCKING RESIDUAL — S-05, no anti-drift guard, and existing coverage is *not* equivalent

**Requirement.** Review scope: "For S-05, verify whether existing behavioral tests and mutation
operators already provide equivalent anti-drift protection."

**Determination — measured, not assumed.** They do **not**, and I record this against the
convenient answer. All six copies of the old raw `re.sub(r"<details>.*?</details>", …)` are
delegated to `status_claims.strip_historical_blocks`; the only textual occurrence remaining is a
docstring in `test_docs_control_system.py:68`. But:

* the roadmap/status mutation battery runs a **single guard node** in
  `test_roadmap_completeness_control.py`, so its details operators (M32–M46) would catch drift only
  in that module;
* the other five delegating modules (`test_docs_control_system`, `test_status_reality`,
  `test_bootstrap_hermeticity`, `test_false_green_defenses`, `test_switch_consistency`) have **no
  details-named behavioural test of their own** (0 each, versus 8 in the roadmap module);
* no guard anywhere asserts that no module under `eval/` performs its own `<details>` stripping.

So a seventh raw copy written into any of those five modules would be caught by nothing.

**Consequence.** RC-01 recurrence risk is real and, as the adjudication noted, S-03 was itself a live
instance of that class — which raises rather than lowers this risk.

**Classification.** **Non-blocking residual risk.** No live instance exists; the adjudication
classified the guard as recommended, not required; and adding it is outside this replacement's
authorized delta. **Does not block.** Accurately disclosed by the handoff.
**Recommended for the next authorization.**

### FR-04 · EVIDENCE DEFICIENCY (minor) — a stray `</summary>` is not reported by `details_structure_defects()`

**Location.** `eval/control/status_claims.py:461-477`.

**Proof.** `details_structure_defects()` reports unterminated `<details>`, stray `</details>` and an
unclosed `<summary>` *inside a closed block* (`"<summary" in body`). A `</summary>` with **no**
opener does not contain the substring `<summary`, so it is silently ignored:
`<details>\nHISTORICAL</summary>\nR-07 remains OPEN…\n</details>` reports **no defect**.

**Consequence.** No laundering: the block is exempt because `HISTORICAL` is genuinely its own first
non-blank body line, which is a valid attachment. The gap is only that a malformed tag goes
unreported, so the "fail loudly as well as closed" promise is incomplete for this one form.

**Classification.** **Evidence deficiency**, non-blocking. Pre-existing — `details_blocks()` and
`details_structure_defects()` are byte-unchanged from `3874d4a` and outside this candidate's delta.
**Does not block.**

### FR-05 · NON-BLOCKING RESIDUAL — the banner region is unauthenticated by design

**Proof.** Appending a line to an existing banner (`> VERDICT: REJECT — …`) leaves
`test_evidence_binding.py` **green (26 passed)**, because `strip_banner()` removes exactly one
leading blockquote block and the sidecar authenticates only the body.

**Assessment.** This is the documented, deliberate design: adding a banner necessarily changes the
file's bytes, so the banner must sit outside the authenticated body. The banner is still *required*
to carry the disarm text (`NOT CURRENT AUTHORITY`) and the sidecar note, banner removal fails, and
body substitution under a valid banner fails. These reports are also excluded from the live-authority
population, so banner text cannot manufacture a live status claim.

**Classification.** **Non-blocking residual risk**, pre-existing, outside this candidate's delta
(`test_evidence_binding.py` is byte-unchanged). Recorded for completeness only. **Does not block.**
Per the review's standing instruction, F-03 is **not** reopened: independent verification did not
fail.

### Carried residuals — confirmed accurately disclosed, not discharged here

**S-07** (symlinked-venv clones report dirty, +2 NOT-RUN skips — environment, not defect) ·
**RR-01** (closed `HISTORICAL`/`SUPERSEDED` vocabulary, deliberately not widened — verified
unchanged) · **RR-02**, **RR-03**, **RR-04** · **RC-01** · **F-06**, **AD-01**, **AD-02**, **RC-02**,
**RC-03**. The builder's own new residual — a genuinely historical *row* must now carry its marker
inside the subject's cell rather than a separate Notes column — is **confirmed real and correctly
stated against the builder's own interest**; two live rows already comply
(`PHASE-OUTPUTS.md:109`, `pr-sequence.md:33`), and the failure direction is a loud guard failure,
never a silent exemption.

### Findings summary

| ID | Class | Severity | Blocks finalizer authorization? |
|---|---|---|---|
| FR-01 | non-blocking residual risk / evidence deficiency | low | **No** |
| FR-02 | non-blocking residual risk (S-04) | low | **No** |
| FR-03 | non-blocking residual risk (S-05) | low–medium | **No** |
| FR-04 | evidence deficiency | very low | **No** |
| FR-05 | non-blocking residual risk | very low | **No** |

**Zero confirmed defects. Zero blocking findings.**

---

## 13. TESTS AND REPRODUCTION — ALL REPRODUCED INDEPENDENTLY

| Check | Claimed | Reproduced |
|---|---|---|
| Canonical suite | 2072 passed · 0 failed · 1 skipped · 2073 collected | **2072 / 0 / 1 / 2073**, exit 0 ✅ |
| The one skip | approved canonical skip | `test_phase0_guard_integrity.py:109` — "no red-by-design cases remain" ✅ |
| `TEST-NODE-MANIFEST.json` | 2073 nodes, exact identity | **2073**, live collection **set-identical** to the manifest ✅ |
| Manifest delta vs `3874d4a` | +29, −0 | **+29, −0** ✅ |
| Roadmap/status battery | 58/58, 0 defective, 0 SKIP-INVALID | **58/58, 0 defective, 0 SKIP-INVALID** ✅ |
| Anti-vacuity on `3874d4a` | 11 MISS | **11 MISS, exact operator set** ✅ |
| P4 boundary battery | 61/61 | **61/61**, byte-exact restoration ✅ |
| Claim-local corpus | 57 / 82 / 47 / 0 | **57 / 82 / 47 / 0** ✅ |
| Union corpus | 58 / 84 / 49 / 0 | **58 / 84 / 49 / 0** ✅ |
| Per-claim vs `3874d4a` | byte-identical | **0 of 84 claims differ** ✅ |
| Production `GateRegistry` | EMPTY | **EMPTY** ✅ |
| Detection count | 13 | **13** ✅ |
| Receipts vs `06ebfdb3` | byte-identical | **byte-identical** ✅ |
| Locks | unheld | **unheld** ✅ |
| Protected refs | unchanged | **unchanged** ✅ |
| Pushed | nothing | **nothing** ✅ |
| Clean-clone gate | PASS | **`CLEAN-CLONE GATE: PASS`**, exit 0 ✅ |

Clean-clone gate detail — run in a disposable clone, fresh temp clone of the committed state, fresh
venv, declared dependencies only, every step exit 0:

```
--- clone committed state (exit 0)          --- no active_workspace in clone: OK
--- python floor (host) (exit 0)            --- fresh venv (exit 0)
--- python floor (venv) (exit 0)            --- install declared deps only (exit 0)
--- complete canonical suite (clean clone) (exit 0)
    clean-clone: {'passed': 2072, 'failed': 0, 'skipped': 1, 'collected': 2073}
--- control guards (clean clone) (exit 0)
--- AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001 (exit 0)

CLEAN-CLONE GATE: PASS
```

The gate's own `GATE-RESULT.json` binds `commit a31a94aa8239113ec8ea3c02b5ef6fad922a1b24` and
`tree 637580b64ca666695d0811c4119e866de6100ce9` — this candidate's exact commit and tree —
independently reproducing **2072 / 0 / 1 / 2073** from a fresh clone and a fresh venv.

`scripts/finalize_status.py` was **not** run. The clean-clone gate was run **only** in a disposable
clone, because it writes `GATE-RESULT.json`.

---

## 14. PRESERVATION, ATTRIBUTION AND HYGIENE

### 14.1 All three rejected candidates remain durably preserved

Every ref verified to resolve to the expected object **and** to have the expected parent:

| Candidate | candidate-preservation ref | archive branch | complete-worktree ref |
|---|---|---|---|
| `11c9112` | `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` ✅ | `refs/heads/archive/p4/r07-rejected-11c9112` ✅ | `refs/preserve/p4-r07-rejected-worktree-11c9112` → `6224b36e`, parent `11c9112` ✅ (641 paths) |
| `4d12b0e` | `refs/preserve/p4-r07-closure-rejected-replacement-candidate-4d12b0e` ✅ | `refs/heads/archive/p4/r07-rejected-replacement-4d12b0e` ✅ | `refs/preserve/p4-r07-rejected-replacement-worktree-4d12b0e` → `6b88dd09`, parent `4d12b0e` ✅ (645 paths) |
| `3874d4a` | `refs/preserve/p4-r07-closure-rejected-successor-candidate-3874d4a` ✅ | `refs/heads/archive/p4/r07-rejected-successor-3874d4a` ✅ | **`refs/preserve/p4-r07-rejected-successor-worktree-3874d4a`** → `3b72853c`, parent `3874d4a` ✅ (647 paths) |

The `3874d4a` complete-worktree preservation ref was **located mechanically** by enumerating
`refs/preserve/*` and testing each for `parent == 3874d4a` — not taken from the handoff.

### 14.2 The `3874d4a` review and adjudication — bytes, sidecars, parents, attribution

Both were absent from the candidate worktree and were read **in full from their preservation
commits**.

| Artifact | Ref | Commit | Parent | Report SHA-256 | Sidecar |
|---|---|---|---|---|---|
| targeted **review** | `refs/preserve/p4-r07-closure-successor-targeted-review-3874d4a` | `ccc9344d…` ✅ | `3874d4a…` ✅ | `104f7ecf…3249d` | matches ✅ |
| targeted **adjudication** | `refs/preserve/p4-r07-closure-successor-targeted-adjudication-3874d4a` | `f48fabbc…` ✅ | `3874d4a…` ✅ | **`38a8271ae336bd64ae3de38d9f61042f7cf22a234070119596d43833b96b1170`** — **matches the expected digest exactly** ✅ | matches ✅ |

Each preservation commit adds **only** its report and sidecar (verified by `git diff --name-status`
against `3874d4a`). Both verdicts read **REJECT — TARGETED REMEDIATION REQUIRED**.

All six reports in the three earlier families were re-hashed from their preservation commits; **every
sidecar matches its report's recomputed digest byte-for-byte**:

| Report | Parent | SHA-256 == sidecar |
|---|---|---|
| `…targeted-review-report-11c9112.md` | `11c9112` | `1659338a…9222` ✅ |
| `…targeted-adjudication-report-11c9112.md` | `11c9112` | `a8cb2768…0335` ✅ |
| `…replacement-targeted-review-report-4d12b0e.md` | `4d12b0e` | `8c26a311…6d42` ✅ |
| `…replacement-targeted-adjudication-report-4d12b0e.md` | `4d12b0e` | `62d2d267…990f` ✅ |
| `…successor-targeted-review-report-3874d4a.md` | `3874d4a` | `104f7ecf…3249d` ✅ |
| `…successor-targeted-adjudication-report-3874d4a.md` | `3874d4a` | `38a8271a…1170` ✅ |

**Mentions of `a31a94a` across all six earlier reports: 0.** None of them names, is parented to, or
can be read as reviewing this candidate.

**Attribution is clean.** Every review and adjudication in this family is parented to the candidate
it actually examined — `11c9112`'s pair to `11c9112`, `4d12b0e`'s pair to `4d12b0e`, `3874d4a`'s pair
to `3874d4a`. **No earlier report is parented to, names, or can be read as reviewing `a31a94a`.**
No report was moved, rewritten or reparented.

### 14.3 Secret and object hygiene

No `.env`, credential, token, virtualenv, cache, `__pycache__`, `.pytest_cache`, Claude scratchpad,
temporary test tree or session data appears in the candidate tree or in any preservation object.
The only matches for the sweep pattern are `.env.example` (a template with no values) and
`docs/architecture/decisions/ADR-014-credential-and-machine-identity.md` (a design document). A
credential-pattern sweep (`sk-…`, `xox…`, `AKIA…`, PEM headers, `ghp_…`, assigned passwords) over
all six changed paths returns nothing. All three complete-worktree preservation trees are clean
(0 suspicious paths of 641 / 645 / 647).

### 14.4 The primary repository was not modified

Measured after all review work completed:

```
HEAD          a31a94aa8239113ec8ea3c02b5ef6fad922a1b24   (unchanged)
branch        p4/adapter-containment-completion          (unchanged)
tree          637580b64ca666695d0811c4119e866de6100ce9   (unchanged)
main          152574e4f4f2969468c9d31b1e705188896175b5
origin/main   152574e4f4f2969468c9d31b1e705188896175b5   (equal)
worktree      0 modified paths        index   0 staged paths
reflog @{0}   a31a94a                 (branch never moved during this review)
preserve refs 36                      archive refs 6
locks         0 holders               remote P4 branches 0
```

---

## 15. WHAT THIS REVIEW DID NOT DO

Did not remediate any finding · did not modify the candidate · did not amend, commit to the product
branch, reset, restore, rebase, merge, checkout, stash, clean, move a branch ref or push · did not
run `scripts/finalize_status.py` · did not perform targeted adjudication · did not begin P5 · did not
deploy or enable any effect · did not modify, move or reinterpret any preservation ref · did not
alter the review or adjudication of `11c9112`, `4d12b0e` or `3874d4a` · did not resume any previous
session · did not review runtime behaviour from the primary worktree.

---

## 16. VERDICT AND WHAT REMAINS

# ACCEPT FOR SEPARATE TARGETED ADJUDICATION

S-01, S-02 and S-03 are completely remediated by the exact delta the controlling adjudication
authorized. The corrected pre-existing assertion is a genuine correction, not test weakening. The
unterminated-summary boundary is mechanically required, narrow, fail-closed, and creates no new
blind spot. The new mutation operators are evidence, not fixtures — 11 of them miss on the rejected
parser. R-07 technical containment, F-01, F-03 and runtime byte-equality to `0891d1a` are all
retained. S-04 and S-05 are correctly carried as non-blocking residuals; the S-06 explanation is
accurate and F-03 is not reopened.

**This review authorizes no finalization.** It is one of the two outstanding prerequisites. The
remaining one is:

* a **separate targeted adjudication** of `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24`, by a further
  distinct session that did not implement P4, did not author any candidate in this family, and
  conducted no prior review or adjudication.

**No third finalizer may run before that adjudication succeeds.** No finalizer has run for this
candidate; none may be fabricated. P5 has not begun.
