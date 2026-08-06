> # ⛔ HANDOFF — NOT CURRENT AUTHORITY, AND NOT A REVIEW
> **This is a builder's handoff to a fresh targeted independent reviewer.** It certifies nothing,
> adjudicates nothing, sets no acceptance criterion, closes no risk and authorizes no finalization.
> The status authority is [`CURRENT.md`](CURRENT.md) and the registry; the operating guide is
> [`../../CLAUDE.md`](../../CLAUDE.md).
>
> ### **DO NOT TREAT ANY CLAIM BELOW AS EVIDENCE.** Re-derive every one from the object store and
> from execution. The P4 remediation handoff was wrong about two numbers (RR-02) and the handoff
> for `42ea24c` named a guard function that does not exist (F-TR-05). A reviewer who trusted either
> would have reported a false result. That is exactly why a handoff is never review evidence.

# P4 R-07 CLOSURE — REPLACEMENT CANDIDATE BUILDER HANDOFF

**Replaces rejected candidate:** `11c911244304d56737913db41b458d5f3278bc80`
**Certified parent:** `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f` (second-finalizer metadata commit)
**Branch:** `p4/adapter-containment-completion`

*(This document cannot contain its own commit or tree hash — it is part of the tree it would
describe. Both are recorded in the replacement commit message and reported to the founder.)*

**Builder standing.** This session did not implement P4, did not author rejected candidate
`11c9112`, did not conduct its targeted independent review, did not conduct its targeted
adjudication, and did not run either finalizer. No previous session was resumed. It performed no
independent review, no adjudication, ran no finalizer, began no P5 work, pushed nothing, and
enabled nothing.

---

## 1. WHAT THIS CANDIDATE IS

Rejected candidate `11c9112` was adjudicated **REJECT — TARGETED REMEDIATION REQUIRED** on three
blocking grounds. Its **R-07 technical containment was independently confirmed as real** and is
**not reopened here**. This candidate carries all of that containment content forward unchanged and
adds only the adjudicated remediation:

| Finding | Remediation |
|---|---|
| **F-01** live false R-07 status claims | corrected or explicitly marked historical — **at ten locations, not five** (§3) |
| **F-02** guard structurally blind to the corpus grammar | word-order matching replaced by a **structural claim parser** (§4) |
| **F-03** evidence chain bound at citation level only | **immutable, banner-aware binding** to preserved blobs (§5) |
| **F-04** inaccurate "nothing narrowed" claim | claim corrected (§7) |
| **F-05** file-tail-fragile quote exemption | quote parity now **block-bounded** (§4.4) |
| **F-06** unbound live-write scalar | explicitly annotated as unbound narrative; **carried, not discharged** (§7) |
| **CB-01** two SKIP-INVALID mutation anchors | both re-pointed; battery now 21/21 with **0 SKIP-INVALID** (§7) |

---

## 2. PRESERVATION OF THE REJECTED STATE

Everything below was created **before any remediation byte was written**.

| Item | Value |
|---|---|
| Rejected candidate | `11c911244304d56737913db41b458d5f3278bc80` |
| Rejected tree | `9a3950b5ffecaaa551b803059eb92b8760aac8f3` |
| Preservation ref (candidate) | `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` → `11c9112` |
| Archive branch | `refs/heads/archive/p4/r07-rejected-11c9112` → `11c9112` |
| Preservation ref (worktree) | `refs/preserve/p4-r07-rejected-worktree-11c9112` → `6224b36e196185851ddf8bd0fc03d0626038dd3b` |
| Worktree-preservation tree | `d48992ad5e910686f6810437bf1351aafeb9caf2` |
| Its parent | `11c9112` — additions only, **no tracked file modified** |
| Rejected targeted review | `refs/preserve/p4-r07-closure-targeted-review-11c9112` → `fa4c459b0507a43cdf6040429e4a4d6a02a7a62e` (parent `11c9112`) — **not moved** |
| Rejected targeted adjudication | `refs/preserve/p4-r07-closure-targeted-adjudication-11c9112` → `030c5954ba266a958a5a1a4ba47b9a9efbd9a2e8` (parent `11c9112`) — **not moved** |

**Prestate hashes, recorded before mutation.**

| Item | Value |
|---|---|
| `.git/index` (file) | `e9bd59dfc4c2dcb768185a2c01b2b3b01a4b6fbcd3029aeb9d68522151f6c672` |
| index content (`git ls-files -s`) | `84c44e3d140575e6c1205ab997bbc456597ad945d3bfaefb4e7e0482303ec1c1` |
| worktree inventory (4041 files, sha256 each) | `e95df1cc3512eab1fab5b41b67d9ac002a2fde2a9cb5bdb12cc25a16bd90920a` |
| `main` / `origin/main` | `152574e4f4f2969468c9d31b1e705188896175b5` — **unmoved** |

