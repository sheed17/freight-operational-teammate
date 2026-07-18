# U2.6BC — Recovery & Qualification Review

> # ### **NOT READY — but the work is SAFE, and it is good.**
> ### **16 failures against the full suite, including two merge-gating cases. The snapshot is substantially correct and NOT qualified. Nothing was discarded; nothing was corrected; the branch is clean.**

| | |
|---|---|
| **1. Starting HEAD** | `edf6ef2` (branch `demos`) |
| **2. Preservation branch** | ### **`recovery/u2-6bc-atomic-cutover`** |
| **3. Preservation snapshot** | ### **`42a87e2`** |
| working-tree digest at discovery | `edb6f94a5a52bd8486608b96b4f18e5189b888578d02c90ec5058cca89e4818f` |

## 4. Files found dirty
**11 modified · 1 untracked · +766 / −288.** `src/freight_recon/schema.py` **(NEW)** · `workflow.py` (**636 lines**) · `operation_router.py` · `migrations/phase2_tenant_first.py` · `eval/phase0/manifest.py` · `eval/phase0/schema_probe.py` · 3 test files · 2 scripts · the Phase-0 manifest. ### **No caches, databases, secrets or logs were committed.**

## 5–8. Exact sets *(recomputed, not inherited)*
| Set | Result |
|---|---|
| affected methods | ### **22 — 21 SCOPED**, 1 unscoped: `_migrate`, which **is** the schema and correctly has no tenant predicate |
| seven tenant-first tables | ### **all 7 now tenant-first in fresh-schema creation** |
| construction sites | ### **154** *(was 146 — the snapshot added 8; all supply a tenant)* |
| new tables | `schema_migrations`, `migration_quarantine` — ### **migration bookkeeping, not tenant-owned business data** |

## 9. Snapshot defects found — ### **NONE in the production logic**
Hostile review found **no** legacy SQL fallback · **no** Python-side tenant filtering · **no** default or hardcoded tenant · **no** second ledger · **no** Phase-3 claim CAS or witness (the code says so explicitly: *"What this deliberately is NOT: the Phase-3 claim CAS. The row is written `GRANTED`."*). The one `except sqlite3.OperationalError` is a **WAL journal-mode** pragma fallback, not a schema fallback.

### ⛔ THE SNAPSHOT FOUND A REAL DEFECT I MISSED
`operation_router.py` now refuses a router/store tenant mismatch, and its reasoning is the finding:
> *"the callback server passed the real tenant to the store and left the router on `"default"`, so every live Commit Key was minted under `"default"` while its row said otherwise. ### **Two brokerages would then compute the SAME key for the same load reference, and the day anyone corrected the router, every outstanding reservation would stop being recognised and the effects behind them would be committed a second time.**"*
### **U2.6A bound the store's tenant and left the router's alone. That gap was mine, and this snapshot closed it.**

