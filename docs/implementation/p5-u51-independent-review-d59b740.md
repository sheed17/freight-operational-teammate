# P5 U5.1 — FRESH INDEPENDENT TARGETED REVIEW of candidate `d59b740`

Transcribed by the campaign controller from the reviewer's return. The reviewer could not write
this file itself (the harness refuses subagent report-file creation). The reviewer built and ran
all evidence below; **it fixed nothing**. It did not build either candidate, did not review
`38b4bda` or `1ae365a`, and wrote no adjudication.

## VERDICT: ACCEPT WITH NONBLOCKING FINDINGS

The candidate satisfies the currently authorized U5.1 contract. The CONSUMES class is no longer
self-certifying: every exploit named in the two prior rejections now fails closed, for the specific
structural reason the re-adjudication required.

## Identity, as the reviewer measured it

| Property | Measured |
|---|---|
| Candidate | `d59b7400a472cc72d522d3f14a365710b9ba6bf0` |
| Tree | `a88921c636df406c5137bc3178e8f01de122ab31` |
| Parent | `6e8127dab02e3443183d06825836f5a805f53de0`, sole parent, no merge |
| Descendant of 38b4bda / 1ae365a | **No** / **No** (`git merge-base --is-ancestor`) |
| Working tree | CLEAN at start and end |
| Content commits on parent | exactly 1 — PROGRESS-PROTOCOL §10 first-parent topology satisfied |
| `docs/specifications/` vs 1ae365a | byte-unchanged |

Delta vs parent: 23 paths, all modifications. Delta vs 1ae365a: 3 paths (guard, audit, regenerated
manifest).

## Measurements

| Measurement | Result |
|---|---|
| Canonical suite (primary worktree) | **2104 passed · 1 skipped · 0 failed**, exit 0, 422.75s |
| The one skip | `test_phase0_guard_integrity.py:109` — "no red-by-design cases remain: AC-SAFE-012/013 went green at Phase 1" |
| `test_status_reality.py -rs` | **7 passed · 0 skipped** (clean-tree-gated nodes RAN rather than skipped) |
| TEST-NODE-MANIFEST | 2105 nodes = 2104 + 1; **+32/−0 vs parent, +3/−0 vs 1ae365a; no node, assertion or test function removed** |
| Classification (recomputed from specs) | PRODUCER 110 · CONSUMES 9 · NON_PRODUCING 6 · DELEGATES_TO 2 · EVENT_REQUIRED 7 = **134**; classifier errors 0 |
| EVENT_REQUIRED membership | exactly the adjudicated seven; set-equal to the hard-coded anchor |
| Canonical events | **98** F1–F13; `events/registry.md` byte-unchanged vs parent → minting impossible |
| EF-3 | PRODUCER, sec-3 owner of the EXISTING `EffectExecuted` |
| P5 acceptance contract | 14 criteria · Σ weights exactly 100 · verbatim ordered match to frozen `PROGRAM-WEIGHTS.yaml` · all PENDING · no score field |
| Frozen-set provenance | `adjudication_digest 30eddf57…9ed9` recomputed, matches byte-exactly incl. `.sha256` sidecar |

Preserved invariants: P4 COMPLETE (14/14) · P5 READY/NOT_STARTED/NO_CHECKPOINT · P6 BLOCKED ·
R-07 CONTAINED · production `GateRegistry` construction removed from production wiring
(`governed_write_registry.py:394`), population EMPTY until P8 · Phase-8 deferral intact · production
writes dark.

Scope: no `src/`, `scripts/`, `configs/`, `data/`, `docs/architecture/`,
`docs/specifications/acceptance/`; no `events/registry.md` or `state-machines/registry.md`; no
`SUITE-RESULT.json`, `GATE-RESULT.json`, `PROGRAM-WEIGHTS.yaml`, `phase-0-baseline-manifest.yaml`.
No review, adjudication or finalizer artifact landed. No criterion scored.

## Mutation / attack results

All mutations in a throwaway `git archive` copy under `/private/tmp`. The real worktree was never
modified.

