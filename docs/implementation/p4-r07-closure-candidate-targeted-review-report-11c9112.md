# P4 R-07 CLOSURE CANDIDATE — FRESH TARGETED INDEPENDENT REVIEW

**Candidate:** `11c911244304d56737913db41b458d5f3278bc80`
**Tree:** `9a3950b5ffecaaa551b803059eb92b8760aac8f3`
**Parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (second-finalizer metadata commit)
**Branch:** `p4/adapter-containment-completion`
**Subject:** Record R-07 CONTAINED and restore canonical documentation consistency

**Reviewer standing.** This session did not implement P4, did not author the R-07 closure
candidate, did not perform either prior review or adjudication, did not run either finalizer, and
did not reconstruct the second-finalization report. No previous session was resumed. Nothing was
remediated, adjudicated, finalized, pushed, or enabled.

**Review environment.** A disposable `git clone --no-local` at
`/private/tmp/.../scratchpad/review-clone`, checked out detached at the candidate, plus a second
disposable clone (`.../scratchpad/hostile`) used exclusively for mutation probes. The primary
worktree was never used for review and was never written.

---

## VERDICT

### CONDITIONALLY ACCEPT — EVIDENCE REMEDIATION REQUIRED

The R-07 containment **mechanism** is real, correctly described, and independently proven. The
record is honest about what containment is and is not. Runtime is byte-identical to the accepted
implementation candidate. No finalizer receipt was forged. P4/P5 state is exactly as claimed.

Three findings block acceptance as-is. **None of them falsifies containment.** All three are
documentation- and evidence-integrity defects of exactly the class this commit exists to close:

* **F-01** — a canonical control document still carries an unmarked, factually false live claim
  that the write half is present and "keeps R-07 OPEN", and that four violation residuals remain.
* **F-02** — the replacement R-07 guard cannot catch F-01's phrasing; it is the same
  regex-does-not-reach-the-corpus defect that ADJ-01 was raised to fix.
* **F-03** — cited evidence documents are not bound to their hashes. An adjudication verdict inside
  a cited document can be flipped from ACCEPT to REJECT with 153 guards staying green.

---

## 1. TOPOLOGY, OWNERSHIP AND CUSTODY — ALL VERIFIED

| Check | Result |
|---|---|
| Commit / tree / parent resolved from Git | `11c91124` / `9a3950b5` / `06ebfdb3` — exact |
| Exactly one content commit above the second finalizer | **CONFIRMED.** `06ebfdb3` has three children: `99f0e59d` and `3cac4d0e` (both `refs/preserve/*`) and `11c9112`. Only `11c9112` is a content commit |
| No second consecutive content commit | **CONFIRMED** — `git rev-list --all --children` shows no child of `11c9112` |
| Branch containment | `p4/adapter-containment-completion` only |
| Finalizer lock | `.git/neyma-finalizer.lock` — **UNHELD** (`flock LOCK_EX\|LOCK_NB` acquired); no holder via `lsof` |
| Builder worktree lock | `.git/neyma-builder-worktree.lock` — **UNHELD** |
| Protected refs | `refs/heads/main` and `refs/remotes/origin/main` both `152574e4` at review start and end — unmoved |
| Nothing pushed | **CONFIRMED against the real remote.** `git ls-remote origin` lists only `add-claude-github-actions-…`, `demos`, `main`, `p3/checkpoint-witness`, `recovery/u2-6bc-atomic-cutover`. No candidate, no `p4/adapter-containment-completion`, no `refs/preserve/*` |
| Candidate unchanged since creation | HEAD, HEAD-tree and primary index all `9a3950b5` at start and end; reflog head still the candidate commit |

---

## 2. EVIDENCE CHAIN — READ AND VERIFIED

Every cited document was recomputed from the candidate tree.

