# Canonical Corpus Errata Review — 2026-07-16

> ### **Bounded errata pass. Corpus only.** No production code, no schema, no migration, no Commit Key change, no symbol rename. ### **`src/` and `scripts/` are byte-identical to `9f20b25`.**
> ### **This pass makes no live effect safer. It makes later release gates possible.**
> ### **Every amendment is the smallest change required to make the frozen documents match their own enumerated contents.** No concept renamed, no requirement added, no behaviour changed.

---

## 1. Defects corrected

| # | Defect | Was | ### Now | Blocked |
|---|---|---|---|---|
| **DEF-4** | canonical transition total | 141 | ### **134** | **G1** |
| **DEF-5** | canonical emitted-event total | 92 | ### **98** | **G2** |
| **DEF-6** | non-tenant-first tables | 6 of 8 | ### **7 of 8** | **P2 / U2.1** |
| **P0-F1** | U0.3 phase placement | Phase 0 | ### **`DEFERRED_BY_DEPENDENCY — REQUIRED AT PHASE 8`** | — |
| ### **ERRATA 5** *(found during this pass)* | ### **U0.5–U0.13 delivered but never declared** | undeclared | ### **declared in `pr-sequence.md`** | ### **the Phase-0 commit was RED** |

---

## 2. Evidence for 134 transitions

Fresh mechanical enumeration of all 13 machine files. ### **Every per-machine count in the acceptance spec matches its file EXACTLY. They sum to 134. Only the `Total` row was wrong.**

| machine | enumerated | acceptance spec | | machine | enumerated | acceptance spec |
|---|---|---|---|---|---|---|
| M1 Work Item | 14 | 14 ✔ | | M8 Expectation | 8 | 8 ✔ |
| M2 Pipeline | 25 | 25 ✔ | | M9 Exception | 7 | 7 ✔ |
| M3 Effect/Grant | 13 | 13 ✔ | | M10 Compensation | 9 | 9 ✔ |
| M4 Approval | 11 | 11 ✔ | | M11 Policy | 7 | 7 ✔ |
| M5 Observation | 8 | 8 ✔ | | M12 Rule | 9 | 9 ✔ |
| M6 Identity Binding | 11 | 11 ✔ | | M13 Brake | 5 | 5 ✔ |
| M7 Conflict | 7 | 7 ✔ | | ### **TOTAL** | ### **134** | ### **claimed 141** |

**Duplicate transition IDs:** none. **Malformed/skipped rows:** none. **Zero-row machines:** none. **Registry cross-check:** every transition cited by the event registry resolves — ### **no event invents a transition outside the 134.** **Exact-set digest:** `de13ddea5a448a0b` (134 ids).

> ### **The error at its source** (`state-machine-specification-review.md` §3, preserved): `14/25/13/11/8/11/7/8/7/9/7/9/5 = **141**`. ### **That list is CORRECT and sums to 134.** A human added it up wrong once; the wrong sum then propagated to six places while the correct list sat beside it.

## 3. Evidence for 98 emitted events

Enumerated from the canonical event list (`events/registry.md` §3).

| F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 | F9 | F10 | F11 | F12 | F13 | ### **emitted** | F14 | F15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12 | 12 | 14 | 7 | 7 | 6 | 4 | 7 | 5 | 7 | 6 | 7 | 4 | ### **98** *(claimed 92)* | ### **13 ✔** | ### **0 — a lens** |

### **`TimerFired` EXCLUDED** — it is a **trigger type** (`state-machines/registry.md`), not an emitted contract; grep-confirmed, and the original event review said so correctly. **F15 excluded** — *"no new contracts — a lens over cross-machine consumption."* **Duplicate event names:** none. **Shared ‡ contracts** (multiple structurally-identical producers) respected, counted once. **Producer cross-check:** 110 producer transitions cited, ### **zero orphans.** **Exact-set digest:** `6deb2ccecdfa8b3f` (98 names).

> ### **No events were invented to preserve 92. No bijection was weakened to an inequality.**

**Observation for G2 (not fixed here — out of scope):** 24 of the 134 transitions have no event cited. `AC-EVT-003` asserts *"every producer transition emits its required event"*. ### **Whether those 24 are non-producing transitions or a genuine mapping gap is a G2 question and must be settled before Phase 5.**

## 4. Evidence for seven offending tenant tables

### **Exactly ONE table is tenant-first. SEVEN are not.**

| table | PK | tenant col | ### tenant-first |
|---|---|---|---|
| `workflow_runs` · `audit_events` · `security_events` | `id` | ### **none** | ### **NO** |
| `operation_action_claims` · `delivery_action_claims` | `action_id` | none | ### **NO** |
| ### **`operation_commit_claims`** | ### **`commit_key`** | ### **YES** | ### **NO — a tenant COLUMN is not tenant isolation** |
| ### **`operation_token_amounts`** | `token_fingerprint` | none | ### **NO ← the one "6 of 8" would have left behind** |
| `autonomous_run_counters` | ### **`(tenant, lane, day)`** | yes | ### **YES — the only one** |

