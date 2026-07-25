> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Verdicts, statuses, counts and "READY"
> declarations below describe the state THEN — several are known-superseded (including any
> "24 of 134" transition figure, retired by U-HANDOFF-1B, and any suite count). Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U2.6BC Blocker 3 — Complete Canonical Schema Readiness

> ### **CLOSED.** One oracle answers one question — *can this database safely serve the tenant-scoped Phase-2 application **right now**?* — by reading what the database **enforces**, never what a marker claims it once did.
> ### **Blockers 4–6 remain OPEN. Phase 2 is NOT complete.**

**1. Starting commit:** `1393275` (branch `recovery/u2-6bc-atomic-cutover`, clean)

## 2–3. Files changed · canonical source
`src/freight_recon/schema.py` · `src/freight_recon/migrations/phase2_tenant_first.py` · `eval/tests/test_u26bc_schema_readiness.py` **(new, 27 cases)**.
### **The contract is DERIVED from `TARGET_SCHEMA`, never hand-listed.** `_canonical_fks()` and `_canonical_columns()` parse the canonical DDL, so a second list cannot drift from the schema it validates — ### **a readiness oracle that disagrees with the thing it checks is worse than none.**

## 4–14. What readiness now proves
| Invariant | Before | ### Now |
|---|---|---|
| exact seven-table SET | ✔ | ✔ *(set equality, not count)* |
| tenant-first primary keys | ✔ | ✔ |
| **tenant NULLABILITY** | ### **⛔ absent** | ### **every canonical NOT NULL column checked** |
| **tenant DEFAULT** | ### **⛔ absent** | ### **a defaulted tenant is refused — it invents an owner nobody chose** |
| **FK DECLARATIONS** | ### **⛔ absent** | ### **composite tenant-aware FKs, column order included** |
| **`PRAGMA foreign_keys`** | ### **⛔ absent** | ### **enforcement verified on the live connection** |
| **`foreign_key_check`** | ### **⛔ absent** | ### **existing orphans reported — observation, never repair** |
| ledger states | ✔ structural | ✔ + `REVOKED` ≠ `EXPIRED_UNCLAIMED` |
| **second ledger** | ### **⛔ absent** | ### **any table with `commit_key` + `state` is a second effect authority** |
| migration marker vs reality | partial | ### **structure wins; a marker is a claim about the past** |

### **Declaration ≠ enforcement ≠ integrity.** A database can declare every foreign key, have the pragma off, and hold orphans — three separate failures, reported separately. ### **Column ORDER is checked because `(tenant, run_id) → (tenant, id)` and `(run_id, tenant) → (tenant, id)` are different constraints and only one of them forbids a cross-tenant child. A count of foreign keys calls both fine.**

## 15–16. Malformed-schema matrix — ### **27/27**
Real SQLite fixtures, each mutating the canonical schema in exactly one plausible way: missing table · **same count, wrong member** · `audit_events` without its tenant FK · `security_events.tenant` nullable · another tenant column nullable · tenant `DEFAULT 'default'` · global doc-hash uniqueness retained · tenant-scoped doc-hash missing · global Commit Key uniqueness · tenant Commit Key missing · **reversed composite FK** · FK enforcement disabled · **existing orphan** · ledger missing · **second ledger** · state missing · extra state · **`REVOKED` collapsed** · state constraint removed · empty database.
### **Fresh ≡ migrated proven structurally** — columns, nullability, defaults, keys, uniqueness, FK column order and CHECK constraints all compared. ### **If those drift, "ready" means two different things.**

## ⛔ THE ORACLE FOUND TWO REAL MIGRATION DEFECTS — BY BEING RUN, NOT BY BEING READ
1. ### **A migrated database was missing three canonical tables.** The migration rebuilt only the tables the legacy database happened to have, so a workspace that never recorded a delivery claim came out *without* `delivery_action_claims`, `operation_action_claims` or `operation_token_amounts`. ### **The migration would report success and the application would meet "no such table" at runtime instead of a clean readiness refusal.**
2. ### **Creating those tables naïvely bound their foreign keys to `_legacy_workflow_runs`.** SQLite resolves an FK to whatever holds the name at `CREATE` time, and the rebuild has `workflow_runs` renamed. ### **The result is a permanently broken reference, invisible until `foreign_key_check` reports a mismatch.** Fixed by creating them *after* the rebuild.
> ### **Both were latent in the snapshot I inherited and had passed every previous run. Neither would have been found by reading the code.**

