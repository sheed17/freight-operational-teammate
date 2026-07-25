> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U-REBASELINE-1A — Founder Rebaseline Adjudication — Review

**Unit:** U-REBASELINE-1A · **Date:** 2026-07-20 · **Session role:** adjudicator — not the
reviewer (U-REBASELINE-REVIEW-1 was independent, run in a fresh testing-account clone) and not the
implementer (**P3 was not begun**).

---

## 1. Starting state — verified before any modification

| | |
|---|---|
| HEAD (metadata commit) | `fb5fcd93faa77a2daf37da192c05b62dd1b5bfbf` |
| Tree | `6bbef434fe78bcb9d41cf492968d0448b89b266c` |
| Parent (content commit) | `98e531fdcc525ba47d780f48232eb0f9891314c6` |
| Working tree | clean |
| Recorded suite | 1268 passed · 0 failed · 1 skipped · 1269 manifest nodes |

**Every identity claim in the independent report matched exactly**, including the two-commit
parentage and the exact five-file metadata diff.

## 2. Independent review source

**U-REBASELINE-REVIEW-1**, produced in a fresh testing-account clone at the exact target, read-only
(no repository file edited, no commit made, no control state modified — re-verified by the reviewer
at review end). Preserved verbatim and complete at
[`u-rebaseline-review-1-independent-report.md`](u-rebaseline-review-1-independent-report.md).
Delivered complete — **no truncation**.

Its verdicts: **Product PASS · Surface/conversational PASS · Freight coverage PASS WITH SIGNIFICANT
FINDINGS · Production specification PASS · Safety/control PASS · Implementation handoff PASS.**
**Zero CRITICAL findings.**

## 3. Adjudication of every finding

Severity as the reviewer assigned it. "Re-verified" = I confirmed the citation at source before
accepting.

| ID | Sev | Disposition | Resolution |
|---|---|---|---|
| **F-01** stale L6→W8 residue in 3 canonical files | HIGH | **ACCEPTED — re-verified** (`W6:3`, `W8:3`, `registry:75`) | **RESOLVED.** In-place ⚠️ supersession notes in all three: the wedge is Delivered Load Closure; W6/W8 are *contributors*, not the slice. |
| **F-02** CK/MF named for ~10% of consequential steps + the false-green self-review row | HIGH | **ACCEPTED — re-verified both sides** | **RESOLVED.** `workflows/registry.md` gains an explicit **CK/MF default-inheritance rule** (inherited ≠ under-specified, bound at P6–P9, silence means the canonical amount-free default); `operational-workflow-review.md`'s overclaiming row is **corrected in place**. |
| **F-03** coverage-guard porosity (blob topics; count-not-membership) | HIGH | **ACCEPTED — re-verified in guard source** | **RESOLVED.** Guard rewritten: topics matched against **parsed records**, population pinned by **exact UC-id membership** (`UC-01..UC-33`, symmetric diff), duplicate-id check added. The count floor — the exact defect CLAUDE.md §8 forbids — is gone. |
| **F-04** broken V-reference namespace (dangling/colliding) | HIGH | **ACCEPTED — re-verified by sample** | **RESOLVED.** `workflows/registry.md` declares the **validation-reference namespace**: canonical items are always `V-01…V-21` in `OPEN-VALIDATION-ITEMS.md`; bare numerals in loop specs are **workflow-local markers that must never be resolved against them**. Re-keying recorded as debt (re-numbering risks silently re-pointing semantics). |
| **F-05** validation-status vocabulary unguarded | MEDIUM | **ACCEPTED** | **RESOLVED.** Closed enum + a guard asserting **zero `VALIDATED*` entries** while `design-partner-observations.md` records no firsthand observation. |
| **F-06** DISARM self-disarm via bare ADR citation; polarity-blind chatbot check | MEDIUM | **ACCEPTED** | **RESOLVED.** A bare ADR citation is **no longer a disarm marker**; retirement vocabulary is required. |
| **F-07** vacuous pass in the src-untouched guard; hardcoded baseline | MEDIUM | **ACCEPTED** | **RESOLVED.** Now **skips loudly** (machine-visible NOT-RUN, registered in `APPROVED-SKIPS.yaml` and deliberately absent from expected canonical-run skips) and reads the baseline **from the registry**. |
| **F-08** RB-13/RB-15 cite ADR-016 for CI/CD & queues it never names | MEDIUM | **ACCEPTED — re-verified (grep: zero CI/CD hits)** | **RESOLVED both ways.** ADR-016 §2 gains a **CI/CD & release row** (incl. rollback exercises), and the RB-13/RB-15 evidence strings are rewritten to cite what actually carries each item. |
| **F-09** gate classes unstated for several consequential effects | MEDIUM | **ACCEPTED** | **RESOLVED.** W2/W4/W5/W6 carry an explicit **gate-class delegation**: unstated gates inherit the registry default (full Action Pipeline); the specific approval class is `NEEDS VALIDATION`; **no step is ungated by omission.** No policy was invented. |
| **F-10** unlabeled trace-id namespaces; 61-point index unpublished | MEDIUM | **ACCEPTED AS RECORDED DEBT** | **NOT resolved.** Re-numbering trace ids across historical review batteries, and reconstructing a 61-point index that no document enumerates, would require inventing structure I cannot verify. Auditability noise only; blocks nothing. Carried as debt. |
| **F-11** literal `NEEDS VALIDATION` marker uneven | LOW | ACCEPTED | **RESOLVED.** All **11** loops now carry the literal marker (was 2). |
| **F-12** guard hygiene (dead code, missing id/use_case, dup check, ordering) | LOW | ACCEPTED | **RESOLVED** with the F-03 rewrite; `UC-32`/`UC-33` reordered. |
| **F-13** ARCHITECTURE lacks the loop map; W10 name drift | LOW | ACCEPTED | **RESOLVED.** ARCHITECTURE.md §28b presents the eleven-loop table; W10 naming aligned. |
| **F-14** CI/CD & rollback outside the production ADR; stale roadmap banner | LOW | ACCEPTED | **RESOLVED** with F-08; roadmap banner refreshed to the canonical seven tiers. |
| **F-15** no forward tripwire for channel divergence | LOW | ACCEPTED | **RESOLVED.** `IMPLEMENTATION-SURFACE.yaml` gains per-channel conversation-store `absent_symbols` — the build fails the moment a second channel store appears before the single cross-channel conversation. |
| **F-16** "headless" terminology absent | INFO | ACCEPTED | **RESOLVED.** PRODUCT.md §5 states **headless-first and channel-independent** explicitly. |