Full per-table detail (PK posture · unique-key posture · tenant target · unit · acceptance · backfill · collision risk · deployment dependency) is now **[migration-plan.md PART 7](migration-plan.md)**. ### **U2.1 is scoped by EXACT SET and is NOT complete while any of the seven remains.**

### ⛔ A live cross-tenant defect surfaced while gathering this evidence
`workflow_runs.document_hash` is **`UNIQUE`** and scoped **only by money direction** — ### **it is GLOBAL across tenants.** Two tenants filing the same document (identical bytes ⇒ identical hash) collide **today**: the second is silently treated as the first's duplicate. ### **This is a present cross-tenant leak, not a future one. It is recorded in PART 7 as a HIGH collision risk against U2.1. No schema was changed here.**

## 5. U0.3 corrected dependency posture

### **`DEFERRED_BY_DEPENDENCY — REQUIRED AT PHASE 8`. A planned dependency, NOT a waiver.** The requirement is preserved in full.

**Phase-0 obligation (met):** the requirement exists · its unit (**U8.1**) is registered · assigned to **P8** · its acceptance case and **G4** dependency resolve · ### **no earlier phase may claim the runtime invariant** · ### **a zero-row runtime checker cannot report success.**
**Phase-8 obligation (recorded on U8.1):** enumerate every registered Action Class · exactly **one positive gate decision** each · ### **reject null · reject default · reject unregistered** · ### **FAIL STARTUP on incomplete registration** · ### **prove a non-zero evaluated count.**
### **No placeholder Policy or gate runtime was added — asserted by a test.**

## 6. Normative documents amended (20 edits)

