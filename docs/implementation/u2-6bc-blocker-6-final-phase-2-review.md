> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Verdicts, statuses, counts and "READY"
> declarations below describe the state THEN — several are known-superseded (including any
> "24 of 134" transition figure, retired by U-HANDOFF-1B, and any suite count). Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U2.6BC Blocker 6 — Final Integrated Phase-2 Qualification

> ### **CLOSED.** Phase 2 is complete. The suite is **GREEN for the first time in this program**: **1073 passed · 0 failed · 1 skipped**, and the skip names its own reason.
> ### **AC-SEC-001 is SATISFIED at the Phase-2 surfaces** — reconstructed from the frozen acceptance specification, not from the implementation, with its seven out-of-phase surfaces deferred by name and by phase rather than quietly dropped.
> ### **R-07 remains OPEN — NOT CONTAINED.** Phases 3–13 remain. This closes a phase, not the product.

**1. Starting commit:** `2a1cbcd` (branch `recovery/u2-6bc-atomic-cutover`, clean tree, Blockers 1–5 green at 130 tests)

---

## 2–7. The six remaining failures — classified, then corrected

| # | Test | Class | What was actually wrong |
|---|---|---|---|
| 2 | `test_deprecated_usage_never_grows` | **STALE_ORACLE** | The ratchet counted the Phase-2 modules that legitimately *name* the tables they guard |
| 3 | `test_deprecated_usage_never_spreads_to_a_new_file` | **STALE_ORACLE** | Same cause; the new files are the guards themselves |
| 4 | `test_tenant_offending_tables_exact_set_not_count` | **STALE_ORACLE** | The Phase-0 probe predated `effect_grants` and the bookkeeping tables |
| 5 | `test_the_already_canonical_table_is_not_in_u21_scope` | **STALE_ORACLE** | Same probe, same cause |
| 6 | `test_22_ac_sec_001_remains_red` | **STALE_ORACLE** | Asserted the pre-Phase-2 table list; AC-SEC-001 is no longer red |
| 7 | ### `test_u26a_does_not_claim_tenant_isolation` | ### **OBSOLETE_LEGACY_BEHAVIOR** | ### **Correctly failing.** It marked the intermediate state *"bound but not scoped"*, which has now ended. It was written to fail exactly here |

### **Nothing was deleted, and no production code was altered to preserve an obsolete result.**
Items 6 and 7 were **REPLACED in place** — same file, same history, new assertion:
`test_22_ac_sec_001_remains_red` → `test_22_ac_sec_001_is_now_satisfied_at_the_schema_level`, and
`test_u26a_does_not_claim_tenant_isolation` → `test_the_tenant_boundary_is_now_complete_not_merely_bound`.
### **Deleting them would have erased the record that the intermediate state ever existed** — the thing a reader in a year most needs in order to trust the sequence.

## 8. Zero business tables remain non-tenant-first — established mechanically
All **7** migrated. The **3** still flagged by the Phase-0 probes are the canonically-exempt bookkeeping tables: `schema_migrations`, `migration_quarantine`, `owner_assertions`.
`eval/phase0/schema_probe.py` now excludes them by default, with the reason recorded at the call site: ### **the audit of a DISPUTED ownership claim must not itself be owned by one of the disputing tenants.**
`phase-0-baseline-manifest.yaml`: `tables_not_tenant_first: []`, all 8 listed tenant-first, **DEF-6 CLOSED**, deprecated counts re-adjudicated (`workflow_runs: 29`, `lane: 234`, `CommandIntent: 57`, `commit_identity: 0`).

---

## 9–14. AC-SEC-001, reconstructed from the specification

`eval/tests/test_ac_sec_001_registry.py` — **27 tests, all executing.** Built from the frozen spec text: *tenant is STRUCTURALLY required on **records, events, grants, witnesses, mappings, credentials, cache keys, leases, adapter calls***.

