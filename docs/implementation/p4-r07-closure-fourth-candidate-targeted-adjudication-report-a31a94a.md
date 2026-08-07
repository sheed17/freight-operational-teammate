# P4 R-07 CLOSURE — SEPARATE TARGETED ADJUDICATION OF FOURTH CANDIDATE `a31a94a`

**Exact candidate adjudicated:** `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24`
**Exact tree:** `637580b64ca666695d0811c4119e866de6100ce9`
**Exact parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (certified metadata commit)
**Branch:** `p4/adapter-containment-completion`

**Adjudicator standing.** This session did not implement P4. It did not author `11c9112`,
`4d12b0e`, `3874d4a` or `a31a94a`. It did not conduct the fresh independent review of `a31a94a`
or any earlier review or adjudication in this family. It ran neither finalizer and reconstructed
no finalization evidence. No prior session was resumed. All behavioural adjudication was performed
from disposable `--no-local` clones at exactly `a31a94a`, never from the primary worktree.

This adjudication is attributable **only** to `a31a94a`. It does not review, amend or reinterpret
`11c9112`, `4d12b0e` or `3874d4a`.

---

## VERDICT

# ACCEPT FOURTH CANDIDATE FOR THIRD FINALIZATION

All three blocking findings of the controlling adjudication of `3874d4a` (S-01, S-02, S-03) are
**fully discharged**, independently ratified against my own hostile cases rather than by repeating
the reviewer's. The candidate implements exactly the §5.3 delta that adjudication authorized and
nothing wider. Two new non-blocking residuals are recorded (A-01, A-02), neither of which has a
live instance and neither of which is correctable inside the authorized delta.

---

## 1. IDENTITY, TOPOLOGY AND ENVIRONMENT — MECHANICALLY VERIFIED