**Specifications:** `acceptance/foundational-machine-acceptance.md` (the Total row + AC-MACH-000 + the 100% claim) · `acceptance/event-and-replay-acceptance.md` (AC-EVT-000/001/003) · `acceptance/release-gates.md` (### **G1 134/134, G2 98/98**) · `acceptance/traceability.md` · `acceptance/registry.md` · `events/registry.md`.
**Implementation:** `pr-sequence.md` (U0.3, U0.4, U2.1, U5.3, U6.3, U8.1, ### **+U0.5–U0.13**) · `implementation-roadmap.md` · `current-to-target-gap-matrix.md` · `current-state-inventory.md` · `implementation-risk-register.md` · `red-to-green-acceptance-plan.md` · `release-gate-plan.md` · `migration-plan.md` (### **+PART 7**) · `phase-0-baseline-manifest.yaml`.

### ⛔ Two occurrences were DELIBERATELY NOT CHANGED
> ### **A global find-and-replace would have silently corrupted both.** They are different metrics that coincidentally equal the wrong totals:
> - ### **`target-spec-revision-report.md`: "141 named validating TESTS"** — a test count.
> - ### **`state-machine-specification-review.md`: "92 STATES"** — a state count.
> ### **Both are now protected by tests that fail if a future pass rewrites them.**

## 7. Historical documents annotated (5)

Preserved as written, each under a dated supersession note marking it ### **HISTORICAL EVIDENCE — NOT normative**: `state-machine-specification-review.md` · `event-specification-review.md` · `acceptance-specification-review.md` · `implementation-planning-review.md` · `phase-0-implementation-review.md`.
> ### **The review trail is not falsified. The wrong sum stays visible at its source, because a corpus that quietly erases its own errors teaches nobody how they happened.**

## 8. Guards updated · 9. Regression tests added

**The oracle changed from a COUNT to EXACT SET EQUALITY** — `enumerated == registered == acceptance-mapped`, backed by `eval/phase0/canonical_expected.yaml` (134 ids + 98 names, by name). ### **Counts are now diagnostics only. A count match with different members FAILS.** That is the precise defect being corrected: a number drifted from the members it claimed to count, and every count-based check agreed with it for as long as it existed.

New: `test_phase0_errata_guards.py` (14). Rewritten: `test_phase0_acceptance_bijection.py`. Extended: `test_phase0_guard_integrity.py`, `test_phase0_null_gate.py`, `test_phase0_identifiers.py`.

**All 14 required regressions + 4 extra — 18/18 detected, stable across 4 consecutive runs, every mutation restored and digest-verified.**

## 10. Exact-set validation results

| probe | ### result |
|---|---|
| transitions enumerated | ### **134** · digest `de13ddea5a448a0b` |
| emitted events enumerated | ### **98** · digest `6deb2ccecdfa8b3f` |
| security events (F14) | 13 ✔ *(was already correct)* |
| tenant tables | 8 total · **1** tenant-first · ### **7 offending, by exact set** |
| duplicates / malformed / zero-row | ### **none · none · none** |
| enumerated == registered | ### **✔ both sets** |

---

## ⛔ WHAT THIS PASS FOUND IN ITS OWN WORK

### 1. THE PHASE-0 COMMIT `d33f251` DID NOT PASS ITS OWN TEST SUITE
> ### **I reported "753 passed, 4 xfailed". That run was launched BEFORE `phase-0-implementation-review.md` existed.** I validated, then wrote two more files, then committed. ### **The validation never covered the tree I shipped.** Checking out `d33f251` and running `test_every_referenced_unit_is_declared_by_the_pr_sequence` **fails**: the review references U0.5–U0.13, which `pr-sequence.md` never declared.
> ### **The Phase-0 verdict "READY" was issued against a red tree. The finding was real, the guard was right, and my process put them out of order.** Fixed by ERRATA 5; the rule going forward: ### **the suite runs LAST, after the final file is written — a green run that predates the commit is not evidence about the commit.**

### 2. THE MUTATION HARNESS MANUFACTURED A FALSE-GREEN — IN THE TOOL BUILT TO CATCH THEM
The errata harness scored **18/18**, then **17/18**, then **17/18**. Not flaky luck — ### **stale bytecode.** Mutation 7 rewrites `(F\d+)` → `(Z\d+)`: ### **exactly the same byte length.** CPython invalidates a `.pyc` by **(mtime, size)**, so restoring the source within one mtime tick left ### **bytecode compiled from the MUTATED parser**. Proven: after a harness run `events()` parsed **0**; after clearing `__pycache__`, **98**.
> ### **Restoring a `.py` is NOT restoring behaviour.** The harness now purges bytecode after every restore, and the lesson is pinned in a test.

### 3. THE SUBTLEST M-9 YET: A NEGATIVE ASSERTION OVER AN EMPTY SET
The stale parser returned zero events — and `assert "TimerFired" not in names` ### **went GREEN while measuring nothing.**
> ### **A negative assertion is VACUOUSLY TRUE over an empty population.** It reads like a real check and is one, right up until the population empties, at which point it reports success forever. ### **Six such tests existed in this suite.** All now prove their population first, and `test_every_negative_assertion_proves_its_population_first` makes the omission un-reintroducible.
> ### **Every one of these three was found by mutation, not by reading. None would have been caught by a passing test suite — all three WERE passing test suites.**

---

## 11–15. Status

| | ### Status |
|---|---|
| **11. Test suite** | ### **777 passed · 2 xfailed · exit 0** *(Phase-0 + errata guards: 100 passed, 2 xfailed)*. The 2 xfails are AC-SAFE-012/013 — red by design. ### **Run LAST, on the final tree — the lesson from finding 1.** |
| ### **12. AC-SAFE-012** | ### **RED_BY_DESIGN — strict xfail, running, named in CI. UNCHANGED.** |
| ### **13. AC-SAFE-013** | ### **RED_BY_DESIGN — strict xfail, running, named in CI. UNCHANGED.** |
| ### **14. R-07** | ### **OPEN — NOT CONTAINED. UNCHANGED.** Six live-write paths remain physically capable of ungated effects until P4. `containment_mechanism: NONE`. |
| `_commit_identity` · effect behaviour · live write paths · adapter imports · schema | ### **ALL UNCHANGED — byte-identical** |

## 15. May Phase 1 begin?

| Condition | Status |
|---|---|
| DEF-4 corrected, transitions not invented, bijection not weakened | ### **✔ 134, exact-set** |
| DEF-5 corrected, events not invented | ### **✔ 98, exact-set** |
| DEF-6 corrected, U2.1 covers all seven | ### **✔ by exact set, PART 7** |
| U0.3 deferred, not waived; no placeholder runtime | ### **✔ P8/U8.1** |
| ERRATA 5 — the Phase-0 tree is green | ### **✔ (it was not)** |
| G1 uses 134 · G2 uses 98 | ### **✔ enforced** |
| noncanonical metrics uncorrupted | ### **✔ protected by tests** |
| historical trail preserved | ### **✔ 5 annotated** |
| AC-SAFE-012/013 red · R-07 open | ### **✔ untouched** |

---

# VERDICT

## ### **READY TO BEGIN IMPLEMENTATION PHASE 1**

**Carried forward:**
- ### **R-07 remains OPEN and NOT CONTAINED.** Nothing here touched it. Until P4, your discipline is the only thing between this repo and an ungated live write.
- ### **A LIVE cross-tenant defect is now recorded:** `workflow_runs.document_hash` is globally unique across tenants. ### **It is a present leak, fixed at P2 (U2.1) — and it means P2 is not merely hygiene.**
- **For G2, before P5:** 24 of 134 transitions cite no event. Settle whether they are non-producing or a real gap in `AC-EVT-003`'s map.
- ### **Phase 1 is unblocked and forward-only.** Once the amount leaves the Commit Key, rollback may disable capability but may never restore the defect.
