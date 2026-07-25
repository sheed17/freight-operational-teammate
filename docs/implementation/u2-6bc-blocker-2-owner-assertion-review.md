> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Verdicts, statuses, counts and "READY"
> declarations below describe the state THEN — several are known-superseded (including any
> "24 of 134" transition figure, retired by U-HANDOFF-1B, and any suite count). Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U2.6BC Blocker 2 — Auditable Historical Tenant-Ownership Assertions

> ### **CLOSED.** Historical ownership now requires a durable, auditable assertion naming **who** decided, **what** they authorised, and **on what basis** — recorded *before* the rows move.
> ### **Blockers 3–6 remain OPEN. Phase 2 is NOT complete.**

**1. Starting commit:** `9d11ede` (branch `recovery/u2-6bc-atomic-cutover`, clean)

## 2–3. Files changed
`src/freight_recon/migrations/phase2_tenant_first.py` · `scripts/migrate_phase2_tenant_first.py` · `eval/tests/test_u26bc_owner_assertion.py` **(new)** · `eval/tests/test_u26bc_migration_tenant_validation.py` *(carries full assertions now)*.

## 4–5. The assertion model
Extends the **existing** audit architecture (`schema_migrations`, `migration_quarantine`) with one `owner_assertions` table — ### **no competing audit system.** `OwnerAssertion` is a **frozen** dataclass: the scope that was validated is the scope applied, with no window in which it could widen.
**Required, all five:** `actor_id` · `tenant` · `scope` · `operational_basis` · `evidence_reference`. Recorded with `assertion_id`, `migration_run_id`, `affected_table_set`, `source_schema_version`, `source_commit`, `asserted_at`, `status`, and the four counts (considered/assigned/quarantined/conflicts).

### Why each field is enforced, not merely requested
- ### **Actor** — 18 sentinels refused (`system`, `migration`, `admin`, `operator`, `ci`, …). ### **A machine that names the actor has named nobody.** Never inferred from the OS user, git, environment or the configured client.
- ### **Basis** — refuses 20 generic phrases (`confirmed`, `requested`, `assumed single tenant`) **and** anything under four words. ### **It exists so a reader in a year can tell WHY; "confirmed" tells them nothing.**
- **Tenant** — routed through the **same `require_tenant()`** production uses. Blocker 1 preserved; ### **no second, looser path**, asserted by a test.

## 6–7. CLI + dry run
`--assert-tenant` **alone is refused** — it needs `--actor`, `--scope`, `--basis`, `--evidence`. The assertion is built and validated **before the database is opened**, the exact scope is printed before apply, and dry run vs apply is stated explicitly. ### **Dry run writes nothing — not a row, not a ledger insert, not a quarantine entry, not an assertion record** (proved by file digest).

## 8–10. Atomicity · rerun · conflict
### **The authority is durable BEFORE the assignment**: recorded `PENDING`, completed `APPLIED`/`PARTIALLY_APPLIED` with the counts that actually happened. ### **Assign-then-record would leave a window in which rows are owned by a tenant nobody is recorded as choosing — and if the recording then failed, that window would be permanent and invisible.**
**Rerun** of the identical assertion is a no-op: one record, original actor/evidence/timestamp preserved. ### **A changed tenant is a CONFLICT, refused, with both claims preserved and zero rows reassigned** — and it is checked *even when the migration is already applied*, since "already applied" would otherwise swallow someone's disagreement about ownership. **Append-only:** a guard forbids `SET actor_id`, `SET asserted_tenant`, `SET operational_basis`, `SET evidence_reference`, `SET assertion_scope` and `DELETE FROM owner_assertions` — ### **rewriting an assertion to hide a failed attempt is how an audit trail stops being evidence.**

## 11–12. Tests + guards — **23 new (42 with Blocker 1)**
All against the **real** migration and a **real copy of the live workspace**. ### **Nothing mocked: a mock that bypasses persistence proves the API is shaped right and nothing about whether rows moved.** Counts in the audit are asserted to equal what the migration actually did. **No assertion still quarantines all 120 rows rather than guessing** — the frozen rule survives.

## 13. Mutation results — ### **19/19 DETECTED**

### ⛔ SIX MUTATIONS FIRST REPORTED "MISSED" — AND ALL SIX WERE MY MUTATIONS, NOT GUARD HOLES
Each disabled **one** of two branches defending the same rule (e.g. the conflict check exists on both the fresh path *and* the already-applied path), so nothing observable changed. ### **A mutation that does not reintroduce the defect proves nothing about the guard** — the same lesson as the Phase-1 "amount back in the hash" fake. I verified this by running the mutant and watching the *second* guard still refuse, then rewrote each to disable **both** paths. All 19 then failed as they should.

### ⛔ AND I DESTROYED MY OWN WORK MID-TASK
While diagnosing those misses I ran `git checkout` on the migration module — reverting it to HEAD and **wiping `OwnerAssertion`, the audit table and the conflict logic**, none of which was committed. No stash, no dangling blob, bytecode purged: **unrecoverable.** I rebuilt it from the surviving tests and CLI.
> ### **The mistake: I used a destructive command inside a debugging loop when the mutation harness already had safe save-and-restore built in. The tests survived only because they lived in a different file — that was luck, not design.**

## 14–18. Status — ### **unchanged**
| | |
|---|---|
| Blocker 1 regression | ### **GREEN (19 tests)** |
| **AC-SAFE-012 / AC-SAFE-013** | ### **unchanged — still failing on the stale router/store fixtures (Blocker 6)** |
| **AC-SEC-001** | ### **RED** |
| ### **R-07** | ### **OPEN — NOT CONTAINED** |

## 19. Remaining failures — ### **all pre-existing, all Blockers 3–6**
7 stale router/store fixtures *(incl. both merge-gating AC-SAFE cases — the guard is right, the tests are old)* · 4 schema-probe *(the bookkeeping tables)* · 2 deprecated ratchet · 1 U2.6A marker *(correctly failing)* · 1 exact-string guard · 1 AC-SEC-001 probe. ### **Blocker 2 introduced none.**

## 20–22. Final-tree validation
| | |
|---|---|
| **Full suite** | **19 failed · 907 passed · 1 skipped** |
| ### **New failures from Blocker 2** | ### **ZERO** — against the true pre-Blocker-2 baseline of 20, this run is **19**: net **−1** |
| validation start tree | `7cd54c493efafb1cf333b570a4be25b071789476` |
| validation end tree | `7cd54c493efafb1cf333b570a4be25b071789476` |
| ### **digests match** | ### **✔ — run LAST, nothing changed after** |

**Blocker-2 suites: 42/42 green** (23 new + 19 Blocker-1). The 19 remaining failures are the pre-existing Blockers 3–6 set, unchanged in kind. · **23. Blocker 2 closed?** ### **Yes.** · **24. Blocker 3 may begin?** ### **Yes.**

---

# VERDICT

## ### **READY TO BEGIN BLOCKER 3 — COMPLETE SCHEMA READINESS**

**Carried forward:** Blockers 3–6 open · ### **AC-SEC-001 RED** · ### **R-07 OPEN — NOT CONTAINED** · six live-write paths · 31 adapter import edges · 24 event-less transitions · the knowledge-base `"default"` tenants. ### **Phase 2 is not complete and this closes one blocker, not the phase.**