**Verified in a disposable `--no-local` clone**, not asserted:

* forward sweep — **641 files checked, 0 missing, 0 mismatched**;
* reverse sweep — **0 preserved paths absent from the prestate inventory**;
* accounting — 641 preserved + 3400 excluded = **4041 exactly**.

**The capture boundary is disclosed, not silent.** Excluded as derived or environmental:
`.venv/` (13228 files), `.chrome-neyma-cdp/` (761), `__pycache__/` (1851), `.pytest_cache/`,
`.pytest_tmp/`, `.claude/.cc-writes/`, `data/active_workspace/` (3220),
`data/synthetic_corpus/` (169), `data/template_sources/downloaded/` (5).

**`.env` is deliberately NOT stored in any git object.** It is gitignored precisely to keep
credentials out of durable objects, and no preservation purpose justifies writing a secret into
one. Its identity is preserved by digest instead —
`sha256(.env) = 220534bc39dbcb0f4698b530ad740674381e1e046c6b52373ed62f1b181d60ab` — which proves it
was unchanged across this remediation without embedding it. **A reviewer should verify this digest
rather than expect the file at a ref.**

The 7 ignored-but-tracked `.playwright-mcp/` paths are carried by the tracked set; the 2
ignored-untracked ones are carried explicitly by the worktree-preservation tree.

---

## 3. F-01 — REMEDIATION MAP FOR EVERY LIVE FALSE CLAIM

### 3.1 The adjudication's five

| # | Location | Was | Now |
|---|---|---|---|
| 1 | `LEGACY-DISPOSITION.md` §S15a | "**Still present — DEFERRED (it keeps R-07 OPEN):** the same file's **write** half. `_build_live_operation_router._build_agent` constructs `CdpActuator`…" | **corrected** — "WRITE HALF CUT at U4.11 (P4) — the deferral below is DISCHARGED", with AST facts. Superseded sentence quoted in place under a `SUPERSEDED` marker |
| 2 | `LEGACY-DISPOSITION.md` §S15a | "…`violation_edges` empty (**not yet** — **four** residuals remain…)" | **corrected** — condition **MET**, zero residuals. Superseded sentence quoted and marked. A count is deliberately not restated as a hand-maintained number |
| 3 | `LEGACY-DISPOSITION.md` §S1 line 44 | `\| **Current risk** \| ### **R-07 — OPEN, NOT CONTAINED.** …\|` | **corrected** — `R-07 — CONTAINED (recorded at P4)`, with the CONTAINED-is-not-ENABLED bound. Superseded row quoted below the table under a `SUPERSEDED` marker |
| 4 | `.claude/agents/principal-architect-supervisor.md` | "**Safety boundaries intact** — R-07 still recorded OPEN unless the unit is P4 itself" | **re-pointed** — verify R-07 against the machine record, which reads `CONTAINED`; superseded instruction retained and marked |
| 5 | `.claude/agents/principal-architect-supervisor.md` | "this repository has six production-reachable live-write paths and **an open R-07**" | **corrected** — the six are the P0 baseline finding, **CUT at P4**; R-07 `CONTAINED`; superseded sentence retained and marked |

**Also reviewed in the same pass, as the adjudication directed:** §S1 `Target phase` (now "executed
and adjudicated") and §S1 `Deletion condition` (now marked **MET at P4**, with the note that a met
condition is not an instruction to delete today).

### 3.2 FIVE MORE, found by the new parser — read this section

The repository-wide sweep required by the remediation brief was run **with the structural parser
built for F-02**, not with a substring search. It found **five additional live false R-07 claims**
that neither the targeted reviewer nor the targeted adjudicator located:

| # | Location | Live false claim |
|---|---|---|
| 6 | `docs/implementation/effect-entry-point-cutover-plan.md` | "The remaining rows are NOT yet done and **keep R-07 OPEN**" — plus "awaiting independent review and final adjudication" |
| 7 | `docs/product/OPERATIONAL-USE-CASE-COVERAGE.yaml` | "the in-progress P4 adapter containment (READY, not COMPLETE; **R-07 OPEN**)" |
| 8 | `docs/product/QUOTE-TO-CASH-LIFECYCLE.md` | "P4 adapter containment READY, not complete; **R-07 OPEN**" |
| 9 | `docs/product/NEYMA-OPERATOR.md` | "P4 adapter containment (READY, not complete; **R-07 OPEN — NOT CONTAINED**)" |
| 10 | `docs/product/AUTONOMY-MATRIX.md` | "P4 adapter containment READY, not complete; **R-07 OPEN**" |

