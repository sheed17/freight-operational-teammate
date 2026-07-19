> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Verdicts, statuses, counts and "READY"
> declarations below describe the state THEN — several are known-superseded (including any
> "24 of 134" transition figure, retired by U-HANDOFF-1B, and any suite count). Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U2.6BC Blocker 4 — Exact Tenant-Scope Qualification

> ### **CLOSED.** Blocker 3 proved the **database enforces** tenant-first structure. This proves the **application uses it**: every affected method carries the bound tenant into the SQL, and a cross-tenant access returns nothing, changes nothing and discloses nothing.
> ### **AC-SAFE-012 and AC-SAFE-013 are GREEN again** — the merge-gating cases now pass against the tenant-scoped store.
> ### **Blockers 5–6 remain OPEN. Phase 2 is NOT complete.**

**1. Starting commit:** `2f61d9a` (branch `recovery/u2-6bc-atomic-cutover`, clean)

## 2–4. The exact sets *(recomputed from source; counts informational, membership is the oracle)*
| Set | Result |
|---|---|
| **tables** | ### **7** — exact SET asserted against a literal |
| **methods** | ### **22 — 13 write · 9 read.** Zero unscoped, zero without a readiness gate |
| **construction sites** | ### **154** *(was 146: **+8 new test fixtures** from Blockers 1–3)*. ### **Production 37/37 explicit** |

### **The one site without a tenant is the U2.6A probe that deliberately constructs without one to prove refusal.** Every other site names its tenant.

## 5–6. Read + write qualification
Each affected method verified for: the **bound** tenant (`self._tenant`), a tenant **predicate in the SQL**, and the **readiness gate** before any tenant-owned statement. Structurally proven: ### **no method accepts a `tenant` argument** — the store's binding is the only source, so there is nothing to override — and ### **no method filters tenant in Python** after a global read, which would already have read another tenant's rows.

## 7. Merge-gating methods — ### **all three qualified**
- ### **`receive_document`** — two brokerages receiving the **same document bytes** each get their own row; ### **same-tenant duplicate absorption still holds** (tenant scoping must not become tenant blindness).
- ### **`get_run_by_hash`** — another tenant's row is never observable, and ### **absent vs cross-tenant are indistinguishable: both are `None`.**
- ### **`claim_operation_commit`** — identical Commit Keys are **independent across tenants**, duplicates **refused within** one tenant, and ### **the method has no `tenant` parameter at all**, so a caller cannot supply ownership. *(Stronger than ignoring a caller's value: a method that accepted one and discarded it would still be one edit from honouring it.)*

## 8. Router/store tenant consistency
Divergence raises **before** reservation, actuation or any success report. ### **No production router carries a hardcoded tenant** — asserted by AST over `src/` and `scripts/`, which is the guard that closes the live `tenant="default"` defect.

## 9–12. Relationship + collision matrices
Cross-tenant child → parent **refused by the composite FK**. Reused numeric ids across tenants connect nothing. ### **A cross-tenant `transition` RAISES "workflow run not found"** — stronger than updating zero rows, because the row genuinely is not there for that tenant. Audit history, single-use action claims and ### **approved token amounts** are each tenant-scoped *(an approved amount readable across tenants would be a money disclosure)*.

## 13–14. Construction sites + tenant sources
Every production site draws from a canonical source — client-config `client_id`, an operator assertion, or an explicit CLI tenant. ### **No document contents, load id, filename, workspace path, first row, ambient or thread-local tenant.**

## 15. Existing-test classifications
| Test | Class | Correction |
|---|---|---|
| 5 × router/store mismatch | ### **STALE_FIXTURE** | store tenant aligned to its router's — ### **the guard was right; the fixtures predated it** |
| `test_ac_safe_012/013` ledger count | ### **STALE_ORACLE** | `operation_commit_claims` → `effect_grants` *(U2.5 was a rename, not a second table)*. ### **Oracle unchanged** |
| `test_delivery_action_claim_is_atomic` | ### **STALE_FIXTURE** | invented `run_id=1`; the Blocker-3 FK now refuses a claim against a run that does not exist. ### **Real parent seeded — the constraint working, not a regression** |
| `test_the_amount_survives_as_a_material_fact` | ### **STALE_ORACLE** | reads `TARGET_SCHEMA` — the DDL moved to one source of truth. ### **Invariant unchanged** |
### **Nothing was weakened to make production pass, and no production behaviour was relaxed to preserve an old test.**

