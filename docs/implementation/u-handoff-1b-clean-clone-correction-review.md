> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Verdicts, statuses, counts and "READY"
> declarations below describe the state THEN — several are known-superseded (including any
> "24 of 134" transition figure, retired by U-HANDOFF-1B, and any suite count). Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U-HANDOFF-1B — Clean-Clone Reproducibility and Authority Correction — Review

> ### **CLOSED.** The repository is now reproducible from a genuinely clean clone: the bootstrap
> fails fast on a wrong Python, every import is declared, the Phase-2 suites build their own
> databases deterministically, the status record is backed by a machine-readable result artifact
> from an actual run, and the clean-clone gate proves the whole chain in one command.
> ### **The independent rehearsal's verdict was VALID and is PRESERVED: NOT READY, 11/13, with
> HANDOFF-03 and HANDOFF-12 failing on exactly the false green corrected here.**
> ### **R-07 remains OPEN — NOT CONTAINED. Phase 3 remains BLOCKED. No production business
> behaviour changed.**

**1. Starting commit:** `eedea343a7320d9c1d90ed1c02536dbbc4bf18af` · tree
`42057b51811a388e2e30d4dc3d6c5e2b5e916620` · branch `recovery/u2-6bc-atomic-cutover`, clean.

## 2. The independent rehearsal's failures — preserved, not rewritten

**11 of 13 criteria PASS; HANDOFF-03 and HANDOFF-12 FAIL.** The decisive evidence: recorded
**1179 passed · 0 failed** versus an actual clean-clone result of **1133 passed · 46 failed** —
every failure tracing to `data/active_workspace/neyma_workflow.sqlite3`, a gitignored, untracked,
developer-local database no clean clone possesses. Plus: an unenforced Python floor, the
undeclared `websocket` dependency, a status guard proving test *counts* rather than test
*results*, a self-contradicting `registry.md`, an unclassified root `stages.txt`, eight graph
inconsistencies, and three load-bearing figures no executable source computed.

## 3–4. H-1 — the bootstrap works from zero

- **Python floor:** [`scripts/check_env.py`](../../scripts/check_env.py) reads
  `requires-python` from `pyproject.toml` (never hardcoded), refuses an old interpreter
  **immediately** with the detected and required versions, and runs **before** any install in
  README/CLAUDE bootstrap sequences — pip never gets to backtrack for twenty minutes first.
- **Dependency:** `websocket-client>=1.6` is declared once in `pyproject.toml` (the `websocket`
  import in `cdp_session.py`). `requirements.txt` — a stale Phase-1 mirror that also omitted it —
  is now an explicitly-labelled compatibility mirror. An AST guard generalises the lesson:
  **every third-party import in `src/` must map to a declared distribution**, so the next
  undeclared dependency fails the build instead of the next reviewer.

## 5. H-2 — hermetic fixtures

[`eval/fixtures/legacy_workspace.py`](../../eval/fixtures/legacy_workspace.py) builds the legacy
pre-P2 database **byte-deterministically from committed code**: the exact legacy DDL and the
exact population profile (18 runs = 15 NEEDS_REVIEW + 3 DONE; 102 audit events = 18×4 + 15×2;
0 security events) with fully synthesized values — **no founder data copied**. All six affected
test files now build their inputs; the `== 18` assertions reference the builder's exported
constants. **Proof by absence: the entire affected suite set (162 tests) was run with
`data/active_workspace` renamed away — all green, random order.** Guards hold it: no test file
may reference `active_workspace`, absolute home paths, or `Path.home()`; no test may skip itself
when a database is absent; the fixture is asserted byte-identical across double builds.

## 6. Clean-clone suite result

1205 passed · 0 failed · 1 skipped — see §22; the clean-clone gate reproduced the committed result in a
fresh clone + fresh venv with only declared dependencies.

## 7. Status-result verification design

- [`scripts/run_canonical_suite.py`](../../scripts/run_canonical_suite.py) — the **only**
  producer of [`SUITE-RESULT.json`](SUITE-RESULT.json); standalone (no pytest recursion);
  **refuses dirty trees**, so a developer-local result can never enter the record.
- The artifact records: command · commit · tree · Python · platform · passed/failed/skipped ·
  collected · deselected · duration · exit status · timestamp · payload sha256.
- [`scripts/suite_result.py`](../../scripts/suite_result.py) — **one shared validator** imported
  by runner, finalizer and guard, so they cannot drift. It rejects: red runs, nonzero exit,
  deselection, vanished tests, results from another commit or tree, tampered payloads,
  non-canonical commands.
- The finalizer **takes no count arguments any more** (the 1A finalizer accepted `--passed` on
  faith); it records status only from a valid artifact.
- The status-reality guard validates the chain end to end and unit-tests the validator against
  **forged artifacts** (green-with-failure, stale commit, stale tree, crashed run, filtered run,
  edited payload) — so weakening the validator is caught even while every real artifact is green.
