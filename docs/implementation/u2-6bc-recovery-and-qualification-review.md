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

### **What stands between it and READY is small and known:**
1. ### **Update the stale fixtures so router and store tenants agree** (7 failures, incl. both merge-gating cases — the guard is right, the tests are old).
2. Classify `schema_migrations` / `migration_quarantine` as **bookkeeping** in the Phase-0 manifest (4).
3. Adjudicate `schema.py`'s deprecated-term counts (2).
4. ### **Supersede `test_u26a_does_not_claim_tenant_isolation`** with the U2.6B assertions the brief specifies (1).
5. Repair one exact-string guard (1).
6. Then: concurrency schedules · the mutation suite · migration qualification · final-tree digests.

> ### **I did not attempt those corrections, because I could not also verify them in this pass — and an unverified green on a tenant boundary is precisely the failure this programme exists to prevent.** The work is preserved at **`42a87e2`** on `recovery/u2-6bc-atomic-cutover`, the branch is clean, and nothing was lost.
