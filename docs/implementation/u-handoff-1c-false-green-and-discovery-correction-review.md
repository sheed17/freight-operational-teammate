> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U-HANDOFF-1C — False-Green, Dynamic-Discovery and Safety-Graph Correction — Review

> ### **CLOSED.** Status can no longer be attested — only executed. The finalizer runs the
> complete suite, the clean-clone gate and the acceptance gates itself and records only what it
> observed; pytest configuration is isolated and the population is verified by exact node
> identity; skip detection covers the whole suite against an exact approved manifest; the
> P3/P4 safety wall is protected transitively for every phase; and guard populations are
> discovered through one central inventory with a meta-guard against hand-enumeration.
> ### **The hostile review's verdict was VALID and is PRESERVED: NOT READY, six HIGH findings —
> every one reproduced here as a mutation and every one now caught.**
> ### **R-07 remains OPEN — NOT CONTAINED. P3 remains BLOCKED. Product direction untouched.**

**1. Starting HEAD:** `c35ed9edad221e3aa8c92e59da6be0c196b3cbda` · tree
`c479d03b2145d8f9851b234432e1976518af6749` · clean.
**2. Hostile review verdict:** NOT READY (after the second independent rehearsal passed 13/13 —
the rehearsal tested comprehension; the hostile review attacked the controls and won).

## 3. The HIGH findings, each closed by construction

| | Finding | Correction |
|---|---|---|
| **H-1** | fabricated suite artifacts accepted | [`scripts/finalize_status.py`](../../scripts/finalize_status.py): the ONLY finalization path **executes** every step itself — dirty-tree refusal, Python floor, dependency check, exact-population check, the complete suite, the clean-clone gate, the control guards, AC-SAFE-012/013, AC-SEC-001 — observing exit statuses directly, purging pre-existing receipts before running, writing evidence only from in-process results. **No count flags, no artifact path, no trust/skip flags** (guard-asserted). The old finalizer is a refusing shim — no second, weaker route. |
| **H-2** | pytest addopts silently removed 31 tests | [`pytest-canonical.ini`](../../pytest-canonical.ini) via explicit `-c` (pyproject/parent configs ignored), `PYTEST_ADDOPTS` cleared, config self-checked for filtering tokens; [`TEST-NODE-MANIFEST.json`](TEST-NODE-MANIFEST.json) records **exact node identities**; the runner compares collection to the manifest by identity, runs `-v`, captures **every node's outcome**, and rejects unexecuted, rogue, deselected and unapproved-skip nodes. Regeneration is a separate intentional command, unreachable from finalization. |
| **H-3** | skip detection covered 25 of 106 files, control guards excluded | AST discovery over **every tracked canonical test module** ([`inventory.skip_xfail_sites`](../../eval/control/inventory.py)) against [`APPROVED-SKIPS.yaml`](APPROVED-SKIPS.yaml) — exact set both directions (unlisted skip fails; vanished approved skip fails), reasons bound to the actual skip messages, dynamic outcomes enforced per-node by the runner. The imperative skip in `test_phase0_deprecated_semantics.py` is now a hard failure (missing baseline = manifest corruption, not silence). |
| **H-4** | live "24 event-less" contradiction in the registry | The registry's P5 blocker now states the adjudication truthfully. The scan is **dynamic**: every current-authority document (discovered from the map) must carry no live stale claim; every historical document must disarm **before** the claim (banner-position aware). Proven by planting a classified control document containing the retired claim — caught without touching the guard. |
| **H-5** | P6+ could bypass the wall with self-consistent views | Transitive-ancestry guard over **discovered** phase units: P3 must be an ancestor of every P≥4, P4 of every P≥5, each P4–P14 keeps its direct predecessor, acyclic, no disconnected island, READY requires all transitive dependencies COMPLETE. **Every bypass P6→P14 generated programmatically as a mutation — all caught**, including an inserted P15 outside the ancestry. |
| **H-6** | systemic hand-enumerated populations | [`eval/control/inventory.py`](../../eval/control/inventory.py): one discovery layer over `git ls-files` + the authority map's own rows + documented family rules + AST. Refactored onto it: volatile-figure files, retired-24 files, citation files, superseded-document set, review family, guard-file discovery, historical exemptions, **NEGATIVE_ASSERTION_TESTS** (now AST-discovered corpus-scanning negatives, all with proven populations — 6 previously-unproven guards gained real population proofs). A **meta-guard** rejects list/tuple/set/dict literals of 3+ path-like strings in any discovered control guard unless annotated `FIXED-SPECIFICATION` with a reason; legitimate fixed specifications (HANDOFF IDs, the P0–P14 chain, the table partition, the errata trio) are annotated as such. |

