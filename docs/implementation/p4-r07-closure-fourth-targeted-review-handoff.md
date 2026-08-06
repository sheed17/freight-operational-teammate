> # ⛔ HANDOFF — NOT CURRENT AUTHORITY, AND NOT A REVIEW
> **This is a builder's handoff to a fresh targeted independent reviewer.** It certifies nothing,
> adjudicates nothing, sets no acceptance criterion, closes no risk and authorizes no finalization.
> The status authority is [`CURRENT.md`](CURRENT.md) and the registry; the operating guide is
> [`../../CLAUDE.md`](../../CLAUDE.md).
>
> ### **DO NOT TREAT ANY CLAIM BELOW AS EVIDENCE.** Re-derive every one from the object store and
> from execution. The P4 remediation handoff was wrong about two numbers (RR-02); the handoff for
> `42ea24c` named a guard function that does not exist (F-TR-05); `4d12b0e`'s commit message
> misstated its suite population (R-05); and the handoff for `3874d4a` gave a factually wrong
> reason for a green probe (S-06, corrected in §9 below). Four handoffs in this family, four
> inaccuracies. A reviewer who trusted any of them would have reported a false result. That is
> exactly why a handoff is never review evidence — **including this one.**

# P4 R-07 CLOSURE — FOURTH CANDIDATE, TARGETED REVIEW HANDOFF

**Certified parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (second-finalizer metadata commit)
**Branch:** `p4/adapter-containment-completion`
**Replaces rejected successor candidate:** `3874d4a1bd02cdf81525aba52268e7aa44343457`
**Which replaced rejected replacement candidate:** `4d12b0e41cfa722fa74338903526c4bbc52cf65a`
**Which replaced rejected candidate:** `11c911244304d56737913db41b458d5f3278bc80`

**Builder standing.** This session did not implement P4, did not author `11c9112`, `4d12b0e` or
`3874d4a`, conducted none of their reviews or adjudications, and ran neither finalizer. No previous
session was resumed. It conducted no review and no adjudication of its own work, ran no finalizer,
began no P5, pushed nothing, moved no shared or protected ref, and enabled no effect.

---

## 1. WHY THIS CANDIDATE EXISTS

`3874d4a` was rejected by a separate targeted adjudication
(`refs/preserve/p4-r07-closure-successor-targeted-adjudication-3874d4a`, verdict **REJECT —
TARGETED REMEDIATION REQUIRED**) on three blocking findings. The adjudication is the controlling
authority for all three and this candidate implements exactly its §5.3 delta — nothing wider.

| | Defect on `3874d4a` |
|---|---|
| **S-01** | `status_claims.py:704` searched `unit.norm[:token_end]` — the **whole row-joined string** — so a conditional word in ANY preceding cell exempted a separate canonical status cell |
| **S-02** | `status_claims.py:701` searched the row **prefix**, so a historical marker in any unrelated preceding cell exempted a live R-07 claim |
| **S-03** | `_prose_blocks` broke only on blank lines and table lines, never on structural `<details>` tags, so prose above a block laundered claims inside it — and this **voided the module's advertised malformed-block fail-closed and nested-block no-inheritance guarantees** |

**The shared root cause, in one sentence.** R-01 correctly widened the CLAIM UNIT from one cell to
one row so subject and status could associate; the three exemption rules were left keyed to that
widened unit, so the EXEMPTION WINDOW widened with it. Association and exemption were conflated.

**S-01 fires accidentally, not only adversarially.** `_CONDITIONAL` contains `when`, `while`,
`before`, `after`, `once`, `should`, `would`, `could` — ordinary English words in evidence,
description and notes columns. `| R-07 | recorded when the gate ran | OPEN |` launders itself with
no adversary present. Reviewer and adjudicator both recorded this; it is why the defect is a latent
silent-failure mode of the control rather than only an evasion vector.

---

## 2. THE DELTA — FOUR FILES

| Path | Change |
|---|---|
| `eval/control/status_claims.py` | the three bounded window/boundary corrections, plus docstring |
| `eval/tests/test_roadmap_completeness_control.py` | S-01 / S-02 / S-03 hostile coverage and their must-stay-exempt negatives; one corrected pre-existing assertion (§4) |
| `scripts/mutate_roadmap_completeness.py` | M34 retargeted; M41–M58 added |
| `docs/implementation/TEST-NODE-MANIFEST.json` | regenerated through `scripts/regenerate_test_manifest.py`, +29 nodes, 0 removed |