| # | Attack | Result |
|---|---|---|
| A1 | AP-9 → `CONSUMES:ApprovalConsumed` (owner AP-7, mutually exclusive) | CAUGHT (10 guards) |
| A2 | AP-9 → `CONSUMES:BrakeReleased` (unrelated M13 event) | CAUGHT (10 guards) |
| A3a | R-01 state-only swap PL-10⇄PL-11, spec only | CAUGHT |
| A3b | same swap coordinated with the audit, all five totals and full membership byte-identical | CAUGHT — only the relationship changed and only the relationship check objected |
| A4a | R-02: PL-7a → `CONSUMES:EffectExecuted` by one token | CAUGHT |
| A4b | PL-7a also forges its own forward leg | **CAUGHT on the REVERSE leg specifically** |
| A4c | PL-7a also forges EF-3's reverse leg in the M3 file | CAUGHT, by bookkeeping + anchors (Finding 2) |
| C1 | total-preserving EVENT_REQUIRED↔CONSUMES swap (AP-9→CONSUMES, PL-6→EVENT_REQUIRED, totals held) | CAUGHT (6 guards) |
| D1 | AP-9 → `NON_PRODUCING:ENUMERATED_NO_OP` with a live durable write | CAUGHT |
| D2 | PL-7a → `DELEGATES_TO:CHECKPOINT=PL-7b` | CAUGHT, by audit set-equality + anchors (Finding 3) |
| B1 | retired "24 of 134" revived bare in ARCHITECTURE.md | CAUGHT |
| B2 | same claim + trailing "retired and superseded" clause | **SURVIVED** (Finding 1) |
| B3 | retired "121/13" restated as current | CAUGHT |
| B4 | `COUNT_NEEDS_ADJUDICATION` revived live | CAUGHT |
| B5 | AP-9 self-exempts in prose | CAUGHT |
| B6 | 5d bypass — field name smuggled into a Writes cell as prose | CAUGHT |

**The reverse-leg proof is real.** Direct probe of `_consumes_relationship_errors`, isolating the
predicate from all bookkeeping:

```
baseline                    : FORWARD error + REVERSE error
+ PL-7a forges its own cell : REVERSE error only
  -> "owner EF-3 declares co-commit [(2,'EXECUTED')], consumer enters M2 ['CHECKPOINT'].
      The owner's own cell must name the state THIS row enters"
```

A candidate row **cannot buy its own exemption from its own cell** — mechanically confirmed.

## Findings

1. **LOW · NON-BLOCKING · not new, not owed.** `test_bootstrap_hermeticity.py:1377-1379` — the
   retired-"24" carve-out skips any sentence matching `retired|never mechanically`, so a labelled
   sentence survives. Positively asserted by the candidate's own hostile node; the already-adjudicated
   residual R-04/R-05. **Not** a regression of the F-03 fix (B1 confirms F-03's exploit is closed).
2. **MEDIUM · NON-BLOCKING.** `TRANSITION-EVENT-AUDIT.yaml:197-199` asserts the reverse leg
   "PRE-EXISTS the claim", but nothing compares co-commit declarations against the certified parent.
   Laundering PL-7a now needs eight coordinated edits versus one token at 1ae365a.
3. **MEDIUM · NON-BLOCKING · NEW, raised by neither prior review.** `_resolve_delegation`
   (`test_bootstrap_hermeticity.py:372-411`) accepts `DELEGATES_TO:CHECKPOINT=PL-7b` on PL-7a with
   one token authored inside the row's own cell — no co-commit, no counterpart evidence. The
   delegation is semantically false: it resolves to `ApprovalBound`, asserting a bound human
   approval on the one path that proceeds WITHOUT a human.
4. **INFORMATIONAL.** Controller's F-04 cleanup independently verified: tree unchanged, no commit,
   blobs reachable from both preserve refs, on-disk copy byte-identical (`3a660afe…f6f1`). Effect
   reproduced deterministically — restoring the report fails exactly one document-classification
   node. Because the files were untracked, a clean clone never contained them, so the cleanup
   removed a divergence rather than creating one.
5. **INFORMATIONAL — reviewer's own disclosure.** It started `scripts/clean_clone_gate.py` and
   **aborted before completion** on discovering it writes the tracked `GATE-RESULT.json` — a
   forbidden surface for this unit and an artifact the finalizer must produce from its own run. It
   verified `GATE-RESULT.json` (`20c46e79…`) and `SUITE-RESULT.json` (`e496d6f7…`) still match HEAD
   and the tree is clean. Consequently it obtained **no** independent clean-clone result.

## Eligibility

d59b740 IS eligible for exactly one finalizer-generated metadata commit, **conditional on the
separate targeted re-adjudication** the U5.1 record's `owed_next` requires.

## Not verified

The clean-clone gate (aborted deliberately); whether the nine CONSUMES relationships are
architecturally true beyond the structured columns; the historical correctness of the 38b4bda and
1ae365a adjudications; any settled P4/R-07 work; mutation testing over `src/`; the merits of the two
carried residuals (`PL-9→EffectAttempted`, `PL-11c→OutcomeUnknown`).