| Surface | Status |
|---|---|
| **records · grants · api** | ### **PHASE-2 — proven** |
| events | DEFERRED — **P5** |
| witnesses · leases | DEFERRED — **P3** |
| mappings | DEFERRED — **P9** |
| credentials · cache keys · adapter calls | DEFERRED — **P4** |

### **Every deferral names its phase, and a test asserts that it does.** A deferral without a phase is an abandonment with better manners.
`AC_SEC_001_MEMBERS` is a **24-member exact tuple**; ### **a registry member with no executing test fails the suite**, so the registry cannot outlive the tests it claims.

### ⛔ TWO OF MY OWN TESTS IN THIS FILE WERE WRONG
1. ### **My skip-guard fired on itself.** It scanned for the substring `mark.skip` — which appears in its own assertion text. Rewritten to walk the **AST** and inspect real decorators.
2. ### **I mistook correct isolation for a leak.** I asserted tenant B's audit read returned `[]`; ids are **per-tenant**, so both runs are `id=1` and B was legitimately reading **its own** events. I verified isolation held, then rewrote the test to assert each tenant sees only its own history. ### **The original assertion would have failed a correct implementation.**

---

## 15–24. The integrated acceptance entry point

`eval/tests/test_phase2_integrated_acceptance.py` — **34 tests. Real SQLite files, real threads, nothing mocked.**
Fixtures are built by ### **production's own `create_canonical_schema`**, never a copied DDL string: a fixture holding its own copy of the schema drifts from the thing it represents, and then the suite qualifies a shape no migration produces.

### **Part A — the 12 named database states**, one canonical answer each
fresh canonical ✔ ready · empty file · untouched legacy · migrated-empty ✔ · migrated + assertion ✔ · ### **populated without assertion ⇒ QUARANTINED_PENDING_REVIEW, 0 assigned** · lying marker over a dropped table ⇒ **structure wins** · orphan rows · ### **second effect ledger** · future schema version ⇒ refused · already-canonical rerun ⇒ **true no-op, index intact** · two tenants in one database ⇒ both ready.

### **Part B — the 20 required concurrency schedules**, each asserting ONE canonical result
| | Schedules | Canonical result |
|---|---|---|
| **document identity** | 1–4 | same bytes in one tenant ⇒ ### **exactly one run** · same bytes in two tenants ⇒ ### **two independent runs** · two directions ⇒ two documents · a reader never sees another tenant mid-write |
| **Commit Key / ledger** | 5–9 | ### **five racing identical keys ⇒ exactly ONE reservation** · same key in two tenants ⇒ ### **both reserve** · ### **three different amounts ⇒ still one reservation** · three distinct occurrences ⇒ three · ledgers never cross |
| **workflow updates** | 10–13 | ### **one winner per transition, and the losers write NO history** · cross-tenant ⇒ ### **"not found", not "forbidden"** · per-tenant dense ids · a refused jump leaves nothing behind |
| **migration** | 14–20 | two concurrent migrations converge · no half-migrated schema is observable · ### **conflicting assertions ⇒ the first owner preserved** · dry runs byte-identical · a new app refuses the legacy shape · ### **zero unowned rows across 60+** · ### **the marker only ever appears after readiness** |

**Part C** — the end-to-end integrated invariant: one database, two brokerages, the same bytes and the same Commit Key, fully independent; a duplicate **within** one tenant still refused.

### ⛔ MUTATION PROVED FOUR OF MY OWN ACCEPTANCE TESTS WERE DECORATION
I mutated the production code specifically to check whether these schedules are load-bearing. **First pass: 8/10.** Both misses were defects in *my tests*, not in the code:

1. ### **Schedule 10 passed with the compare-and-set REMOVED.** One round barely opens the read-then-write window — the threads queue on SQLite's write lock and serialize by luck, so the state-validity check alone looked sufficient. Now **12 rounds**, with every store opened and its run **read before the barrier**, so all racers hold the same stale state when released. ### **That is the interleaving the CAS exists for, and without the repetition the schedule proved nothing.**
2. ### **Schedule 20's watcher could never observe the window it was watching for.** With the completion marker deliberately stamped *before* the constraints existed, the schedule stayed green — I confirmed by instrumenting it that the migration holds the write lock for its entire millisecond duration, so the reader sees nothing until it is already over. ### **Racing was simply the wrong instrument.** The ordering is now also asserted **deterministically**, on a database engineered so readiness can never pass: if the marker is written before readiness is checked it is present, and if written last it is absent.
3. **State 06 asserted only the counts, not the outcome** — so removing the rule that quarantine outranks a clean schema went undetected. ### **A database can hold a perfectly canonical schema and still be unsafe to serve because 12 rows have no owner.** Now asserts `QUARANTINED_PENDING_REVIEW` and a non-empty next action.
4. **Two probes were vacuous**: `get_run_by_hash` takes the *raw* hash while the stored one is direction-scoped, so my isolation reads returned `None` for **everybody**. ### **Positive controls added first** — the writer must be able to see its own rows, or the Nones below prove nothing.

**After the fixes: ### 10/10 DETECTED.**

---

## 25–33. The integrated Phase-2 mutation registry — ### **49/49 DETECTED**

Load-bearing mutations from Blockers 1–5 combined and re-run against the final tree, plus the new Blocker-6 surfaces. Every entry reintroduces a **real prohibited behaviour** and was verified by watching the detector actually fail.

| Group | ID | Mutation | Detector |
|---|---|---|---|
| tenant validation | TV-1–2 | accept `default`; bypass canonical validation in the migration | AC-SEC-001 · B1 |
| ownership | OA-1–6 | drop actor / scope / basis / evidence; assign before persisting; permit conflicting reassignment | B2 · B5 |
| readiness | SR-1–9 | nullable tenant · sentinel DEFAULT · FK checks skipped · ### **reversed FK columns accepted** · pragma ignored · orphans ignored · ### **marker trusted over structure** · second ledger allowed · a canonical state dropped | B3 |
| runtime scope | RS-1–5 | tenant removed from a read · global doc-hash · global Commit Key · ### **readiness gate removed from all 22 methods** · router/store divergence permitted | AC-SEC-001 · B4 |
| exact sets | ES-1–3 | a canonical table omitted · ### **substituted with the count preserved** · the site parser returns zero | AC-SEC-001 |
| migration | MG-1–6 | dry run writes · marker before readiness · ### **timeout ⇒ FAILED** · quarantine reports ready · rerun drops the tenant index · future version accepted | B5 |
| test integrity | TI-1–3 | a required acceptance test skipped · the registry emptied · ### **R-07 marked CONTAINED** | self-guards |
| acceptance | AS-1–10 | dedup made global · ### **serialized write removed** · direction scoping removed · ledger uniqueness made global · ### **CAS removed** · cross-tenant transition permitted · ### **marker stamped early** · quarantine ranking removed · orphans ignored · ### **id allocation made global** | integrated suite |
| structural exemption | PR-1–5 | a real untenanted site added (×2 guards) · ### **exemption widened to every line** · a guard file left unclassified · registry names a phantom file | U2.6A · B4 · registry |

### **The safe in-memory harness held throughout** — save in memory, restore in a `finally`, digest-verified, bytecode purged, and it **refused three no-op mutations outright**. ### **No git command was used at any point**, which is the standing correction from Blocker 2, where I ran `git checkout` inside a debugging loop and destroyed my own uncommitted implementation.

---

## 34–38. Guard consolidation — **25 files, 367 guard tests, every one classified**

`eval/tests/test_phase2_guard_registry.py` — **7 tests.** ### **The classification is EXECUTABLE, not documentary:** a guard file added and left unclassified fails the suite, and a registry entry naming a file that no longer exists fails too.

| Classification | Count | Files |
|---|---|---|
| **RETAIN** | **20** | all Phase-1 (forward-only), all five U2.6BC blocker suites, the merge-gating AC-SAFE guards, the guard-integrity and null-gate guards, and the three Blocker-6 additions |
| **UPDATE** | **3** | `phase0_baseline_manifest` · `phase0_deprecated_semantics` · `phase0_errata_guards` |
| **REPLACE** | **2** | `phase0_tenant_posture` · `u26a_tenant_construction` |
| ### **REMOVE_AS_SUPERSEDED** | ### **0** | ### **nothing was deleted** |

