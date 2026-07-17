# Phase-2 Implementation Review — Tenant-Safe Persistence & The Canonical Ledger

> # ### **NOT READY. PHASE 2 IS INCOMPLETE AND I AM STOPPING RATHER THAN CLAIMING IT.**
> ### **What exists is real, proven against the live data, and inert. What is missing is the half that touches every caller — and a half-migrated tenant boundary is more dangerous than an unmigrated one.**

---

## ⛔ WHY I STOPPED

Phase 2's schema work is done and proven. Its **application integration is not**, and the recon of that surface is what changed my assessment:

| Surface | Size |
|---|---|
| `WorkflowStore` methods touching the seven tables | ### **44** (26 write · 18 read) |
| ### **`WorkflowStore(...)` construction sites** | ### **146** |
| Does `WorkflowStore` know its tenant today? | ### **No. Not a parameter, not a field, nowhere.** |

Every one of those 146 sites must supply a tenant before a tenant-first schema can be switched on, because `tenant` is `NOT NULL` and first in the key. There is no honest shortcut:

> ### **The only way to land the schema without touching 146 call sites is a default tenant — which the brief prohibits in four separate places, and rightly: a default is an inference wearing a constant's clothes, and it silently merges two tenants' history the first time this database is shared.**

Finishing that integration, the 22 acceptance cases, the 11 concurrency schedules, the 13 mutations and the guards is more than I can complete **to the standard this program requires** in one pass. ### **The failure mode I would be inviting is precisely the one this whole reset exists to prevent: a phase reported green whose validation did not cover what shipped.** I have caught that exact error three times already this session — in Phase 0's stale suite, in the errata harness's false-green, and in two of my own decorative guards. ### **I am not going to author a fourth by declaring Phase 2 done.**

---

## WHAT IS DELIVERED (real, tested, and INERT)

**Nothing imports it but its own CLI. No production behaviour changed. `git status` on `src/` and `scripts/` shows two new paths and zero modifications.**

### `src/freight_recon/migrations/phase2_tenant_first.py`
- ### **The exact seven tables, enumerated as a SET, never counted** — the errata's lesson encoded: "6 of 8" executed literally would have left `operation_token_amounts` behind with `AC-SEC-001` red and the phase marked done.
- **The target schema**: tenant-first PKs on all seven · ### **`UNIQUE (tenant, document_hash)` — the live cross-tenant doc-hash fix** · tenant-consistent composite FKs (a cross-tenant child cannot be *spelled*).
- ### **The ONE canonical ledger** (`effect_grants`, U2.2/U2.5 — a rename of `operation_commit_claims`, not a second table): the **eight canonical states enforced by a CHECK**, `REVOKED` distinct from `EXPIRED_UNCLAIMED`, both indexes — the P2 hold `UNIQUE(tenant, commit_key)` and ### **Layer-2 commit-once `UNIQUE(tenant, commit_key) WHERE state='CLAIMED'`** exactly as frozen (spec §16.1).
- **13 reserved columns**, each naming the phase that may honestly populate it (`checkpoint_id`→P3, `gate_decision`→P8, `pipeline_instance_id`→P6 …) — shaped for the checkpoint without pretending to be it.
- **Material facts persisted separately from identity**: `approved_amount` + `material_facts_json` are columns; nothing mutable touches `commit_key`.
- ### **The staged order the plan requires** — structures → backfill → quarantine → **validate** → constraints → verify FKs → cleanup. Nothing destructive runs before validation.

### Proven against the **real** workspace (`neyma_workflow.sqlite3`, 18 runs + 102 audit events)
| Path | Result |
|---|---|
| **dry run** | ### **the real database is byte-identical afterwards** |
| ### **apply, no assertion** | ### **all 120 rows QUARANTINED intact · 0 migrated · 0 guessed** |
| **apply, `--assert-tenant acme`** | 18 + 102 migrated · `PK=(tenant, id)` · tenant-scoped doc-hash index · FKs verified |
| **rerun** | ### **`already_applied=True` — idempotent, no duplication** |

