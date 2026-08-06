# P4 R-07 CLOSURE — SEPARATE TARGETED ADJUDICATION OF SUCCESSOR CANDIDATE 3874d4a

**Verdict: REJECT — TARGETED REMEDIATION REQUIRED**

| | |
|---|---|
| Exact candidate | `3874d4a1bd02cdf81525aba52268e7aa44343457` |
| Expected / observed tree | `82bd3da480f4f1320bd1a9cff076bb8f99827efc` — **matches** |
| Expected / observed parent | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` — **matches** |
| Branch | `p4/adapter-containment-completion` — **matches** |
| Repository state | **PRODUCING**, exactly one content commit above the certified metadata parent |
| Review adjudicated | `refs/preserve/p4-r07-closure-successor-targeted-review-3874d4a` @ `ccc9344d`, verdict REJECT |
| Third finalizer | **NOT AUTHORIZED** |
| Legal remediation path | **A — replace `3874d4a` in place against certified parent `06ebfdb3`** |

This adjudication was performed by a session that did not implement P4, did not author `11c9112`,
did not author `4d12b0e`, did not author `3874d4a`, did not conduct the successor's independent
review, and ran neither finalizer. No previous session was resumed. The candidate was not modified,
remediated, amended, reset, restored, rebased, merged, checked out, stashed or cleaned; no branch ref
was updated; `scripts/finalize_status.py` was not run; P5 was not begun; nothing was deployed or
enabled; nothing was pushed. All parser analysis was performed against a **disposable `--no-local`
clone** and against blobs read with `git show`; the primary worktree, branch and index were never
written.

---

## 1. IDENTITY, TOPOLOGY AND ATTRIBUTION — INDEPENDENTLY VERIFIED

| Property | Required | Observed | |
|---|---|---|---|
| Candidate | `3874d4a1bd02…` | `3874d4a1bd02cdf81525aba52268e7aa44343457` | ✅ |
| Tree | `82bd3da480f4…` | `82bd3da480f4f1320bd1a9cff076bb8f99827efc` | ✅ |
| Parent | `06ebfdb35a54…` | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` | ✅ |
| Single-parent, not a merge | required | `git rev-list --parents -n1` → 2 tokens (commit + one parent) | ✅ |
| Exactly one content commit above `06ebfdb3` | required | `HEAD^` = `06ebfdb3` | ✅ |
| Not a child/descendant of `11c9112` | required | `merge-base --is-ancestor 11c9112 3874d4a` → **false** | ✅ |
| Not a child/descendant of `4d12b0e` | required | `merge-base --is-ancestor 4d12b0e 3874d4a` → **false** | ✅ |
| `main` = `origin/main` | `152574e4` | `152574e4f4f2969468c9d31b1e705188896175b5` (both) | ✅ |
| Nothing pushed | required | `git branch -r --contains 3874d4a` → **empty** | ✅ |
| Working tree / index | clean, equal to HEAD tree | `status` empty; `write-tree` = `82bd3da4…` | ✅ |

### 1.1 The PRODUCING shape is real, not asserted

The driver's state machine (`neyma_product_driver/repo_state.py`) admits exactly three legal shapes.
Each input was re-derived here rather than inherited:

* **recorded content commit** — `docs/implementation/CURRENT.md` status-block records
  `content_commit: 42ea24cfc76fac19406e7eaa44b695b8d032b3aa`, and `42ea24c` is `HEAD^^`.
* **`HEAD^` is a pure status-metadata commit** — `06ebfdb3` touches exactly five files:
  `BUILD-STATUS.yaml`, `CURRENT.md`, `GATE-RESULT.json`, `IMPLEMENTATION-REGISTRY.yaml`,
  `SUITE-RESULT.json`. No CONTENT-classified path. ✅
* **`HEAD` is the next content commit** — `3874d4a`.

`recorded == HEAD^^` ∧ `HEAD^` pure metadata ⇒ **PRODUCING** (`repo_state.py:281–299`). Confirmed.

### 1.2 The review is attributable only to 3874d4a

| Check | Result |
|---|---|
| `refs/preserve/p4-r07-closure-successor-targeted-review-3874d4a` | resolves to `ccc9344d6645320c3817a889bc38c95c50dae7d3` ✅ |
| Preservation parent | `3874d4a1bd02cdf81525aba52268e7aa44343457` — **exactly the candidate** ✅ |
| Diff vs parent | **2 files, +833 lines** — the report and its sidecar, nothing else ✅ |
| Report blob SHA-256 | `104f7ecff720234797915cf92038c6b66e03864adc4246cd7b9a346271a3249d` — **matches expected** ✅ |
| Sidecar content | same digest, naming `p4-r07-closure-successor-targeted-review-report-3874d4a.md` ✅ |
| Materialization | read with `git show` only; branch, worktree and index untouched ✅ |

The report was **not** reinterpreted from any earlier review. Both rejected predecessors and their
complete evidence families remain preserved at their own refs, parented to the candidate each
actually examined:

| Artifact | Object | Parent |
|---|---|---|
| `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` | `11c9112…` | `06ebfdb3` |
| `refs/preserve/p4-r07-rejected-worktree-11c9112` | `6224b36` | **`11c9112`** |
| `refs/preserve/p4-r07-closure-targeted-review-11c9112` | `fa4c459` | **`11c9112`** |
| `refs/preserve/p4-r07-closure-targeted-adjudication-11c9112` | `030c595` | **`11c9112`** |
| `refs/preserve/p4-r07-closure-rejected-replacement-candidate-4d12b0e` | `4d12b0e…` | `06ebfdb3` |
| `refs/preserve/p4-r07-rejected-replacement-worktree-4d12b0e` | `6b88dd0` | **`4d12b0e`** |
| `refs/preserve/p4-r07-closure-replacement-targeted-review-4d12b0e` | `62df39d` | **`4d12b0e`** |
| `refs/preserve/p4-r07-closure-replacement-targeted-adjudication-4d12b0e` | `ce5dbb3` | **`4d12b0e`** |
| archive branches `archive/p4/r07-rejected-11c9112`, `archive/p4/r07-rejected-replacement-4d12b0e` | intact | `06ebfdb3` |

---

## 2. BLOCKING FINDING S-01 — CONDITIONAL EXEMPTION SPANS THE WHOLE TABLE ROW

**CONCLUSION: BLOCKING. CONFIRMED, and materially broader than the review reports.**

### 2.1 The exact implementation that creates the row-wide exemption

`eval/control/status_claims.py:704`:

```python
elif _CONDITIONAL.search(unit.norm[:token_end]):
    exemption = "hypothetical"
```

`unit.norm` for a table row is built by `_row_unit` (`:583–587`) as
`_CELL_JOIN.join(normalize(c) for c in row.cells)` — **the entire row, all cells, joined by `" | "`**.
`token_end` is the end offset of the polarity token inside that row-wide string. The search window is
therefore `[start of the row, end of the polarity token]`, spanning **every preceding cell**. There is
no cell restriction anywhere in the expression.

This is precisely the R-01 widening applied to the wrong thing. R-01 correctly widened the *claim
unit* from the cell to the row so that subject and status could associate. The three exemption rules
were then left keyed to that widened unit, so the *exemption window* widened with it. Association and
exemption were conflated.

### 2.2 Independently reproduced

Executed against the candidate's own parser, read from the candidate tree:

| Case | Result |
|---|---|
| `\| Condition \| if X happens \| R-07 \| OPEN — NOT CONTAINED \|` | **exempt: hypothetical** — the reviewer's exact case ✅ reproduced |
| same row with `if` removed | **LIVE-OPEN** — proving `if` in cell 1 is the sole cause |
| `\| R-07 \| reviewed before the cutover \| OPEN — NOT CONTAINED \|` | **exempt: hypothetical** |
| `\| R-07 \| recorded when the gate ran \| OPEN \|` | **exempt: hypothetical** |
| `\| R-07 \| OPEN — NOT CONTAINED \| unless waived \|` | LIVE-OPEN (trailing marker correctly ignored — R-03 holds) |

### 2.3 Amplification the review did not record

The reviewer framed S-01 as a hostile evasion. It is worse: `_CONDITIONAL` (`:185–190`) contains
`when`, `while`, `before`, `after`, `once`, `should`, `would`, `could`. These are **ordinary English
words that occur constantly in evidence, description and notes columns**. A row reading
`| R-07 | recorded when the gate ran | OPEN |` launders itself with no adversary present. The defect
therefore fires **accidentally**, not only adversarially, which raises it from an evasion vector to a
latent silent-failure mode of the control.

### 2.4 Answers to the adjudication questions