**Also better than my own work:** the readiness contract caches against **`PRAGMA schema_version`** (SQLite's DDL counter) so a database altered under a live store is re-checked rather than coasting on a stale verdict; and `enable_and_verify_foreign_keys()` **verifies** the pragma took — directly addressing the silent-pragma bug I found in Phase 2.

## 10–12. Retained / corrected / removed
### **ALL retained. NOTHING corrected. NOTHING removed.** No edit was made after `42a87e2`.

## 13–16. Schema posture
One central `_require_schema_ready()` · fresh databases created **directly** in the canonical shape (never briefly unsafe, never needing a second startup) · canonical defined **once** in `TARGET_SCHEMA` and imported, so fresh and migrated shapes cannot drift · ### **legacy/partial ⇒ `SchemaNotReady`, raised before tenant-owned SQL. No `else`: "an existing non-canonical database is the migration's business."**

## 23. ### **THE 16 FAILURES — and what they actually are**
| Cause | Count | Verdict |
|---|---|---|
| ### **router/store tenant mismatch `ValueError`** | ### **7** | ### **THE NEW GUARD WORKING.** The tests pass mismatched tenants (`router='acme'` vs `store='tenant-fixture-a'`) — an artefact of **my U2.6A codemod**. ### **Production is right; the fixtures are stale.** |
| schema probe sees `schema_migrations` / `migration_quarantine` | 4 | the Phase-0 manifest has not classified the two **bookkeeping** tables |
| deprecated-term ratchet | 2 | `schema.py` legitimately names the tables it guards; needs adjudication |
| ### **`test_u26a_does_not_claim_tenant_isolation`** | 1 | ### **CORRECTLY failing — the brief says to supersede it.** It was a marker of an intermediate state and that state has ended |
| `test_the_amount_survives_as_a_material_fact` | 1 | exact-string guard vs a reworded line |
| `test_22_ac_sec_001_remains_red` | 1 | the probe sees the new bookkeeping tables |

### **Two are merge-gating** (`AC-SAFE-012` / `AC-SAFE-013` end-to-end) — both failing on the **router/store mismatch**, i.e. on stale fixtures, not on the money invariant. ### **Until they are green, that is a claim, not a fact, and this unit is NOT READY.**

## ⛔ BLOCKER 1 — CLOSED *(2026-07-17)*
### **The migration accepted `--assert-tenant default` and assigned every historical row to a sentinel.** Proven against a copy of the live workspace: **18 real `workflow_runs` rows came out owned by `"default"`.** ### **That hole was mine.**
> ### **`default` is not ownership. It is missing ownership, spelled so that it compiles.** And a migration is the worst place for it: production writes one bad tenant onto one row and someone notices; a migration writes it onto every historical row at once and calls the job done.

**Fix:** the assertion now goes through the **same `require_tenant()` boundary production construction uses** — validated *before* inspect, before open, before anything. ### **There is no second, looser path for migrations**, asserted by a test. The CLI refuses cleanly instead of throwing a traceback, because a traceback invites someone to work around it.
**Proven (19 tests):** every canonical sentinel refused case-insensitively *(iterating `FORBIDDEN_TENANTS`, so a new sentinel is covered the day it is added)* · blank/whitespace/non-string refused · ### **an invalid assertion costs ZERO rows, ZERO ledger inserts and ZERO quarantine entries — quarantining under `"default"` would be the same defect wearing a safety label** · the dry run refuses too · a valid tenant succeeds and normalises exactly as production does · ### **no assertion still quarantines all 120 rows rather than guessing.**

## ⛔ BLOCKER 2 — CLOSED *(2026-07-17)*
Historical ownership now requires a durable **owner assertion**: `actor_id` · `tenant` · `scope` · `operational_basis` · `evidence_reference`, recorded in the **existing** audit architecture (no competing system) ### **BEFORE the rows it authorises move.** 18 sentinel actors and 20 generic bases refused; `--assert-tenant` alone no longer authorises anything; a changed tenant is a **conflict**, refused, with both claims preserved. Append-only — a guard forbids rewriting an assertion. ### **23 tests against the real migration and a real copy of the live workspace; 19/19 mutations detected.** Detail: `u2-6bc-blocker-2-owner-assertion-review.md`.
> ### **Two lessons paid for in this blocker:** six mutations first read as MISSED and all six were *my* mutations disabling one of two defending branches — a mutation that does not reintroduce the defect proves nothing. And I ran `git checkout` inside a debugging loop and **destroyed my own uncommitted implementation**, rebuilding it from the surviving tests.

## ⛔ BLOCKER 3 — CLOSED *(2026-07-17)*
One readiness oracle, its contract **derived from `TARGET_SCHEMA`** rather than hand-listed, now proves what the database **enforces**: tenant nullability and defaults · **composite tenant-aware FK declarations including column order** · `PRAGMA foreign_keys` on the live connection · **`foreign_key_check` orphans (observed, never repaired)** · the eight ledger states · **no second effect ledger** · structure over migration markers. ### **27 real malformed-schema fixtures; fresh ≡ migrated proven structurally; 19/19 mutations detected.**
> ### **It found two real migration defects by being RUN, not read:** a migrated database was left **missing three canonical tables** (the migration rebuilt only what the legacy DB happened to have), and creating them naïvely **bound their foreign keys to `_legacy_workflow_runs`** — permanently broken, invisible until `foreign_key_check`. Both were latent in the inherited snapshot and had passed every previous run.
> ### **The safe restoration harness held:** in-memory save, digest-verified, **no git command anywhere** — written before any mutation ran. Nothing was lost this time.
Detail: `u2-6bc-blocker-3-schema-readiness-review.md`.

## ⛔ BLOCKER 4 — CLOSED *(2026-07-17)*
The **application** boundary now matches the database's: 22/22 methods carry the bound tenant into the SQL and sit behind the readiness gate; ### **no method accepts a tenant argument**, so ownership cannot be supplied by a caller. All three merge-gating methods qualified — identical document bytes, identical load references and identical Commit Keys are **independent across tenants** while duplicates are still refused **within** one. ### **AC-SAFE-012 and AC-SAFE-013 are GREEN again.** 24 hostile tests · **17/17 mutations detected**.
> ### **Mutation found two real gaps in my own suite:** the unfiltered `audit_events()` branch — *"the branch a support tool reaches for"* — was untested and returned every tenant's history when made global; and the exact-set test **compared the registry to itself**, so dropping a table moved both sides together and stayed green. ### **A registry that validates itself validates nothing.**
> The 5 stale router/store fixtures were corrected by aligning them to one canonical tenant — ### **the guard was right and the fixtures predated it. Nothing was weakened to make production pass.**
Detail: `u2-6bc-blocker-4-tenant-scope-review.md`.

## ⛔ BLOCKER 5 — CLOSED *(2026-07-17)*
20 database shapes, 27 cases: every input reaches ### **exactly one of 10 classified outcomes**, each naming a safe next action. ### **The completion marker is written LAST and only if readiness passes.** Dry run is **byte-identical** on every shape; a timeout is ### **`UNKNOWN_OUTCOME`, never `FAILED`**; duplicate legacy reservations are preserved with their material-fact disagreement intact; a future schema version is refused rather than downgraded; an already-canonical database is a true no-op. **16/16 mutations detected.**
> ### **The matrix found three real defects by being run:** quarantined rows were reported **`CANONICAL_READY`** (a tidy shape holding 120 unowned rows is not ready); ### **re-migrating a canonical database DESTROYED its tenant doc-hash index** — leaving a database that documented the constraint without enforcing it; and index creation was not idempotent. All three were latent at `1d31f07`.
> ### **And my own next-action guard was too weak** — it checked word count, so `"okand settle each row…"` passed. Tightening it to *a verb must OPEN the instruction* then failed three real outcome texts that described rather than instructed. ### **A status an operator cannot act on is a status that gets ignored.**
Detail: `u2-6bc-blocker-5-migration-matrix-review.md`.

## 24–25. Concurrency · mutation: ### **NOT RUN.** No qualification was performed.

## 26–32. Open findings — ### **ALL PRESERVED**
`AC-SAFE-012` / `AC-SAFE-013` — ### **currently RED under stale fixtures; must be proven green before any READY** · `AC-SEC-001` — ### **RED** · ### **R-07 — OPEN, NOT CONTAINED** · six live-write paths · 31 adapter import edges · 24 event-less transitions · the knowledge-base `"default"` tenants.

## 33. Legacy dispositions
`workflow.py` **ADAPT** · `schema.py` **KEEP** (the one readiness contract) · `operation_router.py` **ADAPT** · `migrations/` **KEEP** · `tenant.py` / `cli_tenant.py` **KEEP** · Phase-0 guards **ADAPT**.

## 34–37. Validation
### **Full suite on the snapshot: 16 failed · 868 passed · 1 skipped.** No final-tree digest recorded — ### **there is no qualified candidate to digest.** Final commit: `42a87e2` + this review. ### **Branch clean.**

## 38–39. Phase 2 complete? ### **No.** Durable identity work may begin? ### **No.**

---

# VERDICT

## ### **NOT READY**

**The snapshot is the best implementation of U2.6BC that exists, and it is close.** 21/22 methods scoped, one central readiness contract with no fallback, canonical fresh-schema creation, tenant-consistent FKs verified rather than assumed — and ### **it fixes a real cross-tenant money defect that my own U2.6A left open.**

### **Blockers 2–6 remain OPEN:** auditable owner assertions (actor/basis/scope, fail-closed) · the **complete** schema-readiness oracle (the 8 malformed-but-plausible schemas) · exact-set method/table/site qualification · the 16-shape migration matrix · concurrency schedules · the mutation suite.

### **What stands between it and READY is small and known:**
1. ### **Update the stale fixtures so router and store tenants agree** (7 failures, incl. both merge-gating cases — the guard is right, the tests are old).
2. Classify `schema_migrations` / `migration_quarantine` as **bookkeeping** in the Phase-0 manifest (4).
3. Adjudicate `schema.py`'s deprecated-term counts (2).
4. ### **Supersede `test_u26a_does_not_claim_tenant_isolation`** with the U2.6B assertions the brief specifies (1).
5. Repair one exact-string guard (1).
6. Then: concurrency schedules · the mutation suite · migration qualification · final-tree digests.

> ### **I did not attempt those corrections, because I could not also verify them in this pass — and an unverified green on a tenant boundary is precisely the failure this programme exists to prevent.** The work is preserved at **`42a87e2`** on `recovery/u2-6bc-atomic-cutover`, the branch is clean, and nothing was lost.


---

# ⬛ SUPERSEDED BY BLOCKER 6 — PHASE 2 IS COMPLETE

The verdict above was accurate when written and is retained as the record of that moment. It has
since been discharged in full by the six U2.6BC blockers, closed at
[`u2-6bc-blocker-6-final-phase-2-review.md`](u2-6bc-blocker-6-final-phase-2-review.md).

**Final Phase-2 state:** the suite is GREEN — **1073 passed · 0 failed · 1 skipped** (the skip names
its own reason). All 22 store methods are tenant-scoped and readiness-gated; the migration validates
its tenant canonically, records auditable human ownership before assigning a single row, and writes
its completion marker LAST and only if readiness passes. **AC-SEC-001 is satisfied at the Phase-2
surfaces** (records, grants, api), with seven surfaces deferred by name and phase (P3/P4/P5/P9).
The integrated acceptance suite runs 20 concurrency schedules against real SQLite, and **49/49
load-bearing mutations are detected**.

**Still open, and deliberately so:** **R-07 — OPEN, NOT CONTAINED** · six production-reachable
live-write paths · 31 direct adapter import edges (P4) · 24 event-less transitions (P5) ·
checkpoint/witness/claim CAS (P3) · the hardcoded knowledge-base `tenant="default"` findings.

> **This closed a phase, not the product.** Phase 2 made the tenant real in the database; it did not
> make the effect boundary safe — that is Phase 3, and the two-key rule is still unbuilt.