## 4–7. The corrected trust model, stated honestly

An unkeyed local JSON cannot prove execution — its hash proves only post-hoc integrity. The
repository now says so in the validator itself (renamed **`artifact_consistency_errors`**; its
docstring states what consistency does and does not prove). **Proof of execution is the
finalizer's own process observation**; the artifacts are **generated evidence**, bound to commit,
tree, node-manifest hash, config hash and runner hash. No in-repository secret is invented
(a local secret is available to the forger); **externally signed CI provenance is documented as a
possible later strengthening, not claimed and not required.**
The hostile attack is now a permanent test:
`test_a_perfect_forged_artifact_cannot_complete_finalization` handwrites a structurally perfect
green artifact with every unkeyed hash correct, blocks execution, attempts finalization — and is
refused with status untouched and the forgery unconsumed.

## 8. Clean-clone gate — decisive (M-5)

Every previously-advisory condition now fails the gate: suite-count/node-identity divergence,
unapproved skips or xfails, deselection, failed control guards or AC gates, a dirtied clone, a
config differing from the authoring commit's. The gate writes
[`GATE-RESULT.json`](GATE-RESULT.json) **from its own process** — steps, exit statuses,
commit/tree/manifest/config/runner bindings — records its own failures, and the finalizer
**deletes any pre-existing gate result before invoking**, then requires a fresh one bound to the
finalized commit. A gate PASS with no gate-written record is refused (battery case 39).

## 9–10. M-4 — dirty trees never PASS

The status-reality measurement checks now raise an **explicit machine-visible SKIPPED** on a
dirty tree (previously: silent early-return PASS). Those NOT-RUN skips are deliberately absent
from `expected_canonical_run_skips`, and the finalizer refuses dirty trees before pytest starts —
so a canonical run can never contain them, and if one ever appears, finalization fails. The
dirty-tree refusal itself is tested against **temporary git repositories**, not the authoring
checkout's incidental state.

## 11–16. Low findings

- **Branch field** → `recorded_authoring_branch`, marked *advisory; not verified across
  bundles/clones*, guard-held.
- **Bare pytest** → pyproject `testpaths` fixed from the nonexistent `tests/` to `eval` (bare
  `pytest` collects the canonical population; canonical runs still pin `-c`).
- **Vacuous assertion** → the tool-access possession check now tests the property directly
  (affirmative possession-authorizes claims are matched and refused; the `or`-escape is gone).
- **Banner position** → required in the first meaningful block AND physically before every stale
  claim; proven by the moved-banner mutation.
- **P3 acceptance** → the registry now cites **the 105-case checkpoint merge-gating matrix
  (7 steps × 15 conditions) and its universal oracle** in `platform-safety-acceptance.md`, plus
  the AC-CKPT-1-* .. AC-CKPT-7-* step families. No P3 behaviour changed.
- **Line citations** → current-reality documents carry none (dynamic scan); `migration-plan.md`
  and `pr-sequence.md` declare their citations **reset-snapshot coordinates of code Phase 1
  deleted** (guards separately assert those symbols stayed deleted); the frozen architecture
  corpus is snapshot evidence by its own layer/date declaration.
- **Count-only assertions** → the load-bearing counts (manifest, collection) are now derived from
  exact guarded sets.

## 17. Historical review authority (M-2/M-3)

`AUTO-LOADED-GUIDANCE-REVIEW.md` **demoted to HISTORICAL (evidence)** — its live obligations are
enforced by guards, not by the document. **Every implementation review (18 files) and every
remaining pre-reset docs-root file (15 more) now opens with a disarming banner** — classification,
do-not-direct, canonical replacements — derived dynamically and position-enforced.
`canonical-corpus-errata-review.md`'s "READY TO BEGIN" and retired-24 text now sit below its
banner, and the moved-banner mutation proves position matters.

## 18–19. Tests and guards added

