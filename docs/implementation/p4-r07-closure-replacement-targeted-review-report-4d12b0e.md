# P4 R-07 CLOSURE — REPLACEMENT CANDIDATE FRESH TARGETED INDEPENDENT REVIEW

**Replacement candidate:** `4d12b0e41cfa722fa74338903526c4bbc52cf65a`
**Tree:** `35f6755c5ce90dc64c96bb5f4be4236a170fff83`
**Parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (second-finalizer metadata commit)
**Branch:** `p4/adapter-containment-completion`
**Replaces rejected candidate:** `11c911244304d56737913db41b458d5f3278bc80`

**Reviewer standing.** This session did not implement P4, did not author rejected candidate
`11c9112`, did not author replacement candidate `4d12b0e`, did not conduct the prior targeted
review or the prior targeted adjudication, did not run either finalizer, and did not reconstruct
the second-finalization report. No previous session was resumed. It performed no remediation, no
adjudication, ran no finalizer, began no P5 work, pushed nothing and enabled nothing. Every
implementation behaviour below was measured in disposable `--no-local` clones, never in the
primary worktree.

---

## VERDICT

### REJECT — TARGETED REMEDIATION REQUIRED

R-07's **technical containment is real, unchanged and independently re-confirmed** (§6). F-01 and
F-03 are **fully and correctly remediated** (§3, §5) — the ten corrections are genuine, the six
evidence bindings verify against immutable preserved blobs, and the ACCEPT→REJECT attack that
previously left 1957 tests green now fails in every environment, including a clean clone carrying
no preservation refs.

**F-02 is not remediated.** The replacement parser removed the word-order dependency but replaced
it with a *cell*-boundary dependency, and the repository's own canonical R-07 status rows —
in `CLAUDE.md` and in `docs/implementation/CURRENT.md`, the operating guide and the designated
status authority — write the risk id in one table cell and its status in another. Both live rows
are invisible to the new guard. The full canonical suite stays green, byte-for-byte identical to
baseline, with `CURRENT.md`'s canonical R-07 row reading **`OPEN, NOT CONTAINED`** (§4, R-01).

This is the same defect class F-02 named — a guard structurally blind to the grammar this
repository actually writes canonical status in — displaced by one column rather than closed.

---

## 1. CANDIDATE IDENTITY AND TOPOLOGY — VERIFIED

