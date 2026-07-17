# U2.6B — Tenant-Scope Every Affected WorkflowStore Method

> # ### **NOT READY. NO METHOD WAS SCOPED.**
> ### **This is the outcome your brief prescribes for this case, not a shortfall I am dressing up: "If all 22 methods cannot be completed and validated in this pass — do not leave a mixed tenant-scope implementation."**
> ### **Zero methods changed. Zero production files touched. The tree is exactly `55c225f` plus two inert documents.**

**Starting commit:** `55c225f`

---

## 1–4. The exact method set *(recomputed, not inherited)*
### **22 affected methods — 13 write · 9 read.** AST-derived over the exact seven tables; identities, not the count, are the oracle. Full per-method table with target SQL and today's cross-tenant risk: **[u26b-method-inventory.md](u26b-method-inventory.md)**.

## 5–6. Methods migrated: ### **0.** Methods blocked: ### **0** *(none attempted)*.

## ⛔ WHY NOTHING WAS SCOPED

U2.6B is indivisible, and its scope is larger than one method-by-method edit:

| Required, together, in one change | Why it cannot be deferred |
|---|---|
| `_migrate()` creates the **tenant-first** schema | ### **The live schema has no `tenant` column on six of seven tables. A tenant predicate against today's schema is not a safer query — it is a SQL error.** |
| ### **One central schema-readiness check** | pre-migration / partially-migrated DBs must fail closed **before** tenant-owned SQL — never a legacy fallback, never "not found", never something that looks like success |
| **All 22** methods scoped | see below |
| Multi-tenant fixtures reusing ids / hashes / Commit Keys | otherwise the cross-tenant negatives are untested and prove nothing |
| 27 acceptance cases · 20 mutations · guards | a guard never seen to fail is a decoration |

### **The three that make it all-or-nothing**
`receive_document` · `get_run_by_hash` · `claim_operation_commit`.
> ### **Scope nineteen of twenty-two and Tenant B's document is still silently a duplicate of Tenant A's, and Tenant A's Commit Key still blocks Tenant B's invoice — while the store now LOOKS tenant-safe.** A reviewer reading `WorkflowStore(db, tenant=...)` with most methods scoped would reasonably assume the boundary is complete. ### **That is strictly more dangerous than today's honestly-unscoped store, which is exactly what your brief says.**

I could not complete **and validate** that surface in this pass. ### **Rather than leave a mixed store or claim an unverified green, I changed no production code.**

## 7. Tables touched by the 22
`workflow_runs` (8 methods) · `operation_commit_claims`→`effect_grants` (5) · `operation_token_amounts` (2) · `audit_events` (2) · `security_events` (2) · `operation_action_claims` (1) · `delivery_action_claims` (1) · `_migrate` (all seven).

## 8–17. ### **NOT IMPLEMENTED**
Schema-readiness mechanism · pre-migration behaviour · partially-migrated behaviour · read/write/update/delete scoping · join scoping · document-hash behaviour · external-id behaviour · effect-ledger method behaviour — ### **none exist.** Each has a stated target in the inventory.

## 18–20. Tests · guards · mutation: ### **none added.** ### **The U2.6A non-isolation assertion is deliberately LEFT STANDING** — it is still true, and replacing it now would be the false claim it exists to prevent.

## 21–24. Status — ### **unchanged from `55c225f`**
| | |
|---|---|
| **AC-SAFE-012** | ### **GREEN** |
| **AC-SAFE-013** | ### **GREEN** |
| ### **AC-SEC-001** | ### **RED — correctly** |
| ### **R-07** | ### **OPEN — NOT CONTAINED** |

## 25. Knowledge-base `"default"` tenants
`ops_control.py` (5) + `action_callback.py:1639` — ### **recorded, unresolved, untouched.**

## 26. Legacy modules touched: ### **NONE.** `workflow.py` remains **ADAPT** — its 22 methods are U2.6B's whole content.

## 27–28. Final validation
### **Not run — there is no candidate tree to validate.** No production file changed; the last full-tree result stands at `55c225f`: **879 passed, 1 skipped, 0 failed**. The two documents added here are inert prose imported by nothing.

## 29–31. All 22 scoped? ### **No — zero.** U2.6B complete? ### **No.** May U2.6C begin? ### **No — U2.6C activates the schema that U2.6B's methods must already speak.**

---

# VERDICT

## ### **NOT READY**

**U2.6B needs a pass with room to do it in one piece.** It is now fully specified and mechanical:

1. `_migrate()` → the tenant-first `TARGET_SCHEMA` already committed in `migrations/phase2_tenant_first.py` *(fresh DBs and every fixture get it for free)*;
2. ### **one central readiness check — fail closed, no fallback, no default;**
3. ### **all 22 methods in the same change**, each using `self._tenant` in the predicate or the inserted row;
4. multi-tenant fixtures that deliberately collide ids, document hashes and Commit Keys;
5. the 27 cases, the 20 mutations, the guards;
6. then U2.6C, and only then `AC-SEC-001`.

> ### **The inventory names every method, its target SQL, and the cross-tenant defect it currently carries. Nothing remains to be discovered — only built, in one piece, and verified.**