`eval/control/inventory.py` (the discovery layer) · `eval/tests/test_false_green_defenses.py`
(**23 guards**: the hostile forgery reproduction, bypass-surface checks, gate-record binding,
config isolation, node-manifest exactness, whole-suite skip enforcement with reason-binding,
dynamic 24/volatile/citation scans, banner position, transitive safety wall, the anti-enumeration
meta-guard, discovered negative-assertion enforcement, temp-repo dirty refusal) · reworked
`test_status_reality.py` (manifest-identity population check; renamed validator; forged-artifact
unit proofs) · `scripts/finalize_status.py` · reworked runner and gate · manifests
(`TEST-NODE-MANIFEST.json`, `APPROVED-SKIPS.yaml`) · `pytest-canonical.ini` · six previously
vacuous-capable negative guards given real population proofs.

## 20. Mutation battery — ### **44/44 DETECTED or DEFENSE-PROVEN**

All 40 required cases plus four extras (approved-skip removal, reason rewrite, pytestmark hiding,
runner execution-comparison). Programmatic generation covered every P6–P14 bypass individually.
Honesty notes, recorded rather than smoothed over:

- **Three first attempts were invalid and were re-proven properly**: cases 2/3 first "detected"
  for the wrong reason (an old-format artifact fails field checks before the tamper is even
  seen) — re-proven against a complete artifact with the specific rejection message; case 10's
  planted conftest collided with an existing file — re-proven by appending to the real conftest
  and watching 27 nodes vanish from collection against the manifest.
- **One real guard hole found and fixed**: H2-exec — hardcoding `unexecuted_nodes=[]` while
  keeping the field name slipped past a substring check; the guard now requires the actual
  set-difference computations. Re-proven.
- **One documented harness exception**: battery case 9 regenerates the node manifest under a
  hostile `PYTEST_ADDOPTS` to prove immunity, then restores the STAGED manifest via
  `git checkout --` — restoring staged content the harness itself did not text-mutate. No
  uncommitted work was at risk; noted because the no-git-restoration rule exists for uncommitted
  work.

## 21–26. Validation results

| | |
|---|---|
| **Canonical suite (authoring checkout, isolated config)** | SUITE_INSERTED_BY_FINALIZER |
| **Clean-clone gate** | **PASS** — executed BY the finalizer, result written by the gate process, bound to the content commit |
| **Finalizer** | end-to-end: executed the suite, the gate, the control guards and all three AC gates itself; recorded only observed results |
| **AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001** | **GREEN** — executed explicitly by the finalizer and inside both full-suite runs |

## 27–31. Final committed state

| | |
|---|---|
| **Content commit** | `CONTENT_COMMIT_INSERTED_BY_FINALIZER` |
| **Content tree** | `CONTENT_TREE_INSERTED_BY_FINALIZER` |
| **HEAD** | the single status-metadata commit on top (it cannot name itself; the two-commit convention holds) |
| **Recorded suite** | SUITE_INSERTED_BY_FINALIZER — from the finalizer's own executed run |
| **Working tree** | clean · **not pushed** |

## 32–34. Confirmations

**P3 unimplemented** — no checkpoint, witness or CAS symbol exists in `src/`
(IMPLEMENTATION-SURFACE absence guards green). **R-07 OPEN — NOT CONTAINED** (manifest guard
green). **Product direction untouched** — `src/` runtime unchanged; changes are runners,
finalization, gate, guards, manifests, configuration, control documents and banners.
**All 13 HANDOFF criteria remain PENDING.**

## 35. May another fresh hostile review begin? ### **Yes.**

Every attack the first hostile review demonstrated is now a permanent, passing defense test, and
every correction was mutation-proven rather than asserted. What this session cannot do — as ever —
is review itself: the second hostile review must be run fresh, and the clean-clone gate plus the
end-to-end finalizer give it a one-command reproduction surface for every claim above.

---

# VERDICT

## ### **READY FOR SECOND HOSTILE HANDOFF-READINESS REVIEW**

**Carried forward, unchanged:** ### **R-07 OPEN — NOT CONTAINED** · the six adjudicated
production-reachable live-write paths · 31 adapter-import edges · the tenant table partition
(7+1+3=11) · the knowledge-base `tenant="default"` finding (symbol-cited) · the transition/event
finding (**COUNT NEEDS ADJUDICATION** at G2) · founder-operated design-partner limitation ·
P0/P1/P2 COMPLETE · **P3 BLOCKED** · one READY unit (U-HANDOFF-1) · thirteen PENDING criteria.
