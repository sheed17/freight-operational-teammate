> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Verdicts, statuses, counts and "READY"
> declarations below describe the state THEN — several are known-superseded (including any
> "24 of 134" transition figure, retired by U-HANDOFF-1B, and any suite count). Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U2.6BC Blocker 5 — Complete Migration Matrix & Cutover Qualification

> ### **CLOSED.** Every supported starting shape reaches **exactly one classified outcome**, and every outcome tells an operator **what to do next**.
> ### **The completion marker is written LAST, and only if readiness passes** — a marker written earlier is a claim about the past that outranks the present, which is precisely how a half-migrated database gets deployed on top of.
> ### **Blocker 6 remains OPEN. Phase 2 is NOT complete.**

**1. Starting commit:** `1d31f07` (branch `recovery/u2-6bc-atomic-cutover`, clean)

## 2–3. Migration files changed · the outcome vocabulary
`src/freight_recon/migrations/phase2_tenant_first.py` · `src/freight_recon/schema.py` · `eval/tests/test_u26bc_migration_matrix.py` **(new, 27 cases)**.

### **10 canonical outcomes, each carrying a safe next action.** `"It failed"` is not an outcome — it does not say whether to retry, supply an assertion, repair by hand, or stop and call someone. Every `Report` now carries the outcome, `migration_run_id`, `assertion_id`, source/target schema version, database identity, canonical effect rows, readiness problems and the counts.

## 4–20. The shape matrix — ### **20 shapes, 27 cases, all passing**
| Shape | Outcome |
|---|---|
| **1** fresh empty | ### **`CANONICAL_READY`**, rerun ⇒ `MIGRATION_COMPLETE_RESTART_SAFE` |
| **2** empty legacy | canonical; ### **no assertion demanded for zero business rows** *(requiring one would be theatre)* |
| **3** populated + valid assertion | ### **`CANONICAL_READY`** — 120 rows, only the authorized scope |
| **4** populated, no assertion | ### **`QUARANTINED_PENDING_REVIEW`** — 120 quarantined, **0 assigned, 0 guessed** |
| **5** invalid tenant | ### **database byte-identical** — no tables, no markers, nothing |
| **6** incomplete assertion (×4 fields) | fails **before** assignment |
| **7** conflicting assertion | ### **original ownership preserved, conflict recorded, 0 reassigned** |
| **8** partial additive schema | detected; runtime stays blocked |
| **11** ### **marker says complete, schema malformed** | ### **structure wins — NOT READY** |
| **12 / 13** legacy claims absent / empty | ### **the canonical ledger is created either way; no effects manufactured** |
| **14** duplicate legacy reservations | ### **both preserved** — material-fact disagreement (£2,850 vs £3,100) stays visible |
| **15** ### **historical timeout** | ### **`UNKNOWN_OUTCOME`, never `FAILED`** |
| **19** future schema version | ### **refused, never auto-downgraded** |
| **20** already canonical | ### **true no-op** — no duplicate assertion, effects or rows |

**Dry run:** ### **byte-identical on every shape**, and it reports `OWNER_ASSERTION_REQUIRED` **before** apply so an operator learns it in advance.
**Cutover:** a tenant-scoped application ### **refuses a legacy database**; a migrated one serves it. Forward-only asserted structurally — the global doc-hash uniqueness cannot return and the store cannot be built without a tenant.

## ⛔ THE MATRIX FOUND THREE REAL DEFECTS — BY BEING RUN
1. ### **Quarantined rows reported `CANONICAL_READY`.** The schema was canonical and 120 rows had no owner — and the outcome said *safe to proceed*. ### **A tidy shape holding unresolved history is not ready.** Quarantine now outranks a clean schema.
2. ### **Re-migrating a canonical database DESTROYED its indexes.** The rebuild dropped `workflow_runs` and took `ix_workflow_runs_tenant_document_hash` with it, leaving a database that **documented** its tenant constraint without **enforcing** it. The rebuild now skips already-canonical tables.
3. **Index creation was not idempotent** — a canonical database raised instead of no-op'ing.
> ### **All three were latent at `1d31f07` and had passed every previous run.** #2 is the sharpest: a migration that silently un-enforces the very constraint the phase exists to add.