Plus this handoff and its `.sha256` sidecar. **Six changed paths versus `3874d4a`.**

**No path under `src/`, `configs/` or `data/` is touched.** No change to the containment mechanism,
to the R-07 CONTAINED record, to `_HISTORICAL_MARKER`'s vocabulary, to `_SENTENCE_SPLIT`, or to
anything belonging to F-01, F-03, R-03, R-04 or R-05.

**Deliberately NOT done, though the adjudication called them "recommended":** the S-04 header guard
and the S-05 anti-drift guard. Both remain open residuals. The authorization for this replacement
restricts the delta to the adjudicated S-01/S-02/S-03 corrections, their hostile coverage,
mechanically required manifest updates and this handoff; neither guard is any of those. They are
recorded in §12 for whoever holds the next authorization.

---

## 3. S-01 AND S-02 — EXEMPTION IS CLAIM-LOCAL, ASSOCIATION STAYS ROW-WIDE

One new function carries both corrections:

```python
def _governing_window_start(unit: ClaimUnit, norm_pos: int) -> int:
    if unit.kind != "table-row" or not unit.cell_spans:
        return 0                      # prose: the whole unit, exactly as before
    idx = _cell_at(unit, norm_pos)
    if idx is None:
        return norm_pos               # unresolvable -> admit no preceding text (fail closed)
    return unit.cell_spans[idx][0]    # a row: the claim's OWN cell
```

* **S-01** — the conditional window is now `[start of the STATUS TOKEN's own cell, token_end)`.
* **S-02** — the marker window is now `[start of the SUBJECT's own cell, start of the risk id)`.

Both retain the ordering half of the rule (R-03): a qualifier trailing AFTER the token it would
qualify still exempts nothing. `ClaimUnit.cell_spans` and `_cell_at` already existed; the mechanism
was present and simply was not used at `:701`/`:704`.

**Association is untouched.** `test_row_association_still_spans_cells_after_the_exemption_windows_were_narrowed`
is the explicit regression bound, and the three canonical cross-cell anchors
(`CURRENT.md`, `CLAUDE.md`, `README.md`) still parse cross-cell and still read CONTAINED.

### Hostile-test map — S-01

`eval/tests/test_roadmap_completeness_control.py::test_a_conditional_word_exempts_only_the_claim_in_its_own_cell`