## 16–17. Guards + mutation — ### **17/17 DETECTED**
tenant removed from a read predicate · from the doc-hash lookup · from the dedup preflight · Commit Key made global · audit history made global · **audit LIST made global** · router/store divergence permitted · a test skipped · **readiness gate removed from all 22 methods** · Blocker-1 bypassed · Blocker-2 actor removed · Blocker-3 FK check removed · **method parser returns zero** · **site parser returns zero** · a canonical table dropped · ### **a canonical table SUBSTITUTED with the count preserved** · a hardcoded production router tenant.

### ⛔ MUTATION FOUND TWO REAL GAPS IN THIS SUITE
1. ### **The unfiltered `audit_events()` branch was untested.** Making it global left every test green while it returned **every tenant's history** — and the code's own comment calls it *"the branch a support tool reaches for."* ### **The scoped branch was covered and the unscoped-by-default one was not, which is exactly the wrong way round.**
2. ### **The exact-set test compared the registry to itself.** Dropping a table moved both sides together and stayed green. ### **A registry that validates itself validates nothing** — now asserted against a literal, plus every canonical table must be touched by at least one method.

**Three further "misses" were unfaithful mutations**, verified not assumed: one removed a readiness gate from `__init__` while **21 others** remained; two edited `TENANT_FIRST_TABLES` (the migration's input list) rather than `CANONICAL_TENANT_TABLES` — ### **two tuples that exist for documented, different reasons.** Retargeted, all then failed.
### **The safe harness held again** — in-memory restore, digest-verified, **no git command**. It also refused a no-op mutation outright, which is how I found my SQL string was wrong rather than trusting a green.

## 18–24. Status
| | |
|---|---|
| Blocker 1 / 2 / 3 regressions | ### **GREEN (69)** |
| ### **AC-SAFE-012 / AC-SAFE-013** | ### **GREEN** |
| **AC-SEC-001** | ### **RED** — Blockers 5–6 remain |
| ### **R-07** | ### **OPEN — NOT CONTAINED** |

## 25–28. Final-tree validation
| | |
|---|---|
| **Full suite** | ### **6 failed · 971 passed · 1 skipped** *(was 16 failed / 937 passed)* |
| ### **Net** | ### **−10 failures, +34 passing. Zero new.** |
| validation start tree | `4e17f60cc1dae05ad73aff9c822e4b1c4c00c3f8` |
| validation end tree | `4e17f60cc1dae05ad73aff9c822e4b1c4c00c3f8` |
| ### **digests match** | ### **✔ — run LAST, nothing changed after** |

### The 6 remaining, classified — ### **all Blocker 5/6 scope**
| Test | Class | Owner |
|---|---|---|
| `test_deprecated_usage_never_grows`, `..._never_spreads_to_a_new_file` | **STALE_ORACLE** — the new Phase-2 modules legitimately name the tables they guard | Blocker 6 |
| `test_tenant_offending_tables_exact_set_not_count`, `test_the_already_canonical_table_is_not_in_u21_scope` | **STALE_ORACLE** — the Phase-0 probe predates `effect_grants` and the bookkeeping tables | Blocker 6 |
| ### **`test_u26a_does_not_claim_tenant_isolation`** | ### **OBSOLETE_LEGACY_BEHAVIOR — correctly failing.** It marked an intermediate state ("bound but not scoped") that **has now ended**. It was written to fail exactly here | Blocker 6 |
| `test_22_ac_sec_001_remains_red` | **STALE_ORACLE** — the probe reads the pre-Phase-2 table list | Blocker 6 |

## 29–30. · **Blocker 4 closed?** ### **Yes.** · **Blocker 5 may begin?** ### **Yes.**

---

# VERDICT

## ### **READY TO BEGIN BLOCKER 5 — COMPLETE MIGRATION MATRIX**

**Carried forward:** Blockers 5–6 open · ### **AC-SEC-001 RED** · ### **R-07 OPEN — NOT CONTAINED** · six live-write paths · 31 adapter import edges · 24 event-less transitions · the knowledge-base `"default"` tenants. ### **This closes one blocker, not the phase.**