## 26. Existing failing-test classifications *(migration-scope only)*
The six pre-existing failures are **Blocker 6** scope and were **left alone**: 2 deprecated-ratchet + 2 Phase-0 tenant probes + 1 AC-SEC-001 probe (**STALE_ORACLE**), and `test_u26a_does_not_claim_tenant_isolation` (**OBSOLETE_LEGACY_BEHAVIOR** — correctly failing; it marked an intermediate state that has ended).

## 27–28. Guards + mutation — ### **16/16 DETECTED**
marker before readiness · quarantine reported ready · dry run writes · **timeout ⇒ FAILED** · duplicates merged · **rerun duplicates effects (both guards)** · canonical re-migration destroys indexes · **ledger creation removed (both paths)** · future version accepted · lying marker outranks a missing table · new app against legacy schema · **an outcome loses its next action** · a shape skipped · Blocker-1 bypassed · **Blocker-2 conflict removed (both paths)** · Blocker-4 scoping removed.

### ⛔ MY OWN GUARD WAS TOO WEAK, AND ITS FIX FOUND THREE MORE WEAKNESSES
The next-action guard first checked only **word count** — mutation slipped `"okand settle each row by hand…"` past it. Tightening it to *"a verb must OPEN the instruction"* then failed **three real outcome texts** that **described** rather than **instructed** (`"two assertions disagree…"`, `"the schema is malformed…"`, `"this database was written by…"`). ### **All three now begin with what to DO. A status an operator cannot act on is a status that gets ignored.**
**Four further "misses" were unfaithful mutations** — verified, not assumed: one targeted `schema.py` where the raise lives in `workflow.py`; three disabled one of two defending paths. ### **The safe in-memory harness held throughout and refused two no-ops outright — no git command was used.**

## 29–36. Status
| | |
|---|---|
| Blocker 1 / 2 / 3 / 4 regressions | ### **GREEN (93)** |
| ### **AC-SAFE-012 / AC-SAFE-013** | ### **GREEN** |
| **AC-SEC-001** | ### **RED** — Blocker 6 |
| ### **R-07** | ### **OPEN — NOT CONTAINED** |

## 37–40. Final-tree validation
| | |
|---|---|
| **Full suite** | ### **6 failed · 998 passed · 1 skipped** *(was 6 failed / 971 passed)* |
| ### **New failures from Blocker 5** | ### **ZERO** — the failure set is byte-identical to the baseline; **+27 passing** |
| validation start tree | `25f78c2e5500ca574d1cb0c2aaaa2b815089c04b` |
| validation end tree | `25f78c2e5500ca574d1cb0c2aaaa2b815089c04b` |
| ### **digests match** | ### **✔ — run LAST, nothing changed after** |

**The 6 remaining are unchanged and all Blocker 6:** 2 deprecated-ratchet + 2 Phase-0 tenant probes + 1 AC-SEC-001 probe (**STALE_ORACLE**) and the U2.6A marker (**OBSOLETE_LEGACY_BEHAVIOR**, correctly failing).

## 41–42. · **Blocker 5 closed?** ### **Yes.** · **Blocker 6 may begin?** ### **Yes.**

---

# VERDICT

## ### **READY TO BEGIN BLOCKER 6 — FINAL PHASE-2 QUALIFICATION**

**Carried forward:** Blocker 6 open · ### **AC-SEC-001 RED** · ### **R-07 OPEN — NOT CONTAINED** · six live-write paths · 31 adapter import edges · 24 event-less transitions · the knowledge-base `"default"` tenants. ### **This closes one blocker, not the phase.**