| Case | Required | Misses on `3874d4a`? |
|---|---|---|
| `if` in an unrelated LEADING cell (adjudication's exact case) | LIVE | **yes** |
| `when` in an EVIDENCE cell (the accidental form) | LIVE | **yes** |
| `before` between subject and status | LIVE | **yes** |
| `after` in a NOTES cell following the status | LIVE | no — already correct by ordering |
| `while` in a DESCRIPTION cell | LIVE | **yes** |
| conditional word in a cell PRECEDING the subject (review's exact case) | LIVE | **yes** |
| trailing `unless` (R-03 negative) | LIVE | no — already correct |
| in-cell conditional governing its own token | **EXEMPT** | must stay exempt |
| conditional introducing the claim inside the status cell, cross-cell association | **EXEMPT** | must stay exempt |

### Hostile-test map — S-02

`…::test_a_historical_marker_exempts_only_the_claim_in_its_own_cell` and
`…::test_a_marker_in_a_header_or_a_neighbouring_row_reaches_neither`

| Case | Required | Misses on `3874d4a`? |
|---|---|---|
| marker in an unrelated LEADING cell (adjudication's exact case) | LIVE | **yes** |
| `nothing here is superseded` in row form (R-03's own authority sentence) | LIVE | **yes** |
| bare `⛔ HISTORICAL` cell preceding the subject | LIVE | **yes** |
| marker BETWEEN subject and status | LIVE | no — already correct |
| marker AFTER the status in a notes cell | LIVE | no — already correct |
| marker in a column HEADING | LIVE | no — headers are never claims |
| marker in the PRECEDING row / the FOLLOWING row | LIVE | no — no cross-row association |
| marker in the SUBJECT's own cell before the risk id | **EXEMPT** | must stay exempt |

**One pre-existing assertion was CORRECTED, not added.**
`test_the_historical_marker_must_govern_the_claim_it_exempts` asserted that
`| ⛔ HISTORICAL | R-07 | OPEN — NOT CONTAINED |` **must** be exempt — the S-02 defect written down
as an expectation, which is a large part of why it survived a full independent review. It now
asserts the corrected semantics, and the in-cell form the live corpus actually uses
(`PHASE-OUTPUTS.md:109`, `pr-sequence.md:33`) is asserted alongside it so the narrowing is bounded
on both sides. **No row-level marker construct was invented** — adjudication §3.3(2) forbids it.

---

## 4. S-03 — A STRUCTURAL TAG IS A UNIT BOUNDARY

`_prose_blocks` now breaks a prose run at every structural `<details>`, `</details>`, `<summary>`
and `</summary>` tag, alongside the blank line and the table line it already broke on. Tags inside
code are literal mentions and are not boundaries, by the same `_code_mask` rule `details_blocks()`
uses.

**The boundary is the TAG, not the line carrying it.** Breaking on the whole line would have
silently deleted a claim written inside a `<summary>` — rendered, readable text — trading one blind
spot for another. `test_a_claim_written_inside_a_summary_is_still_read` is that bound.

**One boundary beyond the adjudication's literal wording, and why it is required.** An unterminated
`<summary>` has no closing tag, so the tag boundaries alone do not bound it, and its text ran on
into the block body where the marker rule granted `marked-historical` from a label `_build_block`
had already declared void. `_structural_tag_spans` therefore installs an end-of-line boundary after
an unterminated `<summary>`. Without it the malformed-summary case still escaped in the
no-blank-line arrangement — verified, not assumed. This is inside the same surface and the same
finding; it is not a widening.

### Hostile-test map — S-03

| Test | Arrangements | Misses on `3874d4a`? |
|---|---|---|
| `test_a_marker_outside_a_details_block_never_classifies_it` | no blank line / blank line, historical **and** conditional twin | **yes** (no-blank-line only) |
| `test_an_unterminated_details_block_fails_closed_in_both_arrangements` | no blank line / blank line | **yes** (no-blank-line only) |
| `test_a_nested_unlabelled_block_never_inherits_in_either_arrangement` | no blank line / blank line, plus the labelled-in-live inverse | **yes** (no-blank-line only) |
| `test_a_malformed_summary_fails_closed_in_both_arrangements` | no blank line / blank line | **yes** (no-blank-line only) |
| `test_a_correctly_attached_marker_still_exempts_without_any_blank_lines` | must stay exempt | negative bound |
| `test_a_claim_written_inside_a_summary_is_still_read` | closed and unclosed summary | new-blind-spot bound |
| `test_a_details_tag_inside_code_is_not_a_unit_boundary` | inline code and fenced code | new-blind-spot bound |

**Classification is now identical with and without blank lines.** That the two diverged was the
defect signature, and it is why M34 was green while the arrangement it is named for escaped.

---

## 5. MUTATION BATTERY — 58 CASES, AND WHAT EACH ONE PROVES

`.venv/bin/python scripts/mutate_roadmap_completeness.py` →
**58/58 correct (52 must-be-CAUGHT, 6 must-stay-GREEN), 0 defective, 0 SKIP-INVALID.**

**M34 RETARGETED.** Its fixture wrote the external marker with a **blank line** before `<details>`
— an arrangement that already broke the prose run — so it certified "proximity is not attachment"
on a tree where the adjacent arrangement escaped completely. It now attacks the no-blank-line form.
The blank-line form is kept as **M41**, so nothing is lost and both arrangements are measured.

New operators: **M41–M58**.

| Family | Operators |
|---|---|
| S-03 | M34 (retargeted), M41 blank-line twin, M42 unterminated no-blank-line, M43 nested-unlabelled no-blank-line, M44 labelled-nested-in-live (**GREEN**), M45 malformed summary, M46 conditional twin |
| S-01 | M47 `if` leading cell, M48 `when` evidence cell, M49 `before` between, M50 `after` trailing, M51 `while` description cell, M52 in-cell conditional (**GREEN**) |
| S-02 | M53 marker leading cell, M54 `SUPERSEDED` row form, M55 marker in header, M56 marker in neighbouring row, M57 marker after status, M58 attached marker (**GREEN**) |

**ANTI-VACUITY, MEASURED.** The new battery was run against the **rejected candidate's own parser
and tests** (`3874d4a` tree, new `mutate_roadmap_completeness.py` only). Result:
**47/58 correct, 11 defective — 11 MISSES.**

| On `3874d4a` | Operators |
|---|---|
| **MISS** — attack a real defect | M34, M42, M43, M45, M46, M47, M48, M49, M51, M53, M54 (11) |
| already CAUGHT — regression bounds | M41, M50, M55, M56, M57 (5) |
| stayed GREEN, as required | M44, M52, M58 (3) |

M42, M43 and M45 are the three the adjudication specifically demanded: the fail-closed guarantees
were void in exactly the arrangement no operator covered, and restoring them without a mutation
that would have caught them would have repeated the M34 failure mode one operator over.

Each case targets a real non-empty anchor (the battery reports a missing anchor as a battery defect,
never a skip), proves its target bytes changed, requires an `AssertionError` rather than any
exception, and restores byte-exactly — verified clean after the run.

**P4 boundary battery: 61/61 mutants caught**, byte-exact restoration, unchanged.

---

## 6. THE LIVE CORPUS CLASSIFIES IDENTICALLY — THE PROOF THE DELTA IS CORRECTLY SHAPED

Every claim in the live corpus was classified under both parsers and compared **per claim**, not by
totals:

| Population | Documents | Claims | live CONTAINED | **live OPEN** | quoted | hypothetical | marked-historical |
|---|---|---|---|---|---|---|---|
| discovered | 57 | 82 | 47 | **0** | 20 | 8 | 7 |
| union (+ `README.md`) | 58 | 84 | 49 | **0** | 20 | 8 | 7 |

**Per-claim classification is byte-identical to `3874d4a`. Zero claims change.** The narrowed
windows remove only capability the corpus never uses: every row-level exemption in the corpus
already has its marker or conditional in the claim's own cell, and every historical `<details>`
block is already self-labelling. `test_the_live_corpus_classifies_identically_under_the_narrowed_windows`
asserts that property mechanically, so a future edit that starts relying on a cross-cell exemption
surfaces there instead of silently.

These counts were **recomputed on this tree**, not carried forward. They match the adjudication's
independently derived figures (57 / 82 / 47 / 0 discovered) and reconcile with the successor
review's union figures exactly as the adjudication's §7 reconciliation describes.

---

## 7. WHAT WAS RETAINED, UNCHANGED

| Area | Evidence |
|---|---|
| F-01 stale-claim cleanup | zero live OPEN across the union population; no corrected claim's wording touched; no historical report rewritten |
| F-03 immutable evidence binding | `eval/tests/test_evidence_binding.py` **byte-unchanged**; 26 passed baseline in a clone carrying zero `refs/preserve/*` |
| banner-aware authenticated-body verification | unchanged; re-exercised in §9 |
| two-tier clean-clone / ref-backed checks | unchanged |
| R-01 row-aware association | unchanged, and explicitly regression-bounded |
| R-02 details classification | `details_blocks()` / `_build_block()` **byte-unchanged** — the fix stops the prose layer defeating them, it does not touch them |
| R-03 marker governance | ordering half unchanged; scope half corrected (§3) |
| R-04 row-bounded quote parity | unchanged |
| R-05 accurate commit testimony | this candidate's message embeds no volatile counts at all |
| the five delegating guard modules | unchanged |

---

## 8. RUNTIME, PHASE STATE AND CONTAINMENT — RETAINED

| Property | Observed |
|---|---|
| `src/` vs `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e` | `0204261b17ba…` — **IDENTICAL** |
| `configs/` vs `0891d1a` | `124ae4bcbbec…` — **IDENTICAL** |
| `data/` vs `0891d1a` | `8d0210227727…` — **IDENTICAL** |
| `scripts/` vs `0891d1a` | one file: `M scripts/mutate_roadmap_completeness.py` |
| `status_claims` imported from `src/`, `scripts/`, `configs/`, `data/` | **zero** occurrences |
| `mutate_roadmap_completeness` imported anywhere | **zero** (one docstring mention in a test) |
| `status_claims` own imports | `re`, `dataclasses`, `functools`, and lazily `control.inventory` |
| R-07 canonical status | `CONTAINED` |
| recorded / live violation edges | `[]` / `0` — equal, both-sided |
| detection edges | `13` |
| production `GateRegistry` | **EMPTY** — 0 constructions, 0 `register_gate` calls in `src/` |
| Phase-8 Action Class registration | deferred, intact |
| `CdpActuator` construction, `cdp_actuator` import, `_build_live_operation_router` | none in `src/`; every hit is a mutant string literal inside `scripts/mutate_phase4_boundary.py` |
| production default | `ROUTE_NOT_CONFIGURED` (`action_callback.py:662`) |
| P4 | `COMPLETE` / `COMPLETE` |
| P5 | `READY` + `NOT_STARTED`, **sole** READY unit |
| P6–P14 | all `BLOCKED` / `NOT_STARTED` |
| P5 implementation | none begun |
| `SUITE-RESULT.json` / `GATE-RESULT.json` | **byte-identical blobs to `06ebfdb3`** — no receipt forged, no finalizer ran |

**Containment remains containment, not enablement.** No production write is enabled and no bounded
autonomy is claimed.

**Secret and object hygiene.** No `.env`, credential, token, virtualenv, cache, `__pycache__`,
`.pytest_cache` or scratchpad path enters this candidate or any preservation object. A
credential-pattern sweep over every changed path returns nothing. The preservation tree of
`3874d4a` explicitly excludes all of them and its commit message enumerates the exclusion.

---

## 9. S-06 — THE `3874d4a` HANDOFF'S EXPLANATION OF ITS GREEN F-03 PROBE WAS WRONG

The rejected handoff's §7 disclosed a probe that replaced only the phrase
`ACCEPT FOR SEPARATE FINAL ADJUDICATION` and left the suite green, and explained it as:

> *"That was a defect in my probe, not in the control: **that phrase is not the verdict line the
> record binds.**"*

**The first clause is right and the reason is wrong.** I reproduced the probe rather than inheriting
either account. Mutating that exact phrase to `REJECT FOR SEPARATE FINAL ADJUDICATION`, restoring
byte-exactly between cases, in a clone carrying **zero** `refs/preserve/*` (tier 1 only, baseline
**26 passed**):

| Target | Occurrences | Result |
|---|---|---|
| `p4-independent-rereview-report-0891d1a.md` — load-bearing, bannered | 3 | **15 failed** |
| `p4-final-adjudication-report-0891d1a.md` — load-bearing, unbannered | 2 | **1 failed** |
| `CLAUDE.md` — not an authenticated evidence source | 1 | **26 passed (green)** |

**The correct explanation, for the record:**

1. The phrase **is** load-bearing and **is** bound — in **both** load-bearing reports, not one.
2. Changing it **does** fail the evidence guard, in both.
3. The green result is explicable only as an **invalid probe** that wrote to a non-authenticated
   file. The phrase also occurs in `CLAUDE.md`, `BUILD-STATUS.yaml`, `CURRENT.md`,
   `phase-0-baseline-manifest.yaml` and the handoff itself; mutating any of those is green because
   none is authenticated evidence, which the third row demonstrates directly.
4. It was **not** an evidence-binding gap, and it was **not** "a phrase the record does not bind".

**F-03 is not reopened and is not weakened.** No line of `test_evidence_binding.py` was modified.
This is an evidence-record correction: a handoff that misexplains why a probe was green teaches the
next reader a false model of the control, and the next reader might act on it.

---

## 10. EXECUTION RESULTS ON THIS TREE

| Check | Result |
|---|---|
| Canonical suite (`scripts/run_canonical_suite.py`) | **2072 passed · 0 failed · 1 skipped · 2073 collected**, exit 0 |
| `TEST-NODE-MANIFEST.json` | **2073 nodes**, exact node-identity equality enforced by the runner; regenerated via `scripts/regenerate_test_manifest.py` (+29, −0) |
| Clean-clone gate | **`CLEAN-CLONE GATE: PASS`**, exit 0 — fresh clone, fresh venv, declared deps only, independently reproducing **2072 / 0 / 1 / 2073** |
| Roadmap/status mutation battery | **58/58 correct** (52 CAUGHT, 6 GREEN), 0 defective, **0 SKIP-INVALID** |
| Anti-vacuity of the new operators | **11 MISS** on `3874d4a` — they attack a real defect |
| P4 boundary mutation battery | **61/61 caught**, byte-exact restoration |
| Approved skips | exactly one |
| Working tree after every battery | clean, byte-exact |

The single skip is the approved canonical skip. Per carried residual **S-07**, a clone whose `.venv`
is **symlinked** rather than copied is reported dirty and yields two additional NOT-RUN skips with
the same collected count and zero failures; the canonical configuration is a copied or freshly built
venv, which is what the figures above use.

---

## 11. TOPOLOGY, PRESERVATION AND ATTRIBUTION

This candidate has **exactly one parent, `06ebfdb3`**. It is not a merge, and it is **not** a
descendant of `11c9112`, `4d12b0e` or `3874d4a`. The repository shape is
`recorded content commit == HEAD^^` ∧ `HEAD^` pure status metadata ⇒ **PRODUCING**, preserved
exactly. A second content commit on top of `3874d4a` would have been **ILLEGAL** under
`repo_state.py`; replacement in place was the only legal topology, and it is the one the repository
has now used three times for this slot.

`3874d4a` is permanently preserved before this candidate was created:

| Artifact | Ref | Parent |
|---|---|---|
| rejected candidate | `refs/preserve/p4-r07-closure-rejected-successor-candidate-3874d4a` | `06ebfdb3` |
| archive branch | `refs/heads/archive/p4/r07-rejected-successor-3874d4a` | `06ebfdb3` |
| complete worktree (647 paths) | `refs/preserve/p4-r07-rejected-successor-worktree-3874d4a` | **`3874d4a`** |
| targeted review | `refs/preserve/p4-r07-closure-successor-targeted-review-3874d4a` | **`3874d4a`** |
| targeted adjudication | `refs/preserve/p4-r07-closure-successor-targeted-adjudication-3874d4a` | **`3874d4a`** |

The `11c9112` and `4d12b0e` families are untouched, at their own refs, parented to the candidate
each actually examined. **No review or adjudication in this family may be read as reviewing this
candidate.** Every one of them names and is parented to a different commit; this candidate owes its
own fresh independent review and its own separate targeted adjudication, by two further distinct
sessions.

`main` and `origin/main` are unchanged at `152574e4f4f2969468c9d31b1e705188896175b5`. Nothing was
pushed; no remote P4 branch exists.

---

## 12. RESIDUAL RISKS CARRIED FORWARD

**Open and NOT discharged here** — each was recorded by the review or the adjudication of `3874d4a`
and is out of this replacement's authorized scope:

* **S-04** — a table **header** row renders as visible text but is never parsed as a claim. This is
  specified behaviour and the parser is compliant; zero header rows in the live corpus mention the
  risk id. It remains a structurally sanctioned place to write a status no guard reads. A one-line
  guard was recommended by the adjudication and is **not** included.
* **S-05** — no anti-drift guard prevents a seventh copy of the raw
  `re.sub(r"<details>.*?</details>", …)` being written. All six copies are delegated. S-03 was a
  live instance of the same recurrence class (RC-01), which raises rather than lowers this risk. A
  guard was recommended by the adjudication and is **not** included.
* **S-07** — symlinked-venv clones report dirty and add two NOT-RUN skips. Environment, not defect.
* **RR-01** — the historical vocabulary is the closed pair `HISTORICAL` / `SUPERSEDED`; `ARCHIVED`
  and `REJECTED EVIDENCE` are read as live. Deliberately **not** widened.
* **RR-02** fenced content is read · **RR-03** `README.md` is reached only through the union ·
  **RR-04** marker-precedes-claim is an authoring constraint, and this candidate **tightens** it to
  marker-in-the-claim's-own-cell, which is a new authoring constraint on table rows · **RC-01**
  recurrence · **F-06, AD-01, AD-02, RC-02, RC-03** carried from prior adjudications, not reopened.

**New residual introduced by this candidate, stated against my own interest:** narrowing the marker
window to the claim's own cell means an author who writes a genuinely historical row must now put
the marker **inside the subject's cell**, not in a separate "Notes" column. Two live rows already do
this; any future one must. The failure direction is fail-closed — a mis-placed marker produces a
loud guard failure, never a silent exemption — but it is a real change to how a historical row must
be written, and it is not covered by RR-04 as previously worded.

---

## 13. WHAT A FRESH TARGETED REVIEWER SHOULD DO

Assume nothing below. Re-derive it.

1. **Identity and topology** — confirm the branch, HEAD, tree and that the parent is exactly
   `06ebfdb3`; confirm single-parent, not a merge, not a descendant of `11c9112` / `4d12b0e` /
   `3874d4a`; confirm PRODUCING against `repo_state.py`; confirm `main` = `origin/main` and that
   nothing is pushed.
2. **Attack S-01, S-02 and S-03 directly** on the corrected parser, in a disposable `--no-local`
   clone. Do not reuse my cases. In particular try: conditional and historical words in every column
   position; markers in headers, neighbouring rows and adjacent tables; every `<details>` /
   `<summary>` arrangement with and without blank lines; and unterminated, stray and nested forms.
3. **Attack the new boundary for over-correction**, which is this delta's own risk: prove that
   legitimate in-cell markers, legitimate in-cell conditionals, correctly attached `<summary>`
   labels and first-body-line labels all still exempt, and that no live claim disappeared —
   especially inside `<summary>` elements.
4. **Re-derive the corpus counts** with your own instrument on both populations, and compare
   **per claim** against `3874d4a`, not by totals. A total can match while claims swap.
5. **Re-run both mutation batteries**, and re-run the new operators against the `3874d4a` tree
   yourself to confirm the 11 misses. A battery that cannot fail is a fixture.
6. **Re-run the canonical suite and the clean-clone gate** from your own clone with a fresh venv.
   Run the gate ONLY in a disposable clone — it writes `GATE-RESULT.json`.
7. **Verify F-01, F-03, R-03, R-04, R-05 and technical containment are retained**, including that
   `SUITE-RESULT.json` and `GATE-RESULT.json` are still byte-identical to `06ebfdb3` and that no
   finalizer receipt was forged.
8. **Verify runtime byte-equality** to `0891d1a` over `src/`, `configs/` and `data/`, and that
   neither the parser nor the mutation script is reachable from a freight runtime path.
9. **Verify the preservation family** — all three `3874d4a` refs plus both predecessor families,
   with their parents, and that no report has been moved, rewritten or reparented.

**Prerequisites for a later third finalizer — ALL must hold, in order:**

1. `3874d4a` preserved and archived — **done, verified in a disposable `--no-local` clone**.
2. Exactly one replacement content commit on `06ebfdb3` — **done**.
3. A **completely fresh independent targeted review** of this candidate, by a session that did not
   implement P4, did not author `11c9112`, `4d12b0e`, `3874d4a` or this candidate, and conducted no
   prior review or adjudication in this family — **OUTSTANDING**.
4. A **separate targeted adjudication** of this candidate, by a further distinct session —
   **OUTSTANDING**.

**No third finalizer may run before 3 and 4 succeed.** No finalizer has run for this candidate; none
may be fabricated. P5 has not begun.

---

## 14. WHAT THIS SESSION DID NOT DO

Did not review this candidate · did not adjudicate it · did not run `scripts/finalize_status.py` ·
did not begin P5 · did not deploy or enable any effect · did not alter P4 freight runtime behaviour
· did not weaken R-07 technical containment · did not create a second consecutive content commit ·
did not push · did not move `main`, `origin/main` or any shared or protected ref · did not modify,
move or reinterpret any preservation ref · did not alter the review or adjudication of `11c9112`,
`4d12b0e` or `3874d4a` · did not resume any previous session.

All implementation behaviour was measured in disposable clones. The primary worktree and index were
byte-exactly preserved before any mutation and were never written to during validation.