| Evidence | Sidecar/manifest digest | Recomputed | Status |
|---|---|---|---|
| `p4-final-adjudication-report-0891d1a.md` | `078cfea8…c997e` | `078cfea8…c997e` | **MATCH** |
| `p4-closure-candidate-targeted-adjudication-report-42ea24c.md` | `23496e6c…99567` | `23496e6c…99567` | **MATCH** |
| `p4-second-finalization-pass-report-06ebfdb3.md` | `96ef5fe8…a1fa0` | `96ef5fe8…a1fa0` | **MATCH** |
| `p4-independent-rereview-report-0891d1a.md` | `181e1a37…5d316` | `66038843…c274f` | **DIVERGES — disclosed, legitimate** |
| `p4-closure-candidate-targeted-review-report-42ea24c.md` | `5547aa5e…a8ea5` | `d8a39191…7bf28` | **DIVERGES — disclosed, legitimate** |
| `p4-closure-candidate-targeted-review-handoff-42ea24c.md` | `9c5cc187…37e87` | `a70f4dc5…f77f3` | **DIVERGES — disclosed, legitimate** |

The three divergences are the repository's deliberate banner convention, and the disclosure is
**truthful**, which I verified rather than accepted:

* Each bannered file states in-band that the sidecar is the pre-banner original's hash.
* The byte-exact originals live at preserve refs and hash to the claimed values exactly:
  `refs/preserve/p4-independent-rereview-0891d1a` → `181e1a37…`,
  `refs/preserve/p4-closure-targeted-review-42ea24c` → `5547aa5e…`,
  `refs/preserve/p4-r07-closure-prestate-06ebfdb3` → `9c5cc187…`.
* Stripping exactly the banner (36 and 35 lines respectively) reproduces the preserved original
  **byte-for-byte** — no deletion, edit or reordering below the banner.

**Preservation topology verified.** Each review/adjudication preserve commit adds only its report
and sidecar, with its parent the exact commit reviewed:
`p4-independent-rereview-0891d1a` and `p4-final-adjudication-0891d1a` → parent `0891d1a`;
`p4-closure-targeted-review-42ea24c` and `p4-closure-targeted-adjudication-42ea24c` → parent
`42ea24c`; `p4-second-finalization-report-06ebfdb3` (`99f0e59d`) → parent `06ebfdb3`, adding only
the reconstructed report and its sidecar.

**Reconstructed-report attribution is honest.** The preserve commit message and the manifest's
`second_finalization_report` block both state plainly that it is a post-hoc reconstruction by a
session that did not execute the finalizer, that it may be cited only for facts independently
established by Git objects and receipts, and that PID and driver run/session IDs were
`[UNAVAILABLE]` and may not be invented. The candidate copy is byte-identical to the preserved copy.
It is **not** represented as contemporaneous finalizer testimony.

---

## 3. R-07 CONTAINMENT RECORD — SUBSTANTIALLY CORRECT

`docs/implementation/phase-0-baseline-manifest.yaml`, `expected_legacy_paths`:

* `status: CONTAINED` — the repository-authorized spelling, asserted literally by
  `test_r07_containment_record_holds_only_while_its_mechanical_conditions_hold`.
* Prior `OPEN - NOT CONTAINED` changed through the content-owned record; the file is not a
  `STATUS_METADATA_FILE`, so no finalizer could have written it. Correct.