### **REMOVE_AS_SUPERSEDED was used zero times, deliberately.** A guard that is merely *also* covered elsewhere is still evidence; deleting it trades a proven assertion for a claim that some other test would have caught it. The registry enforces this: anything ever classified that way must **name a surviving guard that exists**. Two further rules are asserted mechanically — ### **Phase-1 guards may never be downgraded** (forward-only: that is the defect that raised two invoices) and ### **the R-07 record may never be reclassified away.**

## 39. ⛔ A THIRD FILENAME-ENUMERATION BUG — FOUND AND REMOVED AT THE ROOT
Two guards exempted refusal probes **by filename**. That is the fourth occurrence of this pattern in the program, and this time it had already caused harm: skipping `test_u26a_tenant_construction.py` wholesale also hid that file's **legitimate** construction sites — ### **a blind spot exactly the size of one test module.**
Now decided **structurally**: a `WorkflowStore(...)` built inside a `with pytest.raises(...)` block is a refusal probe by construction. And mutation immediately found the next weakness: ### **widening that exemption to every `with` block slipped past the population floor of 100**, because exempted sites were being dropped from the denominator as well as the check. ### **Every site now enters the population whether it is a probe or not**, and a further guard caps probes at 10% of sites and forbids any in production. **All five exemption mutations then failed as they should.**

---

## 40–44. Final-tree validation *(22 steps, run LAST on the frozen candidate tree)*

| | |
|---|---|
| **Full suite** | ### **1073 passed · 0 failed · 1 skipped** *(was 6 failed · 998 passed)* |
| ### **Net** | ### **−6 failures, +75 passing. Zero new failures.** |
| **The one skip** | conditional and self-describing: *"no red-by-design cases remain: AC-SAFE-012/013 went green at Phase 1"* |
| **AC-SAFE-012 / AC-SAFE-013** | ### **GREEN** |
| ### **AC-SEC-001** | ### **SATISFIED at the Phase-2 surfaces**, seven deferred by phase |
| ### **R-07** | ### **OPEN — NOT CONTAINED** |
| validation start tree | `83be37c55f89390148d512a433adf0227eaccdc5` |
| validation end tree | `83be37c55f89390148d512a433adf0227eaccdc5` |
| ### **digests match** | ### **✔ — byte-identical before and after the run; nothing was touched while it executed** |
| digest after inserting these two lines | `43a8a7ae788e33e5fe27388adf56fc7b1c2e712c` |
| ### **confirmation pass on THAT tree** | ### **1073 passed · 0 failed · 1 skipped, digest unchanged across the run** |

> ### **The only edit made after validation was writing the digest above into this table** — which necessarily changes the tree, so a single self-referential number is impossible and claiming one would be a lie. The inserted-digest tree was therefore validated again in full, and the run below is the one this verdict rests on.

**Carried forward, unchanged and still open:** ### **R-07 OPEN — NOT CONTAINED** · six production-reachable live-write paths · 31 direct adapter import edges · 24 event-less transitions · the hardcoded knowledge-base `tenant="default"` findings · Phase-3 checkpoint/witness · Phase-4 adapter containment.

## 45. · **Blocker 6 closed?** ### **Yes.** · **Phase 2 complete?** ### **Yes.**

---

# VERDICT

## ### **READY TO BEGIN DURABLE CLI-CONTROL DOCUMENTATION**

### **What Phase 2 actually bought:** a tenant is now required to construct the store, validated against sentinels at every boundary, first in every key, enforced by the database rather than asserted by a comment, assigned to historical rows only by a named human on a recorded basis, and verified by an oracle that reads what the database **enforces** instead of what a marker **claims**.

### **What it did not buy:** the two-key rule (P3), event tenancy (P5), adapter containment (P4). ### **Phase 2 is one layer of thirteen, and R-07 is still open.**