| Check | Result |
|---|---|
| Full commit | `4d12b0e41cfa722fa74338903526c4bbc52cf65a` ✅ |
| Tree | `35f6755c5ce90dc64c96bb5f4be4236a170fff83` ✅ matches expected |
| Parent | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` ✅ matches expected |
| Parent count | exactly **1** — `git rev-list --parents -n 1` returns one parent ✅ not a merge |
| Child of `11c9112`? | **NO** — `git merge-base --is-ancestor 11c9112 4d12b0e` returns non-zero ✅ |
| Commits above `06ebfdb3` | exactly **one** (`git rev-list 06ebfdb3..p4/adapter-containment-completion`) ✅ |
| Branch | `p4/adapter-containment-completion` ✅ |
| `repo_state()` | **PRODUCING** — one content commit above a metadata commit ✅ |
| Working tree | clean (`git status --porcelain` empty) ✅ |
| Index | `git ls-files -s` sha256 `761a3a62591a036d4157d38a1d0ce6e13e533b3db5fc4ec7430690117823a001`, unchanged across this review ✅ |

**Changed paths versus `06ebfdb3`: 51 files** — 39 modified, 12 added. No path under `src/`,
`configs/` or `data/`. One `scripts/` path (`mutate_roadmap_completeness.py`).

### 1.1 Locks, processes, protected refs, push state

| Check | Result |
|---|---|
| `.git/neyma-finalizer.lock` | **UNHELD** — `flock(LOCK_EX\|LOCK_NB)` acquired and released; 0 bytes; no `.json` owner record ✅ |
| `.git/neyma-builder-worktree.lock` | **UNHELD** — same probe ✅ |
| Active test/mutation processes | none (`ps` sweep for `pytest`, `finalize_status`, `mutate_*`) ✅ |
| `refs/heads/main` | `152574e4f4f2969468c9d31b1e705188896175b5` — **unmoved** ✅ |
| `refs/remotes/origin/main` | `152574e4f4f2969468c9d31b1e705188896175b5` — **unmoved** ✅ |
| Candidate pushed? | **NO** — `git branch -r --contains 4d12b0e` is empty ✅ |

### 1.2 Rejected candidate and its reports remain preserved

| Item | Value | Result |
|---|---|---|
| `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` | `11c9112…bc80` | ✅ |
| `refs/heads/archive/p4/r07-rejected-11c9112` | `11c9112…bc80` | ✅ |
| Rejected tree | `9a3950b5ffecaaa551b803059eb92b8760aac8f3` | ✅ |
| `refs/preserve/p4-r07-rejected-worktree-11c9112` | `6224b36e…dd3b`, parent `11c9112`, tree `d48992ad…caf2` | ✅ |
| Targeted review of `11c9112` | `refs/preserve/…-targeted-review-11c9112` → `fa4c459b…a62e`, **parent `11c9112`** | ✅ unmoved |
| Its SHA-256 | `1659338af1389ec1c4c77c3fc38bffcff296332556a7beeca50ec92ccd4e9222` | ✅ **exact**, sidecar agrees |
| Targeted adjudication of `11c9112` | `refs/preserve/…-targeted-adjudication-11c9112` → `030c5954…a2e8`, **parent `11c9112`** | ✅ unmoved |
| Its SHA-256 | `a8cb27684e0b6bd108de2260be1eb9809af8c392a5ead7a6e4c81e6847d00335` | ✅ **exact**, sidecar agrees |

Both reports are **absent from the candidate tree** and exist only at their preservation commits
parented to `11c9112`. Their attribution to `11c9112` is therefore mechanically exclusive: nothing
in `4d12b0e` can be read as reviewing or adjudicating the replacement.

---

## 2. REVIEW ENVIRONMENT

Four disposable `--no-local` clones, all detached at `4d12b0e`:

* **`review-clone`** — canonical suite, parser probes, corpus sweep.
* **`mut-clone`** — documentation-guard mutation matrix, full-suite mutation runs.
* **`ev-clone`** — evidence hostile battery; run both with **zero** `refs/preserve/*` (distribution
  clone) and with all 28 fetched, to exercise both tiers.
* **`clean-clone`** — clean-environment control and parent comparison.

Preservation refs are not transferred by `git clone`; they were inspected **read-only** from the
source repository (`git show <ref>:<path>`, `git rev-parse <ref>^`) with no write to the primary
branch, index or worktree. The primary repository's HEAD, tree, index digest, status, `main`,
`origin/main` and 28 preservation refs were identical before and after this review.

---

## 3. F-01 — COMPLETE FALSE-LIVE-CLAIM REMEDIATION: **CLOSED**

### 3.1 All ten corrections independently enumerated and classified

Every one was inspected in the `06ebfdb3 → 4d12b0e` diff. In all ten the live assertion is
**replaced with an accurate current statement** and the superseded wording is **retained in place
inside an explicitly marked quoted block**. None is a laundering edit — no live claim was left
standing and merely exempted.

| # | Location | Classification | Verified treatment |
|---|---|---|---|
| 1 | `LEGACY-DISPOSITION.md` §S15a "it keeps R-07 OPEN" | false live | corrected → "WRITE HALF CUT at U4.11 (P4) — the deferral below is DISCHARGED", AST facts; superseded text quoted under `SUPERSEDED` |
| 2 | `LEGACY-DISPOSITION.md` §S15a "four residuals remain" | false live | corrected → condition **MET**; superseded text quoted |
| 3 | `LEGACY-DISPOSITION.md` §S1 `Current risk` | false live | corrected → `R-07 — CONTAINED (recorded at P4)` + CONTAINED≠ENABLED bound; superseded row quoted |
| 4 | `principal-architect-supervisor.md` "R-07 still recorded OPEN unless…" | false live, **operative** | re-pointed to the machine record; superseded criterion quoted |
| 5 | `principal-architect-supervisor.md` "an open R-07" | false live | corrected → six paths CUT at P4, R-07 CONTAINED; superseded paragraph quoted |
| 6 | `effect-entry-point-cutover-plan.md` "keep **R-07 OPEN**" | false live | corrected → "P4 EXECUTION STATUS — COMPLETE"; superseded block quoted |
| 7 | `OPERATIONAL-USE-CASE-COVERAGE.yaml` "R-07 OPEN" | false live | corrected; superseded comment retained |
| 8 | `QUOTE-TO-CASH-LIFECYCLE.md` "R-07 OPEN" | false live | corrected; superseded paragraph quoted |
| 9 | `NEYMA-OPERATOR.md` "R-07 OPEN — NOT CONTAINED" | false live | corrected; superseded row quoted |
| 10 | `AUTONOMY-MATRIX.md` "R-07 OPEN" | false live | corrected; superseded wording retained |

Also verified as correctly classified, no correction required: `phase-0-baseline-manifest.yaml`
(2 historical comment paragraphs, same-line marker added), `PROGRAM-WEIGHTS.yaml` (frozen P3 gate
evidence, string not rewritten), `EFFECT-PATH-INVENTORY.yaml`, `PHASE-OUTPUTS.md`,
`pr-sequence.md` (legitimate quoted supersession / `[HISTORICAL]`), and `CURRENT.md:63/98` +
`CAPABILITY-TRACEABILITY.yaml:843` ("the open-risks table", "an open decision" — register nouns,
not status claims).

### 3.2 Counts reproduced exactly

The builder's `58 documents · 81 parsed claims · 45 live CONTAINED · 0 live OPEN` **reproduces
exactly** over the guard's *unified* population (discovered live-authority set ∪ the four landing
documents). The discovered set alone yields `57 · 80 · 44 · 0`; `README.md` is outside
`live_authority_documents()` and is contributed by the union. The builder's figure is the correct
one for the population the guard actually asserts over.

### 3.3 No report was rewritten; no claim moved

* No accepted or rejected report body differs from its preserved blob (§5.2, §5.3).
* An independent broad sweep — all tracked `.md`/`.yaml`/`.json`/`.py` files, `R-07` with a
  polarity token within a ±2-line window, run **without** the builder's parser — surfaces 338
  candidate lines across 73 files. Every one resolves to: a corrected current claim, a quoted
  supersession, preserved historical review evidence, guard/mutation source, or the builder's own
  handoff. **No live OPEN/NOT_CONTAINED claim was relocated to another canonical surface.**

**F-01 is closed.** The caveat is that "zero live OPEN claims" is a statement *about the parser's
field of view*, and R-01 below shows that field of view has a hole. No live OPEN claim exists in
the blind spot today — I checked both cross-cell rows directly and both read CONTAINED — but the
count cannot be relied upon to stay true, which is RC-01 recurring.

---

## 4. F-02 — STRUCTURAL DOCUMENT-STATUS PARSER: **NOT REMEDIATED**

### 4.1 What the parser does close

Every required grammar form in the review brief parses with correct polarity and correct liveness:

```
R-07 remains open / is open / stays open            -> OPEN  live
keeps R-07 open / leaves R-07 open                  -> OPEN  live
causes R-07 to remain open                          -> OPEN  live
requires R-07 to remain open                        -> OPEN  live   (correctly NOT exempted)
violation residuals keep R-07 open                  -> OPEN  live
R-07 not contained / is not contained               -> OPEN  live
does not contain R-07                               -> OPEN  live
R-07 remains uncontained                            -> OPEN  live
R-07: OPEN                                          -> OPEN  live
R-07 — OPEN, NOT CONTAINED.                         -> OPEN  live
R-07 contained / is contained                       -> CONTAINED live
```

Verified good: negated containment is resolved before plain containment, so `not contained` can
never read as `contained`; register nouns (`open risks`, `an open decision`, `the open-risks
table`) are correctly excluded; the conditional exemption fires only when the modal *governs* the
polarity token, so the trailing-`unless` and trailing-`cannot` escapes that hid two of the original
five are genuinely closed; `requires`/`required` are deliberately not exemptions.

The **roadmap mutation battery reproduces at 21/21 CAUGHT, 0 MISS, 0 SKIP-INVALID**, with M12–M16
reintroducing the five adjudicated defects verbatim and M17–M21 covering the additional grammar
variants. **CB-01 is discharged.** The corpus non-vacuity assertions are real: corpus ≥15,
`REQUIRED_R07_REACH` must be *inside* the discovered population, ≥5 live CONTAINED claims required,
and a 22-case matrix asserts the parse itself.

### 4.2 R-01 — the parser cannot see the repository's own canonical status rows

**`claim_units()` splits a markdown table row into independent cells and never re-associates
them** (`eval/control/status_claims.py:166-174`):

```python
if _TABLE_ROW.match(block):
    pos = block_off
    for cell in block.split("|"):
        yield cell, pos
```

A claim unit is therefore *one cell*. A row that names the risk in one column and its status in
another produces two units — one with the subject and no polarity, one with the polarity and no
subject — and **both are discarded**. The parser requires subject and status to share a cell,
which is a structural word-*placement* dependency of exactly the kind F-02 required be removed.

**Two live rows in the corpus are written that way, in the two most load-bearing documents:**

| Document | Line | Row |
|---|---|---|
| `CLAUDE.md` | 73 | `\| **R-07** \| ### **CONTAINED.** The containment MECHANISM is built…` |
| `docs/implementation/CURRENT.md` | 105 | `\| **R-07** \| Ungated live-write paths \| ### **CONTAINED** — recorded in…` |

Neither is counted among the 45 live CONTAINED claims, and neither is protected.

**Mechanical proof — full canonical suite, disposable clone, single-line mutation:**

| Tree | Result |
|---|---|
| `4d12b0e` unmodified | **2015 passed · 0 failed · 3 skipped** |
| `4d12b0e` with `CURRENT.md:105` cell 3 changed `**CONTAINED**` → `**OPEN, NOT CONTAINED**` | **2015 passed · 0 failed · 3 skipped** |

*(The 3 skips are an artifact of this reviewer's clone carrying a symlinked `.venv`, which marks
the tree dirty; see §7.2. Both runs are identical, which is the point.)*

**Discriminating matrix** over the seven documentation/status/evidence guard modules
(222 tests baseline):

| Mutation | Result |
|---|---|
| `CLAUDE.md:73` R-07 row → `OPEN, NOT CONTAINED` | **222 passed** — NOT CAUGHT |
| new cross-cell row `\| R-07 \| OPEN, NOT CONTAINED \|` appended to `ARCHITECTURE.md` | **222 passed** — NOT CAUGHT |
| control: same-cell `\| now \| R-07 OPEN, NOT CONTAINED \|` in `ARCHITECTURE.md` | **2 failed** — CAUGHT |

The discriminator is precisely the cell boundary. `test_10_r07_is_recorded_open_and_never_contained`
part (a) does not save this: it asserts `re.search(r"R-07.{0,200}CONTAINED", text, re.S)` — a
proximity substring that `OPEN, NOT CONTAINED` satisfies — and the CONTAINED≠ENABLED bound is
satisfied elsewhere in both files. The *absence* half of the invariant runs only through the
parser.

**The mutation battery cannot detect this** because M12–M21 all inject same-cell or prose forms.
A battery whose cases are drawn from the same instrument's field of view measures that field of
view, not the corpus — the RC-01 lesson the builder recorded, applied to the replacement.

### 4.3 R-02 — `<details>` content is stripped unconditionally

`strip_historical_blocks` (`status_claims.py:138-140`) deletes **every** `<details>…</details>`
region before parsing:

```python
"""Explicitly-labelled <details> blocks may retain superseded claims in place."""
return re.sub(r"<details>.*?</details>", "", text, flags=re.S)
```

The docstring asserts a label requirement the code does not implement — there is no check for
`HISTORICAL`, `SUPERSEDED` or any marker. `CURRENT.md`, `roadmap-steward.md`,
`phase-code-reviewer.md`, `registry.md` and `AUTO-LOADED-GUIDANCE-REVIEW.md` all already use
`<details>`, so this is a live channel, not a hypothetical one.

**Proof:** appending an unlabelled `<details>` block containing
`R-07 remains OPEN and is NOT CONTAINED.` to `CURRENT.md` leaves the guard set at **165 passed**
(baseline 165). The identical sentence outside a `<details>` block yields **2 failed**.

### 4.4 R-03 — the historical-marker exemption is ungoverned

`parse_status_claims` exempts a claim when `_HISTORICAL_MARKER` (`\bHISTORICAL\b|\bSUPERSEDED\b`)
appears **anywhere on the risk id's line** (`status_claims.py:85, 247`), with no requirement that
the marker govern or refer to the claim. The module deliberately narrowed the *conditional*
exemption to markers that govern the polarity token; the historical exemption did not receive the
same treatment.

**Proof:** `R-07 remains OPEN and NOT CONTAINED today; nothing here is SUPERSEDED.` in `CURRENT.md`
→ **165 passed** (not caught). Without the trailing clause → **2 failed**.

### 4.5 R-04 — F-05's quote-parity fix is block-bounded by *paragraph*, not by claim block

`_blocks()` treats each table row as its own block, but `_quoted()` counts parity from
`_block_start_for()`, which is the preceding `\n\n` — a paragraph (`status_claims.py:182-189`).
A markdown table has no blank lines between rows, so the whole table is one parity block: an
unbalanced `"` in an early row exempts every later row in that table.

**Proof:** `| a | he said "hello |` followed by `| b | R-07 remains OPEN |` parses the second row
with `exemption='quoted'`. This is strictly narrower than the file-wide defect F-05 named, so F-05
is *improved*; it is not fully closed.

### 4.6 Shared parser module and guard-registry entry

Both deviations reviewed (§8). Both are mechanically justified and narrowly scoped.

---

## 5. F-03 — IMMUTABLE EVIDENCE BINDING: **CLOSED**

### 5.1 Complete load-bearing manifest — six reports, all independently verified

Each was verified by recomputing SHA-256 over the blob at its preservation ref, resolving the
preservation commit's parent, and reading the worktree sidecar — **without using the guard**:

| # | Key | Preserved blob SHA-256 | Preservation ref → commit | Parent | Sidecar | Banner |
|---|---|---|---|---|---|---|
| 1 | `accepted_independent_rereview` | `181e1a37…d316` ✅ | `p4-independent-rereview-0891d1a` → `5ca6d2e9` | `0891d1a` ✅ | ✅ | **35 lines** |
| 2 | `final_adjudication` | `078cfea8…997e` ✅ | `p4-final-adjudication-0891d1a` → `420e5b2d` | `0891d1a` ✅ | ✅ | none |
| 3 | `first_finalization_report` | `9f5b8f98…1056` ✅ | `p4-closure-acceptance-prestate-86306d5` → `361d10ae` | `86306d5` ✅ | ✅ | none |
| 4 | `accepted_targeted_independent_review` | `5547aa5e…8ea5` ✅ | `p4-closure-targeted-review-42ea24c` → `c30a43be` | `42ea24c` ✅ | ✅ | **34 lines** |
| 5 | `accepted_targeted_adjudication` | `23496e6c…9567` ✅ | `p4-closure-targeted-adjudication-42ea24c` → `d3cf1de9` | `42ea24c` ✅ | ✅ | none |
| 6 | `second_finalization_report` | `96ef5fe8…1fa0` ✅ | `p4-second-finalization-report-06ebfdb3` → `99f0e59d` | `06ebfdb3` ✅ | ✅ | none |

Every recomputed digest, every preservation parent and every sidecar matches the containment
record exactly. `first_finalization_report` is newly bound and its binding is sound —
an unbound load-bearing report was precisely the F-03 defect. The report set is enumerated from
`containment_evidence` rather than hand-listed, and `test_the_load_bearing_report_set_is_non_empty…`
requires all six keys, every parent resolvable and ≥4 parsed verdicts, so the corpus cannot go
empty.

### 5.2 Banner handling — correct

For all six, `strip_banner()` (exactly one leading blockquote block plus trailing blanks) yields a
body that hashes to the recorded digest **and** equals the preserved blob **byte-for-byte**. No
impossible equality between a bannered wrapper and its unbannered original is required; the banner
must additionally disarm (`NOT CURRENT AUTHORITY`) and disclose the sidecar convention. The
disclosed banner-sidecar differences are correctly treated as intentional conventions, not defects.

### 5.3 Hostile evidence battery — reproduced end-to-end, all CAUGHT

Run in disposable clones, restoring between cases; baseline re-verified green after each.

| Case | Distribution clone (0 preserve refs) | With all 28 preserve refs |
|---|---|---|
| baseline | 26 passed | 26 passed |
| **ACCEPT → REJECT** in `p4-final-adjudication-report-0891d1a.md` | **1 failed** ✅ | **1 failed** ✅ |
| sidecar content changed | — | **1 failed** ✅ |
| sidecar missing | — | **1 failed** ✅ |
| report missing | — | **5 failed** ✅ |
| **one** preservation ref deleted (partial availability) | — | **2 failed** ✅ |
| preservation ref re-pointed to a different real commit | — | **1 failed** ✅ |
| required banner removed | — | **13 failed** ✅ |
| valid banner over substituted body | — | **15 failed** ✅ |
| `RECONSTRUCTION` → `CONTEMPORANEOUS RECORD` in the record | — | **1 failed** ✅ |
| adjudicated candidate re-attributed (`42ea24c` → `0891d1a`) | — | **1 failed** ✅ |

**The headline reproduction is confirmed.** Flipping the adjudication verdict in a clean clone
carrying **zero** `refs/preserve/*` fails, where it previously left 1957 tests green. Tier 1 —
banner-stripped worktree body hashed against the digest the record cites — is doing the catching,
exactly as designed. (The tampered digest differs from the builder's cited `610d471b…` only because
I replaced one verdict line rather than every `ACCEPT` token; the detection is identical.)

### 5.4 Two-tier design — reviewed hostilely, judged a justified capability boundary

* Clean clones do **not** falsely require local-only refs. ✅
* The unconditional tier catches every load-bearing content tamper in every environment. ✅
* Partial preservation-ref availability is **not** silently accepted: deleting exactly one ref
  produces **2 failures**, and `test_the_tier_two_condition_is_all_or_nothing` asserts the
  distinction directly. ✅
* A missing individual ref does **not** downgrade to content-only mode. ✅
* The primary repository carries 28 preservation refs, so it runs the full tier-2 check. ✅
* Wrong parent, wrong commit, wrong blob, wrong verdict, wrong finalizer target, wrong attribution
  and mutable-worktree substitution all fail. ✅
* No skip was added; the repository's single approved skip is not spent. ✅

**Judgement: justified clean-clone capability boundary, not an evidence-control weakening.** The
residual is inherent and correctly bounded — in an environment with no preservation history an
adversary who controls the whole tree could move report and recorded digest together. That is not
reachable in the primary repository, where tier 2 binds every report to an immutable off-branch
blob with a verified parent. `_tier2_inputs()` synthesises tier-2 inputs *only* for the negative
battery, never for the positive binding test, so it cannot manufacture a pass.

**F-03 is closed.**

---

## 6. R-07 TECHNICAL CONTAINMENT — VALID AND UNCHANGED

Independently recomputed in a disposable clone, not read from the record:

| Property | Recomputed | Recorded | Result |
|---|---|---|---|
| R-07 canonical status | — | `CONTAINED` (`expected_legacy_paths.status`) | ✅ |
| Live violation edges | **0** (`import_probe.effect_adapter_violation_edges()`) | `[]` | ✅ exact equality |
| Detection edges | **13** (distinct live adapter-import edges) | **13** (`manifest.allowed_adapter_import_edges()`) | ✅ exact equality |
| Production `GateRegistry` | **0** constructions, **0** `register_gate` calls across `src/` + `scripts/` | `EMPTY` | ✅ |
| Phase-8 gate deferral | `AC-CKPT-6-missing` = `DEFERRED_BY_DEPENDENCY — REQUIRED AT PHASE 8` | `DEFERRED BY FOUNDER DECISION to U8.1 / P8` | ✅ intact |
| `CdpActuator` construction | none outside `scripts/mutate_phase4_boundary.py` fixtures | — | ✅ |
| `cdp_actuator` import | none — only prose, comments and mutation fixture strings | — | ✅ |
| Legacy live-operation router | `_build_live_operation_router` absent from `src/` and `scripts/` | — | ✅ |
| Production default | `ROUTE_NOT_CONFIGURED` refusal (`action_callback.py:662`) | — | ✅ |
| P4 | COMPLETE, 100% | — | ✅ |
| P5 | **sole READY**, NOT_STARTED, 0.0% | — | ✅ |
| P6–P14 | all **BLOCKED** (9 units) | — | ✅ |
| P5 implementation | not begun | — | ✅ |

**P4 boundary mutation battery: 61/61 mutants caught**, byte-exact tree restoration.

Containment means external-effect paths are governed or fail closed. Nothing in this candidate
enables a production write or grants autonomy, and I found no evidence to the contrary.

### 6.1 Runtime byte equality versus `0891d1a` — VERIFIED

| Tree | `0891d1a` | `4d12b0e` | Result |
|---|---|---|---|
| `src` | `0204261b17baecd2bab3dc1b7d25a7494eb3b22d` | same | **IDENTICAL** ✅ |
| `configs` | `124ae4bcbbec96cc0ff9282d183d7c97aa1914f5` | same | **IDENTICAL** ✅ |
| `data` | `8d02102277273f6858ce15d3753002e7875bb9df` | same | **IDENTICAL** ✅ |

Tree-object identity covers adapters, the governed approval/write route,
checkpoint/witness/grant/atomic-claim machinery, browser-use boundaries, origin policy, and the
production `GateRegistry` implementation and population, by construction.

**The only `scripts/` change is `mutate_roadmap_completeness.py`.** Import reachability verified
structurally: nothing in `src/`, `scripts/` or `eval/` imports it; it imports only `argparse`,
`shutil`, `subprocess` and `pathlib`, and is invoked as a standalone mutation driver. It is not on
any runtime path. **No freight runtime or external-effect behaviour changed.**

### 6.2 Receipts — unforged

`SUITE-RESULT.json` (`a16cb1fc…`) and `GATE-RESULT.json` (`8201ca74…`) are **the identical blobs**
at `06ebfdb3` and `4d12b0e`. Neither appears in the changed-path set.

### 6.3 No secret or environment content entered any object

* `.env` was **never tracked** in any commit on any ref, and appears in no preservation tree.
* Its recorded digest `220534bc39dbcb0f4698b530ad740674381e1e046c6b52373ed62f1b181d60ab`
  **matches** the current file. ✅
* The only `.env`-family path in the preservation trees is `.env.example`.
* A credential-pattern sweep over the candidate tree surfaces only documentation placeholders
  (`xoxb-…`, `sk-ant-...`) and test fixtures (`xoxb-test`). No live secret. ✅

---

## 7. TESTS AND REPRODUCTION

| Check | Builder claim | Reproduced | Result |
|---|---|---|---|
| Canonical suite | 2017 passed / 0 failed / 1 skipped / 2018 collected | **2017 / 0 / 1 / 2018** | ✅ **exact** |
| Approved skips | exactly one | exactly `test_the_red_by_design_cases_are_strict_xfails` | ✅ |
| `TEST-NODE-MANIFEST.json` | exact set equality at 2018 | **2018 == 2018, 0 missing, 0 extra**; `config_sha256` `22f42941…` verified | ✅ |
| Roadmap/mutation battery | 21/21, 0 SKIP-INVALID, CB-01 discharged | **21/21 CAUGHT, 0 missed, 0 SKIP-INVALID** | ✅ |
| P4 boundary battery | 61/61 | **61/61 caught** | ✅ |
| Corpus sweep | 0 live OPEN, 45 live CONTAINED | **58 docs / 81 claims / 45 CONTAINED / 0 OPEN** | ✅ |
| Production `GateRegistry` | empty | 0 constructions, 0 registrations | ✅ |
| Runtime equality vs `0891d1a` | src/configs/data identical | tree-object identical | ✅ |
| Receipts | byte-identical to `06ebfdb3` | identical blobs | ✅ |
| Locks | unheld | both unheld by `flock` probe | ✅ |
| Protected refs | unchanged | `main`/`origin/main` at `152574e4` | ✅ |
| Pushed | nothing | not on any remote | ✅ |
| Clean-clone gate | PASS | **PASS** (§7.1) | ✅ |

### 7.1 Clean-clone gate — PASS, independently

`scripts/clean_clone_gate.py` was run **only in a disposable clone**, because it writes
`GATE-RESULT.json` and running it in the primary worktree would overwrite a finalizer receipt.

```
clean-clone gate: …/neyma-clean-clone-6zur9mg2/clone (committed 4d12b0e41)
--- clone committed state                       (exit 0)
--- no active_workspace in clone: OK
--- python floor (host)                         (exit 0)
--- fresh venv                                  (exit 0)
--- python floor (venv)                         (exit 0)
--- install declared deps only                  (exit 0)
--- complete canonical suite (clean clone)      (exit 0)
    clean-clone: {'passed': 2017, 'failed': 0, 'skipped': 1, 'collected': 2018}
--- control guards (clean clone)                (exit 0)
--- AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001      (exit 0)

CLEAN-CLONE GATE: PASS
```

The gate builds its own fresh virtualenv from declared dependencies and independently reproduces
**2017 / 0 / 1 / 2018** — corroborating §7's canonical figure from a second, fully independent
toolchain, and confirming R-05.

### 7.2 Two reviewer-environment artifacts, disclosed

Neither is a candidate defect; both are recorded so the numbers reconcile.

1. **3 skips vs 1.** A clone carrying a **symlinked** `.venv` is not matched by `.gitignore`'s
   `.venv/` directory pattern, so `git status` reports it dirty and the two dirty-tree guards in
   `test_status_reality.py` raise their loud NOT-RUN skips. Excluding `.venv` locally restores the
   canonical **2017 / 0 / 1 / 2018** with exactly the one approved skip.
2. **Four CLI smoke failures in a `.venv`-less clone.**
   `test_dispatch_cli_requires_secret_or_explicit_local_flag`, `test_cli_local_outbox_smoke`,
   `test_mailbox_intake_cli_smoke`, `test_mailbox_workflow_cli_smoke` shell out to
   `ROOT/.venv/bin/python`. Verified: **4 failed / 30 passed on the candidate `4d12b0e` and
   4 failed / 30 passed on the unmodified parent `06ebfdb3`, the same four tests.** Confirmed a
   test-environment limitation, not a replacement regression, exactly as the handoff's §8.3
   self-correction states.

---

## 8. DEVIATIONS FROM THE ADJUDICATED PATH SET

| # | Deviation | Mechanically required? | Scope | Runtime? | Blocks acceptance? |
|---|---|---|---|---|---|
| 1 | `eval/control/status_claims.py` (new shared parser module) | **Yes.** The adjudication required the two corpora be *unified*; a parser duplicated across two test modules would drift, which is the defect being fixed. `live_authority_documents()` must have one definition, and `eval/control/` already holds `inventory.py`, the corpus-discovery authority | Narrow — one guard-support module beside its established sibling | No | **No** |
| 2 | `PROGRAM-WEIGHTS.yaml`, `effect-entry-point-cutover-plan.md`, four `docs/product/` files | **Yes.** §9.4's path list was written from a defect set of five; the remediation brief mandated a repository-wide sweep, which found five more. Each edit is confined to the false claim and its superseded quotation — verified line by line (§3.1) | Narrow, documentation only | No | **No** |
| 3 | `eval/tests/test_phase2_guard_registry.py` | **Yes.** `test_every_guard_file_is_classified` fails the suite when a guard file is added unclassified. Verified: the diff is exactly **one `RETAIN` entry plus its reason**; no assertion, prefix or rule changed | Minimal | No | **No** |

**None of the three should block acceptance, and none requires separate ratification beyond the
targeted adjudication that follows this review.** Each is mechanically forced by the adjudicated
invariant or by the control system itself, none touches runtime, and the scope expansion is proven
rather than asserted. Newly discovered defects legitimately expanded the correction set.

---

## 9. FINDINGS

### R-01 — the status parser cannot see the repository's own cross-cell canonical status rows

* **Severity:** HIGH — **confirmed defect**
* **Requirement:** F-02 required the documentation guard to stop depending on word order and to
  detect bounded semantic forms of R-07 status across the canonical/control corpus, failing the
  build when a live document asserts R-07 OPEN / NOT CONTAINED.
* **File/range:** `eval/control/status_claims.py:166-174` (`claim_units`, table branch).
  Unprotected live instances: `docs/implementation/CURRENT.md:105`, `CLAUDE.md:73`.
* **Proof:** full canonical suite **2015 passed / 0 failed / 3 skipped — identical to baseline —
  with `CURRENT.md:105` reading `OPEN, NOT CONTAINED`**. Guard-set matrix: CLAUDE.md flip → 222
  passed (not caught); new cross-cell row in `ARCHITECTURE.md` → 222 passed (not caught);
  same-cell control → 2 failed (caught).
* **Consequence:** the two most-read live statements of R-07's status — in the operating guide and
  in the designated status authority — are outside the guard. The build stays green while the
  status authority says R-07 is open. The adjudicated invariant is not enforced.
* **Blocks third-finalizer authorization: YES.**
* **Remediation (narrow):** in `claim_units`, bind the risk id across the whole table row — either
  yield the normalized full row as an additional claim unit, or attribute each cell's polarity to
  the row's subject cell — so a row whose id and status occupy different cells parses as one
  claim. Add mutation cases reintroducing `CURRENT.md:105` and `CLAUDE.md:73` **verbatim** in the
  cross-cell form, and assert both are CAUGHT. Do not widen beyond table-row association.

### R-02 — `<details>` blocks are stripped without the label the docstring claims to require

* **Severity:** MEDIUM — **confirmed defect**
* **Requirement:** the parser must distinguish live assertions from historical evidence by an
  explicit mechanism; exemptions must not be abusable to launder a live claim.
* **File/range:** `eval/control/status_claims.py:138-140` (`strip_historical_blocks`).
* **Proof:** an unlabelled `<details>` block containing `R-07 remains OPEN and is NOT CONTAINED.`
  appended to `CURRENT.md` → **165 passed** (baseline 165, not caught). The same sentence outside
  a `<details>` block → **2 failed**. `CURRENT.md` and four other corpus documents already use
  `<details>`.
* **Consequence:** any live false claim can be made invisible by wrapping it in an unlabelled
  collapsible block, in documents that already use them. The docstring asserts a check
  ("Explicitly-labelled") that the code does not perform — an inaccurate claim in guard evidence,
  the same class as the F-04 the builder correctly closed elsewhere.
* **Blocks third-finalizer authorization: YES.**
* **Remediation (narrow):** strip a `<details>` block only when its `<summary>` or first line
  carries `HISTORICAL` or `SUPERSEDED`; otherwise parse its contents normally. Add a mutation case.

### R-03 — the historical-marker exemption does not have to govern the claim

* **Severity:** MEDIUM — **non-blocking residual risk**
* **Requirement:** exemptions must identify genuinely historical material, not any line that
  happens to contain a marker word.
* **File/range:** `eval/control/status_claims.py:85` (`_HISTORICAL_MARKER`), `:247` (application).
* **Proof:** `R-07 remains OPEN and NOT CONTAINED today; nothing here is SUPERSEDED.` in
  `CURRENT.md` → **165 passed** (not caught); without the trailing clause → **2 failed**.
* **Consequence:** a live claim is exempted by the mere co-occurrence of `SUPERSEDED`/`HISTORICAL`
  anywhere on its line. The module deliberately narrowed the *conditional* exemption to markers
  that govern the polarity token; this one was left ungoverned, an asymmetry with no stated reason.
* **Blocks third-finalizer authorization: NO** — this is the pre-existing marker convention the
  control system already recognises, carried forward rather than introduced.
* **Remediation:** scope the marker the way `_CONDITIONAL` is scoped — require it to precede the
  risk id within the claim unit — or record the asymmetry explicitly as an accepted convention.

### R-04 — F-05's quote-parity fix is bounded by paragraph, not by claim block

* **Severity:** LOW — **confirmed defect (narrow)**
* **Requirement:** F-05 required quote parity to stop leaking past the construct that contains it.
* **File/range:** `eval/control/status_claims.py:182-189` (`_quoted`, `_block_start_for`) versus
  `:143-164` (`_blocks`, where a table row is its own block).
* **Proof:** `| a | he said "hello |` then `| b | R-07 remains OPEN |` → the second row parses with
  `exemption='quoted'`.
* **Consequence:** one unbalanced quote in an early table row exempts every later row of the same
  table. Strictly narrower than the file-wide defect F-05 named — F-05 is improved, not closed.
* **Blocks third-finalizer authorization: NO.**
* **Remediation:** compute parity from the same block boundary `_blocks()` uses, so a table row's
  parity window is that row.

### R-05 — the commit message's recorded suite figures are inaccurate

* **Severity:** LOW — **evidence deficiency**
* **Requirement:** claims in the candidate's own immutable audit record must be true; this is the
  F-04 standard the builder applied to a docstring.
* **File/range:** commit message of `4d12b0e41cfa722fa74338903526c4bbc52cf65a` — *"Canonical suite
  2014 passed / 0 failed / 3 skipped / 2017 collected, with TEST-NODE-MANIFEST at exact set
  equality."*
* **Proof:** `TEST-NODE-MANIFEST.json` records `node_count: 2018` and collection is **2018** with
  exact set equality (0 missing, 0 extra). Observed runs: **2017 / 0 / 1 / 2018** (clean),
  **2015 / 0 / 3 / 2018** (dirty-marked clone), **2013 / 4 / 1 / 2018** (`.venv`-less clone), and
  **2017 / 0 / 1 / 2018** again from the clean-clone gate's own fresh virtualenv (§7.1).
  `2014 + 3 = 2017 ≠ 2018`, so "2017 collected" and "exact set equality" cannot both hold. The
  handoff §9 separately reports 2015 / 0 / 3 / **2018** for the primary tree, contradicting the
  commit message it accompanies.
* **Consequence:** a durable, unamendable record misstates the certified suite population. No
  mechanical control depends on it — the finalizer writes its own receipt from an actual run — but
  it is a false number in audit evidence, and the discrepancy against the handoff is unexplained.
* **Blocks third-finalizer authorization: NO.**
* **Remediation:** the commit message cannot be amended without breaking topology. Record the
  correction in the containment record or in the adjudication, stating the true figures
  (**2017 / 0 / 1 / 2018**) and that the commit-message line is superseded.

### Non-findings — preserved, not re-litigated

Independently re-verified and **not** converted into defects, consistent with the adjudicated
self-corrections: the three banner-related sidecar differences are disclosed intentional
conventions (§5.2); the original evidence blobs are byte-exact at their preserve refs (§5.1); the
prior reviewer's H-03 MISS was a probe-scoping mistake already caught by
`test_phase0_adapter_imports.py`; and the environment-only CLI smoke failures reproduce on the
unmodified parent (§7.2). RC-02, RC-03, RR-01, AD-01, AD-02, F-06 and the remaining carried
residuals are acknowledged as carried and are **not** re-raised here.

---

## 10. WHAT THIS REVIEW DID NOT DO

Did not remediate any finding · did not modify the candidate · did not amend, commit to the
product branch, reset, restore, rebase, merge, checkout, stash, clean, update a branch ref or
push · did not run `finalize_status.py` · did not adjudicate · did not begin P5 · did not deploy
or enable any effect · did not move `main`, `origin/main` or any protected ref · did not alter the
review or adjudication of `11c9112` · reviewed all implementation behaviour from disposable
`--no-local` clones, never from the primary worktree.

---

## 11. WHAT MUST HAPPEN NEXT

1. **R-01 and R-02 must be remediated** in a replacement candidate on the same parent `06ebfdb3`,
   preserving this candidate the way `11c9112` was preserved.
2. R-03, R-04 and R-05 should be addressed or explicitly accepted by the adjudicator.
3. A **fresh** targeted independent review of that candidate, then a **separate** targeted
   adjudication, before any third finalizer is authorized.
4. Until then `scripts/finalize_status.py` must not run.

**This report is a review. It certifies nothing, adjudicates nothing and authorizes no
finalization.**