All five are corrected to current state with the superseded wording retained and marked.

**Why this matters more than the count.** #6 uses `keeps R-07 OPEN` — the exact verb-precedes
construction F-02 identified as invisible. The other four use a copula-free parenthetical. **Every
one of them was invisible to the instrument the reviewer and adjudicator were using**, which is why
both stopped at five. This is recorded as **RC-01**: a defect count produced by a broken instrument
is a lower bound, never a total. A reviewer re-deriving this set must use the structural parser.

### 3.3 Historical material retained and explicitly marked (not corrected)

| Location | Treatment |
|---|---|
| `phase-0-baseline-manifest.yaml` (2 comment paragraphs) | genuine historical narrative whose `HISTORICAL` marker sat on a *neighbouring* line; a same-line `(HISTORICAL, SUPERSEDED)` marker added so the marking is local to the claim |
| `PROGRAM-WEIGHTS.yaml` frozen gate evidence | "R-07 honestly OPEN" is what an independent review found **at P3**; a same-line historical note added. The evidence string itself is not rewritten |

### 3.4 Verified clean, no change made

`EFFECT-PATH-INVENTORY.yaml:18/28/130`, `PHASE-OUTPUTS.md:109`, `pr-sequence.md:33`,
`phase-0-baseline-manifest.yaml:358/661` — legitimate quoted supersession or same-line
`[HISTORICAL]` marking. `CURRENT.md:63/98` and `CAPABILITY-TRACEABILITY.yaml:843` are **not** status
claims ("the open-risks table", "an open decision") and the parser correctly ignores them.
`PHASE-OUTPUTS.md:127` ("R-07 **may not** be marked CONTAINED before this phase completes") is a
rule whose modal governs the claim, immediately followed by "THAT CONDITION IS NOW MET".

### 3.5 Final sweep result

**58 documents · 81 parsed status claims · 45 live CONTAINED · 0 live OPEN.**

---

## 4. F-02 — PARSER DESIGN AND HOSTILE-TEST MATRIX

### 4.1 What was wrong

Both guards required a copula from the closed set `{is, stays, remains}` to **follow** `R-07`:

```python
r"R-07[^.\n|]{0,60}?\b(?:is|stays|remains)\s+\*{0,3}(?:OPEN|NOT\s+CONTAINED|UNCONTAINED)\b"
```

The repository's own canonical status rows are copula-free em-dash table cells
(`| **Current risk** | ### **R-07 — OPEN, NOT CONTAINED.** |`), so the pattern could never see
them. Measured on the rejected tree: **8 of 12 forms missed, 0 of 5 live defects caught, suite
green**.

### 4.2 What replaces it — `eval/control/status_claims.py`

Not another alternation. A parser:

1. **SEGMENT** into claim units — markdown table cells and sentences — so a neighbouring sentence's
   vocabulary cannot leak in. Colons and semicolons are **not** sentence boundaries: `R-07: OPEN`
   is a claim, and splitting there would cut it in half.
2. **NORMALIZE** — markdown emphasis stripped, whitespace runs collapsed — so `**OPEN**`,
   `### **R-07` and a construction wrapped across three source lines all read alike.
3. **POLARITY from a closed vocabulary**, negated containment resolved **first**, so
   `not contained` can never read as `contained`.

Word order is irrelevant to every step. `R-07 remains open`, `keeps R-07 open` and
`does not contain R-07` are one parse.

**Unrelated identifier usage is excluded by construction.** `open` immediately qualifying a
register noun (`open risks`, `an open decision`, `the open-risks table`) is not a status claim.

### 4.3 Positive assertions — this cannot pass vacuously

* corpus non-empty and not collapsed (≥15 documents);
* **`REQUIRED_R07_REACH`** — 15 named documents that must be *inside* the discovered population, so
  a corpus that silently stops including `LEGACY-DISPOSITION.md` or an agent lens **fails**. It is
  annotated `FIXED-SPECIFICATION` because discovering it would defeat its purpose;
* **≥5 live CONTAINED claims** must be parsed, so a corpus that stops stating R-07's status fails
  rather than passing by saying nothing;
* the grammar matrix asserts the **parse itself**, so a parser returning "no claims" for everything
  fails instead of keeping the corpus assertions green forever.

