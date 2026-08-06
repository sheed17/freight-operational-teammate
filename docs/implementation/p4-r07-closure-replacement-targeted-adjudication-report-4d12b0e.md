# P4 R-07 CLOSURE — REPLACEMENT CANDIDATE SEPARATE TARGETED ADJUDICATION

**Replacement candidate:** `4d12b0e41cfa722fa74338903526c4bbc52cf65a`
**Tree:** `35f6755c5ce90dc64c96bb5f4be4236a170fff83`
**Parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (second-finalizer metadata commit)
**Branch:** `p4/adapter-containment-completion`
**Replaces rejected candidate:** `11c911244304d56737913db41b458d5f3278bc80`
**Adjudicated review:** `docs/implementation/p4-r07-closure-replacement-targeted-review-report-4d12b0e.md`
(SHA-256 `8c26a311cb80d26715624f43ad5b062fece3ca9319f21948cd242651f95a6d42`)

**Adjudicator standing.** This session did not implement P4, did not author rejected candidate
`11c9112`, did not author replacement candidate `4d12b0e`, did not conduct the replacement
candidate's independent targeted review, did not conduct the prior review or adjudication of
`11c9112`, and did not run either finalizer. No previous session was resumed. It remediated
nothing, finalized nothing, began no P5 work, enabled no effect, moved no protected ref and pushed
nothing. Every implementation behaviour recorded below was measured in a disposable `--no-local`
clone detached at `4d12b0e`; the primary branch, index and worktree were never written.

---

## VERDICT

### REJECT — TARGETED REMEDIATION REQUIRED

The targeted review's verdict is **UPHELD**, and on one point **strengthened**.

R-07's technical containment is real, unchanged and independently re-confirmed. F-01 and F-03 are
correctly and completely remediated. Those results are ratified and are **not** reopened.

The rejection stands on the **certification controls**, not the containment. The replacement parser
removed F-02's word-order dependency and installed a **cell-boundary** dependency in its place. The
repository's own canonical R-07 status rows write the risk id in one Markdown cell and its status in
another, so the guard that exists to prove "no live document asserts R-07 OPEN" **cannot read the
three most load-bearing live statements of R-07's status**. This is the F-02 defect class displaced
by one column, not closed.

I additionally find that R-02 is **more serious than the reviewer graded it**, on evidence the
review did not cite: the repository's own status authority records a past incident of a false claim
planted inside a `<details>` block and states the derived control requirement in terms the
implementation violates.

---

## 1. INDEPENDENT VERIFICATION OF IDENTITY, TOPOLOGY AND ATTRIBUTION

All verified directly, not accepted from the review.