1. **What creates it** — `:704`, searching `unit.norm[:token_end]` over the row-joined normalization.
2. **Must conditional classification attach to the exact claim cell / bounded claim unit?** **Yes.**
   The conditional must *govern the polarity token*; the smallest structure that can govern it is the
   cell that contains it. Anchoring the window at the start of the **status token's own cell** and
   ending at `token_end` preserves the correct rule ("R-07 may not be recorded CONTAINED until the
   gate asserts empty") and eliminates every cross-cell path.
3. **May a conditional token in an evidence / description / notes / status-independent cell affect a
   separate canonical status cell?** **No.** A separate cell is a separate field of the record. A
   qualifier in one field does not qualify another field's value. Today it does — this is the defect.
4. **May subject and status still associate across cells while exemption metadata stays cell-local?**
   **Yes, and they must.** These are independent axes: *association* answers "which subject does this
   status belong to" and is correctly row-scoped (R-01); *exemption* answers "is this assertion
   qualified" and must be claim-local. Separating them is the whole delta. It costs nothing:
   `ClaimUnit.cell_spans` already carries per-cell offsets and `_cell_at` already resolves a
   normalized position to its cell — the mechanism is present and simply is not used at `:701`/`:704`.
5. **`| Condition | if X happens | R-07 | OPEN — NOT CONTAINED |`** must be read as a **LIVE OPEN
   contradiction**. Cell 3 is an unqualified canonical status assertion about R-07. `if X happens` is
   a statement about cell 1's subject; it does not reach into cell 3. The guard must FAIL on this row.
6. **Prevention** — bound the conditional window to `[start of the status token's cell, token_end]`.
   That single change blocks row-wide laundering and cross-cell inheritance, and provably does not
   disturb cross-cell subject/status parsing (§5).
7. **Must hostile tests include the reviewer's live cases and multiple descriptive arrangements?**
   **Yes.** Both reproduced cases plus arrangements varying the number and position of descriptive
   columns, since column count is the free variable an author controls.
8. **Must mutation operators attack conditional words before the subject, between subject and status,
   after the status, and in unrelated descriptive columns?** **Yes — all four.** The
   after-the-status position is a required **must-stay-GREEN negative** (R-03's rule); the other three
   are required CAUGHT positives. Without the negative, a remediation that simply deleted the
   conditional rule would score full marks.

---

## 3. BLOCKING FINDING S-02 — HISTORICAL MARKER SPANS THE TABLE-ROW PREFIX

**CONCLUSION: BLOCKING. CONFIRMED.**

### 3.1 The exact implementation

`eval/control/status_claims.py:701`:

```python
elif _HISTORICAL_MARKER.search(unit.norm[:risk_in_norm.start()]):
    exemption = "marked-historical"
```

Same structural error as S-01, one line earlier: the window is `[start of the row, start of the risk
id]` over the row-joined normalization, so **any cell preceding the subject cell** can carry the
marker.

### 3.2 Independently reproduced

| Case | Result |
|---|---|
| `\| Historical example \| unrelated text \| R-07 \| OPEN — NOT CONTAINED \|` | **exempt: marked-historical** ✅ reproduced |
| `\| R-07 \| OPEN — NOT CONTAINED \| nothing here is SUPERSEDED \|` | LIVE-OPEN (R-03's trailing-marker rule holds) |

### 3.3 Answers to the adjudication questions

1. **What propagates it** — `:701`, the row-wide prefix window.
2. **Where must the marker be structurally attached?** To a **repository-authorized bounded
   construct** that contains the claim. Three are already authorized and each remains valid:
   (a) the **claim's own cell**, preceding the risk id — the form the live corpus actually uses;
   (b) a **self-labelling `<details>` block** carrying the claim (`details_blocks`, correct today);
   (c) a **quoted span** within the claim's own block (`_quoted`, correct today).
   An *explicit row-level marker* is **not** currently an authorized construct and must not be
   invented as part of this remediation — no live document uses one, and adding one would be a
   vocabulary/scope change, not a defect correction.
3. **May a historical token in an unrelated description / evidence / example cell, or a column
   heading, exempt a separate live R-07 claim?** **No.** A heading in particular must not: headings
   name columns, they do not qualify values, and the entire corpus would become exemptible by naming
   a column "Historical status".
4. **What is the correct rule?** **The marker applies only to its own claim unit — bounded to the
   subject cell for a table row, and to the claim's own sentence for prose.** Not "whole row". This
   is the same discipline `_CONDITIONAL` must receive, which is what the module docstring already
   claims it has ("one marker discipline governs this module rather than two contradictory ones",
   `:120–124`) — the docstring is currently true of *ordering* and false of *scope*.
5. **`| Historical example | unrelated text | R-07 | OPEN — NOT CONTAINED |`** must remain a **live
   contradiction**. Only an explicit marker attached to the R-07 claim itself may exempt it.
6. **Must row-aware subject/status association be preserved?** **Yes.** Restricting the marker window
   is independent of association; §5 proves the restriction changes no live classification.
7. **Must hostile tests cover markers before R-07, after R-07, in the status cell, in an unrelated
   cell, in headers, and in neighbouring rows?** **Yes, all seven.** *Before R-07 in the subject's own
   cell* and *neighbouring rows* are must-stay-GREEN / must-stay-LIVE negatives respectively; the rest
   are CAUGHT positives. The neighbouring-row case is essential to prove the fix did not overcorrect
   into cross-row association.

---

## 4. BLOCKING FINDING S-03 — PROSE ABOVE `<details>` LAUNDERS THE WHOLE BLOCK

**CONCLUSION: BLOCKING. CONFIRMED, and it defeats two of the module's advertised fail-closed
guarantees — a consequence the review did not record.**

### 4.1 The exact implementation

`_prose_blocks` (`eval/control/status_claims.py:590–607`) terminates a prose run on exactly two
conditions: a blank line, or a table line. It does **not** break on `<details>`, `<summary>` or
`</details>`. Compounding this, `_SENTENCE_SPLIT` (`:198`) requires the following character to be in
`[A-Z*#\`\[("'>-]`, which **does not include `<`** — so a sentence never splits before an HTML tag
either. An entire `<details>` region written without blank lines therefore collapses into **one prose
claim unit**, and the row-prefix marker rule of §3 then exempts a claim inside the block using text
from outside it.

Note the mechanism precisely: the exemption granted is **`marked-historical`**, not
`historical-details`. `details_blocks()` correctly refuses to label the block. The laundering happens
entirely in the prose-unit layer, *behind* the details classifier.

### 4.2 Independently reproduced

| Case | Result |
|---|---|
| `HISTORICAL` sentence **immediately above** `<details>` (no blank line), unlabelled block, `R-07 — OPEN, NOT CONTAINED` inside | **exempt: marked-historical** ✅ reproduced |
| Same, but **blank line** between marker and `<details>` — the M34 arrangement | **LIVE-OPEN** — does *not* reproduce ✅ |
| Conditional sentence (`if …`) immediately above `<details>` | **exempt: hypothetical** — the same escape via the conditional rule |
| Correctly attached `<summary>HISTORICAL — superseded</summary>` | exempt: historical-details ✅ correct behaviour preserved |

The second row is decisive and independently confirms the review's M34 claim: **M34 is green for the
wrong reason.** Its fixture (`scripts/mutate_roadmap_completeness.py:298–304`) writes
`⛔ HISTORICAL — the superseded notes below.\n\n<details>` — a blank line, so the prose block breaks
and the parser survives. It therefore certifies "proximity is not attachment" while the adjacent
arrangement it is named for escapes.

### 4.3 Amplification — two advertised fail-closed properties are defeated

The module docstring makes two explicit fail-closed promises. `details_blocks()` honours both. The
prose-unit merge silently defeats both:

| Docstring promise | Reproduced behaviour |
|---|---|
| `:86–89` "Malformed structure FAILS CLOSED. An unterminated `<details>` grants no exemption at all, so a live claim can never disappear because the HTML did not parse" | `<details>` / `<summary>HISTORICAL</summary>` / `R-07 — OPEN, NOT CONTAINED` with **no closing tag and no blank lines** → **exempt: marked-historical**. The claim disappeared. |
| `:82–84` "a block NEVER inherits its parent's label … An unlabelled block nested inside a labelled one is therefore LIVE" | Unlabelled inner block inside a `HISTORICAL`-labelled outer block, **no blank lines** → **exempt: marked-historical**. The child inherited. |

M36 (malformed) and M37 (nested) pass only because their fixtures contain blank lines. The
adjacent-arrangement variants of both are uncovered. This makes S-03 strictly more severe than
reported: it is not merely one laundering path but a **bypass of the details classifier as a whole**.

### 4.4 Answers to the adjudication questions

1. **May a marker outside a `<details>` block ever classify the block?** **No — never.** The corpus's
   own recorded incident (CURRENT.md, quoted at `:69–72`) requires historical blocks to be
   *self-labelling rather than silently trusted*. An external marker is by construction not
   self-labelling.
2. **What marker must be attached before a block's claims may be excluded?** A `_HISTORICAL_MARKER`
   token (`HISTORICAL` / `SUPERSEDED`) in the block's **own `<summary>`**, or — absent a summary — the
   **first non-blank line of its own body**. This is exactly what `_build_block` (`:392–420`) already
   implements. No new construct is required or authorized.
3. **Must `<details>`, `<summary>`, `</details>` terminate ordinary prose-block association?**
   **Yes.** They are structural boundaries; a claim unit that straddles one is not bounded by the
   structure it is written in, which is the module's stated segmentation principle (`:17–19`).
4. **Is a marker on the immediately preceding prose line insufficient?** **Yes, insufficient** —
   unless it is encoded in an authorized block-attached position. Adjacency is proximity, and
   proximity is not attachment.
5. **May blank-line adjacency affect classification?** **No — and that it currently does is itself the
   defect signature.** Classification must be identical whether or not a blank line separates the
   marker from the block. Today the two arrangements diverge, which is why one mutation passes and its
   twin escapes.
6. **Do nested blocks inherit markers?** **No**, in either direction. `details_blocks()` is correct;
   the fix must make the prose layer stop defeating it.
7. **Must malformed details structures fail closed?** **Yes**, and `details_structure_defects()` must
   continue to report them loudly. Reproduced above: today the promise is void for the adjacent
   arrangement.
8. **Is the narrow correction for the prose-block parser to break at structural details tag lines?**
   **Yes — that is the correct and sufficient narrow correction**, verified by simulation (§5).
   Breaking `_prose_blocks` on lines that begin with `<details…>`, `</details>`, `<summary…>` or
   `</summary>` closes the adjacent-marker escape, the conditional twin, the malformed-block bypass
   and the nested-inheritance bypass simultaneously.
9. **Must the existing marker vocabulary remain unchanged?** **Yes.** `_HISTORICAL_MARKER` stays the
   closed two-word set. Widening it is a separate deliberate act with its own hostile cases
   (RR-01) and is **not authorized** here. Fail-closed is the correct direction for `ARCHIVED` /
   `REJECTED EVIDENCE`.
10. **Must M34 be retargeted from the blank-line case to the exact adjacent-marker escape?** **Yes —
    required, not optional.** Verified: the current fixture cannot fail on this defect. Retargeting is
    what converts M34 from a fixture that passes for the wrong reason into evidence.
11. **Must hostile tests cover adjacent external marker, blank-line external marker, valid attached
    marker, marker inside summary, marker in block content, nested blocks, and malformed/unclosed
    blocks?** **Yes, all seven** — and, on the evidence in §4.3, each of the last two must appear in
    **both** the blank-line and the no-blank-line arrangement, since only the latter escapes.

---

## 5. IS THE PROPOSED REMEDIATION THE COMPLETE NARROW DELTA? — DECISIVE TEST

The review proposes three corrections plus mutation coverage. I did not take that on trust. I
**implemented the proposed fix as a simulation** against the candidate's own parser and re-ran the
entire live-authority corpus, comparing every claim's classification.

Simulated delta, exactly as proposed:
* (a) conditional window bounded to the **status token's own cell**;
* (b) historical-marker window bounded to the **subject's own cell**;
* (c) `_prose_blocks` breaks at structural `<details>` / `<summary>` / `</details>` lines.

### 5.1 Live-corpus effect: none

| Population: 57 discovered live-authority documents | Current parser | Simulated fix |
|---|---|---|
| live OPEN | **0** | **0** |
| live CONTAINED | 47 | 47 |
| exempt — quoted | 20 | 20 |
| exempt — hypothetical | 8 | 8 |
| exempt — marked-historical | 7 | 7 |
| total claims | 82 | 82 |

**Per-claim classification is byte-identical. Zero claims change.** The reason is mechanical and I
verified it directly: **all four** row-level exemptions in the live corpus have
`subject_cell == status_cell` — the marker or conditional already sits in the claim's own cell:

| Document | Exemption | Cells |
|---|---|---|
| `docs/implementation/PHASE-OUTPUTS.md:109` | marked-historical | `(HISTORICAL — this row states the state AFTER P3 …) R-07 stays OPEN through P3` — marker **in-cell**, before the subject |
| `docs/implementation/pr-sequence.md:33` | marked-historical | `(HISTORICAL — this frozen Phase-0 sequence …) R-07 stays OPEN at P0` — marker **in-cell** |
| `docs/implementation/CURRENT.md:62` | hypothetical | conditional and polarity in the **same** cell |
| `docs/implementation/CURRENT.md:106` | hypothetical | conditional and polarity in the **same** cell |

The two live OPEN claims that legitimately need exemption are exempted correctly under the tightened
rule. This is strong evidence that the proposed delta is **correctly shaped**: it removes only
capability the corpus never uses.

### 5.2 Hostile effect: all three escapes close, all legitimate exemptions survive

| Case | Current | Simulated fix |
|---|---|---|
| S-01 conditional in preceding cell | exempt | **LIVE-OPEN** ✅ |
| S-01 conditional in evidence cell | exempt | **LIVE-OPEN** ✅ |
| S-02 historical in preceding cell | exempt | **LIVE-OPEN** ✅ |
| S-03 adjacent external marker | exempt | **LIVE-OPEN** ✅ |
| S-03 conditional adjacent above block | exempt | **LIVE-OPEN** ✅ |
| **malformed unterminated block, adjacent** | exempt | **LIVE-OPEN** ✅ (fail-closed restored) |
| **unlabelled block nested in labelled, adjacent** | exempt | **LIVE-OPEN** ✅ (no-inheritance restored) |
| conditional *after* the status cell | LIVE | LIVE ✅ (R-03 preserved) |
| historical marker *after* the subject | LIVE | LIVE ✅ (R-03 preserved) |
| valid attached `<summary>` marker | exempt: historical-details | exempt: historical-details ✅ |
| in-cell historical marker | exempt | exempt ✅ |
| in-cell conditional | exempt | exempt ✅ |
| cross-row false association | LIVE-CONTAINED (no join) | LIVE-CONTAINED ✅ |

### 5.3 Adjudicated conclusion on the remediation delta

**The reviewer's six-item minimum is the correct narrow remediation and is very nearly complete.
Three bounded additions are mechanically required, all inside the same surfaces already being
touched; nothing broader is authorized.**

Required, as proposed:
1. S-01 — conditional window → the claim's own cell / bounded claim unit.
2. S-02 — historical-marker window → the subject's own authorized bounded location.
3. S-03 — `_prose_blocks` breaks at structural `<details>` tag lines.
4. Mutation operators for S-01, S-02, S-03.
5. M34 retargeted to the exact adjacent-marker variant.
6. Retain unchanged: R-07 technical containment, F-01 cleanup, F-03 evidence binding, R-03, R-04,
   R-05, and the entire runtime implementation.

**Additionally required by evidence developed in this adjudication:**

7. **Adjacent-arrangement variants of the malformed-block and nested-block mutations** (M36/M37
   twins with no blank line). §4.3 proves the module's two advertised fail-closed guarantees are
   currently void in exactly the arrangement no mutation covers. Restoring them without a mutation
   that would have caught them repeats the M34 failure mode one operator over.
8. **A must-stay-GREEN negative for each tightened window** — conditional after the status cell,
   marker after the subject, marker in a neighbouring row, cross-row and cross-table non-association.
   Without these, deleting the exemption rules outright would score full marks on the new operators.
9. **The `_CONDITIONAL` twin of S-03 must be covered explicitly** (conditional prose adjacent above a
   `<details>` block), since correction (c) is what closes it and a details-only test would not
   demonstrate that.

**Explicitly NOT authorized:** widening `_HISTORICAL_MARKER`; introducing a new row-level marker
construct; changing `_SENTENCE_SPLIT`'s character class; any change to `src/`, `configs/` or `data/`;
any re-litigation of R-07 containment, F-01, F-03, R-03, R-04 or R-05; any parser redesign beyond the
three bounded windows.

**A smaller delta is not available.** Each of the three corrections closes escapes the other two do
not: (a) and (b) are independent rules, and (c) closes a class that survives both (the malformed and
nested bypasses reach the marker rule through a *prose* unit, where cell bounds do not exist).

---

## 6. NON-BLOCKING FINDINGS S-04 THROUGH S-07

### S-04 — header rows are rendered text but are never parsed as claims

**Legitimate non-blocking residual. Confirmed, with a caveat.**

Reproduced: `| R-07 | OPEN — NOT CONTAINED |` written as a header (delimiter row beneath) parses to
**zero claims** — not exempt, *absent*. The cause is `claim_units` (`:614`), which admits only
`role == "body"`. This is specified behaviour: the prior adjudication requires header and separator
rows not be parsed as claims, and the parser is compliant.

Independently measured: **0 header rows in the 57-document live-authority corpus mention R-07.** No
canonical status is written in a header row today, and the corpus convention places status in body
cells.

**However**, nothing structurally *forbids* it — a header row renders as visible document text, so it
is a sanctioned location for a claim no guard reads. It is a genuine residual, not a false one.
**Does not block.** Since the replacement already edits this module, a one-line guard asserting that
no header row in the live-authority population mentions the risk id is **recommended but not
required**; the claim-parsing semantics must not change.

### S-05 — no anti-drift guard against reintroducing the raw details regex

**Should receive a narrow anti-drift test in the replacement. Does not block.**

Confirmed: all copies of `re.sub(r"<details>.*?</details>", …)` are delegated to
`control.status_claims`, and no guard prevents a seventh from being written. The recurrence risk is
not hypothetical — this adjudication has just recorded, in S-03, a **live instance of RC-01**: the
same defect class reappearing in a new layer. A guard asserting that no module under `eval/` performs
its own unconditional `<details>` stripping is cheap, sits inside the surface already being touched,
and converts a convention into a mechanism. **Recommended for inclusion in the replacement; not a
blocking condition on its own, and not sufficient to block finalization independently.**

### S-06 — the builder handoff's stated reason for its green F-03 probe is wrong

**Only the replacement handoff/explanation must be corrected. F-03 is NOT reopened.**

The reviewer independently established that the phrase the handoff called unbound **is** bound in two
load-bearing reports, that mutating it produces 15 failures, and that the green probe result reflects
an **invalid probe** rather than a binding gap. Nothing in my independent verification contradicts
this, and the binding itself does not fail. Under the standing instruction, F-03 remains **CLOSED**.

The defect is an **evidence-record defect**: a handoff that misexplains why a probe was green teaches
the next reader a false model of the control. The replacement's handoff must state the correct reason
— the probe was invalid, the phrase is bound, the binding is sound. **No code change. Does not block.**

### S-07 — symlinked `.venv` produces two additional NOT-RUN skips

**Test-environment limitation, not a candidate defect.**

The reviewer reproduced 2043 passed / 1 skipped with a copied venv and 2041 passed / 3 skipped with a
symlinked one, 2044 collected and zero failures in both. The variance is entirely in NOT-RUN skips
caused by the clone being reported dirty; no test changes outcome, and the canonical configuration is
the copied venv. Accurately disclosed in the handoff. **Does not block.**

### Cumulative assessment of S-04 – S-07

Taken together these are two coverage residuals (S-04, S-05), one evidence-record correction (S-06)
and one environment note (S-07). None asserts a false status, none conceals a live claim, and none
compounds with another to do so. **Cumulatively non-blocking.** They do not alter the verdict in
either direction: the rejection rests entirely and sufficiently on S-01, S-02 and S-03.

---

## 7. CONTAINMENT VERSUS CERTIFICATION CONTROLS

These are answered separately and deliberately not equated.

**1. Is the actual R-07 containment mechanism technically valid? — YES.**
Not reopened, and nothing found contradicts it. `src/`, `configs/` and `data/` are unchanged from
`0891d1a`; the containment record in `phase-0-baseline-manifest.yaml` states the mechanism (single
effect-capable importer, CI import gate failing the build on a second, sole external-write path behind
checkpoint → witness → grant → atomic claim, refuse-not-fallback); the production `GateRegistry` is
EMPTY; detection count 13; the Phase-8 Action Class gate deferral is intact. CONTAINED ≠ ENABLED, and
the record says so.

**2. Is immutable evidence binding valid? — YES.** F-03 is closed and remains closed. S-06 is a defect
in a *narrative explanation of* the binding, not in the binding.

**3. Are row-aware and details-aware parsing concepts valid apart from S-01 – S-03? — YES.**
Independently confirmed: subject/status association within a row across any column order and any
number of descriptive columns; no association across rows or across tables; negated containment
decided before plain containment; register-noun suppression; escaped-pipe handling; quote parity
bounded to the row's own block; per-block `<details>` labelling from the block's own `<summary>` or
first body line; no label inheritance in `details_blocks()`. The *architecture* is right. The three
defects are all one narrow error — **exemption windows keyed to the association unit instead of to the
claim** — and correcting them requires no conceptual change.

**4. Are the reported corpus counts trustworthy while the three laundering defects remain? — YES as a
measurement, NO as evidence that the control works.** This distinction is the crux and §5.1 settles
it mechanically: under the corrected parser the live corpus classifies **identically** — 0 live OPEN,
47 live CONTAINED, 35 exempt across the 57 discovered documents. No live claim's classification
depends on any of the three defects, so today's counts are not artefacts. What the counts cannot do is
support the forward-looking claim the control exists to make. **A count is a measurement of the
present corpus; a control is a guarantee about the next edit.** The measurement is sound; the
guarantee is absent.

*Reconciliation of the review's figures:* the review reports 58 documents / 84 claims / 49 live
CONTAINED / 0 live OPEN / 35 exempt. My discovered-population scan returns 57 / 82 / 47 / 0 / 35. The
difference is fully explained and is **not** a discrepancy: the review scanned the **union**
population, which adds `README.md` — outside the discovered population, reached only through the union
(carried residual RR-03) — and `README.md` contributes exactly **2 live CONTAINED and 0 exempt**.
57 + 1 = 58 documents; 82 + 2 = 84 claims; 47 + 2 = 49 live CONTAINED; exempt 35 and live OPEN 0
identical in both. The reviewer's counts are correct for the union scan and are **confirmed**.

**5. Is candidate 3874d4a eligible for the third finalizer? — NO.**
Runtime containment being valid is not the certification question. The commit under adjudication is
the commit that *records* R-07 CONTAINED, and the control that must prove the repository never
silently claims R-07 is open can be defeated by an ordinary word in an adjacent table cell, by a
historical marker in an unrelated column, and by a sentence placed above a `<details>` block — the
last of which additionally voids the module's own malformed-block and no-inheritance guarantees.
Finalizing would certify a status-reality control that does not hold, and would do so in the very
commit whose subject matter is the truthfulness of that status. **Not eligible.**

---

## 8. TOPOLOGY AND THE NARROWEST LEGAL REMEDIATION PATH

Current graph: `06ebfdb3` (certified metadata) → `3874d4a` (candidate). State: **PRODUCING**.

### 8.1 The options, adjudicated against the real state machine

**A. Replace `3874d4a` in place against certified parent `06ebfdb3` — LEGAL. This is the required
path.** The replacement is again the one content commit whose parent is `06ebfdb3`; the shape
`recorded == HEAD^^` ∧ `HEAD^` pure metadata is preserved exactly; PRODUCING is maintained. It is also
the path the repository has already used twice for this same candidate slot (`11c9112` → `4d12b0e` →
`3874d4a`), so it introduces no new mechanism.

**B. Evidence-only `refs/preserve/*` artifact without changing the candidate — LEGAL, and used here
for this report, but INSUFFICIENT as remediation.** A `refs/preserve/*` commit is off-branch and does
not alter HEAD topology. It can preserve findings; it cannot correct `eval/control/status_claims.py`,
which lives in the candidate's tree. It therefore cannot discharge S-01, S-02 or S-03.

**C. Finalize `3874d4a` and correct later — ILLEGAL, and specifically a trap.** Beyond certifying a
control that does not hold, it is *mechanically unrecoverable in the narrow way it presupposes*. After
a third finalizer the repository would be FINALIZED with `3874d4a` recorded. A correcting content
commit would then be the next content commit — legal in isolation — but the correction would have to
be certified by yet another finalizer, and the repository would in the meantime carry a certified
record asserting a status-reality control it does not have. The correction cannot be made *before*
that certification without exactly the replacement of path A. **Not authorized.**

**D. Another repository-authorized mechanism — NONE EXISTS, and a second content commit on top of
`3874d4a` is ILLEGAL.** Verified directly against `neyma_product_driver/repo_state.py`. The recorded
content commit is `42ea24c`. Adding content commit `X` on top of `3874d4a` gives HEAD = `X`,
HEAD^ = `3874d4a`, HEAD^^ = `06ebfdb3`. `42ea24c` then matches **none** of HEAD, HEAD^ or HEAD^^, so
resolution falls through to `repo_state.py:301–304`: **ILLEGAL** — *"the status record names 42ea24c
but HEAD is X, which is neither HEAD, HEAD^ nor HEAD^^ of it — the status authority is stale beyond
every legal state."* The adjacent guard at `:284–289` names the same prohibition directly: *"this is
two unfinalized content commits, which the convention forbids."*

**The real status-reality guard does not permit a second content commit on top of `3874d4a`. No
`commit-tree` or `update-ref` invocation may be used to manufacture one; those are plumbing, not
authorization, and using them to bypass this rule would itself be the violation.**

### 8.2 Required replacement specification

| Item | Requirement |
|---|---|
| Exact rejected candidate | `3874d4a1bd02cdf81525aba52268e7aa44343457` |
| Exact certified parent for the replacement | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` |
| Resulting topology | `06ebfdb3` → `<replacement>`; single-parent, not a merge, exactly one content commit above the certified metadata commit; PRODUCING preserved |
| Prohibited | any replacement that is a child or descendant of `11c9112`, `4d12b0e` or `3874d4a` |

**Required archive / preservation refs before the replacement is created** (matching the discipline
already applied to both predecessors):

* `refs/preserve/p4-r07-closure-rejected-successor-candidate-3874d4a` → `3874d4a`
* `refs/heads/archive/p4/r07-rejected-successor-3874d4a` → `3874d4a`
* `refs/preserve/p4-r07-rejected-successor-worktree-3874d4a` → complete worktree, parent `3874d4a`
* `refs/preserve/p4-r07-closure-successor-targeted-review-3874d4a` → **already exists** at `ccc9344d`, parent `3874d4a` — must not be moved, rewritten or reparented
* `refs/preserve/p4-r07-closure-successor-targeted-adjudication-3874d4a` → this report, parent `3874d4a`

**Attribution:** the successor review at `ccc9344d` and this adjudication remain attributable **only
to `3874d4a`**. Neither may be reinterpreted as reviewing or adjudicating the replacement, exactly as
the `11c9112` and `4d12b0e` families were not reinterpreted for `3874d4a`.

**Allowed changed surfaces in the replacement** (relative to `3874d4a`):

* `eval/control/status_claims.py` — the three bounded window/boundary corrections only
* `eval/tests/*` — hostile cases for S-01, S-02, S-03, plus the negatives and the adjacent-arrangement
  malformed/nested cases required by §5.3; optionally the S-04 header guard and the S-05 anti-drift
  guard
* `scripts/mutate_roadmap_completeness.py` — new operators and the M34 retarget
* `docs/implementation/*` — the corrected handoff (S-06) and any status/registry text the corrections
  require, including refreshed `TEST-NODE-MANIFEST.json` node identities for the added tests

**Prohibited surfaces:** `src/`, `configs/`, `data/`; the containment mechanism; the R-07 CONTAINED
record itself; `_HISTORICAL_MARKER`'s vocabulary; anything belonging to F-01, F-03, R-03, R-04 or R-05.

**Retention:** every previously accepted remediation must be carried forward byte-for-byte — R-07
technical containment, the complete F-01 stale-claim cleanup, the complete F-03 immutable evidence
binding, R-03, R-04, R-05, R-01's row-aware association and R-02's details-aware classification. The
corrections narrow three exemption windows; they remove no accepted work.

**Sequencing — all four steps must succeed, in order, before any finalizer runs:**

1. Preserve and archive `3874d4a` as specified above.
2. Create the replacement content commit on `06ebfdb3`.
3. A **completely fresh independent review** of the replacement, by a session that did not implement
   P4, did not author `11c9112`, `4d12b0e`, `3874d4a` or the replacement, and conducted no prior
   review or adjudication in this family.
4. A **separate targeted adjudication** of the replacement, by a further distinct session.

**No third finalizer may run before steps 1–4 succeed.**

---

## 9. FINALIZER AUTHORIZATION

**A third finalizer is NOT AUTHORIZED on `3874d4a`.** Exactly zero finalizer runs are authorized on
this candidate.

Recorded against the required authorization fields, so the deficiency is precise rather than general:

| Field | Status on `3874d4a` |
|---|---|
| Exact candidate and tree | `3874d4a1bd02cdf81525aba52268e7aa44343457`, tree `82bd3da480f4f1320bd1a9cff076bb8f99827efc` — identity verified |
| Status-parser coverage | **INSUFFICIENT** — three confirmed laundering paths (S-01, S-02, S-03) reproduced independently |
| Exemption / marker attachment correctness | **INCORRECT** — conditional and historical windows are keyed to the association unit (the row) instead of the claim; markers inherit across cells |
| Details-boundary correctness | **INCORRECT** — prose association does not terminate at structural `<details>` lines; the malformed-block and no-inheritance fail-closed guarantees are void in the adjacent arrangement |
| Evidence-binding status | **VALID** — F-03 closed and not reopened; S-06 is a record correction only |
| Canonical suite and manifest status | **GREEN and confirmed** — 2043 passed / 0 failed / 1 skipped / 2044 collected, reproduced in a disposable clean clone; clean-clone gate PASS; TEST-NODE-MANIFEST 2044 exact node-identity equality; `SUITE-RESULT.json` and `GATE-RESULT.json` byte-identical to `06ebfdb3`; batteries 40/40 and 61/61 — **green, and not sufficient, because the defects are in what the guards fail to look at** |
| R-07 / P4 / P5 status | R-07 technical containment **VALID**; production `GateRegistry` **EMPTY**; Phase-8 Action Class gate deferral **intact**; P4 COMPLETE at 100%; P5 sole READY and NOT_STARTED; P6–P14 BLOCKED; no P5 implementation begun; nothing pushed |
| Residuals | S-04, S-05 (coverage), S-06 (record correction), S-07 (environment); carried RR-01 – RR-04, RC-01 (**S-03 is a live instance**), F-06, AD-01, AD-02, RC-02, RC-03 |
| Finalizer prerequisites | **UNMET** — steps 1–4 of §8.2 are outstanding |

Finalization is **not** authorized on the strength of valid runtime containment. The commit's subject
is the *record* that R-07 is contained; certifying it requires that the control proving the repository
never claims otherwise actually holds. It does not.

---

## 10. VERDICT

# REJECT — TARGETED REMEDIATION REQUIRED

Three confirmed blocking defects, each independently reproduced against the candidate's own parser
rather than inherited from the review:

* **S-01** — `status_claims.py:704`: the conditional-exemption window spans the whole table row, so a
  conditional word in any preceding cell launders a separate canonical status cell. Fires
  **accidentally** on ordinary words (`when`, `before`, `after`), not only adversarially.
* **S-02** — `status_claims.py:701`: the historical-marker window spans the row prefix, so a marker in
  any unrelated preceding cell exempts a live R-07 claim.
* **S-03** — `_prose_blocks` (`:590–607`) does not terminate at structural `<details>` lines, so prose
  above a block launders claims inside it — and, beyond what the review recorded, **voids the module's
  advertised malformed-block fail-closed and nested-block no-inheritance guarantees**.

**Narrowest legal remediation delta:** the review's six items, plus the three additions in §5.3
(adjacent-arrangement malformed/nested mutations; must-stay-GREEN negatives for each tightened window;
explicit coverage of the conditional twin of S-03). Verified by simulation to close every reproduced
escape while leaving all 82 live-corpus claim classifications byte-identical. No broader parser
redesign is authorized.

**Topology:** path **A** — replace `3874d4a` in place against certified parent `06ebfdb3`. A second
content commit on top of `3874d4a` is ILLEGAL under `repo_state.py`, and no plumbing invocation may be
used to manufacture one.

Not remediated. Not finalized. P5 not begun.

---

## 11. PRESERVATION AND PROOF OF NON-MUTATION

*Values in this section are recorded by the preservation step that commits this report; the report
blob's own digest is carried in the adjacent `.sha256` sidecar and in the preservation commit message.*

| Item | Value |
|---|---|
| Report path | `docs/implementation/p4-r07-closure-successor-targeted-adjudication-report-3874d4a.md` |
| Sidecar | `docs/implementation/p4-r07-closure-successor-targeted-adjudication-report-3874d4a.md.sha256` |
| Preservation ref | `refs/preserve/p4-r07-closure-successor-targeted-adjudication-3874d4a` |
| Preservation parent | `3874d4a1bd02cdf81525aba52268e7aa44343457` — exactly the candidate |
| Adds | this report and its sidecar only |

**Pre-state, captured before any write:** branch `p4/adapter-containment-completion`;
HEAD `3874d4a1bd02cdf81525aba52268e7aa44343457`; HEAD tree and `git write-tree` both
`82bd3da480f4f1320bd1a9cff076bb8f99827efc`; `git status --porcelain` empty; `main` = `origin/main` =
`152574e4f4f2969468c9d31b1e705188896175b5`; 57 refs.

No earlier report was overwritten; the candidate branch was not modified or moved; no finalizer ran;
nothing was pushed.