- The two-commit convention survives with a third recognised transient state (PRODUCING: exactly
  one content commit atop a pure metadata commit, the window in which the runner produces the
  next artifact). Collection cross-checking **remains** — as a drift tripwire at rest, no longer
  as the proof of green.

## 8. `registry.md` authority correction (H-3)

Design chosen and documented in-file: **human-readable index, NO independent status authority.**
The YAML registry is the machine-readable authority; `CURRENT.md` is the status authority. The
contradictory status table (Phase 2 "IN PROGRESS — NOT READY", "begin U2.6B") is quarantined in a
labelled `<details>` block as evidence; a guard fails the build if live text asserts Phase-2
IN PROGRESS or instructs U2.6B, and the banner text itself is excluded from the scan by structure
(blockquote stripping), not by exception.

## 9. `stages.txt` disposition (H-4)

Moved to `docs/stages.txt` with a full in-file supersession banner; classified **SUPERSEDED** in
the authority map. The root-document guard is now **dynamic discovery**: every root `.md`/`.txt`
must be classified by the authority map, and any file presenting stage-roadmap content without
superseded-marking fails — proven by a file-creation mutation (`NEW_ROADMAP.md` appearing at root
was detected).

## 10. Implementation-graph correction (M-1)

Canonical model chosen: **`dependencies` is authoritative; `unlocked_by`, `blocks` and
`next_units_unlocked` are derived views**, regenerated for all 17 units and mechanically enforced.
The full-graph guard proves: every dependency exists · reverse edges agree exactly · acyclic ·
**P3 requires U-HANDOFF-1 · P4 requires P3 · P5 requires P4** (the rehearsal's exact bypass:
P5 depended on P2) · exactly one READY unit · ≥16 edges (zero-edge discovery rejected).

## 11. Superseded-document banners (M-2)

Every document the authority map classifies SUPERSEDED or QUARANTINED_GUIDANCE now **opens** with
a disarming banner (classification, do-not-direct-implementation, canonical replacement,
evidence-only status): `NEYMA_VISION` · `PRODUCT_ROADMAP` · `AGENTIC_ARCHITECTURE` ·
`OWNER_OPERATOR_ROADMAP` · `DESIGN_PARTNER_PILOT` · `INTERNAL_DOGFOOD_PILOT` · `CODEX_HANDOFF` ·
`CODEX_FIX_HANDOFF` · `stages.txt`. The guard **derives the list from the map's own
classifications** — classifying a new file without bannering it fails immediately — plus a
self-claim scan for any docs-root file declaring itself a source of truth.

## 12. Agent-frontmatter corrections (M-3)