**15 of 16 resolved; F-10 accepted as recorded debt.** Every finding the reviewer said must be
resolved **before RB-24 is declared PASS** (F-01, F-02, F-04, F-08) and the full guard-integrity set
(F-03, F-05, F-06, F-07) were resolved **before** RB-24 was set.

## 4. RB-01…RB-24

**All 24 PASS.** RB-01…RB-23 were executed and evidenced by the U-REBASELINE-1 session (two
citations corrected here under F-08). **RB-24 was awarded by this adjudication from the INDEPENDENT
review** — its evidence cites the preserved report, and a guard now requires exactly that: RB-24's
evidence must name `u-rebaseline-review-1-independent-report.md`, and that file must exist. The
executing session never self-certified it.

## 5. Control transition

| | Before | After |
|---|---|---|
| U-HANDOFF-1 | COMPLETE | **COMPLETE** (unchanged) |
| U-REBASELINE-1 | READY | **COMPLETE** |
| P3 | BLOCKED | **READY — the one and only READY unit** |
| P4…P14 | BLOCKED | **BLOCKED** (unchanged) |
| R-07 | OPEN — NOT CONTAINED | **OPEN — NOT CONTAINED** (unchanged; closes at P4) |

**P3's weighted acceptance contract is instantiated**: 14 criteria from the approved
`acceptance_template`, weights summing exactly 100, **every result PENDING**. P3 is READY, *not*
started — and the absence guards still prove no checkpoint/witness/claim-CAS symbol exists in
`src/`.

Guards that pinned the previous state were **replaced, not deleted** (CLAUDE.md §5 rule 20):
`test_24` (READY must now be P3, with every gate ancestor COMPLETE and evidenced), the rebaseline
checklist guard (fully adjudicated; RB-24 must cite the independent report), the hermeticity READY
set, the rebaseline-invariants READY guard, and the status-reality guard (P3 READY **and** provably
not implemented; P4+ BLOCKED).

## 6. Derived progress (mechanical — the finalizer computes and refuses inflation)

| | |
|---|---|
| CLI switch readiness | **100%** — all five gates DONE (handoff closed · rebaseline written · **independent review passed** · **independent repository inspection agreed** · **P3 weighted contract instantiated**) |
| Overall implementation program | **0%** — P3's criteria are all PENDING; nothing past P2 is built |
| Current phase P3 | **0%** |
| User-visible product maturity | **0%** |
| Production readiness | **0%** |
| Readiness tier | **SPECIFIED** |

## 7. Files changed

Product/spec: `PRODUCT.md`, `ARCHITECTURE.md`, `workflows/registry.md`, `W2/W4/W5/W6` (gate
delegation), `W6/W8` (supersession), `W3/W7/W9/W10/W11` (validation markers), `W10` (naming),
`operational-workflow-review.md` (corrected row), `ADR-016` (CI/CD row).
Control: `IMPLEMENTATION-REGISTRY.yaml`, `U-REBASELINE-1-ACCEPTANCE.yaml`, `PROGRAM-WEIGHTS.yaml`,
`BUILD-STATUS.yaml`, `CURRENT.md`, `APPROVED-SKIPS.yaml`, `IMPLEMENTATION-SURFACE.yaml`,
`implementation-roadmap.md`, `CANONICAL-DOCUMENTS.md`, `registry.md`, `OPERATIONAL-USE-CASE-COVERAGE.yaml`.
Guards: `test_rebaseline_invariants.py`, `test_docs_control_system.py`, `test_status_reality.py`,
`test_bootstrap_hermeticity.py`, plus `TEST-NODE-MANIFEST.json`.
Evidence: `u-rebaseline-review-1-independent-report.md`, this review.
**No file under `src/` changed.**

## 8. Confirmations

- **No runtime code changed** — the diff is documentation, specification, control and guards only.
- **P3 remains unimplemented** — READY is permission to begin, not evidence of beginning.
- **R-07 remains OPEN — NOT CONTAINED.** It closes at P4 and nowhere earlier.
- **Every customer-specific validation blocker stands**; no design-partner validation is claimed;
  no freight rule was invented; no transportation mode is claimed validated.

---

## Verdict

**READY FOR FORMAL CLAUDE CODE IMPLEMENTATION AT P3**