* The superseded sentence is quoted in place, and the permanent rule ("discipline is never
  containment") is retained and separately asserted.

**Every cited fact independently recomputed:**

| Claim | Independent verification |
|---|---|
| implementation candidate `0891d1a` | matches; runtime trees identical (§5) |
| first finalizer `86306d5`, closure candidate `42ea24c`, second finalizer `06ebfdb3` | all resolve; receipts still bind `42ea24c`/`1e2bba79` |
| canonical suite 1961/0/1/1962 | matches `SUITE-RESULT.json` for `42ea24c` |
| clean-clone PASS | **reproduced on the candidate** — gate run: PASS, 1963/0/1/1964 |
| violation edges 0 live / 0 recorded | **recomputed**: `effect_adapter_violation_edges()` = `set()`; manifest `violation_edges: []`; sets agree |
| detection count 13 | **recomputed**: 13 live adapter import edges; manifest records 13; **exact set match**, no recorded-not-live, no live-not-recorded |
| callback socket tests 34 | `test_action_callback.py` collects **34** |
| production GateRegistry EMPTY | **AST sweep over 152 files in `src/` + `scripts/`**: 0 `GateRegistry()` constructions, 0 `register_gate` calls |
| Phase-8 deferral intact | `AC-CKPT-6-missing` `DEFERRED_BY_DEPENDENCY`, `green_at_phase P8`; `kernel_factory = None` at `run_action_callback_server.py:366` |
| production default `ROUTE_NOT_CONFIGURED` | `action_callback.py:662` refusal path present |
| no reachable legacy callback→actuator path | **AST-proved**: `run_action_callback_server.py` has 0 `CdpActuator` constructions, 0 `cdp_actuator` imports; `_build_live_operation_router`/`_build_agent` no longer exist |

**The mechanism is described as a mechanism, not as a test result** — effect-capable adapter →
sole application importer `effect_boundary` → CI import gate failing both-sided → sole write path
`execute_invoice_write` behind checkpoint/witness/grant/atomic claim, refusing rather than falling
back. This matches the code.

**Containment is not equated with enablement.** The record states explicitly and repeatedly that
CONTAINED is not production enablement, not a registered gate, and not autonomy of any kind. No
rejection ground here.

---

## 4. HOSTILE PROBE BATTERY — 18/18 CAUGHT, 0 MISS

Run in the disposable sandbox; every case restored and byte-exactness verified after each
(final tracked tree recomputed to `9a3950b5…`, exact).

| # | Hostile case | Result |
|---|---|---|
| H-01 | one LIVE violation edge introduced (unrecorded cut) | **CAUGHT** |
| H-02 | one RECORDED violation edge introduced (not real) | **CAUGHT** |
| H-03 | live vs recorded surfaces disagree | **CAUGHT** (`test_phase0_adapter_imports.py`) |
| H-04 | production GateRegistry populated before Phase 8 | **CAUGHT** |
| H-05 | Phase-8 deferral removed/weakened | **CAUGHT** |
| H-06 | direct callback→actuator path restored | **CAUGHT** |
| H-07 | implementation review evidence removed | **CAUGHT** |
| H-08 | adjudication evidence removed | **CAUGHT** |
| H-09 | second-finalizer evidence mismatched | **CAUGHT** |
| H-10 | candidate/tree binding changed | **CAUGHT** |
| H-11 | reconstructed report hash mismatched *(manifest side)* | **CAUGHT** |
| H-12 | R-07 CONTAINED with evidence block removed | **CAUGHT** |
| H-13 | P5 implementation begun | **CAUGHT** |
| H-14 | zero READY units | **CAUGHT** |
| H-15 | two READY units | **CAUGHT** |
| H-16 | selected-READY prose disagrees with registry | **CAUGHT** |
| H-17 | R-07 shown OPEN in live authority | **CAUGHT** |
| H-18 | manifest R-07 reverted to OPEN | **CAUGHT** |

**Corpus non-emptiness positively proved for every negative assertion:** 152 Python files parsed
for the GateRegistry sweep; 152 files / 13 import sites for the edge sweep; 57 live-authority
documents; 18 registry units; 8 sidecars; 1964 collected test nodes. No probe passed over an empty
population.

**H-11 caveat — see F-03.** H-11 proves the *manifest* cannot cite a wrong hash. It does **not**
prove the cited *document* matches its hash. That gap is F-03.

---

## 5. IMPLEMENTATION BYTE-EQUALITY — PROVED

Tree-object identity against accepted implementation candidate
`0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e`:

```
src      0204261b17baecd2bab3dc1b7d25a7494eb3b22d   IDENTICAL
configs  124ae4bcbbec96cc0ff9282d183d7c97aa1914f5   IDENTICAL
data     8d02102277273f6858ce15d3753002e7875bb9df   IDENTICAL
```

This covers, by construction, the governed approval/write route, checkpoint/witness/grant/claim
machinery, browser-use boundaries, origin policy, adapters, production GateRegistry code, and all
configuration and data surfaces affecting runtime behaviour.

`0891d1a → 11c9112` full path diff touches **no** runtime file. The only `scripts/` change is
`mutate_roadmap_completeness.py` — evidence infrastructure, never imported by runtime — where M1
and M3 anchors were re-pointed because this commit legitimately moved their target text. I
reproduced the battery: **9/11 CAUGHT, 2 SKIP-INVALID, 0 MISS**, exactly as claimed, and confirmed
both SKIP-INVALID anchors (M4, M11) were **already absent at `06ebfdb3`** — genuinely pre-existing,
honestly recorded as CB-01.

**No finalizer receipt forged.** `SUITE-RESULT.json` and `GATE-RESULT.json` are byte-identical to
`06ebfdb3` (`a16cb1fc…`, `8201ca74…`) and still bind commit `42ea24c` / tree `1e2bba79`.

---

## 6. P4 / P5 STATE — VERIFIED MECHANICALLY

* P4 `COMPLETE` / `COMPLETE`; 14 acceptance criteria, **100/100 weight, all PASS**.
* P5 sole `READY`, `NOT_STARTED`, `checkpoint_state: NO_CHECKPOINT`, no `landed_checkpoints`, no
  `acceptance_criteria` block. No P5 implementation exists.
* P6–P14 all `BLOCKED` / `NOT_STARTED` (9 units).
* `BUILD-STATUS.derived.single_ready_unit = P5`; `content_commit` still `42ea24c` — correct, since
  no finalizer ran for this candidate.
* Canonical suite on the candidate: **1963 passed, 0 failed, 1 skipped, 1964 collected**, exit 0.
* `TEST-NODE-MANIFEST.json` identity vs live pytest collection: **1964 == 1964, exact set equality,
  0 missing, 0 extra.**
* `pytest-canonical.ini` and `scripts/run_canonical_suite.py` byte-identical to the hashes recorded
  in the receipts (`22f42941…`, `75b924e9…`).

**No guard weakened to obtain green.** Assertion counts rose in every changed test file
(e.g. `test_phase0_baseline_manifest.py` 19→45, `test_switch_consistency.py` 19→26). Node delta:
+3 / −1, the removal being `test_r07_is_never_described_as_contained`, replaced by two strictly
stronger guards that assert *state* rather than a word.

---

## 7. ADJ-01 SWITCH-CONSISTENCY GUARD

The new `test_the_selected_ready_unit_construction_is_present_singular_and_matches_the_registry`
satisfies the review requirements: it parses the real selected/sole-READY construction; anchors on
unit **tokens**, not bare substrings; blanks program ranges (`P0–P14`) to avoid false attribution;
**fails on absence** (`assert carriers`, plus a ≥3-carrier thinning guard); fails on zero or two
READY units; fails on registry/prose/derived disagreement; and derives everything from the registry
rather than hard-coding P5, so it survives the next transition. H-14/H-15/H-16 confirm all three
failure modes fire. The de-vacuuming of
`test_an_executing_phase_is_never_described_as_not_begun` (silent `return` over an empty
population) is a genuine strengthening.

Two qualifications: **F-02** and **F-04** below.

---

## 8. ADJ-02 CANONICAL-DOCUMENT PARITY

F-TR-01 through F-TR-04 are remediated:

* **F-TR-01** — `ARCHITECTURE.md:272` now reads `P4 | ✅ COMPLETE — ADJUDICATED`; `:273` reads
  `P5 | 🔄 READY *(selected)* — NOT STARTED, NOT COMPLETE`.
* **F-TR-02** — `AGENTS.md` states P0–P4 COMPLETE, P5 sole READY / NOT STARTED, R-07 CONTAINED, and
  replaces *"only completing P4 closes R-07"* with an explicit four-act sequence that names P4's
  completion as **not** the closing act. The superseded sentence is quoted, not erased.
* **F-TR-03** — `FREIGHT-CAPABILITY-MAP.md` reflects P4 COMPLETE — ADJUDICATED, R-07 CONTAINED with
  the not-enablement bound, P5 sole READY / NOT STARTED, P6–P14 BLOCKED.
* **F-TR-04** — `EFFECT-PATH-INVENTORY.yaml` no longer presents "P4 REMAINS NOT COMPLETE" as live;
  the string survives only inside quoted supersession and `[HISTORICAL]`-marked text.

**Machine-consumed structure was not edited to improve prose.** Deep structural diff of
`EFFECT-PATH-INVENTORY.yaml` across `06ebfdb3 → 11c9112`: 128 leaves both sides, **0 keys added,
0 removed**, 3 values changed — two prose, one scalar
(`production_reachable_live_write_remaining: 2 → 1`, justified because EP-3 became
READ_ONLY_STRUCTURAL, and deliberately still counting EP-1, i.e. under-claiming). EP-1's
classification was explicitly left unchanged.

**No historical review or adjudication report was rewritten** — verified byte-for-byte below the
banners (§2).

**Correction scope vs the P3 precedent** (`f579d92`): the candidate's root-document set is a strict
superset (`AGENTS.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `README.md` + `PRODUCT.md`), plus
`docs/product/` and the implementation corpus. Scope is adequate.

**Mechanical stale-claim sweep** over the whole tracked tree for `P4 IN PROGRESS`,
`P4 NOT COMPLETE`, `P4 remains incomplete`, `P4 alone closes R-07`, `R-07 OPEN`, `P5 BLOCKED`.
Every occurrence classified. All are historical evidence, quoted supersession, explicitly
`[HISTORICAL]`-marked, or unrelated — **except** the occurrences in F-01.

Live-state parity now holds across `CLAUDE.md`, `ARCHITECTURE.md`, `AGENTS.md`, `README.md`,
`PRODUCT.md`, `CURRENT.md`, `BUILD-STATUS.yaml`, `IMPLEMENTATION-REGISTRY.yaml`,
`FREIGHT-CAPABILITY-MAP.md` and `EFFECT-PATH-INVENTORY.yaml`: P4 COMPLETE, P5 READY / NOT_STARTED,
R-07 CONTAINED, P6–P14 BLOCKED, production writes dark, Phase-8 registration deferred.

---

## 9. RESIDUAL RISKS — ALL VISIBLE AND HONESTLY CLASSIFIED

* **RR-01** — recorded as *"a BINDING P12 PRECONDITION, NOT DISCHARGED"*, `OPEN — must be
  discharged before any live writer is injected`. **Code-verified**: `base_url` is absent from
  `payload_hash()`'s canonical set (`freight_operations.py:173–183`) and absent from
  `approval_operation_mismatch` (`governed_write_route.py:536+`, which compares tenant, approval-id,
  work-item, pipeline-instance, operation-class and revision). Compounding by F-08 and F-09 stated.
* **AD-01** — carried, with its stale *"provider is None"* prose corrected in both artifacts and the
  stale wording explicitly barred from reappearing. Recorded as **not discharged**.
* **AD-02** — recorded with its operating instruction (`finalizer_lock.py` has zero committed test
  coverage; a hostile battery is owed).
* **RR-02…RR-06, F-03, F-06, F-07, F-08, F-09, F-10** — all present across the register.
* **CB-01** (new) — two pre-existing broken mutation anchors, `OPEN, RECORDED, NOT FIXED HERE`,
  with a stated reason for deferring. Verified pre-existing at `06ebfdb3`.
* **PD-01** (new) — the Product Driver `BLOCKED_AUTHORITY` observation, classified as a pre-existing
  prose-extraction ambiguity **in that external tool**, `NOT DISCHARGED`, with the evidence for the
  classification stated (no repository guard reported it; `build_status_errors()` empty;
  `repo_state()` legal; suite green). This is an honest classification, not a dismissal.
* **No residual is described as discharged.** The registry block is titled
  `newly_recorded_non_blocking` and the AD-01 entry says in terms: *"THE FINDING ITSELF IS CARRIED,
  NOT DISCHARGED"*.
* Production Action Class gate registration remains deferred to U8.1/P8.

---

## 10. FINDINGS

### F-01 — MEDIUM — confirmed defect — stale, false, unmarked live claims in a canonical control document

**Requirement.** ADJ-02: consistent live state across every repository-authorized canonical
document affected by the P4 transition; no stale live statements across canonical status surfaces.

**Location.** `docs/implementation/LEGACY-DISPOSITION.md:425` and `:428` (section `### S15a —
Effect-capable entry points`).

Line 425: *"**Still present — DEFERRED (it keeps R-07 OPEN):** the same file's **write** half.
`_build_live_operation_router._build_agent` constructs `CdpActuator` for the
OperationRouter→OperatorAgent autonomous browser WRITE — the live R-07 write…"*

Line 428: *"…`effect_adapter_import_gate.violation_edges` empty (**not yet** — **four** residuals
remain…)"*

**Mechanical proof.**

1. Not historical: no `<details>`, `HISTORICAL` or `SUPERSEDED` marker occurs anywhere in
   lines 395–430; the governing heading is `### S15a`, an ordinary live section.
2. In scope: `LEGACY-DISPOSITION.md` is a canonical `IMPLEMENTATION_CONTROL` document
   (`docs/CANONICAL-DOCUMENTS.md:130`) and is present in **both** guard corpora
   (`_live_authority_documents()` → True; `live_guidance_documents()` → True).
3. Factually false: AST over `scripts/run_action_callback_server.py` finds **0** `CdpActuator`
   constructions and **0** `cdp_actuator` imports; `_build_live_operation_router` and `_build_agent`
   do not exist anywhere in `src/` or `scripts/`; `operation_router = None` unconditionally at
   line 133. Manifest `violation_edges: []` and live recomputation `set()` — not "four residuals".
   EP-1 is no longer listed in `effect_capable_by_import`.
4. Self-contradictory: the same file's "Current risk" row (~line 224) was updated by this very
   commit to *"R-07 is CONTAINED"* and *"EP-1's write is now cut too"*.

**Consequence.** A canonical control document asserts, as live status, that the exact write path
this commit certifies as cut is still present and still holds R-07 open. A grep-first reader lands
on a direct contradiction of the containment record.

**Blocks R-07 closure finalization?** **Yes, for evidence/parity purposes** — this is the same
defect class as F-TR-01…F-TR-04, which the targeted adjudication made binding on this commit. It
does **not** falsify containment; the mechanism is independently proven (§3, §4).

**Remediation (narrow).** In `LEGACY-DISPOSITION.md` §S15a only: correct lines 425 and 428 to
current state, quoting the superseded sentences in place with an explicit `HISTORICAL` /
`SUPERSEDED` marker on the same line, consistent with the treatment already applied elsewhere in
this commit. Change nothing else.

---

### F-02 — MEDIUM — confirmed defect — the replacement R-07 guard cannot reach the corpus's phrasing

**Requirement.** The strengthened guards must fail when a live document contradicts the R-07
record; ADJ-01's own stated principle is that a guard whose regex does not reach the corpus's
actual constructions is not a guard.

**Location.** `eval/tests/test_roadmap_completeness_control.py:396–397`
(`test_r07_is_never_represented_as_contained_anywhere_live`).

```python
re.finditer(r"R-07[^.\n|]{0,60}?\b(?:is|stays|remains)\s+\*{0,3}"
            r"(?:OPEN|NOT\s+CONTAINED|UNCONTAINED)\b", text, re.I)
```

**Mechanical proof.** The alternation requires the verb to **follow** `R-07`. Against the live
string `"**Still present — DEFERRED (it keeps R-07 OPEN):**"` the regex returns **no match**
(verified directly). It equally misses `kept R-07 OPEN`, `leaves R-07 open`, and a bare `R-07 OPEN`
in a table cell. This is precisely why F-01 survived a commit whose stated purpose included
sweeping such claims.

**Consequence.** The guard that the containment record leans on to keep live documents honest has
a reachability gap in the same direction as the defect ADJ-01 identified. F-01 is the live proof.

**Blocks R-07 closure finalization?** **Yes** — paired with F-01. The record's durability claim
("a re-pointed guard fails the build if… any evidence element is missing or mismatched") is weaker
than stated for the live-prose surface.

**Remediation (narrow).** Broaden the alternation to cover verb-precedes constructions
(`keeps|kept|leaves|left|holds|held … R-07 … OPEN`) and bare `R-07 OPEN`, and match over
whitespace-normalised text as `test_switch_consistency._live_text` already does. Add a hostile case
reintroducing the F-01 phrasing. Do not narrow any existing pattern.

---

### F-03 — MEDIUM — evidence deficiency — cited evidence documents are not bound to their hashes

**Requirement.** "Evidence binding for R-07"; hostile case 11 — reconstructed report hash
mismatched must fail closed.

**Location.** `eval/tests/test_phase0_baseline_manifest.py`, `REQUIRED_DOCUMENTS` block
(~lines 100–118); and the absence of any sidecar guard anywhere in `eval/`.

**Mechanical proof.**

1. The guard asserts only that the digest **string appears in the manifest text** and that the
   named path **exists**. It never recomputes the referenced document's hash.
2. `grep -rn '\.sha256' eval/tests/` finds no sidecar-verification guard. All 8 sidecars under
   `docs/implementation/` are unverified by any test.
3. **Decisive probe:** editing `p4-final-adjudication-report-0891d1a.md` to replace
   `ACCEPT P4 FOR FINALIZATION` with `REJECT P4 — REMEDIATION REQUIRED` (2 occurrences) changes its
   content hash from `078cfea8…` to `902f8d8d…`, leaving the sidecar stale — and
   `test_phase0_baseline_manifest.py`, `test_docs_control_system.py`, `test_status_reality.py`,
   `test_roadmap_completeness_control.py` and `test_false_green_defenses.py` return
   **153 passed, 2 skipped**.

**Consequence.** H-11 protects the manifest from citing a wrong hash, but the cited documents
themselves are unprotected. The containment record's evidence chain is bound at the *citation*
level, not the *content* level — weaker than the record's language implies. The banner convention
(§2), which deliberately decouples in-tree copies from their sidecars, makes this materially harder
to detect by eye.

**Blocks R-07 closure finalization?** **Yes, as an evidence deficiency** — not because containment
is false, but because the record's own binding claim is not mechanically true.

**Remediation (narrow).** Add one guard that, for each `docs/implementation/*.sha256`, verifies its
target hashes to the recorded digest **or** that a byte-exact original hashing to it exists at the
named `refs/preserve/*` ref, failing if neither holds; assert the sidecar population is non-empty.
No change to the containment record is required.

---

### F-04 — LOW — confirmed defect — ADJ-01's "nothing narrowed" claim is inaccurate

**Requirement.** "does not weaken any earlier guard"; the commit states *"all four original
patterns are still here, verbatim"* and *"every phrasing the original matched still matches."*

**Location.** `eval/tests/test_switch_consistency.py:305–310`.

**Mechanical proof.** The bound changed from `[^\n]{0,80}` to `[^.]{0,80}`. Demonstrated:

| Input | old (raw) | new (flat) |
|---|---|---|
| `P4 is the single READY unit` | match | match |
| `P4 v1.0 status: the single READY unit` | **match** | **no match** |
| `P4 (see sec. 3) is the single READY unit` | **match** | **no match** |
| `P4 (adapter\ncontainment) is the single READY unit` | no match | **match** |

**Consequence.** A narrow coverage regression: a stale claim with a period between the unit token
and the claim, within 80 characters, is no longer caught. The change is a large **net** improvement
(it fixes the line-wrap blindness that was the actual defect) and I found **no live occurrence** of
the regressed class in the current corpus. The defect is the inaccurate "verbatim / never narrowed"
claim in a commit message and docstring that are themselves audit evidence.

**Blocks R-07 closure finalization?** **No.**

**Remediation (narrow).** Either restore sentence-crossing coverage (e.g. `[^|]{0,80}` over
normalised text) or correct the commit-message/docstring claim to state the bound change and its
trade-off honestly.

---

### F-05 — LOW — non-blocking residual risk — `_is_superseded_in_place` quote-parity is file-tail fragile

**Location.** `eval/tests/test_roadmap_completeness_control.py:288–295`.

`text.count('"', 0, pos) % 2 == 1` treats "inside a quoted span" as exempt. A single unbalanced
double quote anywhere in a document inverts parity for the **entire remainder of the file**,
silently exempting every later stale claim.

**Proof of current safety and of the hazard.** I scanned all 57 live-authority documents: **0**
have odd quote parity today, so the hazard is latent, not live. It becomes live the moment any
document acquires a stray quote.

**Blocks?** **No.** **Remediation:** bound the exemption to a single line, or require a balanced
quote pair on the same line.

---

### F-06 — LOW — non-blocking residual risk — an unguarded machine-shaped scalar was edited

**Location.** `docs/implementation/EFFECT-PATH-INVENTORY.yaml`,
`meta.production_reachable_live_write_remaining: 2 → 1`.

The change is factually justified (EP-3 became READ_ONLY_STRUCTURAL) and deliberately conservative
(still counts EP-1). But `grep -rn production_reachable_live_write_remaining eval/ scripts/` finds
**no** guard binding it, so the field can drift silently in either direction.

**Blocks?** **No.** **Remediation:** bind it to the recomputed live-write set, or annotate it
explicitly as unbound narrative metadata.

---

### F-07 — INFORMATIONAL — test-environment limitation — mutation battery SKIP-INVALID cases

`scripts/mutate_roadmap_completeness.py` cases M4 and M11 SKIP-INVALID. I confirmed both anchors
were already absent at `06ebfdb3`, so they are genuinely pre-existing and are honestly recorded as
CB-01 with a stated reason for deferral. No action required of this candidate.

---

## 11. WHAT I COULD NOT INDEPENDENTLY REPRODUCE

* **Mutation battery 61/61** for the P4 boundary is cited as prior finalization evidence for
  `42ea24c`, not as a claim about this candidate's tree. I reproduced the roadmap-completeness
  battery (9/11 CAUGHT, 2 SKIP-INVALID, 0 MISS) exactly, and verified the P4 boundary and Phase-3
  batteries exist in-tree. I did not re-run the full 61-case boundary battery; it is outside this
  candidate's delta and its result is unchanged by a commit that alters no runtime byte.
* **Finalizer-lock exclusivity during the historical runs** rests on the reconstructed report,
  which states its own evidentiary limits. I independently confirmed the present state: both locks
  0-byte and UNHELD, no holder.

---

## 12. PRESERVATION RECORD

| Item | Value |
|---|---|
| Report path | `docs/implementation/p4-r07-closure-candidate-targeted-review-report-11c9112.md` |
| Report SHA-256 | `9de20eadb60ed483c9222c3845a0aa184af9f9b0d3779881c97e7e6dc5385e30` |
| Sidecar | `docs/implementation/p4-r07-closure-candidate-targeted-review-report-11c9112.md.sha256` |
| Preservation ref | `refs/preserve/p4-r07-closure-targeted-review-11c9112` |
| Preservation commit | `(recorded in the preserve commit message)` |
| Preservation parent | `11c911244304d56737913db41b458d5f3278bc80` (exactly the candidate) |
| Candidate branch after | `p4/adapter-containment-completion` → `11c9112…` (unmoved) |
| Candidate tree after | `9a3950b5…` (unchanged) |
| Primary index after | `9a3950b5…` (never written — a temporary `GIT_INDEX_FILE` was used) |
| Pushed | Nothing. `git ls-remote origin` shows no candidate, no preserve ref |

---

## VERDICT

### CONDITIONALLY ACCEPT — EVIDENCE REMEDIATION REQUIRED

R-07 containment is real and correctly recorded. The mechanism is structural, the record describes
it as a mechanism rather than as a test result, and it refuses to equate containment with
enablement or autonomy. Runtime is byte-identical to `0891d1a`; no finalizer receipt was forged;
P4 is COMPLETE at 100/100; P5 is the sole READY unit and NOT_STARTED with no checkpoint; P6–P14 are
BLOCKED; the production GateRegistry is empty over a proven non-empty corpus; the Phase-8 deferral
is intact; the canonical suite and clean-clone gate are green on the candidate with exact node
identity at 1964; and 18/18 hostile probes fail closed with byte-exact restoration.

Acceptance is conditional on **F-01**, **F-02** and **F-03** — one false live claim in a canonical
control document, the guard gap that let it through, and the unbound evidence-document hashes.
None falsifies containment; all three are the documentation- and evidence-integrity class this
commit was chartered to close, and F-03 in particular weakens the record's own binding claim.

**F-04 through F-07** are non-blocking and may be carried forward.

This candidate owes its own **separate targeted adjudication** and, after remediation, exactly one
third finalizer. This review adjudicates nothing, finalizes nothing, and authorizes no P5 work.