`roadmap-steward` frontmatter no longer advertises the 8-stage roadmap: it names **P0–P14**,
`CURRENT.md` as the status authority, and "Phase 3 does not start automatically".
`build-supervisor` frontmatter drops the stage vocabulary. A guard inspects **frontmatter
separately from body** (the listing shows frontmatter without the body's banner) and forbids
stage-roadmap language there; codex surfaces must open with their compatibility pointer.

## 13. Transition/event result — COUNT NEEDS ADJUDICATION

The claimed "24 of 134" **was never mechanically computed** — the plausible source parsed
machine tables with a naive split that mis-aligns columns on escaped pipes (`H\|S`). The
escape-aware computation ([`TRANSITION-EVENT-AUDIT.yaml`](TRANSITION-EVENT-AUDIT.yaml), recomputed
by guard on every run): **134 transitions; 121 name an event; 13 do not, in four structurally
different classes** — 5 bare `—` · 3 documented non-producing · 3 unnamed-ILLEGAL (while two
other ILLEGAL rows *do* name `IllegalTransitionAttempted`) · 2 delegating ("as those").
**The specifications do not define which classes violate AC-EVT-003**, so per instruction the
finding carries **COUNT NEEDS ADJUDICATION** with the exact G2 decision spelled out, exact
members guarded as sets, and the retired "24" forbidden as a live count in control documents.

## 14. Canonical table partition (M-4)

Recorded explicitly in `CURRENT.md` and guarded as four exact disjoint sets:
**7 migrated tenant-owned + 1 already-tenant-first (`autonomous_run_counters` — the eighth
tenant-first table "7+3" had been hiding) + 3 exempt bookkeeping = 11 canonical.**

## 15. Live-write inventory (M-4)

[`EFFECT-PATH-INVENTORY.yaml`](EFFECT-PATH-INVENTORY.yaml): all **10 import-probe candidates plus
EP-2** adjudicated with per-entry reachability, enablement, bypass, classification, containment
phase, disposition, and an explicit exclusion reason for everything outside the six.
**The production-reachable live-write set was RE-DERIVED, not forced, and remains exactly six**
(EP-1, EP-3, EP-6, EP-7, EP-9, EP-10). `read_tms_browser_use.py` is **adjudicated EP-14**
(closes P0-F4): reads the mock TMS behind an optional dependency, actuator-capable by transitive
import — read-by-convention class with EP-8, inside the R-07 containment scope, not a live-write
path. Guards enforce exact membership both ways against the manifest probe.

## 16. Count-drift corrections

WORKFLOW_BLOCKER summary 5→**4** (four exist) · volatile corpus counts (198 docs, 23 files,
52 scripts, 77 modules) removed rather than maintained · the KB citation is symbol-based
(`action_callback.py::_learn_correction`) with a guard that verifies the sites *exist* and
forbids line-number citations — the recorded `:1639` had already drifted to 1657 ·
`durable-cli-control-documentation-review.md` and both `u-handoff-*` reviews are covered by an
explicit **FAMILY RULE** in the authority map (every implementation review = HISTORICAL evidence,
automatically), with a guard that every implementation document is classified or family-covered.

## 17. HANDOFF-10 wording

Now distinguishes **describing** the broad formal-session tool posture from **operating** under
it: the rehearsal agent must summarise the policy, remain repository-only, and not claim live
external tools. Evidence requirements updated; a guard holds the repository-only boundary.
**All 13 criteria remain PENDING** — nothing was marked passed in this session.

## 18–19. Tests and guards added

`eval/fixtures/legacy_workspace.py` (deterministic builder) ·
`eval/tests/test_bootstrap_hermeticity.py` (**26 guards**: bootstrap fail-fast, import
declaration, hermeticity static+dynamic proofs, fixture determinism, transition audit, table
partition, effect-path inventory, full-graph consistency, registry.md authority, dynamic root
discovery, banner derivation, frontmatter, finalizer/runner posture, citation symbol guard,
HANDOFF-10 boundary) · reworked `eval/tests/test_status_reality.py` (**7 guards** incl. the
forged-artifact unit proofs) · `scripts/check_env.py` · `scripts/suite_result.py` ·
`scripts/run_canonical_suite.py` · `scripts/clean_clone_gate.py` — all dispositioned S15g.

## 20. Mutation results — ### **23/23 DETECTED** *(first pass 21/23; both misses fixed and re-proven)*

All 23 required mutations ran under the safe in-memory harness (digest-verified restoration,
bytecode purged, no git restoration, no-ops rejected — one no-op rejection caught a mutation
aimed at the wrong file, and the file-creation mutation for the root-roadmap case got its own
create/finally-delete handling).

| First-pass miss | Root cause | Fix |
|---|---|---|
| **B-6** (status reality compares collection only) | the meta-guard checked for the SUBSTRING `validation_errors`, satisfied by the import line while the actual call had been deleted | AST-based: the artifact-backing test must contain a **Call** to `validation_errors` |
| **B-22** (repository-only boundary weakened) | my mutation removed one of TWO repository-only sentences — unfaithful, verified rather than assumed | mutation made faithful (both sentences); guard fired |

## 21–25. Validation results

| | |
|---|---|
| **Authoring-checkout suite** | 1205 passed · 0 failed · 1 skipped |
| **Clean-clone gate** | **PASS** — fresh clone · fresh venv · declared deps only · env check · full suite · control guards · gates · clone tree clean (§22 of the gate output, recorded below) |
| **AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001** | **GREEN** in both the authoring checkout and the clean clone |
| **Hermeticity spot-proof** | the six affected suites ran green with `data/active_workspace` renamed away |

## 26–31. Final committed state

| | |
|---|---|
| **Content commit** | `e563a4fc6153c3b44e775ebaa95b0fe01009df7f` |
| **Content tree** | `c8770e46f87f7b984d5cbf61d2097e9c7390db27` |
| **HEAD** | the single status-metadata commit on top (per the two-commit convention it cannot name itself here) |
| **Recorded suite result** | 1205 passed · 0 failed · 1 skipped — from the artifact written by the canonical runner on the clean content-commit checkout |
| **Status-reality guard** | **GREEN** on the committed checkout |
| **Working tree** | clean · **not pushed** |
| **Production business behaviour** | **UNCHANGED** — `src/` untouched except nothing; changes are dependency metadata, bootstrap/control scripts, test fixtures/infrastructure, guards and documentation |

## 32. May a second independent rehearsal begin? ### **Yes.**

The first independent rehearsal did its job: it found the false green the author could not see
from inside the authoring machine. Its verdict stands in the record. The corrections are
mechanical, guarded and mutation-proven, and the clean-clone gate now exists precisely so the
next rehearsal can verify reproducibility with one command instead of discovering its absence
over twenty minutes of pip backtracking. What this session cannot do — again — is grade itself:
**all 13 HANDOFF criteria remain PENDING until the second independent run fills them in.**

---

# VERDICT

## ### **READY FOR SECOND INDEPENDENT ZERO-CONTEXT REHEARSAL**

**Carried forward, unchanged:** ### **R-07 OPEN — NOT CONTAINED** · the six production-reachable
live-write paths (now exactly inventoried) · 31 adapter-import edges · the transition/event
completeness finding (**COUNT NEEDS ADJUDICATION** at G2) · the knowledge-base `tenant="default"`
sites (symbol-cited, guard-verified) · founder-operated design-partner limitation · P3
unimplemented and BLOCKED · P4 containment unimplemented · unresolved freight rules ·
unfinished legacy reduction.
