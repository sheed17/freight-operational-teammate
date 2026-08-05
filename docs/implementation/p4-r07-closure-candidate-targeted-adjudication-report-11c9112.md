# P4 R-07 CLOSURE CANDIDATE — SEPARATE TARGETED ADJUDICATION

**Candidate:** `11c911244304d56737913db41b458d5f3278bc80`
**Candidate tree:** `9a3950b5ffecaaa551b803059eb92b8760aac8f3` (resolved directly from Git)
**Parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (second-finalizer metadata commit)
**Branch:** `p4/adapter-containment-completion` (tip == candidate)
**Repository state at adjudication:** `PRODUCING`

This session did not implement P4, did not author the closure candidate, did not conduct the
targeted independent review, did not run either finalizer, and did not reconstruct the
second-finalization report. It resumed no previous session. It remediated nothing, finalized
nothing, and began no P5 work. All hostile probing was performed in disposable `--no-local`
clones under a scratchpad; the primary worktree, index, branch and refs were never written.

---

## VERDICT

### REJECT — TARGETED REMEDIATION REQUIRED

R-07 containment is **technically real and independently reproduced**. The candidate is
nevertheless **not eligible for finalization**, on three independent grounds, two of which are
materially **wider than the targeted review reported**:

* **F-01** — not two but **five** unmarked, live, factually false R-07 status claims, spread
  across **two** canonical surfaces, not one. One of them is the `Current risk` row of the section
  literally titled **"THE R-07 SURFACE"**; another is an operative instruction telling an
  adjudicating agent to require R-07 to be recorded OPEN.
* **F-02** — the replacement guard is not merely word-order-fragile. It requires a copula from a
  closed three-verb set to *follow* `R-07`, and is therefore **structurally blind to the
  repository's own canonical status-row grammar**. It detects **0 of the 5** live defects while
  returning green.
* **F-03** — reproduced at full-suite scale. Flipping a load-bearing adjudication verdict from
  ACCEPT to REJECT leaves **1957 tests passing**. No test in the repository reads a `.sha256`
  sidecar or recomputes any evidence document's hash.

The narrowest legal remediation is **replacement of `11c9112` in place** (parent stays
`06ebfdb3`). A second consecutive content commit is **mechanically illegal** — proven by
experiment, not by reading. A finalizer **cannot** repair F-01: the offending files are not
`STATUS_METADATA_FILES`.

---

## 1. IDENTITY, TOPOLOGY AND EVIDENCE CUSTODY — VERIFIED