**The two corpora are unified**: `live_authority_documents()` now has ONE definition in
`control.status_claims`, used by both guards. Guard B's hard-coded four-tuple, which could never
grow, is replaced by that discovered population unified with its four; those four keep their
stronger per-document obligation (state CONTAINED **and** state the bound).

### 4.4 F-05, closed in the same pass

`_is_superseded_in_place` counted quote parity **from the start of the file**, so one unbalanced
quote inverted parity for the entire remainder. It now counts **from the start of the enclosing
block** — strictly narrower than what it replaced, and it still admits the multi-line quoted
supersessions the corpus legitimately uses. A regression test proves a stray quote in one block no
longer exempts a live claim in a later one.

### 4.5 Hostile-test matrix

**Mutation battery — `scripts/mutate_roadmap_completeness.py`: 21/21 CAUGHT, 0 MISS, 0 SKIP-INVALID,
byte-exact restoration.**

| Case | Reintroduces |
|---|---|
| M12 | F-01 #3 **verbatim** — the copula-free em-dash cell in "THE R-07 SURFACE" |
| M13 | F-01 #1 **verbatim** — "it keeps R-07 OPEN" |
| M14 | F-01 #2 **verbatim** — the "four residuals remain" count |
| M15 | F-01 #4 **verbatim** — "R-07 still recorded OPEN unless the unit is P4 itself" |
| M16 | F-01 #5 **verbatim** — "an open R-07" |
| M17–M21 | `leaves R-07 open` · `R-07 not contained` · `does not contain R-07` · `violation residuals keep R-07 open` · `R-07: OPEN` |

Every one of these was a **proven MISS** on the rejected tree.

**In-memory grammar matrix** (`test_the_r07_status_parser_decides_every_required_grammar_form`):
**22 forms, all parsed with the correct polarity; all 18 OPEN forms detected as LIVE**, including
the two the previous `_EXEMPT` wrongly excused via a *trailing* `unless` / `cannot`.

**Conditional exemption narrowed to what governs the claim.** A modal exempts only when it falls
between the start of the claim unit and the polarity token. `requires`/`required` are deliberately
**not** exemptions — "a supervisor must require R-07 to remain recorded OPEN" is a defect *because*
it prescribes.

### 4.6 The `:428` count claim is now mechanically caught

`test_the_recorded_effect_violation_surface_is_the_mechanically_recomputed_one` was widened from
`IMPLEMENTATION-SURFACE.yaml` only to any live-authority document stating a violation-residual
count, held to the recomputed number, over the same claim units and normalization (so
`**four** residuals remain` cannot escape through markdown emphasis — the first draft of this check
did let exactly that through, and M14 caught it).

---

## 5. F-03 — IMMUTABLE, BANNER-AWARE EVIDENCE BINDING

### 5.1 Design — `eval/tests/test_evidence_binding.py`

**The preserved blob is the source of truth, not the worktree file.** A naive
`sha256(worktree) == sidecar` guard cannot be the fix: it would fail on three documents *by design*,
because `test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale_claim`
requires tracked historical reviews to carry a disarming banner, which necessarily changes bytes.

The binding is therefore: **the preserved blob must hash to the recorded digest, and the worktree
rendering must reduce to that same blob byte-for-byte.**

**Banner-aware, deterministically.** The parser removes **exactly one** leading markdown blockquote
block plus the blank lines after it — nothing else. It does not scan for a marker and cannot be
steered by content below. Reports legitimately contain further blockquotes in their own bodies, so
only the first contiguous block is a banner.

**The report set is mechanically enumerated from the containment record**, not hand-listed: any
citation naming a path, a digest and a preservation ref is load-bearing by construction, and each
expected preservation **parent** is resolved from the commit fields recorded in the same block.

**TWO TIERS, because a clean clone has no `refs/preserve/*`.** `git clone` copies only
`refs/heads/*` and `refs/tags/*`, and these preservation refs are deliberately never pushed — so a
guard that can only run where they exist cannot run in the clean-clone gate. **The first draft of
this guard failed there, and the gate is what caught it.** The answer was not to skip:

* **Tier 1 — unconditional, and the load-bearing one.** The banner-stripped worktree body must hash
  to the digest the record cites; the sidecar must record the same digest; a banner-required
  document must still be bannered; the recorded verdict must appear in the body. This catches the
  verdict flip, sidecar tampering, a missing report or sidecar, banner removal and body
  substitution — **in every environment**.
* **Tier 2 — attribution, where preservation history exists.** The preserved blob hashes to the
  digest, the body equals it byte-for-byte, and the preservation commit parents the attested commit.