| Check | Result |
|---|---|
| Candidate commit | `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24` ✅ |
| Candidate tree | `637580b64ca666695d0811c4119e866de6100ce9` ✅ |
| Parent | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` ✅ |
| Parent count | `git rev-list --parents -n1` returns exactly one parent — **not a merge** ✅ |
| Position | exactly **one content commit** above the certified metadata commit ✅ |
| Descendant of `3874d4a`? | `merge-base --is-ancestor` → **NO** ✅ |
| Descendant of `4d12b0e`? | **NO** ✅ |
| Descendant of `11c9112`? | **NO** ✅ |
| Legal PRODUCING topology | `06ebfdb3` (pure metadata) → `a31a94a` (content). Recorded content commit `42ea24c` == `HEAD^^`; no second consecutive content commit ✅ |
| Branch moved since review? | No — branch head == `a31a94a` == the commit the review preservation commit is parented on ✅ |
| Primary worktree / index | `git status --porcelain` **empty** ✅ |
| Builder / finalizer ownership | none — no `MERGE`/`REBASE`/`index.lock`; no `pytest`, `mutate_*`, `finalize_status` or runner process ✅ |
| Finalizer lock | `.git/neyma-finalizer.lock` is 0 bytes, no owner record, `lsof` empty, non-blocking `flock` acquired and released immediately → **UNHELD** ✅ |
| `main` / `origin/main` | both `152574e4f4f2969468c9d31b1e705188896175b5`, unchanged ✅ |
| Remote P4 branch | `git ls-remote --heads origin` lists no `p4/*` ref ✅ |
| Nothing pushed | `p4/adapter-containment-completion` has **no upstream**; remote heads unchanged ✅ |

A second worktree exists at `/private/tmp/claude-501/wt-dt` on the unrelated branch
`docs/deployment-topology-adr-020` (marked prunable). It is not the primary worktree, is not on the
P4 branch, and holds no lock. Recorded, not a finding.

### 1.1 The narrow delta

Against the rejected successor `3874d4a`, the candidate changes **exactly six paths**:

```
M docs/implementation/TEST-NODE-MANIFEST.json
A docs/implementation/p4-r07-closure-fourth-targeted-review-handoff.md
A docs/implementation/p4-r07-closure-fourth-targeted-review-handoff.md.sha256
M eval/control/status_claims.py
M eval/tests/test_roadmap_completeness_control.py
M scripts/mutate_roadmap_completeness.py
```

Every one is inside a surface §5.3 of the controlling adjudication explicitly authorized. No
prohibited surface is touched.

---

## 2. THE REPOSITORY-AUTHORIZED PRESERVATION ARTIFACT FOR THE FRESH REVIEW

Located **mechanically**, not by name: every `refs/preserve/*` ref was enumerated and its parent
resolved; **exactly one** has parent `a31a94a`.

| Field | Value |
|---|---|
| Preservation ref | `refs/preserve/p4-r07-closure-fourth-candidate-targeted-review-a31a94a` |
| Preservation commit | `c26aeae9fd73651736707f68e3faa66621efcfc0` |
| Preservation parent | `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24` ✅ (exact) |
| Report path | `docs/implementation/p4-r07-closure-fourth-candidate-targeted-review-report-a31a94a.md` |
| Report blob | `66711a283ebd572c80264693b1482505e0b84c9f` (49 941 bytes, 876 lines) |
| Report SHA-256 | `436dc56017e1dea095fead9c5938f7526f72dc8ee4038f3316932db5a35d6e92` |
| Sidecar | `…-report-a31a94a.md.sha256`, blob `9cac4f4f351cc798a0897bd906954382969b076d` |
| Sidecar content | `436dc56017e1…d6e92  p4-r07-closure-fourth-candidate-targeted-review-report-a31a94a.md` |
| Recomputed digest | `git cat-file -p c26aeae9:<path> | shasum -a 256` → **identical to the sidecar** ✅ |
| Commit adds | exactly the report and its sidecar, nothing else ✅ |
| Report verdict | **ACCEPT FOR SEPARATE TARGETED ADJUDICATION** ✅ |
| Attribution | 15 mentions of `a31a94a`; discusses predecessors only as history ✅ |

The complete report was read **directly from the preservation commit** via `git cat-file`. The
product branch, tree and primary index were never used to materialise it, and `git status`
remained empty throughout.

---

## 3. REJECTED PREDECESSORS — ALL THREE DURABLY PRESERVED

| Candidate | Archive ref | Candidate-preservation ref | Worktree preservation | Review report | Adjudication report |
|---|---|---|---|---|---|
| `11c9112` | `archive/p4/r07-rejected-11c9112` | `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` | `…-rejected-worktree-11c9112` = `6224b36e` | `fa4c459b`, parent `11c9112` | `030c5954`, parent `11c9112` |
| `4d12b0e` | `archive/p4/r07-rejected-replacement-4d12b0e` | `…-rejected-replacement-candidate-4d12b0e` | `…-rejected-replacement-worktree-4d12b0e` = `6b88dd09` | `62df39dd`, parent `4d12b0e` | `ce5dbb30`, parent `4d12b0e` |
| `3874d4a` | `archive/p4/r07-rejected-successor-3874d4a` | `…-rejected-successor-candidate-3874d4a` | `…-rejected-successor-worktree-3874d4a` = `3b72853c` | `ccc9344d`, parent `3874d4a` | `f48fabbc`, parent `3874d4a` |

Each report-preservation commit adds **exactly** its report and sidecar. Each worktree-preservation
commit carries the complete primary worktree including untracked artefacts.

**Exclusive attribution verified mechanically:** each of the six earlier reports was grepped for
`a31a94a` — **all six return 0**. No previous report can be interpreted as reviewing or
adjudicating the fourth candidate.

---

## 4. S-01 — CONDITIONAL EXEMPTION · **FULLY DISCHARGED**

### 4.1 The implementation, read structurally

`_governing_window_start` (`eval/control/status_claims.py:784-818`) returns, for a table row, the
start offset of the cell containing the position it is asked about; `0` for prose units (no cells);
and — fail-closed — the position itself when the offset resolves to no cell (it fell in the `" | "`
join). `parse_status_claims` (`:855-864`) then applies it **separately** on two different axes:

```python
_HISTORICAL_MARKER.search(unit.norm[_governing_window_start(unit, risk_in_norm.start()):risk_in_norm.start()])
_CONDITIONAL.search(unit.norm[_governing_window_start(unit, token_start):token_end])
```

The five properties the adjudication required to be modelled separately **are** separate:

| Axis | Where it lives |
|---|---|
| row-level subject/status association | `_row_unit` joins all cells — **unchanged** (R-01) |
| status-cell ownership | `StatusClaim.status_cell` = `_cell_at(unit, token_start)` |
| conditional-marker ownership | `_governing_window_start(unit, **token_start**)` |
| claim polarity | `_polarity(unit.norm)` → `(polarity, token_start, token_end)` |
| live/historical/hypothetical classification | the `exemption` ladder, ordered `historical-details` → `quoted` → `marked-historical` → `hypothetical` |

Association is keyed to the row; exemption is keyed to the claim. That is exactly the separation
§2.4(4) demanded.

### 4.2 Independently reproduced — my own cases, run against the candidate's own parser

Every case required by the adjudication scope, plus five placement variants I added:

| Case | Candidate | Rejected `3874d4a` |
|---|---|---|
| `\| Conditional \| if X happens \| R-07 \| OPEN — NOT CONTAINED \|` | **LIVE OPEN** ✅ | exempt: hypothetical |
| `\| Evidence \| recorded when the gate ran \| R-07 \| OPEN — NOT CONTAINED \|` | **LIVE OPEN** ✅ | exempt: hypothetical |
| `\| Before remediation \| evidence \| R-07 \| OPEN — NOT CONTAINED \|` | **LIVE OPEN** ✅ | exempt: hypothetical |
| `\| R-07 \| OPEN — NOT CONTAINED \| verified after the run \|` | **LIVE OPEN** ✅ | LIVE (R-03) |
| `\| R-07 \| OPEN — NOT CONTAINED \| while collecting evidence \|` | **LIVE OPEN** ✅ | LIVE (R-03) |
| conditional *between* subject and status | **LIVE OPEN** ✅ | exempt: hypothetical |
| conditional in a **header** row | **LIVE OPEN** ✅ | LIVE |
| conditional in a **neighbouring row** | **LIVE OPEN** ✅ | LIVE |
| conditional in **adjacent prose** above the table | **LIVE OPEN** ✅ | LIVE |
| conditional in a **neighbouring table** | **LIVE OPEN** ✅ | LIVE |
| **legitimate attached conditional**, in the status token's own cell | **exempt: hypothetical** ✅ | exempt |
| **legitimate** conditional + polarity in one cell | **exempt: hypothetical** ✅ | exempt |

Cross-cell subject/status association survives: the live cases report `subj=2, stat=3` — different
cells, still associated as one claim. Leading cells, evidence cells, notes cells, headers,
neighbouring rows, neighbouring tables and adjacent prose **cannot launder the claim**.

**S-01 is FULLY DISCHARGED.**

**Residual FR-01 — ratified, non-blocking.** I reproduced the reviewer's residual independently:
an ordinary word preceding the polarity token **inside the status cell itself** still exempts
(`| R-07 | note | recorded when the gate ran OPEN — NOT CONTAINED |` → hypothetical). This is
**exactly the window §2.4(6) authorized** ("`[start of the status token's cell, token_end]`"), zero
live corpus claims are affected, and narrowing further is a design change the adjudication
explicitly bounded against. The accidental-firing case the adjudication itself named
(`| R-07 | recorded when the gate ran | OPEN |`) **is** closed, because there the conditional and
the status sit in different cells. Non-blocking.

---

## 5. S-02 — HISTORICAL-MARKER OWNERSHIP · **FULLY DISCHARGED**

The window is `[start of the SUBJECT's own cell, start of the risk id)`.

| Case | Candidate | Rejected `3874d4a` |
|---|---|---|
| `\| Historical example \| unrelated text \| R-07 \| OPEN — NOT CONTAINED \|` | **LIVE OPEN** ✅ | exempt: marked-historical |
| `\| Evidence from superseded test \| R-07 \| OPEN — NOT CONTAINED \|` | **LIVE OPEN** ✅ | exempt: marked-historical |
| `\| R-07 \| OPEN — NOT CONTAINED \| historical note about another field \|` | **LIVE OPEN** ✅ | LIVE (R-03) |
| `\| Historical \| R-07 \| OPEN — NOT CONTAINED \|` | **LIVE OPEN** ✅ | exempt: marked-historical |
| marker in a **header** | **LIVE OPEN** ✅ | LIVE |
| marker in a **neighbouring row** | **LIVE OPEN** ✅ | LIVE |
| marker in a **neighbouring table** | **LIVE OPEN** ✅ | LIVE |
| marker in **adjacent prose**, blank line | **LIVE OPEN** ✅ | LIVE |
| marker in **adjacent prose**, no blank line | **LIVE OPEN** ✅ | LIVE |
| **legitimate** in-cell marker before the subject (the `PHASE-OUTPUTS.md` / `pr-sequence.md` form) | **exempt** ✅ | exempt |
| **legitimate** explicitly historical prose sentence | **exempt** ✅ | exempt |
| **legitimate** in-cell `SUPERSEDED` | **exempt** ✅ | exempt |

**Vocabulary was not broadened.** `_HISTORICAL_MARKER.pattern` is byte-identical between the two
parsers: `\bHISTORICAL\b|\bSUPERSEDED\b`. `_CONDITIONAL.pattern` is likewise byte-identical. No
row-level marker construct was invented.

**Markers do not leak; exempt claims remain visible; neighbouring live content remains live.**
Seven `marked-historical` claims are still parsed, counted and auditable in the live corpus.

### 5.1 The old defective assertion was genuinely corrected

The removed assertion was:

```python
assert not status_claims.live_open_claims("| ⛔ HISTORICAL | R-07 | OPEN — NOT CONTAINED |"), (
    "a marker in an EARLIER cell of the same row must govern the row")
```

That is the S-02 defect written down as a required expectation, and it is **mechanically
incompatible** with §3.3(5), which holds that this exact shape must remain a live contradiction. It
is replaced by an assertion that the marker in the **subject's own cell** must still exempt — the
form the live corpus actually uses. The test went from four assertions to five. This is a
**strengthening**, not test weakening.

**S-02 is FULLY DISCHARGED.**

---

## 6. S-03 — STRUCTURAL `<details>` BOUNDARIES · **FULLY DISCHARGED**

`_prose_blocks` now terminates a prose run at every structural `<details>`, `</details>`,
`<summary>` and `</summary>` **tag** (not line), via `_structural_tag_spans`, which also excludes
tags inside code so that backticked mentions stay literal.

### 6.1 All fourteen required arrangements, reproduced independently

| # | Arrangement | Candidate | Rejected |
|---|---|---|---|
| 1 | adjacent external historical prose before `<details>` | **LIVE** ✅ | exempt |
| 2 | blank-line-separated historical prose before `<details>` | **LIVE** ✅ | LIVE |
| 3 | valid marker attached to the block | exempt: historical-details ✅ | exempt |
| 4 | historical marker inside `<summary>` | exempt: historical-details ✅ | exempt |
| 5 | live R-07 status inside `<summary>` | **LIVE, visible** ✅ | LIVE |
| 6 | live cross-cell table row inside `<details>` | **LIVE** ✅ | LIVE |
| 7 | unlabelled details nested in labelled historical details | **LIVE** ✅ | exempt |
| 8 | labelled historical details nested in live details | exempt: historical-details ✅ | exempt |
| 9 | unterminated details, no blank lines | **LIVE** ✅ | exempt |
| 10 | unterminated `<summary>` | **LIVE** ✅ | exempt |
| 11 | malformed summary syntax | **LIVE** ✅ | exempt |
| 12 | missing closing `</details>` | **LIVE** ✅ | exempt |
| 13 | multiple adjacent details blocks | **LIVE** ✅ | exempt |
| 14 | structural tags containing additional text | **LIVE** ✅ | exempt |
| + | conditional prose adjacent above `<details>` (the S-03 twin) | **LIVE** ✅ | exempt: hypothetical |
| + | live claim inside an **unterminated** `<summary>` | **LIVE, visible** ✅ | LIVE |

Blank-line and no-blank-line arrangements behave **identically** — the divergence that was the
defect signature is gone. `details_structure_defects()` still reports unterminated `<details>`,
stray `</details>` and unclosed `<summary>` loudly.

### 6.2 The extra end-of-line boundary — adjudicated mechanically

I rebuilt the candidate's parser **with the boundary block deleted** and compared:

| Question | Determination |
|---|---|
| Required? | **YES.** With the boundary removed, arrangement 10 (unterminated `<summary>` carrying `HISTORICAL`) reverts to **exempt: marked-historical** — the void label's text runs into the block body and grants an exemption the module had just declared void. With it, **LIVE**. Mechanically required. |
| Bounded? | **YES.** It fires only when the next structural tag after a `<summary>` opener is not a `</summary>`. A well-formed summary installs no synthetic boundary (verified: identical output with and without). |
| Fails closed? | **YES.** More boundaries ⇒ smaller units ⇒ exemption reach can only shrink, never grow. |
| Valid summary content still visible? | **YES.** Arrangements 4, 5 and the unterminated-summary live claim all parse and stay visible. |
| Changes unrelated prose behaviour? | **NO.** Six prose regressions (marker-before, R-03 ordering across sentences, quoted, multi-line runs, blank-separated runs) are **6/6 identical** between the two parsers. |
| Can malformed markup still hide or exempt a live claim? | **No exemption** — every malformed form resolves LIVE. One **deletion** path exists and is recorded as A-01 below. |

**S-03 is FULLY DISCHARGED**, with residual A-01 recorded.

---

## 7. NEW FINDING A-01 · NON-BLOCKING RESIDUAL + EVIDENCE DEFICIENCY

**A structural tag written INLINE between the risk id and the polarity token splits the claim
unit, and the claim parses to ZERO claims — it disappears rather than remaining live.**

Reproduced against the real guard node
(`test_r07_is_never_represented_as_contained_anywhere_live`) by injecting into `CURRENT.md`, with
byte-exact restore:

| Injection | Candidate | Rejected `3874d4a` |
|---|---|---|
| **control:** plain `R-07 remains OPEN and is NOT CONTAINED.` | CAUGHT | CAUGHT |
| `<summary>R-07</summary> remains OPEN and is NOT CONTAINED.` | **HIDDEN** | CAUGHT |
| `R-07</summary> remains OPEN and is NOT CONTAINED.` | **HIDDEN** | CAUGHT |
| `R-07 <details>remains OPEN and is NOT CONTAINED.</details>` | **HIDDEN** | CAUGHT |
| `R-07 </details>remains OPEN and is NOT CONTAINED.` | **HIDDEN** | CAUGHT |
| table row with an inline tag inside the status cell | CAUGHT | CAUGHT |

This is outside the reviewer's fuzz space: the 300-arrangement campaign surrounded an intact claim
with tags, and all fourteen required arrangements keep the claim text contiguous. My own
1 080-arrangement structured fuzz likewise found **0** vanishing claims, because it too placed tags
on their own lines. The escape requires the tag to sit **between** the subject and the status.

**Why this does not block:**

1. **The class is pre-existing and is not created by this delta.** Blank-line and table-line
   boundaries already delete a claim split the same way, on **both** parsers: `R-07\n\nremains OPEN
   and is NOT CONTAINED.` is **HIDDEN on `3874d4a`** as well. "A unit boundary between subject and
   status deletes the claim" is an inherent property of unit-based segmentation that predates this
   candidate and was never adjudicated as blocking. The delta adds four new *spellings* to a
   pre-existing alphabet; it does not create the class.
2. **Zero live instances.** Across the union population, **0** lines carry both `R-07` and a
   structural tag — let alone one positioned between the subject and the status.
3. **Adversarial-only.** Unlike S-01, which fired on ordinary English words with no adversary
   present, this requires deliberately writing HTML tags mid-claim — conspicuous in source review.
4. **Table rows are unaffected**, and table rows are the corpus's canonical status construction.
5. **Correcting it exceeds the authorized delta.** A fix requires changing claim segmentation or
   association semantics; §5.3 explicitly withholds authorization for "any parser redesign beyond
   the three bounded windows."
6. **The alternative was worse.** The adjudication's literal wording ("break at structural details
   tag *lines*") would delete every claim written inside a `<summary>` — a strictly larger and more
   likely deletion class. The builder's tag-not-line choice is the safer reading and is defended in
   the module docstring.

**Why it must nonetheless be recorded.** The module docstring asserts, in the very paragraph that
justifies this delta, that "a live claim may never disappear because of how this parser segments."
For these four forms that promise does not hold. The candidate falls short of a property it claims
about itself, in the layer it just changed. That is an **evidence deficiency**, not a false status:
no live claim is affected and no status is misstated.

**Classification: non-blocking residual risk + evidence deficiency. Recommended for the next
authorization, together with S-05.**

## 7.1 NEW FINDING A-02 · EVIDENCE DEFICIENCY (minor), extends FR-04

`details_structure_defects()` reports **no defect** for a stray `</summary>` with no opener, for an
inline `<summary>…</summary>` pair, or for an inline `<details>`. Only the stray `</details>` form
is reported. The "fail loudly as well as closed" promise is therefore incomplete for three of the
four A-01 forms. Pre-existing — `details_structure_defects()` is byte-unchanged from `3874d4a` —
and outside this delta. **Does not block.**

---

## 8. MUTATION AND ANTI-VACUITY EVIDENCE — INDEPENDENTLY REPRODUCED

### 8.1 Battery integrity, checked before its result was believed

The battery enforces, in its own code, every property the adjudication scope demands: a case whose
anchor is absent is a **battery defect** (`SKIP-INVALID`), never a skip; a mutation that changes no
bytes is a defect; restoration is asserted **byte-for-byte**; a node that fails **without an
`AssertionError`** is scored `WRONG REASON`, because an unrelated exception is not a catch; and
`must-stay-GREEN` negatives are scored as defects if they fire.

### 8.2 Results, reproduced in a disposable clone at `a31a94a`

```
roadmap/status battery : 58/58 correct (52 must-be-CAUGHT, 6 must-stay-GREEN), 0 defective
SKIP-INVALID           : 0     (genuine — grepped; the sole textual hit is descriptive prose)
MISS / WRONG REASON / FALSE POSITIVE : 0
P4 boundary battery    : 61/61 mutants caught
tree after the battery : 637580b64ca666695d0811c4119e866de6100ce9 — restored byte-exactly
```

### 8.3 Anti-vacuity — measured, not inherited

The candidate's battery was run **against the rejected parser** (`3874d4a`'s
`status_claims.py` swapped into an otherwise identical clone), at node level.

```
CAUGHT on rejected parser : 41
MISS   on rejected parser : 11
must-stay-GREEN negatives : 6/6 stayed green (M30 M31 M33 M44 M52 M58)
MISS IDS: M34 M42 M43 M45 M46 M47 M48 M49 M51 M53 M54
```

**Exactly 11, and exactly the claimed set.** Each was verified to target a real non-empty anchor,
to change the intended bytes, to fail by `AssertionError` on the candidate, and to restore the tree
byte-exactly.

| Attack | Operators |
|---|---|
| **S-01** | M47 (leading cell), M48 (evidence cell — the *accidental* case), M49 (between subject and status), M51 (description cell) |
| **S-02** | M53 (unrelated leading cell), M54 (R-03's authority sentence in row-shaped form) |
| **S-03** | M34 (adjacent marker — **retargeted**), M42 (unterminated, no blank lines), M43 (nested unlabelled, no blank lines), M45 (malformed summary), M46 (**conditional twin**) |

**M34 now attacks the adjacent-marker escape:** its fixture went from `…notes below.\n\n<details>`
to `…notes below.\n<details>` — the blank lines removed, which is precisely the arrangement it is
named for and could not previously fail on. **The blank-line form is separately retained as M41**,
verbatim, so both arrangements are measured and the boundary is proven structural rather than
whitespace-dependent. Malformed and nested no-blank-line cases are covered (M42, M43, M45);
ordinary conditional words are covered (M48 `when`, M49 `before`, M51 `while`); unrelated
historical-marker cells are covered (M53, M54).

Every §5.3 requirement 4, 5, 7, 8 and 9 is discharged.

### 8.4 The manifest delta is the coverage delta

`TEST-NODE-MANIFEST.json`: **2044 → 2073 nodes, +29 added / −0 removed.** All 29 are in
`test_roadmap_completeness_control.py` and all attack S-01, S-02 or S-03 — including both
`[blank line]` and `[no blank line]` parametrisations of the malformed, nested and unterminated
cases, the must-stay-exempt negatives, `test_row_association_still_spans_cells_after_the_exemption_windows_were_narrowed`,
`test_a_claim_written_inside_a_summary_is_still_read`,
`test_a_details_tag_inside_code_is_not_a_unit_boundary` and
`test_the_live_corpus_classifies_identically_under_the_narrowed_windows`.

---

## 9. CORPUS COUNTS — RECOMPUTED INDEPENDENTLY

Computed with my own instrument against the candidate's own tree:

| View | Documents | Claims | live CONTAINED | live OPEN | exempt |
|---|---|---|---|---|---|
| Claim-local (discovered `live_authority_documents`) | **57** | **82** | **47** | **0** | 35 (quoted 20 / hypothetical 8 / marked-historical 7) |
| Full / union canonical | **58** | **84** | **49** | **0** | 35 |

**Both views reproduce exactly.**

**The view difference is fully explained.** The union adds exactly one document, `README.md`, which
contributes **2 live CONTAINED and 0 exempt**: 57+1 = 58 documents, 82+2 = 84 claims, 47+2 = 49
live CONTAINED, exempt 35 and live OPEN 0 identical in both. `README.md` is the **public landing
document** and is deliberately outside the *discovered* population — reachable only through the
union with the landing documents. This is not an accounting gap: the battery's own case M31 is
pointed at the unified guard precisely because the roadmap node "genuinely cannot see" `README.md`,
and the capability difference is accounted for honestly rather than concealed.

Verified further:
* **Deterministic** — three repeat runs produce byte-identical per-claim signatures.
* **Positively anchored** — `_CROSS_CELL_ANCHORS` names `CURRENT.md`, `CLAUDE.md` and `README.md`
  and requires each to still contain a parsed, **live**, **CONTAINED** cross-cell R-07 row;
  `live_authority_documents` asserts `len(out) >= 15`; the row-exemption anchor asserts at least one
  exempt table-row claim survives. A missing document or a collapsed corpus **fails**.
* **No live OPEN claim is removed through exemption laundering** — the per-claim classification is
  identical under both parsers. I proved this the hard way: the R-07 guard node is **green at
  baseline against the rejected parser**, which is only possible if the narrowing changes no live
  classification. The delta removes only capability the corpus never uses.
* **Historical claims remain visible** — 7 `marked-historical` claims still parsed and counted.
* **Malformed structures cannot reduce the count silently** — for existing corpus claims, counts
  are stable and pinned by `test_the_live_corpus_classifies_identically_under_the_narrowed_windows`.
  The one path by which a *newly written* claim can be silently removed is A-01 (§7), which has zero
  live instances.

**Counts are trustworthy — as a measurement and, now, as evidence that the control works.** This is
the material change from `3874d4a`, where the same counts were sound as measurement but could not
support the forward-looking guarantee.

---

## 10. S-04 AND S-05 — ADJUDICATED MECHANICALLY

### S-04 — header rows are never parsed as claims · **NON-BLOCKING RESIDUAL**

**Does repository authority permit authoritative live R-07 status in a Markdown header?** **No —
and it also does not forbid writing one.** The parser docstring records the governing rule: "Header
rows and separator/alignment rows are structure, not claims, and are never parsed as claims," and
`claim_units()` admits only `role == "body"`. A prior adjudication **required** this. So a header is
not an authorized location for authoritative status; the parser is **compliant**, not defective.

Independently measured: **0 header or separator rows mention R-07** across the union population.

The residual is genuine but narrow: a header renders as visible text, so it remains a structurally
sanctioned place to write a status no guard reads. Changing claim-parsing semantics to read headers
would contradict a standing adjudicated requirement and is out of scope. **Non-blocking residual.**
Correctly disclosed by the handoff.

### S-05 — no anti-drift guard against the raw details regex · **NON-BLOCKING RESIDUAL**

**Do existing parser tests and mutation operators provide equivalent behavioural anti-drift
protection?** **No.** I ratify the reviewer's determination, which was recorded against the
convenient answer:

* the roadmap/status battery runs a **single guard node**, so its details operators (M32–M46) bound
  only `test_roadmap_completeness_control.py`;
* the other five delegating modules (`test_docs_control_system`, `test_status_reality`,
  `test_bootstrap_hermeticity`, `test_false_green_defenses`, `test_switch_consistency`) carry **no
  details-named behavioural test of their own**;
* no guard asserts that no module under `eval/` performs its own unconditional `<details>`
  stripping, so a seventh raw copy in any of those five would be caught by nothing.

Recurrence risk is real — S-03 was itself a live instance of RC-01. But **no live instance exists**,
the controlling adjudication classified this guard as **recommended, not required** and explicitly
"not sufficient to block finalization independently," and adding it now would exceed the authorized
delta. **Non-blocking residual. Recommended for the next authorization**, alongside A-01.

I decline to expand scope to add another guard, and I decline to treat a genuinely authorized
format as a defect.

---

## 11. S-06 AND F-03 — REPRODUCED IN FULL

### 11.1 The exact attack

**Phrase:** `ACCEPT FOR SEPARATE FINAL ADJUDICATION` → `REJECT FOR SEPARATE FINAL ADJUDICATION`.
Run in a tier-1 clone (zero `refs/preserve/*`, baseline **26 passed**), byte-exact restore between
cases:

| Target | Occurrences | Bytes changed | Result |
|---|---|---|---|
| `p4-independent-rereview-report-0891d1a.md` (bannered) — **all** | 3 | 12 | **15 failed** |
| same — **first occurrence only** (inside the banner) | 3 | 4 | 26 passed (green) |
| same — **last occurrence** (in the body) | 3 | 4 | **15 failed** |
| `p4-final-adjudication-report-0891d1a.md` (unbannered) — all | 2 | 8 | **1 failed** |
| `CLAUDE.md` — not authenticated evidence | 1 | 4 | 26 passed (green) |

**Determinations.** The phrase **is** load-bearing and **is** bound, in **both** load-bearing
reports. The intended bytes do change. Evidence-binding tests **do** fail. The earlier probe
remained green because it was aimed at a non-authenticated location — either `CLAUDE.md`, or the
**banner region**, which `strip_banner()` deliberately excludes from the authenticated body (the
first occurrence in a bannered report lies inside the banner). **The corrected handoff explanation
is accurate**, and the reviewer's sharper mechanism — that the first occurrence sits inside the
banner — is independently confirmed. F-03 is **not** reopened.

### 11.2 Complete F-03 retention

| Property | Result |
|---|---|
| Expected report SHA-256 values, sidecars, authenticated bodies | verified; sidecar tamper → **1 failed**; body tamper → **2 failed** |
| Preservation refs / commits / parents / attribution | verified for all six predecessor reports and the `a31a94a` review (§2, §3) |
| Verdict / finalizer target binding | ACCEPT→REJECT **blocked** in all five authenticated reports (rereview 15, final adjudication 1, closure review 2, closure adjudication 1, second finalization 1) |
| Banner-aware body authentication | body verdict-line substitution → **2 failed**; forged disarming banner without the sidecar note → **2 failed**; banner-only mutation green **by design** (FR-05) |
| Clean-clone unconditional content binding | tier-1 clone (0 preserve refs) → **26 passed**, content checks unconditional |
| All-or-nothing ref verification when refs present | tier-2 clone (37 refs) → **26 passed** |
| **One missing ref fails** | deleting `p4-closure-targeted-review-42ea24c` → **3 failed**; `p4-independent-rereview-0891d1a` → **16 failed**; `p4-final-adjudication-0891d1a` → **2 failed**. **No silent downgrade.** |
| Removing **all** refs | correctly reverts to tier 1 and is green — the condition is genuinely all-or-nothing, not "any ref present ⇒ fail" |
| Mutable-worktree substitution | body substitution **blocked**; only banner-region edits pass, by design |
| Reconstructed report attribution | honest — the second-finalization report is bannered, bound, and its ACCEPT→REJECT mutation fails |
| `test_evidence_binding.py` | blob `d2a09a7d09c9d1a77d5bf4432203c8ef58b59a8e` — **byte-identical to `3874d4a`** |

*Note on method:* deleting `refs/preserve/p4-r07-closure-fourth-candidate-targeted-review-a31a94a`
leaves the suite green. That is **correct**, not a downgrade: that ref postdates the candidate and
is not cited by any load-bearing report in the candidate's tree. A commit cannot bind evidence
created after it.

**F-03 remains FULLY CLOSED.**

---

## 12. F-01 RETENTION — FULLY CLOSED

Every canonical/control document and agent instruction was swept for the nine live-claim forms
(`R-07 remains open`, `R-07 is open`, `keeps R-07 open`, `leaves R-07 open`, `R-07 not contained`,
`does not contain R-07`, `EP-1 write path remains present`, `direct actuator route remains
present`, `violation residuals remain`):

* **53 hits fall outside the live-authority population** — historical review documents, frozen
  `U-*-ACCEPTANCE.yaml` contracts and `IMPLEMENTATION-REGISTRY.yaml` itself. All three exclusions
  are **derived** by `live_authority_documents()`, not hand-listed.
* **3 hits fall inside**, and every one is properly classified:
  * `phase-0-baseline-manifest.yaml:367` → **exempt: hypothetical**
  * `EFFECT-PATH-INVENTORY.yaml:141` → **exempt: quoted**
  * `LEGACY-DISPOSITION.md:436` → carries **two** claims: the SUPERSEDED old wording is
    **exempt: quoted** (OPEN), paired with a **live CONTAINED** statement reading "It is not a live
    statement: R-07 is recorded CONTAINED in phase-0-baseline-manifest.yaml." Correct and honest.

| Check | Result |
|---|---|
| Zero false live OPEN claims | **0** live OPEN across both the 57-document and 58-document views ✅ |
| Legitimate historical statements use attached classification | all 23 OPEN-polarity claims carry a valid attached exemption (quoted 20 / marked-historical 7 / hypothetical 8 across all claims) ✅ |
| Historical reports were not rewritten | the delta touches 6 paths, **none** a canonical status or historical report ✅ |
| No stale claim moved into an unparsed structure | 0 lines in the union population carry both `R-07` and a structural tag; 0 header rows mention R-07 ✅ |

**F-01 remains FULLY CLOSED.**

---

## 13. TECHNICAL R-07 CONTAINMENT — VALID AND RETAINED

| Property | Verification |
|---|---|
| R-07 CONTAINED | `phase-0-baseline-manifest.yaml` → `status: CONTAINED` ✅ |
| Zero live violation edges | `containment_evidence/violation_edges: 0 live / 0 recorded, agreeing both-sided` ✅ |
| Zero recorded violation edges | same record; `effect_adapter_import_gate/violation_edges: []` ✅ |
| Exact live/recorded equality | stated and agreeing both-sided ✅ |
| Detection count 13 | `containment_evidence/detection_edges: 13` ✅ |
| Production `GateRegistry` EMPTY | `test_phase0_null_gate.py` + `test_status_reality.py` → **13 passed**; the construction site in `governed_write_registry.py:392-410` is REMOVED and deliberately not relocated ✅ |
| Phase-8 Action Class gate deferral intact | recorded `DEFERRED_BY_DEPENDENCY — REQUIRED AT PHASE 8`, `green_at_phase P8`, `accountable_unit U8.1` ✅ |
| No `CdpActuator` construction | `grep "CdpActuator("` over `src/` → **none** ✅ |
| No `cdp_actuator` import | only a comment in `governed_write_route.py:499` stating nothing on the path imports it ✅ |
| No legacy live-operation router | `grep "_build_live_operation_router"` over `src/` → **none** ✅ |
| Production default `ROUTE_NOT_CONFIGURED` | `action_callback.py:662` refuses governed writes with `ROUTE_NOT_CONFIGURED` ✅ |
| Boundary / topology guards | `test_integration_topology` + `test_adapter_boundary_acceptance` + `test_no_mock_effect_in_production` + `test_consequential_read_boundary` → **60 passed** ✅ |
| P4 COMPLETE | "Adapter containment" unit `status: COMPLETE`, `execution_state: COMPLETE` ✅ |
| P5 sole READY and NOT_STARTED | exactly one READY unit — "Canonical events, outbox/inbox, replay isolation, and production persistence" — `execution_state: NOT_STARTED` ✅ |
| P6–P14 BLOCKED | all remaining units `BLOCKED` / `NOT_STARTED` ✅ |
| No P5 implementation | P5 unit `NOT_STARTED`; no P5 surface in the delta ✅ |

**Containment means external-effect paths are governed or fail closed. It does not mean production
writes, unsupervised actions or bounded autonomy are enabled — and nothing in this candidate
enables any of them.**

---

## 14. RUNTIME BYTE EQUALITY TO `0891d1a` — PROVEN BY TREE HASH

| Directory | `0891d1a` | `a31a94a` | |
|---|---|---|---|
| `src/` | `0204261b17baecd2bab3dc1b7d25a7494eb3b22d` | `0204261b17baecd2bab3dc1b7d25a7494eb3b22d` | **IDENTICAL** |
| `configs/` | `124ae4bcbbec96cc0ff9282d183d7c97aa1914f5` | `124ae4bcbbec96cc0ff9282d183d7c97aa1914f5` | **IDENTICAL** |
| `data/` | `8d02102277273f6858ce15d3753002e7875bb9df` | `8d02102277273f6858ce15d3753002e7875bb9df` | **IDENTICAL** |

Tree-hash identity is stronger than a file sweep: it covers runtime scripts, configs, runtime data,
adapters, governed approval/write machinery, checkpoint/witness/grant/claim machinery, browser-use
boundaries, origin policy and the production `GateRegistry` implementation and population, in one
comparison. The only difference under `scripts/` is `mutate_roadmap_completeness.py`.

**None of the six changed paths enters the freight runtime.** `status_claims` is referenced only by
`eval/` tests, `scripts/mutate_roadmap_completeness.py`, three handoff documents and the registry —
**never** by `src/`, `configs/`, `data/` or any runtime entry point, by import, configuration or
execution. The mutation script is evidence infrastructure that adjudicates nothing.

---

## 15. TEST AND ENVIRONMENT REPRODUCTION

All figures reproduced against the candidate's own tree in disposable `--no-local` clones:

| Item | Result |
|---|---|
| Canonical suite | **2072 passed / 0 failed / 1 skipped / 2073 collected**, recorded against commit `a31a94aa8`, tree `637580b64` ✅ |
| Disposable clean clone, same result | ✅ |
| Clean-clone gate | **PASS** — fresh clone, fresh venv, declared-deps-only install, same four figures ✅ |
| TEST-NODE-MANIFEST identity | **2073 nodes**, exact node identity (the runner aborts on any divergence and did not) ✅ |
| Mutation battery | **58/58**, 0 defective, 0 SKIP-INVALID ✅ |
| Boundary battery | **61/61** ✅ |
| Corpus counts | 57/82/47/0 and 58/84/49/0 ✅ |
| Production `GateRegistry` empty | ✅ |
| Detection count 13 | ✅ |
| Receipts byte-identical to `06ebfdb3` | `SUITE-RESULT.json` `a16cb1fc…`, `GATE-RESULT.json` `8201ca74…` — **identical blobs**; no finalizer ran and no receipt is forged ✅ |
| Locks unheld | ✅ |
| Protected refs unchanged | ✅ |
| Nothing pushed | ✅ |

**Environment-only behaviour, classified separately from candidate defects.** A venv built from
`requirements.txt` alone omits `pymupdf` and `websocket-client`, which causes conftest/collection
import errors and a manifest-identity refusal. This is **not** a candidate defect: the runner
correctly **refused** rather than reporting a false green, and the clean-clone gate — which installs
the **declared** dependency set from `pyproject.toml` — passes with the exact canonical figures.
Carried residual S-07 (symlinked `.venv` producing extra NOT-RUN skips) was not encountered; my
clones used copied venvs, the canonical configuration.

---

## 16. SECRET AND OBJECT HYGIENE

No `.env` contents, credentials, tokens, virtualenv files, caches, temporary clones, Claude
scratchpads or session data entered the candidate or any preservation object created by this
campaign.

* The candidate tree's only `.env`-matching path is **`.env.example`** — a template with no secrets.
* `.gitignore` covers `.env`, `.venv/`, `__pycache__/`, `*.db`, `.pytest_cache/`, `.DS_Store`,
  `.playwright-mcp/`, `eval/results/` and `data/active_workspace/`.
* The `.claude/agents/*.md` files in the tree are repository-authorized agent lens documents and
  part of the reviewed corpus — not session data.
* The review preservation commit `c26aeae9` adds **exactly two** objects: the report and its
  sidecar.
* This adjudication's preservation commit adds exactly two objects, listed in §19.

---

## 17. FINALIZER ELIGIBILITY — ANSWERED SEPARATELY

| # | Question | Answer |
|---|---|---|
| 1 | Is technical R-07 containment valid? | **YES** — §13, §14 |
| 2 | Is F-01 still closed? | **YES, fully** — §12 |
| 3 | Is F-03 immutable evidence binding still closed? | **YES, fully** — §11 |
| 4 | Is S-01 fully discharged? | **YES — FULLY DISCHARGED** — §4 |
| 5 | Is S-02 fully discharged? | **YES — FULLY DISCHARGED** — §5 |
| 6 | Is S-03 fully discharged? | **YES — FULLY DISCHARGED**, with residual A-01 recorded — §6, §7 |
| 7 | Are status corpus counts trustworthy? | **YES** — as measurement *and* as evidence the control works — §9 |
| 8 | Are S-04 and S-05 blocking or residual? | **Both NON-BLOCKING RESIDUALS** — §10 |
| 9 | Is candidate `a31a94a` eligible for exactly one third finalizer? | **YES** |

### Why the evidence now supports final certification

`3874d4a` was rejected because the commit that *records* R-07 CONTAINED carried a status-reality
control that could be defeated by an ordinary word in an adjacent cell, a historical marker in an
unrelated column, and a sentence placed above a `<details>` block — the last of which additionally
voided the module's own malformed-block and no-inheritance guarantees. Certifying it would have
certified a control that did not hold, in the very commit whose subject is the truthfulness of that
status.

All three are now closed, and closed **provably rather than assertedly**:

* Exemption is **claim-local** while association stays **row-wide** — the two axes the rejected
  parser conflated are now separately modelled and separately tested.
* The structural boundary is the **tag**, so classification no longer depends on whether an author
  left a blank line — the divergence that was the defect signature.
* The two advertised fail-closed guarantees the rejected parser had voided (unterminated block;
  unlabelled block nested in a labelled one) are **restored in both arrangements**.
* The evidence is **non-vacuous**: exactly 11 new operators MISS on the rejected parser and are
  CAUGHT here, M34 is retargeted from a fixture that could not fail to the escape it is named for,
  the blank-line twin is retained as M41, and six must-stay-GREEN negatives prevent a remediation
  that simply deleted the exemption rules from scoring full marks.
* The narrowing is **regression-bounded**: the live corpus classifies **identically** under both
  parsers — proven independently by the rejected parser passing the R-07 guard node at baseline —
  so the delta removes only capability the corpus never uses.
* Everything previously accepted is retained byte-for-byte: runtime trees identical to `0891d1a`,
  `test_evidence_binding.py` identical to `3874d4a`, receipts identical to `06ebfdb3`.

The residuals that remain (FR-01, S-04, S-05, FR-04, FR-05, A-01, A-02) share three properties:
**none asserts a false status, none conceals a live claim in the actual corpus, and none is
correctable inside the delta this candidate was authorized to make.** None compounds with another
to produce a false green.

### Authorization binding

| Field | Value |
|---|---|
| Exact candidate | `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24` |
| Exact tree | `637580b64ca666695d0811c4119e866de6100ce9` |
| Exact parent | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` |
| Accepted review report | `docs/implementation/p4-r07-closure-fourth-candidate-targeted-review-report-a31a94a.md` |
| Review report SHA-256 | `436dc56017e1dea095fead9c5938f7526f72dc8ee4038f3316932db5a35d6e92` |
| Review preservation | `refs/preserve/p4-r07-closure-fourth-candidate-targeted-review-a31a94a` → `c26aeae9fd73651736707f68e3faa66621efcfc0`, parent `a31a94a` |
| Adjudication report | `docs/implementation/p4-r07-closure-fourth-candidate-targeted-adjudication-report-a31a94a.md` |
| Adjudication report SHA-256 | in its `.sha256` sidecar and the preservation commit message (§19) |
| Adjudication preservation | `refs/preserve/p4-r07-closure-fourth-candidate-targeted-adjudication-a31a94a`, parent `a31a94a` |
| Canonical suite | 2072 passed / 0 failed / 1 skipped / 2073 collected |
| Clean-clone gate | PASS |
| Manifest identity | exact, 2073 nodes (+29 / −0 vs `3874d4a`) |
| Mutation results | roadmap 58/58 (0 defective, 0 SKIP-INVALID); boundary 61/61; anti-vacuity exactly 11 MISS on `3874d4a` |
| P4 / P5 / R-07 states | P4 COMPLETE; P5 sole READY and NOT_STARTED; P6–P14 BLOCKED; R-07 CONTAINED |
| Production-gate state | `GateRegistry` EMPTY; Phase-8 Action Class gate registration DEFERRED to U8.1 |
| Residual risks | FR-01, FR-02 (S-04), FR-03 (S-05), FR-04, FR-05, **A-01**, **A-02**; carried S-07, RR-01–RR-04, RC-01, F-06, AD-01, AD-02, RC-02, RC-03 |
| Finalizer prerequisites | §18 |

**Exactly one third finalizer is authorized. This adjudication session did not run it.**

---

## 18. FINALIZER PREREQUISITES — ONE FRESH, INDEPENDENT THIRD-FINALIZER SESSION

The finalizer session must be **distinct** from the P4 implementer, from the authors of `11c9112`,
`4d12b0e`, `3874d4a` and `a31a94a`, from the fresh reviewer of `a31a94a`, from this adjudicator,
and from both previous finalizers. It must resume no prior session.

**Verify before invoking:**

1. `refs/heads/p4/adapter-containment-completion` still points to exactly
   `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24`.
2. Candidate tree is still `637580b64ca666695d0811c4119e866de6100ce9`; parent still `06ebfdb3`;
   single-parent, not a merge; still not a descendant of `11c9112`, `4d12b0e` or `3874d4a`;
   topology still PRODUCING with `42ea24c` == `HEAD^^`.
3. Review preservation verifies: `refs/preserve/p4-r07-closure-fourth-candidate-targeted-review-a31a94a`
   → `c26aeae9…`, parent `a31a94a`, report SHA-256 `436dc560…d6e92` matching its sidecar.
4. Adjudication preservation verifies: the ref, commit, parent and SHA-256 recorded in §19.
5. Worktree and index satisfy finalizer authority — `git status --porcelain` empty; the runner
   refuses a dirty tree by design.
6. Finalizer lock `.git/neyma-finalizer.lock` is **unheld** (non-blocking `flock`). A held lock is
   never reclaimed on the inference that a run "looks" stale.
7. No builder, test, mutation or gate process is active.
8. Canonical receipts remain valid and byte-identical to `06ebfdb3` — `SUITE-RESULT.json`
   `a16cb1fc…`, `GATE-RESULT.json` `8201ca74…`.
9. No protected ref moved: `main` and `origin/main` at `152574e4…`; all three archive refs, three
   candidate-preservation refs, three worktree-preservation refs and all seven review/adjudication
   preservation refs present and unmoved.
10. Nothing pushed; no remote P4 branch exists.

**During finalization:**

11. **Exactly one** invocation of `scripts/finalize_status.py`. No second run for any reason.
12. **No hand-editing of `STATUS_METADATA_FILES`** — the finalizer writes derived status; a human
    or agent edit to those files invalidates the receipt convention.
13. **No P5 work begins** during finalization. No effect is deployed or enabled.
14. No amend, reset, restore, rebase, merge, checkout, stash, clean, ref move or push of the
    product branch beyond what the finalizer itself performs.

**Expected legal topology after successful finalization:**

```
06ebfdb35a544df8e9cf36d739cc54a0b6877e1f   (certified metadata — existing)
        └── a31a94aa8239113ec8ea3c02b5ef6fad922a1b24   (content — the accepted candidate)
                └── <new status-metadata commit>        (pure metadata, written by the finalizer)
```

`HEAD` = the new metadata commit; `HEAD^` = `a31a94a` (the recorded content commit); the repository
resolves **FINALIZED** with `recorded == HEAD^`. Single-parent throughout, no merge, exactly one
content commit between the two metadata commits. Any second content commit on top of `a31a94a`
before finalization would make the recorded content commit match neither `HEAD`, `HEAD^` nor
`HEAD^^` and resolve **ILLEGAL** under `repo_state.py`.

---

## 19. PRESERVATION AND PROOF OF NON-MUTATION

**This adjudication is preserved through the repository-authorized adjudication mechanism: a
`refs/preserve/*` commit whose parent is exactly the candidate it adjudicates.**

*Values recorded by the preservation step that commits this report. The report blob's own digest
cannot appear inside itself; it is carried in the adjacent `.sha256` sidecar and in the preservation
commit message, which is the convention every predecessor report in this family used.*

| Field | Value |
|---|---|
| Report path | `docs/implementation/p4-r07-closure-fourth-candidate-targeted-adjudication-report-a31a94a.md` |
| Report SHA-256 | in the sidecar and the preservation commit message |
| Sidecar | `docs/implementation/p4-r07-closure-fourth-candidate-targeted-adjudication-report-a31a94a.md.sha256` |
| Preservation ref | `refs/preserve/p4-r07-closure-fourth-candidate-targeted-adjudication-a31a94a` |
| Preservation parent | `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24` — exactly the candidate |
| Adds | this report and its sidecar only |

**Pre-state, captured before any write:** branch `p4/adapter-containment-completion`; HEAD
`a31a94aa8239113ec8ea3c02b5ef6fad922a1b24`; HEAD tree `637580b64ca666695d0811c4119e866de6100ce9`;
`git status --porcelain` empty; `main` = `origin/main` = `152574e4f4f2969468c9d31b1e705188896175b5`;
62 refs, of which 37 are `refs/preserve/*`.

The preservation commit adds **only** this report and its sidecar. It does not overwrite any
previous review or adjudication report — all seven earlier reports remain at their original refs,
parented to the candidates they actually reviewed, unmodified.

**Proof the branch, tree and index were not changed.** `refs/heads/p4/adapter-containment-completion`
still points to `a31a94a`; the candidate tree is still `637580b6`; `git status --porcelain` on the
primary worktree is empty. The report was committed via a **temporary index file**
(`GIT_INDEX_FILE` in a scratch directory) with `hash-object` / `read-tree` / `write-tree` /
`commit-tree` / `update-ref` — the primary index was never read or written, and no checkout,
amend, reset, restore, rebase, merge, stash, clean or branch-ref move occurred.

**Proof every rejected candidate and prior report remains preserved.** All three archive refs, all
three candidate-preservation refs, all three complete-worktree preservation refs and all six
predecessor review/adjudication preservation refs are present and unmoved (§3), plus the `a31a94a`
review at `c26aeae9` (§2).

**Proof nothing was pushed.** `p4/adapter-containment-completion` has no upstream; `git ls-remote
--heads origin` lists no `p4/*` ref and is otherwise unchanged; `main` and `origin/main` remain
`152574e4f4f2969468c9d31b1e705188896175b5`. `refs/preserve/*` refs are local and were never pushed.

---

## 20. WHAT THIS ADJUDICATION DID NOT DO

It did not remediate, modify or amend the candidate. It did not run `finalize_status.py` or any
finalizer. It did not begin P5. It did not deploy or enable any effect. It did not move the product
branch or any shared or protected ref, did not push, and did not test implementation behaviour from
the primary worktree.

---

# VERDICT

# ACCEPT FOURTH CANDIDATE FOR THIRD FINALIZATION

**Candidate `a31a94aa8239113ec8ea3c02b5ef6fad922a1b24` is eligible for exactly one third
finalizer**, subject to the prerequisites in §18, to be run by a fresh, independent session.