| Check | Result |
|---|---|
| Candidate commit | `11c911244304d56737913db41b458d5f3278bc80` ✔ |
| Candidate tree (from Git) | `9a3950b5ffecaaa551b803059eb92b8760aac8f3` ✔ |
| Parent | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` ✔ as expected |
| Branch tip | `p4/adapter-containment-completion` → `11c9112` ✔ |
| Content commits above `06ebfdb3` | exactly **one** ✔ |
| `repo_state()` | `PRODUCING` (recorded `42ea24c` == `HEAD^^`) ✔ |
| Nothing pushed | `git ls-remote origin` carries no candidate branch and no `refs/preserve/*` ✔ |

### The targeted independent review — bytes independently verified

| Item | Value | Result |
|---|---|---|
| Report path | `docs/implementation/p4-r07-closure-candidate-targeted-review-report-11c9112.md` | present **only** at the preserve ref, not in the candidate tree |
| Preserved blob SHA-256 | `1659338af1389ec1c4c77c3fc38bffcff296332556a7beeca50ec92ccd4e9222` | ✔ **exact match** to the expected value |
| Sidecar (preserved) | `1659338af138…9222` | ✔ agrees |
| Preserve commit message digest | `1659338af138…9222` | ✔ agrees |
| Preservation ref | `refs/preserve/p4-r07-closure-targeted-review-11c9112` | → `fa4c459b0507a43cdf6040429e4a4d6a02a7a62e` ✔ |
| Preservation parent | `11c911244304d56737913db41b458d5f3278bc80` | ✔ **exactly the candidate** |
| Preservation delta | adds **only** the report and its sidecar (`A`, `A`) | ✔ no candidate byte touched |
| Attribution | commit message names candidate, tree and parent exactly | ✔ |

I read the complete 537-line report. Its verdict is
**CONDITIONALLY ACCEPT — EVIDENCE REMEDIATION REQUIRED**.

**One defect in the review artifact itself (not a candidate defect).** The report's own §12
records *"Report SHA-256 `9de20eadb60ed483c9222c3845a0aa184af9f9b0d3779881c97e7e6dc5385e30`"*.
That is **not** its hash, and no blob at any ref hashes to it. A document cannot contain its own
digest, so this is a structurally unavoidable placeholder; the authoritative bindings (sidecar and
preserve-commit message) both carry the true `1659338a…` and both verify. Recorded for
completeness. It does not impair the review's substance and is **not** charged against the
candidate — but it is itself an instance of the F-03 class.

---

## 2. THE REVIEWER'S POSITIVE RESULTS — INDEPENDENTLY REPRODUCED

Per instruction I did not reopen the complete P4 runtime. I re-derived the load-bearing facts
directly; **none failed**.

| Reproduced fact | Method | Result |
|---|---|---|
| `src/`, `configs/`, `data/` byte-identical to `0891d1a` | tree-object comparison | `0204261b…`, `124ae4bc…`, `8d021022…` — **IDENTICAL** |
| Zero live violation edges | `import_probe.effect_adapter_violation_edges()` | `[]` |
| Zero recorded violation edges | `manifest.recorded_effect_violation_edges()` | `[]` |
| Live == recorded | set equality | **True** |
| Corpus non-vacuity | probe `Evaluation` | 152 sources inspected, 10 candidates, `allow_empty=False` |
| Production `GateRegistry` EMPTY | containment guard §(3) | PASS over proven non-empty corpus |
| No `CdpActuator` construction / `cdp_actuator` import | AST guard §(4) | PASS |
| No legacy `build_live_operation_router` route | AST + grep | absent from `src/` and `scripts/` |
| P4 COMPLETE | registry | `COMPLETE` / `COMPLETE` / `PHASE_ACCEPTANCE_COMPLETE` |
| P5 sole READY, NOT_STARTED | registry | `READY` / `NOT_STARTED` / `NO_CHECKPOINT` |
| P6–P14 BLOCKED | registry | all 9 `BLOCKED` / `NOT_STARTED` |
| Receipts not forged | blob identity vs `06ebfdb3` | `SUITE-RESULT.json`, `GATE-RESULT.json` **BYTE-IDENTICAL** |
| No runtime byte changed | full path diff `06ebfdb3→11c9112` | only docs, agent lenses, 8 guard files, `mutate_roadmap_completeness.py` |
| Canonical suite green on candidate | full run in disposable clone | **1961 passed, 4 failed (environmental), 3 skipped** — see note |

**Note on the 4 failures.** `test_delivery_dispatch`, `test_first_design_partner`,
`test_mailbox_intake`, `test_mailbox_workflow` CLI smoke tests fail identically on the
**untampered** candidate tree in my sandbox. They are subprocess/CLI environment artifacts of the
disposable clone, reproduce with and without any modification, and are **not** attributable to the
candidate. I record them rather than suppress them.

**Conclusion.** The reviewer's verified positive result stands. **R-07 containment is real,
structural, and correctly recorded in `phase-0-baseline-manifest.yaml`.** Nothing below disturbs
that.

---

## 3. F-01 — STALE CANONICAL CONTROL PROSE — **BLOCKING**, AND WIDER THAN REPORTED

### 3.1 Is `LEGACY-DISPOSITION.md` a canonical control document?

**Yes.** It is classified `IMPLEMENTATION_CONTROL` in `docs/CANONICAL-DOCUMENTS.md`, and it is a
member of the discovered live-authority corpus used by the R-07 documentation guard
(`_live_authority_documents()` → 57 documents; membership confirmed `True` by direct execution).
It is *not* in the hard-coded corpus of the second guard (§4.1).

### 3.2 Are these statements live status, historical evidence, or malformed historical prose?

**Live status.** Mechanically:

* they survive `_strip_historical()` — no `<details>` block encloses them;
* no `HISTORICAL` or `SUPERSEDED` token appears on their lines;
* they are not inside a quoted span;
* they sit under ordinary live headings (`## S1`, `### S15a`).

They are therefore neither historical evidence nor malformed historical prose. They are **live,
unmarked, factually false assertions of current status**.

### 3.3 The confirmed defect set — five claims, two surfaces

The reviewer reported **two**. I confirm both and find **three more**.

| # | Location | Text | Reported by reviewer |
|---|---|---|---|
| 1 | `LEGACY-DISPOSITION.md:425` | "**Still present — DEFERRED (it keeps R-07 OPEN):** … `_build_live_operation_router._build_agent` constructs `CdpActuator`…" | ✔ yes |
| 2 | `LEGACY-DISPOSITION.md:428` | "…`violation_edges` empty (**not yet** — **four** residuals remain…)" | ✔ yes |
| 3 | **`LEGACY-DISPOSITION.md:44`** | `\| **Current risk** \| ### **R-07 — OPEN, NOT CONTAINED.** This is the highest-risk subsystem in the repository. \|` | ✘ **missed** |
| 4 | **`.claude/agents/principal-architect-supervisor.md:53`** | "**Safety boundaries intact** — R-07 still recorded OPEN unless the unit is P4 itself" | ✘ **missed** |
| 5 | **`.claude/agents/principal-architect-supervisor.md:75`** | "this repository has six production-reachable live-write paths and **an open R-07**" | ✘ **missed** |

**Why #3 is the most serious of the five.** Line 44 is the `Current risk` cell of `## S1 — Effect-bearing
write paths ⛔ **THE R-07 SURFACE**` — the section a reader consults *first* to learn R-07's status.
It uses the **same field name** (`Current risk`) as line 224, which this very commit updated to
*"R-07 is CONTAINED"*. The document therefore now answers the same question twice, in the same
grammar, with opposite values, both unmarked. The candidate's diff shows why: the sweep updated
the effect-boundary rows at 221–227 and never touched §S1 or §S15a.

**Why #4 is independently serious.** It is not narrative — it is an **operative adjudication
criterion** instructing the principal-architect supervisor to verify that "R-07 [is] still
recorded OPEN unless the unit is P4 itself". An agent following this instruction today would
**reject the correct repository state**. A false control document that merely misinforms is bad;
one that instructs a reviewer to enforce the superseded state is a control-system defect.

**#5** is doubly stale: "an open R-07", and "six production-reachable live-write paths" against a
recorded `production_reachable_live_write_remaining: 1` (cf. F-06).

**Falsity is AST-proven**, as the reviewer established and I re-confirmed: zero `CdpActuator`
constructions and zero `cdp_actuator` imports in `run_action_callback_server.py`;
`_build_live_operation_router` / `_build_agent` exist nowhere in `src/` or `scripts/`; manifest
`violation_edges: []` and live recomputation `set()` — not "four residuals".

### 3.4 Can `11c9112` be finalized while a canonical control document contradicts the record?

**No.** Finalization is the act that makes the containment record authoritative and at-rest. The
repository's own doctrine — enforced by `test_10_r07_is_recorded_open_and_never_contained`, whose
docstring states that "every live control document records R-07 as CONTAINED, so a document
silently reverting to 'R-07 is OPEN' now fails as loudly as an early CONTAINED once did" — is that
canonical documents may restate the registry but never contradict it. Finalizing here would
enter the at-rest state carrying five live contradictions of the very record being finalized, in
the same defect class (F-TR-01…F-TR-04) the targeted adjudication already made **binding on this
commit**. The commit message's own claim, *"ADJ-02 PARITY RESTORED across every canonical status
surface the sweep reached"*, is literally true and materially misleading: the sweep did not reach
these.

### 3.5 What the narrow remediation must do

For each of the five: **either** correct it to the certified current state, **or** preserve the
superseded sentence quoted in place with an explicit `HISTORICAL` / `SUPERSEDED` marker **on the
same line** — the two mechanisms `_is_superseded_in_place()` already recognises, and the treatment
this commit already applies elsewhere. Deletion of architectural history is not permitted.

Specifically: line 44's `Current risk` row must be brought into agreement with line 224 (and its
now-met `Deletion condition` and stale `Target phase` rows at 47–48 reviewed in the same pass);
lines 425/428 corrected or marked; and `principal-architect-supervisor.md:53` must be re-pointed
so the criterion reads on the CONTAINED record, with `:75`'s counts corrected.

**The reviewer's instruction "Change nothing else" is insufficient and must not be followed as
written** — obeying it literally would leave three live false claims standing, one of them an
active mis-instruction.

### 3.6 Any other canonical surface?

Yes — that is finding #4/#5 above (`.claude/agents/principal-architect-supervisor.md`, a
**second** canonical surface). I swept all 57 live-authority documents. Beyond the five, the guard
pattern raises 7 further raw hits, and I verified **every one is legitimately suppressed**:

| Location | Suppression | Legitimate |
|---|---|---|
| `EFFECT-PATH-INVENTORY.yaml:18` | `[HISTORICAL]` marker on line | ✔ |
| `EFFECT-PATH-INVENTORY.yaml:28` | quoted supersession | ✔ |
| `EFFECT-PATH-INVENTORY.yaml:130` | quoted ("This block ended …") | ✔ |
| `PHASE-OUTPUTS.md:109` | `*(HISTORICAL — … see below)*` | ✔ |
| `phase-0-baseline-manifest.yaml:358` | quoted supersession | ✔ |
| `phase-0-baseline-manifest.yaml:661` | quoted | ✔ |
| `pr-sequence.md:33` | `*(HISTORICAL — … recorded CONTAINED at P4)*` | ✔ |

The F-TR remediation demonstrably works where the sweep reached. The defect is coverage, not
technique.

### **F-01 conclusion: BLOCKING.** Confirmed, and enlarged from 2 defects on 1 surface to 5 on 2.

---

## 4. F-02 — THE GUARD DOES NOT REACH THE DEFECT — **BLOCKING**, AND STRUCTURALLY WORSE

### 4.1 Exact implementation and test surface

Two guards carry the invariant.

**Guard A** — `eval/tests/test_roadmap_completeness_control.py::test_r07_is_never_represented_as_contained_anywhere_live`

```python
re.finditer(r"R-07[^.\n|]{0,60}?\b(?:is|stays|remains)\s+\*{0,3}"
            r"(?:OPEN|NOT\s+CONTAINED|UNCONTAINED)\b", text, re.I)
```
Corpus: **discovered** (`_live_authority_documents()` → 57 docs). Exemptions: `_EXEMPT`
(conditional prose) and `_is_superseded_in_place()` (quoted / same-line marker).

**Guard B** — `eval/tests/test_docs_control_system.py::test_10_r07_is_recorded_open_and_never_contained`

```python
re.finditer(r"R-07[^\n]{0,60}?\b(?:is|stays|remains)\s+\*{0,3}OPEN\b", text, re.I)
```
Corpus: **hard-coded 4-tuple** `(CURRENT, CLAUDE, ARCHITECTURE, README)`. Note it omits
`NOT CONTAINED` / `UNCONTAINED` from its alternation entirely.

### 4.2 Structural parsing, or narrow word order?

**Narrow word order — and worse than the reviewer characterised it.** The requirement is not
merely that the verb *follow* `R-07`; it is that a copula from the **closed three-verb set**
`{is, stays, remains}` be **present at all**. The repository's canonical status rows are written
copula-free, in markdown table cells, using an em-dash:

```
| **Current risk** | ### **R-07 — OPEN, NOT CONTAINED.** … |
```

There is no verb, so neither guard can ever see it. **The guard is structurally blind to the exact
grammar the canonical control document uses for status rows** — while the *updated* row at line
224 happens to read "R-07 **is** CONTAINED", with a verb. The document's two status rows are
written in two different grammars and only one is reachable. Neither guard performs any structural
or semantic parse of a status claim.

### 4.3 Does it positively prove the corpus and documents are non-empty?

**Partially — Guard A yes, Guard B no.**

* Guard A asserts `docs` non-empty, `len(out) >= 15`, and `scanned >= 5`, and additionally asserts
  the manifest reads `CONTAINED`. Corpus non-vacuity **is** positively proved (57 documents).
* Guard B's corpus is hard-coded, so it cannot collapse — but it also cannot **grow**. It never
  reaches `LEGACY-DISPOSITION.md` or any agent lens. It does make a positive per-document
  assertion (each of its 4 must match `R-07.{0,200}CONTAINED` and state the CONTAINED≠ENABLED
  bound), which is genuine non-vacuity for those four only.

**Neither guard proves the *relevant* documents are non-empty** — which is the property that
matters, and precisely the gap through which all five defects passed.

### 4.4 Does it detect the equivalent stale forms? — mechanically tested

| Form | Guard A | Guard B | Detected |
|---|---|---|---|
| `R-07 remains open` | ✔ | ✔ | yes |
| `R-07 is open` | ✔ | ✔ | yes |
| `R-07 stays uncontained` | ✔ | ✘ | yes |
| **`keeps R-07 open`** | ✘ | ✘ | **NO** |
| **`leaves R-07 open`** | ✘ | ✘ | **NO** |
| **`R-07 not contained`** | ✘ | ✘ | **NO** |
| **`does not contain R-07`** | ✘ | ✘ | **NO** |
| **`R-07 — OPEN` (table cell)** | ✘ | ✘ | **NO** |
| **`R-07: OPEN`** | ✘ | ✘ | **NO** |
| **`R-07 still OPEN`** | ✘ | ✘ | **NO** |
| **`R-07 was never contained`** | ✘ | ✘ | **NO** |
| **live defect `:425`** | ✘ | ✘ | **NO** |
| **live defect `:44`** | ✘ | ✘ | **NO** |

**Four of the six forms named in the adjudication brief are missed. Eight of twelve tested forms
are missed. The guard detects 0 of the 5 live defects while the suite reports green.**

### 4.5 Structured parsing or another substring expression?

**Structured / bounded-normalized semantic matching is required.** A third substring alternation
would be the same defect a third time — ADJ-01 was itself raised to fix "regex does not reach the
corpus", and F-01 is that defect recurring *inside the remediation for it*. The remediation must:

1. **Extract status claims structurally** — for markdown control documents, parse table rows and
   evaluate the `Current risk` / status cells as claims about a subject, rather than scanning raw
   prose for a verb;
2. **Normalize before matching** — collapse whitespace and markdown emphasis so line-wrapped and
   `**`-decorated constructions cannot escape, as `test_switch_consistency._live_text` already
   does;
3. **Match on polarity, not word order** — treat `R-07` and an OPEN/NOT-CONTAINED token within a
   bounded window as a claim regardless of which side the verb falls on, or whether one exists;
4. **Unify the two corpora** — Guard B's hard-coded 4-tuple must become the discovered population,
   or explicitly justify each exclusion;
5. **Positively prove per-document reach** — assert that the specific canonical control documents
   (`LEGACY-DISPOSITION.md`, the agent lenses) are in the scanned set, so a future corpus change
   cannot silently drop them.

### 4.6 Must hostile tests reintroduce the exact LEGACY-DISPOSITION failure?

**Yes — and not only that one.** The battery must reintroduce, and prove CAUGHT:

* the exact `:425` string *"(it keeps R-07 OPEN)"*;
* the exact `:44` table-cell string *"R-07 — OPEN, NOT CONTAINED"* (the copula-free form);
* the exact `:428` residual-count string;
* `principal-architect-supervisor.md:53`'s *"R-07 still recorded OPEN"*;
* `:75`'s *"an open R-07"*;
* each of the four brief-named forms currently missed.

A mutation case that a guard cannot catch must fail as MISS, not be quietly re-anchored.

### **F-02 conclusion: BLOCKING.** Confirmed, and the defect is structural blindness, not word order.

---

## 5. F-03 — EVIDENCE DOCUMENTS ARE NOT HASH-BOUND — **BLOCKING**

### 5.1 Which reports the containment record relies upon

`expected_legacy_paths.containment_evidence` cites, and
`test_r07_containment_record_holds_only_while_its_mechanical_conditions_hold` §(5) requires, five
documents:

| Key | Required digest | Worktree file hashes to |
|---|---|---|
| `accepted_independent_rereview` | `181e1a37…d316` | `66038843…` ✘ |
| `final_adjudication` | `078cfea8…997e` | `078cfea8…` ✔ |
| `accepted_targeted_independent_review` | `5547aa5e…8ea5` | `d8a39191…` ✘ |
| `accepted_targeted_adjudication` | `23496e6c…9567` | `23496e6c…` ✔ |
| `second_finalization_report` | `96ef5fe8…1fa0` | `96ef5fe8…` ✔ |

Plus, for this cycle, the targeted review of `11c9112` itself (`1659338a…`, preserved only at
`refs/preserve/*`).

### 5.2 Does the canonical containment guard verify the chain?

| Property | Verified? |
|---|---|
| Report existence | **YES** — `assert (ROOT / named.group(0)).exists()` |
| Exact expected SHA-256 | **NO** — asserts only that the digest **string occurs in the manifest text**; never recomputes the file's hash |
| Sidecar correctness | **NO** — no test in `eval/` reads any `.sha256` file |
| Preservation ref | **NO** |
| Preservation parent | **NO** |
| Preserved blob equality | **NO** |
| Candidate attribution | **NO** |

Independently confirmed by exhaustive search: no `eval/tests/*.py` opens a `.sha256` sidecar, and
all 8 sidecars under `docs/implementation/` are unverified by any guard. **The chain is bound at
the citation level, never at the content level.** A valid sidecar sitting on disk is not
verification — nothing reads it.

### 5.3 Decisive reproduction

In a disposable clone at the exact candidate tree `9a3950b5…`, I flipped the verdict inside
`docs/implementation/p4-final-adjudication-report-0891d1a.md`:

```
**Verdict: ACCEPT P4 FOR FINALIZATION**  →  **Verdict: REJECT P4 FOR FINALIZATION**
# ACCEPT P4 FOR FINALIZATION            →  # REJECT P4 FOR FINALIZATION
```

* file hash `078cfea8…997e` → `610d471b…3dc3`; sidecar left stale;
* evidence-guard subset: **160 passed, 2 skipped, 0 failed** (the 2 skips are dirty-tree artifacts
  of the method, not detections);
* **full canonical suite: 1957 passed, 4 failed, 3 skipped** — and all 4 failures reproduce
  identically on the untampered tree (environmental CLI smoke tests, §2).

**The repository accepts a load-bearing adjudication whose recorded verdict has been inverted, and
reports green.**

### 5.4 Can mutable worktree prose substitute for the accepted preserved evidence?

**Yes, today — and this is already the live condition, not a hypothetical.** Two of the five
required documents (`accepted_independent_rereview`, `accepted_targeted_independent_review`)
**already** hash to values different from the digests the containment record cites, and every
guard is green. The originals survive byte-exact at `refs/preserve/*` (§6), so the accepted
evidence is not *lost* — but the in-tree copies the guard's existence-check points at are **not**
the accepted bytes, and nothing detects the difference between benign divergence and tampering.

### 5.5 A constraint the remediation must respect

A naive `sha256(worktree file) == sidecar` guard **cannot** be the fix: it would fail immediately
on three documents **by design**. `test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale_claim`
*requires* historical evidence documents to carry a disarming banner, which necessarily changes
their bytes. The correct binding target is therefore the **preserved blob at the named
`refs/preserve/*` ref**, not the worktree rendering. The reviewer's proposed remediation already
states this correctly and should be adopted.

### 5.6 Can `11c9112` be finalized without mechanically binding load-bearing evidence?

**No.** The candidate's own record asserts durability — *"a re-pointed guard fails the build … if
any evidence element is missing or mismatched"*. That claim is **not mechanically true** for
document content. Finalizing would make an unbacked tamper-evidence claim authoritative.

### 5.7 Minimum report set that must be hash-bound

1. `p4-independent-rereview-report-0891d1a.md` → `181e1a37…`
2. `p4-final-adjudication-report-0891d1a.md` → `078cfea8…`
3. `p4-closure-candidate-targeted-review-report-42ea24c.md` → `5547aa5e…`
4. `p4-closure-candidate-targeted-adjudication-report-42ea24c.md` → `23496e6c…`
5. `p4-second-finalization-pass-report-06ebfdb3.md` → `96ef5fe8…`
6. the fresh targeted review of the replacement candidate
7. the fresh targeted adjudication of the replacement candidate

Each bound as: **worktree hashes to the recorded digest, OR a byte-exact original hashing to it
exists at the named `refs/preserve/*` ref** — failing if neither holds; plus an assertion that the
sidecar population is non-empty.

### 5.8 Required hostile cases

All six named in the brief must be proven CAUGHT: ACCEPT→REJECT flip fails; candidate hash changed
fails; sidecar changed fails; worktree report differs from preserved blob **with no valid preserve
original** fails; preservation parent mismatch fails; missing report or missing sidecar fails.

### **F-03 conclusion: BLOCKING.**

---

## 6. REVIEWER CORRECTIONS — BOTH CONFIRMED, NEITHER CONVERTED INTO A DEFECT

**(a) The three sidecar mismatches are disclosed banner conventions.** **Confirmed.**

| Document | Sidecar | Worktree | Preserved blob |
|---|---|---|---|
| `p4-closure-candidate-targeted-review-report-42ea24c.md` | `5547aa5e…` | `d8a39191…` | **`5547aa5e…` ✔ exact** |
| `p4-independent-rereview-report-0891d1a.md` | `181e1a37…` | `66038843…` | **`181e1a37…` ✔ exact** |
| `p4-closure-candidate-targeted-review-handoff-42ea24c.md` | `9c5cc187…` | `a70f4dc5…` | `83081a1e…` at `c30a43be` |

The third initially appeared to match nothing. It resolves benignly: `9c5cc187…` is the blob's
exact hash at prestate `3cac4d0` and at `d2ae8f4`; `11c9112` added the disarm banner without
re-cutting the sidecar. **And the banner says so explicitly, in the file:**

> **THE SIDECAR HASH IS THE ORIGINAL'S, DELIBERATELY.** … records
> `9c5cc18793117c9d37f7014ed910e8a6ab34e806dd25b6b8bc0fd24559237e87`, the SHA-256 of the file
> **without** this banner… The sidecar authenticates the handoff, not the in-tree rendering of it.

This is a **disclosed, guard-driven convention**, not drift. The reviewer's correction is upheld in
full and charged against nothing. (The handoff is not among the five `REQUIRED_DOCUMENTS`.)

**(b) The initial H-03 MISS was the reviewer's own probe-scoping error.** **Confirmed.** The
live-vs-recorded disagreement edge is caught by `eval/tests/test_phase0_adapter_imports.py`, and
the delivered report already records H-03 as **CAUGHT** with that attribution. The self-correction
landed. **No product defect exists here**, and none is recorded.

---

## 7. F-04 THROUGH F-07 — INDIVIDUALLY ADJUDICATED

| # | Finding | Adjudication |
|---|---|---|
| **F-04** | ADJ-01's "nothing narrowed" claim inaccurate — bound changed `[^\n]{0,80}` → `[^.]{0,80}` | **NON-BLOCKING.** A truthfulness defect in a commit-message/docstring claim, not a guard weakness that admits a false green. Carry; correct the claim or restore sentence-crossing coverage during remediation. |
| **F-05** | `_is_superseded_in_place` quote-parity is file-tail fragile | **NON-BLOCKING today, but see below.** I re-verified: **0 of 57** live-authority documents have odd quote parity. Latent, not live. |
| **F-06** | `production_reachable_live_write_remaining: 2 → 1` unbound by any guard | **NON-BLOCKING.** Confirmed unguarded. Note it is **not inert**: the stale "six production-reachable live-write paths" at `principal-architect-supervisor.md:75` is the same quantity gone stale on a canonical surface (F-01 #5). Bind it or annotate it as unbound narrative. |
| **F-07** | M4/M11 SKIP-INVALID | **NON-BLOCKING — INFORMATIONAL.** Independently confirmed pre-existing at `06ebfdb3`, honestly recorded as CB-01. No action owed by this candidate. |

### Do they become blocking cumulatively?

**No — none is promoted to blocking, and the verdict does not rest on them.** But one cumulative
observation is recorded: **F-05 + F-02 mean the documentation-consistency control has two
independent evasion paths** — a pattern that cannot see the corpus's grammar (F-02, *live*), and an
exemption that can invert for an entire file tail on one stray quote (F-05, *latent*). Remediating
F-02 alone leaves the second path open. F-05 should be fixed **in the same pass**, bounded to a
single line, not deferred — not because it blocks, but because it is the cheapest moment to close
the pair.

---

## 8. CONTAINMENT VERSUS EVIDENCE — THE FOUR QUESTIONS SEPARATED

| # | Question | Answer |
|---|---|---|
| **1** | Is the R-07 containment **mechanism** technically valid? | **YES.** Structural, not test-derived: an external effect requires an effect-capable adapter; the sole application-layer importer is `effect_boundary`; the CI import gate fails the build if a second appears, live and recorded both-sided; inside the boundary the only external-write path is `execute_invoice_write` behind checkpoint/witness/grant/atomic-claim; anything else REFUSES. 0 live / 0 recorded edges over a proven non-empty 152-file corpus. Runtime byte-identical to `0891d1a`. |
| **2** | Is the canonical containment **record internally consistent**? | **NO.** Five unmarked live claims across two canonical surfaces contradict it — including the `Current risk` row of the section titled "THE R-07 SURFACE", and an operative instruction to an adjudicating agent. |
| **3** | Is the evidence chain **mechanically tamper-evident**? | **NO.** Proven: an inverted adjudication verdict leaves 1957 tests green. No sidecar is read by any guard. Two of five required documents already diverge from their cited digests. |
| **4** | Is `11c9112` **eligible for finalization**? | **NO.** |

### Does repository authority permit finalizing a valid mechanism with insufficient controls?

**It does not.** Three independent reasons:

1. **The doctrine is explicit.** `phase-0-baseline-manifest.yaml`'s own rule — asserted by
   `test_no_allowance_section_may_be_read_as_containment` — is that *"an allowance is never
   containment, and discipline is never a mechanism."* The mirror of that rule applies here: a
   valid mechanism whose record is contradicted and whose evidence is unbound is being held
   together by **discipline** — the good faith of every future reader and agent — and this
   repository has ruled, repeatedly and in writing, that discipline is not a control.
2. **The record makes a claim that is not true.** `11c9112` asserts that a re-pointed guard fails
   the build "if any evidence element is missing or mismatched." §5.3 falsifies that. Finalization
   would make an unbacked tamper-evidence claim authoritative and at-rest.
3. **This is the commit's own charter.** The candidate exists to close R-07 *and* "restore
   canonical documentation consistency." F-01 and F-02 are failures of the commit's stated
   purpose, not out-of-scope defects inherited from elsewhere. The targeted adjudication of
   `42ea24c` already made this exact defect class (F-TR-01…F-TR-04) **binding on this commit**.

**Containment is real. The controls that make it durable and auditable are not yet sufficient. The
repository's own standard forbids finalizing that combination.**

---

## 9. TOPOLOGY AND THE NARROWEST LEGAL REMEDIATION PATH

### 9.1 A second consecutive content commit is mechanically ILLEGAL — proven, not asserted

`eval/tests/test_status_reality.py::repo_state()` recognises exactly three legal states:

| State | Condition |
|---|---|
| `BASELINE` | recorded == `HEAD` |
| `FINALIZED` | recorded == `HEAD^`, top commit touched only `STATUS_METADATA_FILES` |
| `PRODUCING` | recorded == `HEAD^^`, `HEAD^` a pure status-metadata commit, `HEAD` the content commit |

Anything else raises. Today: recorded `42ea24c` == `HEAD^^` → **`PRODUCING`** ✔.

**Experimental proof.** In a disposable clone I committed one additional content commit above
`11c9112`. Result:

```
AssertionError: CURRENT.md records 42ea24cf but HEAD is 321ea63e -
the status authority is stale beyond every legal state.
```

The guard's own docstring names the case: *"it is two unfinalized content commits, which the
convention forbids."* **The status-reality guard does not permit it.** Option D is closed.

### 9.2 A finalizer cannot repair F-01

`STATUS_METADATA_FILES` contains exactly ten paths. **`docs/implementation/LEGACY-DISPOSITION.md`
is not one of them, and neither is `phase-0-baseline-manifest.yaml` nor any agent lens** (verified
by direct import). A finalizer that wrote them would be caught by `repo_state()`'s stray-file
assertion. F-01 is therefore reachable **only** by a content commit.

### 9.3 The four options adjudicated

| Option | Legal? | Adjudication |
|---|---|---|
| **A. Replace/amend `11c9112`, parent `06ebfdb3`** | **YES** | **REQUIRED.** Preserves exactly one content commit above the metadata commit; keeps `PRODUCING`; reaches every offending path. |
| **B. Evidence-only `refs/preserve/*` artifact** | Legal, but **insufficient** | A preserve ref is off-branch and changes no tracked content, so it cannot correct the five false claims (F-01) or re-point the guards (F-02). It cannot discharge F-03 either: the binding guard must live **in** the suite. Rejected as a complete remedy. |
| **C. Finalize first, correct later** | Topologically legal, **governance-prohibited** | Finalization is precisely the act that makes the record authoritative. Entering the at-rest state carrying five known-false canonical claims and an unbound evidence chain is the false green this phase exists to prevent. Rejected. |
| **D. Second consecutive content commit** | **NO** | Mechanically forbidden (§9.1). Rejected. |

**Neither `git commit-tree` nor `update-ref` may be used to manufacture a topology the
status-reality guard would reject.** The guard is the authority; a hand-built object that evades it
is a bypass, not a remediation.

### 9.4 Replacement specification

| Item | Value |
|---|---|
| **Exact old candidate** | `11c911244304d56737913db41b458d5f3278bc80` (tree `9a3950b5…`) |
| **Required preservation ref** | `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` — must pin the **rejected** candidate before it is replaced |
| **Also preserved** | `refs/preserve/p4-r07-closure-targeted-review-11c9112` (`fa4c459b…`) and this adjudication — already durable; **must not be moved or overwritten** |
| **Certified parent** | `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` — unchanged |
| **Resulting topology** | `06ebfdb3 → <replacement>` — exactly one content commit; state stays `PRODUCING` |

**Allowed changed paths** (relative to `11c9112`; nothing else may move):

* `docs/implementation/LEGACY-DISPOSITION.md` — §S1 line 44 row (and the stale `Target phase` /
  `Deletion condition` rows at 47–48), §S15a lines 425 and 428
* `.claude/agents/principal-architect-supervisor.md` — lines 53 and 75
* `eval/tests/test_roadmap_completeness_control.py` — Guard A restructured (F-02); `_is_superseded_in_place` line-bounded (F-05, same pass)
* `eval/tests/test_docs_control_system.py` — Guard B corpus and alternation (F-02)
* one guard file (new or existing) carrying the evidence-binding guard (F-03)
* `scripts/mutate_roadmap_completeness.py` — hostile cases for §4.6 and §5.8
* `docs/implementation/TEST-NODE-MANIFEST.json` — regenerated **only** through
  `scripts/regenerate_test_manifest.py`
* `docs/implementation/phase-0-baseline-manifest.yaml` — only if the evidence-binding remediation
  requires a recorded ref/parent alongside each digest

**Prohibited:** any byte under `src/`, `configs/`, `data/`; `SUITE-RESULT.json`; `GATE-RESULT.json`;
any registry status field; any weakening of an existing assertion; any edit to a preserved
evidence blob; any P5 work.

**A completely fresh targeted independent review is required** of the replacement candidate, by a
session that did not implement P4, did not author either candidate, did not perform this
adjudication and has not run a finalizer — followed by its own separate targeted adjudication.

**The current conditional review remains attributable ONLY to `11c9112`.** It reviewed tree
`9a3950b5…` and nothing else. It may not be re-cited, re-pointed or carried forward as evidence
for any replacement, and its preserve ref must remain exactly where it is, parented to
`11c9112`.

---

## 10. FINALIZER AUTHORIZATION

### **NOT AUTHORIZED. No third finalizer may run on `11c9112`.**

Technical validity of containment is **not** sufficient grounds, and is expressly not the basis on
which authorization is withheld or granted.

| Element | Status for `11c9112` |
|---|---|
| Exact candidate and tree | `11c9112…` / `9a3950b5…` — verified |
| Accepted review report and hash | `1659338af138…9222` — verified, but verdict is **CONDITIONAL**, not ACCEPT |
| Evidence-binding status | **NOT BOUND** (F-03) |
| Documentation-consistency status | **INCONSISTENT** — 5 live false claims, 2 surfaces (F-01) |
| R-07 status | **CONTAINED — mechanism valid; record contradicted; evidence unbound** |
| P4 / P5 status | P4 COMPLETE 100/100; P5 sole READY, NOT_STARTED — both verified and unaffected |
| Residual risks | RR-01 (binding, undischarged P12 precondition), AD-01, AD-02, RR-02…RR-06, F-03, F-06…F-10, CB-01, PD-01 — carried, none discharged here |

**Prerequisites for the one permitted third finalizer** — all must hold on the **replacement**
candidate, in order:

1. F-01 remediated at **all five** locations, corrected or same-line-marked historical.
2. F-02 remediated by structured / bounded-normalized matching, both corpora unified and
   per-document reach positively proved; every §4.4 form and every §4.6 hostile case CAUGHT.
3. F-03 remediated by a guard binding the §5.7 minimum set to preserved-blob-or-worktree equality;
   all six §5.8 hostile cases CAUGHT.
4. F-05 closed in the same pass (line-bounded quote exemption).
5. No runtime byte changed; `src/`/`configs/`/`data/` still tree-identical to `0891d1a`.
6. Topology exactly `06ebfdb3 → <replacement>`; `repo_state()` == `PRODUCING`.
7. Rejected candidate `11c9112` and its review preserved and immovable.
8. A **fresh** targeted independent review returning unconditional ACCEPT, and a **separate**
   fresh targeted adjudication authorizing exactly one finalizer.
9. Canonical suite and clean-clone gate green on the replacement tree with exact node identity;
   working tree clean; finalizer lock free.

Until all nine hold, `scripts/finalize_status.py` must not run.

---

## 11. VERDICT

### REJECT — TARGETED REMEDIATION REQUIRED

**R-07 containment is real.** The mechanism is structural rather than test-derived, the runtime is
byte-identical to the accepted implementation candidate, no finalizer receipt was forged, P4 is
COMPLETE at 100/100, P5 is the sole READY unit and NOT_STARTED, P6–P14 are BLOCKED, the production
`GateRegistry` is empty over a proven non-empty corpus, and the Phase-8 deferral is intact. None of
that is disturbed by this rejection, and the complete P4 runtime is not reopened.

**The candidate is rejected on its controls, not its containment**, and on findings materially
wider than the targeted review reported:

* **F-01 — BLOCKING.** Five unmarked live false R-07 status claims across **two** canonical
  surfaces, not two claims on one. Includes the `Current risk` row of the section titled "THE R-07
  SURFACE", and an operative instruction telling an adjudicating agent to require R-07 to be
  recorded OPEN. The reviewer's "Change nothing else" remediation is insufficient and must not be
  followed as written.
* **F-02 — BLOCKING.** The replacement guard requires a copula from a closed three-verb set to
  follow `R-07`, making it structurally blind to the repository's own canonical status-row grammar.
  It misses 8 of 12 tested forms, 4 of the 6 named in the brief, and **0 of 5** live defects are
  caught while the suite reports green.
* **F-03 — BLOCKING.** Reproduced at full-suite scale: an inverted adjudication verdict leaves
  **1957 tests passing**. No guard reads any sidecar. Two of five required evidence documents
  already diverge from their cited digests.

**F-04 through F-07 are non-blocking individually and do not become blocking cumulatively**;
F-05 should nonetheless be closed in the same pass as F-02.

**Both reviewer self-corrections are upheld and neither is converted into a product defect:** the
three sidecar mismatches are disclosed, guard-driven banner conventions whose originals remain
byte-exact at preserve refs, and the initial H-03 MISS was the reviewer's own probe-scoping error,
already corrected in the delivered report.

**Narrowest legal remediation:** replace `11c9112` in place against certified parent `06ebfdb3`,
preserving the rejected candidate and its review under immovable `refs/preserve/*` refs, within
the allowed path set of §9.4. A second consecutive content commit is mechanically forbidden and a
finalizer cannot reach the defect.

This adjudication finalizes nothing, remediates nothing, moves no branch, and authorizes no P5
work. **No finalizer is authorized on `11c911244304d56737913db41b458d5f3278bc80`.**

---

## 12. PRESERVATION RECORD

| Item | Value |
|---|---|
| Report path | `docs/implementation/p4-r07-closure-candidate-targeted-adjudication-report-11c9112.md` |
| Sidecar | `docs/implementation/p4-r07-closure-candidate-targeted-adjudication-report-11c9112.md.sha256` |
| Preservation ref | `refs/preserve/p4-r07-closure-targeted-adjudication-11c9112` |
| Preservation parent | `11c911244304d56737913db41b458d5f3278bc80` (exactly the candidate) |
| Adjudicated candidate | `11c911244304d56737913db41b458d5f3278bc80`, tree `9a3950b5ffecaaa551b803059eb92b8760aac8f3` |
| Branch after | `p4/adapter-containment-completion` → `11c9112…` (unmoved) |
| Candidate tree after | `9a3950b5…` (unchanged) |
| Primary index after | unchanged (a temporary `GIT_INDEX_FILE` was used) |
| Earlier reports | none overwritten; `refs/preserve/p4-r07-closure-targeted-review-11c9112` untouched |
| Pushed | nothing |

*(Report SHA-256, preservation commit and the post-state proofs are recorded in the preservation
commit message and in the sidecar — a document cannot contain its own digest.)*