**The tier-2 condition is all-or-nothing, which is what keeps it honest.** No `refs/preserve/*` at
all ⇒ distribution clone, tier 2 inapplicable. **Any** present ⇒ every load-bearing report's ref
must resolve correctly; a single missing or re-pointed ref is a hard failure. Partial availability
is exactly what tampering looks like, and `test_the_tier_two_condition_is_all_or_nothing` asserts
that distinction directly. **No skip was added** — the repository permits exactly one approved skip
and this guard does not spend it.

### 5.2 Complete load-bearing report manifest — all six verified

| # | Key | Report | SHA-256 | Preservation ref | Parent | Banner |
|---|---|---|---|---|---|---|
| 1 | `accepted_independent_rereview` | `p4-independent-rereview-report-0891d1a.md` | `181e1a37…d316` | `refs/preserve/p4-independent-rereview-0891d1a` | `0891d1a…` | **35 lines** |
| 2 | `final_adjudication` | `p4-final-adjudication-report-0891d1a.md` | `078cfea8…997e` | `refs/preserve/p4-final-adjudication-0891d1a` | `0891d1a…` | none |
| 3 | `first_finalization_report` | `p4-first-finalization-pass-report-86306d5.md` | `9f5b8f98…1056` | `refs/preserve/p4-closure-acceptance-prestate-86306d5` | `86306d5…` | none |
| 4 | `accepted_targeted_independent_review` | `p4-closure-candidate-targeted-review-report-42ea24c.md` | `5547aa5e…8ea5` | `refs/preserve/p4-closure-targeted-review-42ea24c` | `42ea24c…` | **34 lines** |
| 5 | `accepted_targeted_adjudication` | `p4-closure-candidate-targeted-adjudication-report-42ea24c.md` | `23496e6c…9567` | `refs/preserve/p4-closure-targeted-adjudication-42ea24c` | `42ea24c…` | none |
| 6 | `second_finalization_report` | `p4-second-finalization-pass-report-06ebfdb3.md` | `96ef5fe8…1fa0` | `refs/preserve/p4-second-finalization-report-06ebfdb3` | `06ebfdb3…` | none |

**#3 is newly bound.** The first finalization pass was already load-bearing — it is the one
canonical finalizer run on `0891d1a` and the source of the `canonical_finalizer` PASS — but it was
cited only in prose, with no digest or preservation ref in the containment record, so the guard had
nothing to bind. **An unbound load-bearing report is exactly the F-03 defect.** This is the sole
addition to `containment_evidence`.

### 5.3 What is verified per report

Preservation ref resolves · preserved blob hashes to the recorded digest · sidecar agrees with the
record · worktree rendering reduces to the preserved blob (banner-stripped where bannered) ·
banner is a real disarm notice and discloses the sidecar convention · **banner-required documents
are still bannered** · preservation commit parents the exact attested commit · the recorded verdict
appears in the preserved evidence.

### 5.4 Banner-aware verification rules

* **Bannered** — verify the banner exists and disarms; isolate the body with the deterministic
  parser; verify that body **byte-for-byte** against the preserved blob; verify the blob against
  the expected SHA-256; verify ref, parent and attribution.
* **Unbannered** — verify the complete report bytes against the preserved blob and sidecar.
* A knowingly impossible byte equality between a bannered wrapper and its unbannered original is
  **never** required. A sidecar is **never** accepted merely because it exists.

### 5.5 Hostile evidence results — all CAUGHT

Run end-to-end in a disposable `--no-local` clone, restoring between each case:

| Case | Baseline | Tampered |
|---|---|---|
| **ACCEPT → REJECT** (the adjudicator's exact reproduction) | 26 passed | **1 failed** |
| sidecar content changed | 26 passed | **1 failed** |
| report missing | 26 passed | **5 failed** |
| sidecar missing | 26 passed | **1 failed** |
| **one** preservation ref deleted | 26 passed | **2 failed** |
| required banner removed | 26 passed | **13 failed** |
| banner-body substitution | 26 passed | **15 failed** |

**And in a clean clone carrying no `refs/preserve/*` at all:** baseline **26 passed**, and the
ACCEPT→REJECT tamper still **1 failed**. Tier 1 does the catching; tier 2 adds attribution.

The ACCEPT→REJECT case reproduces the adjudication §5.3 tamper exactly: the report hash moves
`078cfea8…997e → 610d471b…3dc3`, **matching the hash the adjudicator recorded**. On the rejected
tree that left **1957 tests passing**. It now fails.

**The banner-removal case is the subtle one.** Debannering makes the worktree copy byte-identical
to the preserved blob, so a pure body-equality check goes green while the document has quietly
stopped disarming itself. The requirement is therefore bound over the **discovered**
`banner_required_documents()` population, and a regression test asserts precisely that
`body == preserved` at the moment the case must still fail.

Fifteen in-process hostile tests cover the same surface plus candidate/tree/verdict/attribution and
finalizer-target changes. **Every negative test anchors on the real report set, refs and parsed
verdicts, and asserts its anchor is GREEN before tampering** — none can pass on an empty corpus.

---

## 6. RUNTIME EQUALITY PROOF

Tree-object identity against accepted implementation candidate
`0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e`:

```
src      0204261b17baecd2bab3dc1b7d25a7494eb3b22d   IDENTICAL
configs  124ae4bcbbec96cc0ff9282d183d7c97aa1914f5   IDENTICAL
data     8d02102277273f6858ce15d3753002e7875bb9df   IDENTICAL
```

This covers by construction: adapters, the governed approval/write route, checkpoint/witness/grant/
atomic-claim machinery, browser and origin policy, the production `GateRegistry` implementation and
population, and every config/data surface affecting runtime.

**No receipt was forged.** `SUITE-RESULT.json` and `GATE-RESULT.json` are **byte-identical to
`06ebfdb3`** and still bind `42ea24c` / `1e2bba79`. The clean-clone gate was deliberately run only
in a disposable clone, because it writes `GATE-RESULT.json` and running it in the primary worktree
would have overwritten a finalizer receipt.

**Changed paths versus `06ebfdb3`** are `11c9112`'s set plus this remediation's; **changed paths
versus `11c9112`** are exactly:

```
M  .claude/agents/principal-architect-supervisor.md
M  docs/implementation/EFFECT-PATH-INVENTORY.yaml
M  docs/implementation/IMPLEMENTATION-REGISTRY.yaml
M  docs/implementation/LEGACY-DISPOSITION.md
M  docs/implementation/PROGRAM-WEIGHTS.yaml
M  docs/implementation/TEST-NODE-MANIFEST.json
M  docs/implementation/effect-entry-point-cutover-plan.md
M  docs/implementation/phase-0-baseline-manifest.yaml
M  docs/product/AUTONOMY-MATRIX.md
M  docs/product/NEYMA-OPERATOR.md
M  docs/product/OPERATIONAL-USE-CASE-COVERAGE.yaml
M  docs/product/QUOTE-TO-CASH-LIFECYCLE.md
M  eval/tests/test_docs_control_system.py
M  eval/tests/test_phase2_guard_registry.py
M  eval/tests/test_roadmap_completeness_control.py
M  eval/tests/test_switch_consistency.py
M  scripts/mutate_roadmap_completeness.py
A  eval/control/status_claims.py
A  eval/tests/test_evidence_binding.py
A  docs/implementation/p4-r07-closure-replacement-targeted-review-handoff.md
A  docs/implementation/p4-r07-closure-replacement-targeted-review-handoff.md.sha256
```

**Three deviations from the adjudication's §9.4 allowed-path set, all declared:**

1. **`eval/control/status_claims.py` is a new file under `eval/control/`,** not one of the two named
   test files. The adjudication required the two corpora to be *unified*; a parser duplicated in two
   test modules would drift, which is the defect being fixed. It is a guard file in substance and
   sits beside `inventory.py`, the existing corpus-discovery authority.
2. **`docs/implementation/PROGRAM-WEIGHTS.yaml`, `effect-entry-point-cutover-plan.md` and four
   `docs/product/` files** are outside §9.4's list because §9.4 was written from a defect set of
   five. They carry defects #6–#10 (§3.2), which the remediation brief's repository-wide sweep
   required be found and fixed.
3. **`eval/tests/test_phase2_guard_registry.py`** — mechanically unavoidable. Its
   `test_every_guard_file_is_classified` fails the suite when a guard file is added and left
   unclassified, so the new F-03 guard had to be classified there. The edit is one `RETAIN` entry
   plus its reason; no assertion changed.

**Two frictions with the control system are worth the reviewer's attention, because both are it
working as designed and neither was worked around.** The H-6 anti-hand-enumeration meta-guard
rejected `REQUIRED_R07_REACH` until it carried a `FIXED-SPECIFICATION` reason *inside its 8-line
window*; the Phase-2 registry rejected the new guard file until it was classified.

---

## 7. RESIDUAL RISKS — CARRIED FORWARD

**Nothing below is discharged except where stated.**

| ID | Status |
|---|---|
| **RR-01** | **BINDING P12 PRECONDITION, NOT DISCHARGED.** `base_url` is outside `payload_hash()`'s canonical set and outside `approval_operation_mismatch`. Compounded by F-08/F-09. Must be discharged before any live writer is injected |
| **AD-01** | carried; prose corrected earlier, **the finding itself is not discharged** |
| **AD-02** | carried — `finalizer_lock.py` has zero committed test coverage; a hostile battery is owed |
| **RR-02…RR-06, F-07…F-10** | carried, unchanged |
| **F-04** | **CLOSED** — the inaccurate "verbatim / never narrowed" claim is corrected with the exact bound change and its trade-off stated |
| **F-05** | **CLOSED** — quote parity is block-bounded |
| **F-06** | **CARRIED, NOT DISCHARGED** — `production_reachable_live_write_remaining` is explicitly annotated as unbound narrative metadata. It is deliberately conservative (still counts EP-1), so it under-claims. Binding it needs a "production-reachable live write" probe that does not exist; inventing one to retire a non-blocking finding would be the wrapper PL-6 rejects |
| **CB-01** | **DISCHARGED** — M4 and M11 re-pointed at anchors that exist, preserving the defect each reintroduces. 0 SKIP-INVALID |
| **RC-01** *(new)* | **RECORDED** — five further live false claims found only by the structural parser. The lesson is load-bearing: a count from a broken instrument is a lower bound |
| **RC-03** *(new)* | **OPEN, NOT FIXED HERE — PRE-EXISTING** — `p4-r07-closure-handoff.md` (added by `11c9112`) matches neither the review-family rule nor any current-authority class, so no guard reads it and no banner is required of it. This candidate's own handoff avoids the gap by following the established naming convention |
| **RC-02** *(new)* | **OPEN, NOT FIXED HERE** — two stale "six production-reachable live-write paths" framings remain in `red-to-green-acceptance-plan.md` and `TOOL-ACCESS-POLICY.md`. These are count claims, not R-07 status claims, and are genuinely the P0 baseline finding that `test_11to14_open_findings_remain_recorded` **requires** stay recorded, so the fix is a historical re-framing that belongs with the F-06 binding decision |
| **PD-01** | carried — Product Driver `BLOCKED_AUTHORITY` prose-extraction ambiguity in that external tool, not discharged |

---

## 8. REVIEWER SELF-CORRECTIONS — PRESERVED, NOT CONVERTED INTO DEFECTS

Independently re-verified this session, and recorded because they must not be re-litigated:

1. **The three sidecar mismatches are disclosed banner conventions, not drift.** Each bannered file
   states in-band that its sidecar is the pre-banner original's hash. Re-verified: stripping exactly
   the banner reproduces the preserved original **byte-for-byte** at
   `181e1a37…`, `5547aa5e…` and `9c5cc187…`. **Not a defect.** The F-03 guard is built to respect
   this, not to flag it.
2. **The reviewer's initial H-03 MISS was a probe-scoping error, self-corrected.** The
   live-vs-recorded disagreement edge is caught by `eval/tests/test_phase0_adapter_imports.py`, and
   the delivered report already records H-03 as CAUGHT with that attribution. **No product defect
   exists here.**
3. **The environment-only CLI smoke failures are not candidate regressions.** `test_delivery_dispatch`,
   `test_first_design_partner`, `test_mailbox_intake`, `test_mailbox_workflow` reproduce identically
   on the **unmodified parent** in a sandbox. They did not reproduce in this session's primary-tree
   runs (2014 passed, 3 skipped, 0 failed), which is consistent with them being subprocess/CLI
   environment artifacts of a disposable clone.
4. **The targeted review's §12 self-referential digest** (`9de20ead…`) is a structurally unavoidable
   placeholder — a document cannot contain its own hash. The authoritative bindings (sidecar and
   preserve-commit message) both carry the true `1659338a…` and both verify.

---

## 9. VERIFICATION RESULTS

| Check | Result |
|---|---|
| Canonical suite (primary tree) | **2015 passed · 0 failed · 3 skipped · 2018 collected** |
| Canonical suite (detached, disposable clone) | **2017 passed · 0 failed · 1 skipped · 2018 collected** |
| Clean-clone gate | **PASS** |
| `TEST-NODE-MANIFEST.json` identity | **2018 == 2018, exact set equality, 0 missing, 0 extra**; `config_sha256` verified |
| Roadmap-completeness battery | **21/21 CAUGHT, 0 MISS, 0 SKIP-INVALID** |
| P4 boundary battery | **61/61 caught** (unchanged) |
| Hostile evidence battery | **7/7 CAUGHT** end-to-end, in BOTH a preservation-carrying repo and a clean clone; **26 in-process** |
| R-07 grammar matrix | **22/22 parsed; 18/18 OPEN forms live-detected** |
| Repository-wide stale-claim sweep | **58 docs · 81 claims · 45 live CONTAINED · 0 live OPEN** |
| Runtime equality vs `0891d1a` | **src / configs / data IDENTICAL** |
| Receipts | `SUITE-RESULT.json`, `GATE-RESULT.json` **byte-identical to `06ebfdb3`** |
| `repo_state()` | **PRODUCING** |
| P4 / P5 | P4 **COMPLETE** 100/100 · P5 **sole READY, NOT_STARTED**, `NO_CHECKPOINT` · P6–P14 **BLOCKED** |
| R-07 | **CONTAINED** |
| Production `GateRegistry` | **EMPTY** |
| Phase-8 gate deferral | **intact** |
| `main` / `origin/main` | **unmoved** at `152574e4` |
| Pushed | **nothing** |

---

## 10. PREREQUISITES FOR THE FRESH TARGETED INDEPENDENT REVIEWER

**Standing.** A session that did **not** implement P4, did **not** author `11c9112` or this
replacement, did **not** perform the targeted review or adjudication of `11c9112`, and has **not**
run a finalizer. Resume no previous session.

**The review and adjudication of `11c9112` may NOT be carried forward.** They reviewed tree
`9a3950b5…` and nothing else. Their preserve refs must remain exactly where they are, parented to
`11c9112`. This candidate owes a **completely fresh** targeted review and its own **separate**
targeted adjudication.

**Verify, do not accept:**

1. Topology — exactly one content commit above `06ebfdb3`; `repo_state()` == `PRODUCING`; not a
   merge; parent exactly `06ebfdb3`; not a child of `11c9112`.
2. `11c9112` still resolves at both preservation refs and the archive branch, and its review and
   adjudication remain attributable **only** to it.
3. All ten F-01 locations — corrected or correctly marked historical. **Re-run the sweep with the
   structural parser, not a substring search** (§3.2); an independent sweep is the point.
4. F-02 — every §4.5 form CAUGHT; the parser matrix; corpus non-vacuity; `REQUIRED_R07_REACH`;
   that no existing assertion was weakened.
5. F-03 — every §5.5 hostile case; that the preserved blob, not the worktree file, is the binding
   target; that the banner convention is respected rather than circumvented.
6. Runtime byte-equality vs `0891d1a`; receipts unforged.
7. Containment is **technically valid and unchanged** — it was independently confirmed on `11c9112`
   and is not reopened here, but confirm it was not *altered*.
8. That `.env` was not written into any git object, and that its recorded digest matches.

**Adversarial angles this builder could not test on itself:** whether the parser's claim-unit
segmentation can be evaded by a construction not in the matrix; whether the exemption rules can be
abused to launder a live claim; whether the evidence guard can be satisfied by a forged preservation
ref; whether `REQUIRED_R07_REACH` drifts out of date silently.

---

## 11. PREREQUISITES FOR THE EVENTUAL THIRD FINALIZER

**No finalizer is authorized on this candidate today.** All of the following must hold first:

1. A fresh targeted independent review returning **unconditional ACCEPT**.
2. A **separate** fresh targeted adjudication authorizing **exactly one** finalizer.
3. Topology exactly `06ebfdb3 → <replacement>`; `repo_state()` == `PRODUCING`.
4. Canonical suite and clean-clone gate green on the final tree with exact node identity.
5. Working tree clean; `.git/neyma-finalizer.lock` and `.git/neyma-builder-worktree.lock` free.
6. `11c9112` and its review and adjudication preserved and immovable.
7. No runtime byte changed; `src`/`configs`/`data` still tree-identical to `0891d1a`.

Until all seven hold, `scripts/finalize_status.py` must not run.

---

## 12. WHAT THIS BUILDER DID NOT DO

Did not review or adjudicate this candidate · did not run any finalizer · did not begin P5 · did not
push, merge, deploy or enable any effect · did not weaken the R-07 containment mechanism · did not
change P4 runtime behaviour · did not register a production gate · did not create a second
consecutive content commit · did not move `main`, `origin/main` or any protected ref · did not
rewrite any historical review or adjudication body · did not forge a finalizer receipt.