### ⛔ THE FINDING THAT SHAPES THE REST OF PHASE 2
**Only `operation_commit_claims` carries a tenant. The other six of the seven have no tenant anywhere** *(errata-safe phrasing: the affected set is SEVEN; six of them are tenantless)* — not a column, not a parent, not a payload. I checked the real rows: `{id, load_id, document_hash, state, invoice_number, carrier, outcome, reason, created_at, updated_at}`. ### **There is nothing to derive from.**
The frozen plan already ruled on this — *"ownership cannot be inferred — a human assigns it"* — so the migration takes an **owner assertion** (`--assert-tenant`, recorded as an assertion) or **quarantines**. ### **There is deliberately no fallback value.**

### Four real bugs found by exercising it (not by reading it)
| Bug | Why it mattered |
|---|---|
| Legacy `DROP` order | SQLite rewrites a child's FK target on parent rename, so dropping the parent tripped the constraint |
| ### **`PRAGMA foreign_keys` inside a transaction** | ### **Silently ignored — the pragma appeared to work and did nothing** |
| Ledger created only when legacy rows existed | a fresh database would have had **no ledger at all** |
| ### **Idempotency keyed on a table's existence** | ### **A workspace with no commit claims reported itself unmigrated forever** — the rerun was safe only because the step markers held |

---

## WHAT IS **NOT** DONE — the honest list

| Unit / requirement | Status |
|---|---|
| **U2.1** tenant-first keys, all seven | ### **SCHEMA + MIGRATION DONE · NOT APPLIED, NOT WIRED** |
| **U2.2 / U2.5** the one `effect_grants` ledger | ### **SCHEMA DONE · store does not use it** |
| **U2.3** the two partial unique indexes | ### **CREATED BY THE MIGRATION · not exercised by the runtime** |
| **U2.4** ledger backfill (dry-run first) | ### **DONE + proven read-only** |
| ### **Store / call-site integration (146 sites)** | ### **NOT STARTED — the blocking work** |
| The 22 Phase-2 acceptance cases | ### **NOT WRITTEN** |
| 11 concurrency schedules | ### **NOT WRITTEN** |
| 13 mutations | ### **NOT RUN** |
| Phase-2 structural guards | ### **NOT WRITTEN** |
| `AC-SEC-001` | ### **STILL RED** — correctly: the live schema is unchanged |
| Final-tree validation | ### **NOT RUN — there is no candidate tree to validate** |

## Preserved / unchanged
`AC-SAFE-012` **GREEN** · `AC-SAFE-013` **GREEN** · `operation_commit_key` still deleted · no parallel constructor · occurrence identity still canonical · **`workflow_runs.document_hash` still globally unique in the live schema** (the fix exists in the migration; it is not applied).
### **Open findings, ALL still open:** **R-07 — OPEN, NOT CONTAINED** · 31 adapter import edges (P4) · 24 event-less transitions (before P5/G2) · checkpoint, witness, claim CAS (P3) · typed policy (P8).

## Legacy modules touched
`workflow.py` — ### **UNTOUCHED. Provisional disposition: ADAPT** (its 44 table-touching methods and 146 construction sites are the Phase-2 completion work).

## Rollback posture
### **Nothing to roll back.** The migration is inert; the live schema is unchanged; the real databases are byte-identical. The two new files can be deleted with no effect.

---

# VERDICT

## ### **NOT READY**

**Phase 2 needs a second pass.** The schema, the ledger, the migration and the quarantine model are done and proven against live data — ### **the remaining work is the 146-site store integration, and it is the part that must not be rushed, because it is the part that can break a running system or tempt a default tenant.**

**Recommended next step:** authorise Phase 2 to continue as a bounded unit of its own — ### **"U2.6: make `WorkflowStore` tenant-scoped across all 146 construction sites, fail-closed with no default"** — then apply the migration, then the acceptance/concurrency/mutation suites.

> ### **I would rather hand you an accurate NOT READY than a Phase 2 whose green I could not stand behind.**