| Check | Required | Observed | Result |
|---|---|---|---|
| Candidate commit | `4d12b0e4…cf65a` | `4d12b0e41cfa722fa74338903526c4bbc52cf65a` | ✅ |
| Tree | `35f6755c…fff83` | `35f6755c5ce90dc64c96bb5f4be4236a170fff83` | ✅ exact |
| Parent | `06ebfdb3…877e1f` | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` | ✅ exact |
| Parent count | 1 | `git rev-list --parents -n1` → one parent | ✅ not a merge |
| Commits above `06ebfdb3` | exactly 1 | `git rev-list --count 06ebfdb3..4d12b0e` = **1** | ✅ |
| Child of `11c9112`? | must be NO | `git merge-base --is-ancestor` → non-zero | ✅ NOT a child |
| Branch | `p4/adapter-containment-completion` | same | ✅ |
| Working tree | clean | `git status --porcelain` empty | ✅ |
| Index digest | — | `761a3a62591a036d4157d38a1d0ce6e13e533b3db5fc4ec7430690117823a001` | ✅ matches the review's recorded value |

### 1.1 Legal PRODUCING topology — mechanically confirmed

`repo_state()` (`eval/tests/test_status_reality.py:64-97`) recognises `PRODUCING` when the recorded
content commit equals `HEAD^^` **and** `HEAD^` changed only `STATUS_METADATA_FILES`.

* `CURRENT.md` status-block records `content_commit: 42ea24cfc76fac19406e7eaa44b695b8d032b3aa`.
* `git rev-parse HEAD^^` = `42ea24cfc76fac19406e7eaa44b695b8d032b3aa`. ✅ equal.
* `git diff --name-only 42ea24c 06ebfdb3` = `BUILD-STATUS.yaml`, `CURRENT.md`, `GATE-RESULT.json`,
  `IMPLEMENTATION-REGISTRY.yaml`, `SUITE-RESULT.json` — **all five inside `STATUS_METADATA_FILES`,
  zero stray paths.** ✅ `HEAD^` is a pure status-metadata commit.

**State = PRODUCING. The topology is legal.** This is load-bearing for §8.

### 1.2 Review report — bytes, sidecar, preservation, attribution

| Check | Observed | Result |
|---|---|---|
| Report SHA-256 (recomputed from the preserved blob) | `8c26a311cb80d26715624f43ad5b062fece3ca9319f21948cd242651f95a6d42` | ✅ **exact** match to expected |
| Sidecar content | `8c26a311…6d42  p4-r07-closure-replacement-targeted-review-report-4d12b0e.md` | ✅ agrees |
| Preservation ref | `refs/preserve/p4-r07-closure-replacement-targeted-review-4d12b0e` → `62df39dd531e7bd751dab070361a9601ce7a8cc9` | ✅ exact |
| Preservation parent | `4d12b0e41cfa722fa74338903526c4bbc52cf65a` | ✅ **exactly the candidate** |
| Paths added by the preservation commit | exactly 2 — the report and its `.sha256` | ✅ evidence-only, no content smuggled |
| Report present in the candidate tree? | **NO** | ✅ attribution is mechanically exclusive |
| Report length | 634 lines / 39,591 bytes — **read in full** | ✅ |

### 1.3 Rejected predecessor and its reports remain preserved and correctly attributed

| Item | Observed | Result |
|---|---|---|
| `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` | `11c911244304d56737913db41b458d5f3278bc80` | ✅ |
| `refs/heads/archive/p4/r07-rejected-11c9112` | `11c911244304d56737913db41b458d5f3278bc80` | ✅ |
| `refs/preserve/p4-r07-rejected-worktree-11c9112` | `6224b36e…` | ✅ present |
| Targeted **review** of `11c9112` | `fa4c459b…a62e`, **parent `11c9112`** | ✅ unmoved, attributable only to `11c9112` |
| Targeted **adjudication** of `11c9112` | `030c5954…a2e8`, **parent `11c9112`** | ✅ unmoved, attributable only to `11c9112` |

Neither `11c9112` report appears in `4d12b0e`'s tree. **No report of `11c9112` is reinterpreted here
as reviewing `4d12b0e`.**

### 1.4 Protected refs and push state

`refs/heads/main` = `refs/remotes/origin/main` = `152574e4f4f2969468c9d31b1e705188896175b5` —
**unmoved**. `git branch -r --contains 4d12b0e` is **empty**: nothing pushed. 29 `refs/preserve/*`
refs present.

---

## 2. THE REVIEWER'S POSITIVE RESULTS — RE-VERIFIED AND RATIFIED

Spot-verified independently. All hold; none is reopened.

| Claim | Independent observation | Result |
|---|---|---|
| `src/` tree-identical to `0891d1a` | both `0204261b17baecd2bab3dc1b7d25a7494eb3b22d` | ✅ IDENTICAL |
| `configs/` identical | both `124ae4bcbbec96cc0ff9282d183d7c97aa1914f5` | ✅ IDENTICAL |
| `data/` identical | both `8d02102277273f6858ce15d3753002e7875bb9df` | ✅ IDENTICAL |
| Receipts byte-identical to `06ebfdb3` | `SUITE-RESULT.json`, `GATE-RESULT.json` are the same blob objects | ✅ |
| Production `GateRegistry` EMPTY | 0 `GateRegistry(` constructions, 0 `register_gate` calls in `src/` + `scripts/` | ✅ |
| No actuator route | `CdpActuator` / `cdp_actuator` appear **only** in `scripts/mutate_phase4_boundary.py` mutation fixture strings | ✅ |
| R-07 recorded CONTAINED | `phase-0-baseline-manifest.yaml` → `expected_legacy_paths.status: CONTAINED` | ✅ |
| P4 COMPLETE | registry `status: COMPLETE` | ✅ |
| P5 sole READY, NOT_STARTED | exactly **1** unit `READY`, `execution_state: NOT_STARTED` | ✅ |
| P6–P14 BLOCKED | exactly **9** units `BLOCKED` | ✅ |
| `TEST-NODE-MANIFEST` node count | `node_count: 2018` | ✅ (see R-05) |
| Corpus sweep | **58 docs scanned, 81 claims, 45 live CONTAINED, 0 live OPEN** | ✅ reproduced exactly |

**F-01 is closed** for every claim the parser can see, and **F-03 is closed**. I ratify both and do
not reopen them. The four CLI smoke failures reproducing on the unmodified parent `06ebfdb3` are
**preserved as an environment limitation, not a replacement regression**.

---

## 3. BLOCKING FINDING R-01 — CROSS-CELL TABLE CLAIMS

### 3.1 Independent reproduction

`claim_units()` (`eval/control/status_claims.py:166-174`) splits a table row on `|` and yields each
cell as an independent claim unit, never re-associating them:

```python
if _TABLE_ROW.match(block):
    pos = block_off
    for cell in block.split("|"):
        yield cell, pos
```

`parse_status_claims` then discards any unit lacking the risk id, and any unit lacking a polarity
token. A row that names R-07 in one cell and its status in another therefore yields **two units,
both discarded, and no claim at all.**

**Parser-level proof.** Every canonical form the brief enumerates:

| Input row | Parse result |
|---|---|
| `\| R-07 \| OPEN — NOT CONTAINED \|` | **NO CLAIM PARSED** |
| `\| Risk \| R-07 \| Status \| OPEN \|` | **NO CLAIM PARSED** |
| `\| R-07 \| CONTAINED \|` | **NO CLAIM PARSED** |
| `\| R-07 \| note \| OPEN \| more \|` | **NO CLAIM PARSED** |

All four — **including the CONTAINED forms** — are invisible.

**Corpus-level proof.** Running the parser over the guard's own unified population, the live
canonical R-07 rows at `CLAUDE.md:73` and `docs/implementation/CURRENT.md:105` produce **no parsed
claim** (parsed claim lines for `CLAUDE.md` are 74/256/289/291; for `CURRENT.md`, 12/62/106/…—
neither 73 nor 105 appears).

**Guard-level proof.** In a disposable clone, against the seven documentation/status guard modules
(`test_docs_control_system.py` + `test_roadmap_completeness_control.py`, baseline **143 passed**):

| Mutation | Result |
|---|---|
| `CURRENT.md:105` cell 3 `**CONTAINED**` → `**OPEN — NOT CONTAINED**` | **143 passed — NOT CAUGHT** |
| `CLAUDE.md:73` cell 2 `**CONTAINED.**` → `**OPEN — NOT CONTAINED.**` | **143 passed — NOT CAUGHT** |
| unlabelled `<details>` containing `R-07 remains OPEN and is NOT CONTAINED.` | **143 passed — NOT CAUGHT** |
| control: same sentence in ordinary prose | **2 failed — CAUGHT** |

**The discriminator is exactly the cell boundary.** The designated status authority can be made to
read *R-07 — OPEN, NOT CONTAINED* with the entire guard set green.

### 3.2 The blind spot is WIDER than the review reported

The review named two live cross-cell rows. Sweeping the unified corpus for table rows that mention
R-07 with a polarity token but yield no parsed claim, I find **four**, of which **three are genuine
canonical R-07 status rows** — and the third was **not named in the review**:

| Document | Line | Row (normalized, truncated) |
|---|---|---|
| `CLAUDE.md` | 73 | `\| R-07 \| CONTAINED. The containment MECHANISM is built…` |
| **`README.md`** | **63** | `\| R-07 — ungated live-write paths \| CONTAINED — the mechanism is built…` |
| `docs/implementation/CURRENT.md` | 105 | `\| R-07 \| Ungated live-write paths \| CONTAINED — recorded in…` |
| `docs/implementation/CURRENT.md` | 63 | P4 row; its R-07 mention is incidental, not an R-07 status claim |

So the guard is blind to R-07's status in the **public landing document, the operating guide, and
the designated status authority** — the three most-read live surfaces in the repository. The
remediation scope must be **measured after the fix**, not assumed to be the two rows the review
named.

### 3.3 The mutation battery measures the parser's own field of view

Every replacement case M12–M21 (`scripts/mutate_roadmap_completeness.py:109-178`) is built on the
template

```
| **Current risk** | ### **R-07 — OPEN, NOT CONTAINED.** |
```

— risk id and polarity token in the **same cell**. Not one case separates them. The battery
therefore reports 21/21 CAUGHT while never testing the construction the corpus actually uses for its
canonical rows. This is precisely **RC-01, the lesson the builder itself recorded** — *a defect count
produced by a broken instrument is a lower bound, never a total* — recurring inside the replacement.

### 3.4 Adjudication of the ten questions

1. **Are Markdown table rows repository-authorized canonical status constructions?** **YES —
   decisively.** `CURRENT.md`'s "Open risks and findings" register, `CLAUDE.md`'s status table and
   `README.md`'s risk table are all Markdown tables, and they are the documents the control system
   designates as live authority. The parser's own docstring cites a table cell as the canonical form
   F-02 existed to catch.
2. **Must cells within one row be interpreted as one bounded semantic unit?** **YES.** A table row is
   a single record; its cells are that record's fields. Subject in column 1 and status in column 3 is
   one assertion, not two fragments. Treating the cell as the bound discards the row's meaning.
3. **Must a row-aware parser retain document, line, row identity, cell identity, subject cell and
   status/polarity cell?** **YES, all six.** Document and line are already retained and must not
   regress. Row identity is required to scope association. Cell identity, subject cell and status
   cell are required so the failure message names *which* cell asserted the polarity — an
   unlocalized failure is not actionable, and the guard's value is that it names the defect.
4. **May status and subject be associated across cells only within the same row?** **YES — and only
   within the same row.** That is the exact bound.
5. **Must cross-row and cross-table association be forbidden?** **YES, unconditionally.** Permitting
   it would let an unrelated row's polarity attach to an R-07 row and manufacture false failures —
   the unrelated-identifier failure mode CLAUDE.md §9 names. Row-scoped association is the whole fix;
   anything wider is a new defect.
6. **Must the parser understand the enumerated constructions?** **YES, all of them**: `| R-07 | OPEN
   — NOT CONTAINED |`; `| Risk | R-07 | Status | OPEN |`; `| R-07 | CONTAINED |`; descriptive columns
   before or after the status; escaped pipes (`\|`) and ordinary table syntax; header and separator
   rows (which must not be parsed as claims); inline code inside cells; and prose containing a
   literal pipe, which **must not** be treated as a table row. All four enumerated forms currently
   parse as nothing.
7. **Is the corpus count of 81 trustworthy?** **NO — not as a completeness measure.** It is exactly
   *reproducible*: I recomputed 58 / 81 / 45 / 0 independently. But it counts only parser-visible
   claims, and at least three canonical R-07 status rows sit outside that view. The figure "45 live
   CONTAINED" excludes the three most load-bearing CONTAINED statements in the repository. "0 live
   OPEN" is **true today by my direct inspection** of the blind rows — and is **not guard-enforced**,
   which is the whole point of the control.
8. **Must all corpus and mutation counts be recomputed after remediation?** **YES.** Row-aware
   parsing will admit claims currently invisible; every count — documents, claims, live CONTAINED,
   live OPEN, `REQUIRED_R07_REACH` membership, the ≥5-live-CONTAINED floor and the 22-case parse
   matrix — must be recomputed from the fixed parser and re-recorded. Counts carried forward
   unchanged would be evidence produced by the superseded instrument.
9. **Must hostile tests include the exact `CURRENT.md` and `CLAUDE.md` rows that escaped?** **YES,
   verbatim**, and on this adjudication's evidence **`README.md:63` as well.** A regression test
   written from a paraphrase does not prove the escape is closed.
10. **Must the mutation battery add cross-cell variants?** **YES, mandatory.** Same-cell cases cannot
    discriminate; the battery must contain at least one case per authorized column arrangement,
    including the 2-cell, 3-cell and interleaved (`| Risk | R-07 | Status | OPEN |`) forms.

### 3.5 Conclusion

**R-01 is CONFIRMED and BLOCKING.** The canonical status-control claim is not enforced over the
repository's own canonical status construction.

---

## 4. BLOCKING FINDING R-02 — `<details>` BLOCKS

### 4.1 Independent reproduction

`strip_historical_blocks` (`status_claims.py:138-140`) deletes **every** `<details>…</details>`
region before parsing, with no label check whatsoever:

```python
def strip_historical_blocks(text: str) -> str:
    """Explicitly-labelled <details> blocks may retain superseded claims in place."""
    return re.sub(r"<details>.*?</details>", "", text, flags=re.S)
```

The docstring asserts a check — *"Explicitly-labelled"* — that the code does not perform.
Reproduced: an **unlabelled** `<details>` block appended to `CURRENT.md` containing
`R-07 remains OPEN and is NOT CONTAINED.` leaves **143 passed**; the identical sentence outside the
block yields **2 failed**. Eleven corpus documents already use `<details>`, `CURRENT.md` among them.

### 4.2 Evidence the review did not cite — this is a regression against a documented requirement

`docs/implementation/CURRENT.md:591-620` preserves an incident record. A prior working tree planted
a **false transition claim** — that P3 had been reviewed and adjudicated when it had not — inside a
`<details>` block. The document's own words:

> It sat inside this `<details>` block, **where every control guard deliberately stops reading** —
> which is exactly why a false claim placed here is **more dangerous than one in live text, not
> less**.

and it states the derived control requirement explicitly:

> …which is why the roadmap-completeness drift guard reads live text only and **requires historical
> blocks to be self-labelling rather than silently trusted**.

The replacement parser **silently trusts** every `<details>` block. This is not merely a
docstring/implementation mismatch: it is a **regression against an incident-derived control
requirement written into the designated status authority**, in the very document the guard is
supposed to police, reopening the exact channel through which a false status claim was once actually
planted in this repository.

I therefore grade R-02 **above** the reviewer's MEDIUM. It is independently blocking.

*(Mitigating, and recorded: all `<details>` blocks in the corpus **today** are in fact labelled —
`⛔ HISTORICAL — SUPERSEDED …`, `Historical status …`, `(historical, non-authoritative)`. No live
false claim is hidden in one right now. The defect is that nothing enforces this, in a repository
that has already suffered the corresponding attack.)*

### 4.3 Adjudication of the ten questions

1. **Is `<details>` inherently historical?** **NO.** It is a presentation container — collapsible
   markup. HTML carries no historical semantics. Treating a rendering choice as a truth qualifier is
   the category error at the root of this finding.
2. **May live canonical status claims appear inside `<details>`?** **YES.** Nothing forbids it, and
   the corpus already places substantive material inside them. Any surface that *may* carry a live
   claim *must* be read.
3. **Must the parser inspect details content by default?** **YES. Parse-by-default, exclude only on
   proof.** The current default is exactly inverted.
4. **What exact marker is required before details content may be excluded?** A **machine-readable,
   structurally bounded** marker **attached to the block itself** — the `<summary>` element, or the
   first non-blank line of the block body, matching the existing closed marker vocabulary
   (`HISTORICAL` / `SUPERSEDED`, i.e. `_HISTORICAL_MARKER`). Bounded means: the marker's scope is
   that block and nothing else, and it is found by parsing the block, never by proximity search.
5. **Are labels such as Historical / Superseded / Rejected evidence / Archived sufficient only when
   attached to the specific block?** **YES — attachment is the whole requirement.** A marker inferred
   from surrounding prose is exactly the ungoverned-marker defect R-03 names, and it is trivially
   forgeable: one sentence before the block would launder everything inside it. The marker must be
   **inside the block's own boundary** (its `<summary>` or its first body line). Extend the accepted
   vocabulary only deliberately; `ARCHIVED` and `REJECTED EVIDENCE` are reasonable additions but must
   be added to the closed vocabulary explicitly, never matched loosely.
6. **Must nested details blocks be handled?** **YES.** The current non-greedy regex `<details>.*?
   </details>` mis-pairs on nesting: it binds the outer opener to the **inner** closer, so content
   after the inner `</details>` re-enters the parse in one arrangement and is dropped in another.
   Nesting must be handled by depth-tracking, and an inner block must **not** inherit the outer
   block's label — each block is labelled or it is read.
7. **Must a status claim hidden in an unlabelled details block fail the guard?** **YES,
   unconditionally.** This is the direct fix, and it is what the incident record demands.
8. **Must a claim in a properly labelled historical details block remain readable but excluded from
   live counts?** **YES — both halves.** It must be **parsed and returned** (as `parse_status_claims`
   already returns exempt claims, carrying an exemption such as `marked-historical`) and **excluded
   from live OPEN/CONTAINED counts**. Deleting the text before parsing destroys the auditability the
   control system depends on: an excluded claim must remain *visible as excluded*, never invisible.
9. **Do the docstring and implementation contradict one another?** **YES, directly.** The docstring
   claims a label requirement; the code implements none. This is the **same class as F-04**, which
   this candidate correctly closed elsewhere — an inaccurate claim inside guard evidence — and it
   must be held to the same standard.
10. **Must hostile tests cover the six enumerated cases?** **YES, all six**: unlabelled details
    containing R-07 OPEN (must FAIL); explicitly historical details containing R-07 OPEN (must be
    parsed, exempt, excluded from live counts, and PASS); live details containing R-07 CONTAINED
    (must be counted live); nested details; malformed or missing closing tags (must fail closed —
    an unterminated `<details>` must **not** swallow the remainder of the document); and labels
    placed **outside** rather than inside the block (must NOT exempt).

### 4.4 Conclusion

**R-02 is CONFIRMED and BLOCKING**, at a severity above the review's grading.

---

## 5. R-03, R-04, R-05 — INDEPENDENTLY CHECKED, ASSESSED CUMULATIVELY

I did not accept the non-blocking classification without checking. All three reproduce.

### R-03 — ungoverned historical marker · **CONFIRMED**

Reproduced at parser level:

| Input | Parse |
|---|---|
| `R-07 remains OPEN and NOT CONTAINED today; nothing here is SUPERSEDED.` | `('OPEN', 'marked-historical')` — **exempted** |
| `R-07 remains OPEN and NOT CONTAINED today.` | `('OPEN', None)` — **live, caught** |

A live false claim is exempted by the mere co-occurrence of a marker word anywhere on its line. The
module deliberately narrowed the *conditional* exemption to markers that **govern** the polarity
token but left the historical exemption ungoverned — an asymmetry with no stated reason.

**Adjudication: individually NON-BLOCKING** — it is the pre-existing marker convention carried
forward, not introduced here. **But it is cumulatively in scope.** R-02's correct fix requires a
*bounded, attached* marker discipline; R-03 is the same discipline missing one function away, in the
same module, in the same pass. Fixing R-02's attachment rule while leaving R-03's line-proximity rule
would ship two contradictory marker semantics in one file. **Include in the remediation scope.**

### R-04 — quote parity bounded by paragraph, not by claim block · **CONFIRMED**

Reproduced: `| a | he said "hello |` followed by `| b | R-07 remains OPEN |` parses the second row
with `exemption='quoted'`; with the quote balanced, the same row parses live. `_blocks()` makes each
table row its own block, but `_quoted()` counts parity from `_block_start_for()`, the preceding
blank line — and a Markdown table has no blank lines between rows, so the whole table is one parity
window.

**Adjudication: NON-BLOCKING.** F-05 is genuinely *improved* — strictly narrower than the file-wide
defect it replaced — but not closed. **Include in the remediation scope**: the fix is a one-line
alignment (`_quoted` must use the boundary `_blocks()` already computes), it is in the same function
family, and it interacts directly with R-01 — once rows are parsed as rows, per-row parity is
required for the row-aware parser to be correct.

### R-05 — inaccurate suite figures in the commit message · **CONFIRMED**

The commit message of `4d12b0e` states *"Canonical suite 2014 passed / 0 failed / 3 skipped / 2017
collected, with TEST-NODE-MANIFEST at exact set equality."*

* `TEST-NODE-MANIFEST.json` records **`node_count: 2018`**.
* The independently reproduced canonical result is **2017 passed / 0 failed / 1 skipped / 2018
  collected**, corroborated by the clean-clone gate's own fresh virtualenv.
* `2014 + 3 = 2017 ≠ 2018`, so "2017 collected" and "exact set equality" **cannot both be true**.

Determinations requested:

* **Is the commit message non-authoritative testimony?** **YES.** Authority for the suite result is
  `SUITE-RESULT.json`, written only by `run_canonical_suite.py` from a real run on a clean checkout,
  and `TEST-NODE-MANIFEST.json`. The message is narrative testimony accompanying them.
* **Do canonical receipts and manifests correctly override it?** **YES.** `repo_state()` and the
  status-reality chain read the artifact and the manifest; the record is derived from
  `update_current_status.py`, never from prose.
* **Does any machine guard consume the inaccurate message?** **NO.** I found no guard parsing commit
  messages for suite figures. Nothing mechanical depends on it.
* **Must it be corrected in a replacement candidate?** **YES — but as a consequence, not as a
  cause.** It alone would not justify replacing a commit, because a commit message cannot be amended
  without breaking topology, and topology outranks a cosmetic correction. **However, R-01 and R-02
  already require the candidate to be replaced.** The replacement author writes a new message
  regardless, so stating the true figures costs nothing and is therefore **mandatory in the
  replacement**.
* **Would leaving it unchanged create a misleading certified history?** **YES.** Finalizing `4d12b0e`
  would make a false suite population permanent in immutable audit evidence — the F-04 standard this
  candidate correctly applied to a docstring, unapplied to its own record.

**Adjudication: NON-BLOCKING on its own; MANDATORY to correct in the replacement.**

### Cumulative assessment

R-03, R-04 and R-05 do not individually block, and they do not change the verdict — **R-01 and R-02
each independently block.** Cumulatively they sharpen the scope: R-02 + R-03 are one coherent marker
discipline; R-01 + R-04 are one coherent row-boundary discipline; R-05 rides free on a replacement
that must happen anyway. Deferring any of them would mean reopening `status_claims.py` a third time.

**The four CLI smoke failures are preserved as environment limitations, not replacement
regressions**, per the review's verified reproduction of 4 failed / 30 passed on both `4d12b0e` and
the unmodified parent `06ebfdb3`.

---

## 6. CONTAINMENT VERSUS PARSER COVERAGE — ANSWERED SEPARATELY

Answered separately and deliberately **not** conflated.

| # | Question | Answer |
|---|---|---|
| 1 | Is the actual external-effect containment mechanism technically valid? | **YES.** `src/`, `configs/`, `data/` tree-identical to `0891d1a`; 0 live and 0 recorded violation edges; 13 detection edges; production `GateRegistry` empty; no actuator construction or import outside mutation fixtures; `ROUTE_NOT_CONFIGURED` default; Phase-8 deferral intact. |
| 2 | Is F-01 documentation cleanup complete for the claims the parser can see? | **YES.** All ten corrections are genuine, with superseded wording quoted in place under explicit markers; no laundering; no claim relocated. |
| 3 | Is the parser capable of discovering every authorized live status construction? | **NO.** It cannot read cross-cell table rows (R-01) or any `<details>` content (R-02) — at least three canonical live R-07 rows are outside its field of view. |
| 4 | Are the live OPEN/CONTAINED corpus counts trustworthy? | **NO, not as completeness measures.** They are exactly reproducible (58 / 81 / 45 / 0) but scoped to what the parser can see. "0 live OPEN" is true today by direct inspection; it is **not guard-enforced**. |
| 5 | Is immutable evidence binding valid? | **YES.** Six load-bearing bindings verify against preserved blobs with correct parents and sidecars; ACCEPT→REJECT now fails even in a zero-preserve-ref clean clone; tier 2 is all-or-nothing. |
| 6 | Is candidate `4d12b0e` eligible for the third finalizer? | **NO.** |

**Technical containment is not equated with sufficient certification controls.** R-07's containment
is real; the control that is supposed to *prove* the repository never claims otherwise cannot read
the repository's own canonical claims. Finalizing would certify the second on the strength of the
first.

---

## 7. WHY THIS BLOCKS — THE PRECISE CERTIFICATION FAILURE

The third finalizer would certify that no live authority document asserts R-07 OPEN. That
certification rests entirely on the parser. On this candidate:

* the **status authority** (`CURRENT.md:105`) can read *R-07 — OPEN, NOT CONTAINED* with the full
  guard set green;
* so can the **operating guide** (`CLAUDE.md:73`) and the **public landing document**
  (`README.md:63`);
* any live false claim can be hidden by wrapping it in an **unlabelled `<details>`** block, in
  documents that already use them, through a channel this repository has **already been attacked
  through once**;
* the mutation battery reports 21/21 CAUGHT while testing only forms inside the parser's own field
  of view.

A green suite would then mean "no live OPEN claim *in the subset the parser can read*", while being
presented as "no live OPEN claim". **That gap is the finding.**

---

## 8. TOPOLOGY AND THE NARROWEST LEGAL REMEDIATION

### 8.1 A second consecutive content commit is MECHANICALLY ILLEGAL

The current legal graph is `06ebfdb3 → 4d12b0e`, state **PRODUCING** (§1.1). Stacking a second
content commit `X` on `4d12b0e` gives `HEAD = X`, `HEAD^ = 4d12b0e`, `HEAD^^ = 06ebfdb3`, with the
record still at `42ea24c`. In `repo_state()`:

* `recorded == HEAD`? No. * `recorded == HEAD^`? No. * `recorded == HEAD^^`? No.

→ the final `raise AssertionError` fires: *"the status authority is stale beyond every legal state."*
And had the record advanced, the `PRODUCING` branch would fail on its own terms —
*"HEAD^ is not a pure status-metadata commit — this is not the producing state, it is two unfinalized
content commits, **which the convention forbids**."*

**The real status-reality guard does not permit it. A second consecutive content commit is not
authorized.**

### 8.2 The fix cannot ride in a metadata commit

`STATUS_METADATA_FILES` is exactly ten paths: `SUITE-RESULT.json`, `GATE-RESULT.json`, `CURRENT.md`,
`IMPLEMENTATION-REGISTRY.yaml`, `BUILD-STATUS.yaml`, and five `u-handoff/u-rebaseline` reviews.
**`eval/control/status_claims.py` is not among them**, and neither is
`scripts/mutate_roadmap_completeness.py` or `TEST-NODE-MANIFEST.json`. A parser correction is
necessarily **content**, so it can only exist in a content commit.

### 8.3 Decision between the offered paths

| Option | Ruling |
|---|---|
| **A. Replace `4d12b0e` in place against certified parent `06ebfdb3`** | **AUTHORIZED — the only legal path.** Preserves the one-content-commit-above-`06ebfdb3` invariant, keeps the graph `06ebfdb3 → 4d12b0e′` single-parent and PRODUCING, and is exactly the mechanism already used to replace `11c9112`. Precedent is established and repository-authorized. |
| **B. Preserve `4d12b0e` and create an evidence-only `refs/preserve` artifact** | **REQUIRED, BUT NOT SUFFICIENT.** `refs/preserve/*` is the correct mechanism for preserving the superseded candidate and this report — and must be used for both. It **cannot carry the remediation**: a fix living off-branch is not in the certified tree and enforces nothing. Necessary complement to A, never a substitute. |
| **C. Finalize `4d12b0e` and correct the parser later** | **REFUSED.** This certifies a status-control claim the instrument cannot support, and writes it into an immutable finalizer receipt. It is the precise failure mode — a green record over an instrument that cannot see the defect — that F-02, F-03 and RC-01 were all raised to close. Finalizing first and fixing after inverts the control system. |
| **D. Another repository-authorized mechanism** | **NONE EXISTS.** No metadata path can carry a parser fix (§8.2); no second content commit is legal (§8.1); no merge is permitted (single-parent invariant). |

**Ruling: OPTION A, with OPTION B as its mandatory preservation complement.**

`commit-tree` / `update-ref` are used in this adjudication **only** for the authorized
`refs/preserve/*` evidence mechanism, whose parent is exactly the candidate — never to construct
branch topology and never as a permission bypass.

### 8.4 Replacement authorization

Authorized, with these terms binding:

* **Rejected candidate:** `4d12b0e41cfa722fa74338903526c4bbc52cf65a` — rejected, superseded, **not
  deleted**.
* **Certified parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f`, unchanged. The replacement is
  **exactly one single-parent, non-merge content commit** above it. State must remain PRODUCING.
* **Required preservation refs (before the branch moves):**
  * `refs/preserve/p4-r07-closure-rejected-replacement-candidate-4d12b0e` → `4d12b0e`
  * `refs/heads/archive/p4/r07-rejected-replacement-4d12b0e` → `4d12b0e`
  * the complete worktree of `4d12b0e`, matching the treatment `11c9112` received
* **Review preservation:** `refs/preserve/p4-r07-closure-replacement-targeted-review-4d12b0e`
  (`62df39dd…`, parent `4d12b0e`) and this adjudication's ref remain **unmoved and parented to
  `4d12b0e`**. Both `11c9112` refs and both `11c9112` reports likewise remain unmoved.
* **Allowed changed surfaces:** §9 only.
* **Must retain:** every valid F-01 correction; every valid F-03 immutable evidence binding; R-07
  technical containment; `src/`+`configs/`+`data/` tree-identity to `0891d1a`.
* **Must produce:** a completely fresh targeted independent review by a session that authored neither
  candidate and conducted neither prior review nor adjudication; then a **separate** targeted
  adjudication.
* **Attribution:** every report remains attributable **only** to the candidate it actually reviewed.
  No report of `11c9112` or `4d12b0e` may be reinterpreted as reviewing the successor.

---

## 9. PERMITTED REMEDIATION SCOPE

The permitted scope is **limited to** the following. It is narrower than a re-implementation and
must not widen.

1. **Row-aware status parser correction** — `claim_units()` associates subject and status **within a
   single table row and no wider**; retain document, line, row identity, cell identity, subject cell
   and status cell; handle header/separator rows, escaped pipes, inline code, descriptive columns,
   and prose containing a literal pipe.
2. **Details-block historical/live classification correction** — parse by default; exclude only on a
   machine-readable marker **attached to the block** (its `<summary>` or first body line) from the
   closed vocabulary; handle nesting by depth; fail closed on malformed/unterminated blocks; retain
   excluded claims as *exempt and visible*, never deleted.
3. **R-03 marker scoping and R-04 per-row quote parity** — same module, same pass, per §5.
4. **Focused and hostile parser tests** — including the exact `CURRENT.md:105`, `CLAUDE.md:73` and
   `README.md:63` rows **verbatim**, and all six `<details>` cases from §4.3(10).
5. **Cross-cell mutation operators** — at least one per authorized column arrangement (2-cell,
   3-cell, interleaved `| Risk | R-07 | Status | OPEN |`), each asserted CAUGHT.
6. **`TEST-NODE-MANIFEST` regeneration** — from a real canonical run, with exact set equality
   re-established.
7. **Mechanically required guard-registry update** — only if `test_every_guard_file_is_classified`
   forces it, and only a classification entry plus its reason.
8. **Recomputed corpus and mutation counts** — every figure re-derived from the fixed parser; no
   count carried forward from the superseded instrument.
9. **Candidate handoff and residual recording**, including **RC-01 recurrence**: a battery drawn from
   the instrument's own field of view measures that field of view.
10. **Commit-message correction** — the replacement's message must state the true canonical figures
    (**2017 passed / 0 failed / 1 skipped / 2018 collected**) and record that `4d12b0e`'s
    2014/0/3/2017 line was inaccurate and is superseded.

**Explicitly out of scope:** any change to `src/`, `configs/` or `data/`; any change to the
containment mechanism; any re-litigation of F-01 or F-03; any widening of association beyond a single
table row; any new skip; any deletion of a preservation ref.

**Must be retained, unchanged:** all valid F-01 corrections · all valid F-03 immutable evidence
binding · R-07 technical containment · runtime byte equality to `0891d1a` · P4 COMPLETE · P5 sole
READY and NOT_STARTED · R-07 CONTAINED · production gates empty · Phase-8 deferral.

**No P5 implementation may begin.**

---

## 10. FINALIZER AUTHORIZATION

### THE THIRD FINALIZER IS **NOT AUTHORIZED** ON `4d12b0e`

Not authorized merely because containment and evidence binding are valid — they are, and that is
not the question the finalizer answers.

| Required statement | Determination |
|---|---|
| Exact candidate | `4d12b0e41cfa722fa74338903526c4bbc52cf65a` |
| Exact tree | `35f6755c5ce90dc64c96bb5f4be4236a170fff83` |
| **Parser coverage status** | **INSUFFICIENT** — cross-cell table rows unreadable; ≥3 canonical live R-07 rows outside the field of view (R-01) |
| **Details-block status** | **UNSAFE** — all `<details>` content stripped unlabelled, contrary to the docstring and to a documented, incident-derived requirement (R-02) |
| **Corpus count trustworthiness** | **NOT TRUSTWORTHY as a completeness measure** — 58 / 81 / 45 / 0 exactly reproducible but parser-scoped; "0 live OPEN" true today by inspection, not guard-enforced |
| **Evidence-binding status** | **VALID** — F-03 closed; six bindings verified; ACCEPT→REJECT fails in a zero-preserve-ref clean clone |
| **Canonical suite / manifest status** | **VALID** — 2017 / 0 / 1 / 2018, exact set equality at `node_count: 2018`, clean-clone gate PASS; the candidate's **commit message misstates this** (R-05) |
| R-07 / P4 / P5 states | R-07 **CONTAINED**; P4 **COMPLETE** 100%; P5 **sole READY, NOT_STARTED**; P6–P14 **BLOCKED** (9); no P5 work begun |
| **Residuals** | **R-01 BLOCKING** · **R-02 BLOCKING** · R-03 non-blocking, in scope · R-04 non-blocking, in scope · R-05 non-blocking, mandatory in replacement · RC-01 recurrence recorded · F-06, RR-01, AD-01, AD-02, RC-02, RC-03 carried, not discharged |
| **Finalizer prerequisites** | R-01 and R-02 remediated on a replacement candidate parented to `06ebfdb3`; R-03/R-04/R-05 addressed per §9; all counts recomputed; cross-cell and details mutation operators CAUGHT; manifest regenerated at exact set equality; **a completely fresh targeted independent review**; **a separate targeted adjudication**; both returning acceptance. Only then may **exactly one** third finalizer run. |

`scripts/finalize_status.py` **must not run** on `4d12b0e`.

---

## 11. VERDICT

### REJECT — TARGETED REMEDIATION REQUIRED

**Narrowest legal remediation delta:** §9, items 1–10 — a row-aware parser bounded to a single table
row, label-gated `<details>` handling that parses by default, the two same-module scoping fixes,
hostile tests carrying the three escaped canonical rows verbatim, cross-cell mutation operators,
recomputed counts, a regenerated manifest, and a corrected commit message.

**Topology:** `06ebfdb3 → 4d12b0e′`. Replace `4d12b0e` **in place** against certified parent
`06ebfdb3` (§8.3, Option A) — exactly one single-parent, non-merge content commit above `06ebfdb3`,
state PRODUCING. Preserve `4d12b0e` first, the way `11c9112` was preserved (Option B as complement).
**A second consecutive content commit is mechanically forbidden by `repo_state()` and is not
authorized.**

---

## 12. WHAT THIS ADJUDICATION DID NOT DO

Did not remediate any finding · did not modify the candidate · did not amend, commit to the product
branch, reset, restore, rebase, merge, checkout, stash, clean, update a branch ref or push · did not
run `finalize_status.py` · did not begin P5 · did not deploy or enable any effect · did not move
`main`, `origin/main` or any protected ref · did not delete, move or reinterpret any preservation ref
· did not alter the review or adjudication of `11c9112`, which remain attributable only to `11c9112`
· did not resume any previous session · measured all implementation behaviour in a disposable
`--no-local` clone, never in the primary worktree.

**This report adjudicates. It remediates nothing and finalizes nothing.**