## 17–18. Guards · mutation — ### **19/19 DETECTED**
Guards: one oracle only · contract derived from `TARGET_SCHEMA` · the matrix proves a **non-zero** fixture population · exact table set and eight states asserted as **sets**.
Mutations: nullability ignored · tenant default allowed · FK declarations skipped · **reversed FK accepted** · pragma ignored · `foreign_key_check` ignored · ledger check omitted · second ledger allowed · state dropped/added · **`REVOKED` collapsed at source** · canonical table omitted · **marker trusted over structure** · doc-hash index ignored · required indexes ignored · **fresh/migrated drift** · a test skipped · Blocker-1 bypassed · Blocker-2 actor removed.

### ⛔ TWO MUTATIONS FIRST READ "MISSED" — AND BOTH WERE MY MUTATIONS AGAIN
`effect_grants` is *in* `CANONICAL_TENANT_TABLES`, so the generic table loop already catches its absence; disabling only my dedicated check changed nothing observable. ### **I verified this by running the mutant and watching the second guard still fire — then disabled both paths, and all 19 failed as they should.** Same lesson as Blocker 2: ### **a mutation that does not reintroduce the defect proves nothing about the guard.**

### ✔ AND THE RESTORATION MECHANISM HELD
The harness saves the original **in memory** and restores in a `finally`, digest-verified, with **no git command anywhere** — written *before* any mutation ran, because in Blocker 2 I used `git checkout` inside a debugging loop and destroyed my own uncommitted work. ### **Nothing was lost this time.**

## 19–24. Status
| | |
|---|---|
| Blocker 1 regression | ### **GREEN (19)** |
| Blocker 2 regression | ### **GREEN (23)** |
| **AC-SAFE-012 / 013** | unchanged — still on the stale router/store fixtures (**Blocker 6**) |
| **AC-SEC-001** | ### **RED** |
| ### **R-07** | ### **OPEN — NOT CONTAINED** |

## 25–28. Final-tree validation
| | |
|---|---|
| **Full suite** | **16 failed · 937 passed · 1 skipped** |
| ### **New failures from Blocker 3** | ### **ZERO** — baseline was **20**, this run is **16**: net **−4** |
| validation start tree | `22b55c196f604315caddfc849ab8192c4015deb1` |
| validation end tree | `22b55c196f604315caddfc849ab8192c4015deb1` |
| ### **digests match** | ### **✔ — rerun in full after the manifest change; nothing altered after** |

**Remaining 16, all pre-existing Blockers 4–6:** 7 stale router/store fixtures *(incl. both merge-gating AC-SAFE cases — the guard is right, the tests are old)* · 4 schema-probe · 2 deprecated ratchet · 1 U2.6A marker *(correctly failing)* · 1 exact-string guard · 1 AC-SEC-001 probe.

### ⛔ A GUARD CAUGHT ME ADDING AN UNJUSTIFIED EXEMPTION
Adding `owner_assertions` to the tenant-exempt list broke `test_the_exempt_list_is_not_an_escape_hatch` — ### **I had exempted a table in code without justifying it in the manifest, which is exactly the escape hatch that guard exists to prevent.** Adjudicated with a reason, an owner and a bounded condition: it may never carry `commit_key` + `state`, so it cannot quietly become a second effect ledger.

## 29–30. · **Blocker 3 closed?** ### **Yes.** · **Blocker 4 may begin?** ### **Yes.**

---

# VERDICT

## ### **READY TO BEGIN BLOCKER 4 — EXACT TENANT-SCOPE QUALIFICATION**

**Carried forward:** Blockers 4–6 open · ### **AC-SEC-001 RED** · ### **R-07 OPEN — NOT CONTAINED** · six live-write paths · 31 adapter import edges · 24 event-less transitions · the knowledge-base `"default"` tenants. ### **This closes one blocker, not the phase.**
