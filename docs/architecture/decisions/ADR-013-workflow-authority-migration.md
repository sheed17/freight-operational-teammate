# ADR-013 — TMS Relationship and Workflow-Authority Migration

**Status:** ✅ **FINAL — U-REBASELINE-1 (founder-authorized, 2026-07-20).**
**Supersedes:** `operating-model.md` §2.4/§7.2 ("Neyma is never the system of record" as a
permanent boundary) and the "wrong customer" screen for TMS-replacement demand.
**Preserves:** ADR-001 (authority model) — authority is per-truth-domain and explicit, always.

---

## 1. Decision — the eight-point position

1. **Initial adoption does not require TMS replacement.**
2. Neyma **integrates with the systems the customer already uses**.
3. The TMS **may initially remain** the contractual or operational system of record.
4. Neyma **may become authoritative for individual workflows** when the customer deliberately
   migrates that authority.
5. Neyma **may become the primary operating interface**.
6. Neyma **may replace individual tools and workflow surfaces**.
7. Neyma **may eventually become the primary operating platform** where customer choice, product
   evidence and migration readiness support it.
8. Migration occurs **workflow by workflow**, never through an assumed immediate rip-and-replace.

"Integrate-first" and "migration-capable" are simultaneous truths. Neither erases the other.

## 2. The canonical authority-migration model

**No workflow's authority moves by drift.** A workflow-authority migration is a first-class,
recorded decision. Every migration MUST specify all thirteen fields before cutover:

| # | Field | Meaning |
|---|---|---|
| 1 | **Current system of record** | Who is authoritative today, per truth domain (ADR-001) |
| 2 | **Target authoritative system** | The post-migration authority (possibly Neyma) |
| 3 | **Source-of-truth precedence** | Conflict resolution during coexistence |
| 4 | **Synchronization model** | Direction, cadence, conflict handling while both systems live |
| 5 | **Cutover conditions** | The objective preconditions for the authority flip |
| 6 | **Customer authorization** | The accountable human decision, recorded — never inferred |
| 7 | **Rollback plan** | How authority returns if the migration fails |
| 8 | **Data migration plan** | What moves, how it is validated |
| 9 | **Reconciliation plan** | How divergence is detected and resolved, before and after |
| 10 | **Audit requirements** | What must be provable about the migration afterwards |
| 11 | **Effect authority** | Which system's writes are consequential during each stage |
| 12 | **Operational fallback** | How the business operates if both systems are impaired |
| 13 | **Success metrics** | How "this migration worked" is measured |

A migration missing any field is **not authorized**. The migration record is per-tenant,
per-workflow, owner-asserted, and auditable.

## 3. What this does NOT change

- Authority remains **per truth domain** — becoming authoritative for Documentation does not
  make Neyma authoritative for Billing.
- **Authentication and access never create authority** (ADR-014, TOOL-ACCESS-POLICY).
- External effects still route through the effect boundary (ADR-004) regardless of who is the
  system of record.
- No migration is performed, offered, or scheduled anywhere in the current program before the
  capability phase that implements this model (P13) — this ADR makes the *decision* durable,
  not the feature.

## 4. Consequences

- The "no rip-and-replace" adoption posture stays true **as the entry point** and stops being a
  ceiling.
- A customer who wants eventual TMS replacement is a **valid customer** with a longer migration
  path, not a disqualified one.
- P13 (multi-loop expansion) carries the implementation obligation for the migration model.
