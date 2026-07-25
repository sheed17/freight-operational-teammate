# U2.6B — The Exact 22-Method Inventory *(mechanically derived; inert)*

> ### **NOTHING IN THIS FILE IS IMPLEMENTED.** All 22 methods remain UNSCOPED. This is the work plan for U2.6B, not a record of it.

**22 affected methods** — **13 write · 9 read**. AST-derived over the exact seven tables. The identities are the oracle, not the count.

| # | Method | Line | Ops | Tables | ### Tenant-first target | ### Cross-tenant risk today |
|---|---|---|---|---|---|---|
| 1 | `_migrate` | 158 | — | `audit_events`, `delivery_action_claims`, `operation_action_claims`, `operation_commit_claims`, `operation_token_amounts`, `security_events`, `workflow_runs` | creates the tenant-first schema for FRESH databases | n/a — this IS the schema |
| 2 | `receive_document` | 249 | INSERT | `workflow_runs` | INSERT tenant; **dedup lookup by (tenant, document_hash)** | ### **THE live cross-tenant defect: Tenant B's identical bytes are silently called a duplicate of Tenant A's** |
| 3 | `get_run` | 289 | SELECT | `workflow_runs` | WHERE tenant=? AND id=? | Tenant A reads Tenant B by numeric id |
| 4 | `get_run_by_hash` | 293 | SELECT | `workflow_runs` | WHERE tenant=? AND document_hash=? | ### **the read half of the doc-hash defect** |
| 5 | `list_runs` | 299 | SELECT | `workflow_runs` | WHERE tenant=? (+ pagination inside the partition) | listing leaks every tenant's runs |
| 6 | `transition` | 303 | UPDATE | `workflow_runs` | UPDATE ... WHERE tenant=? AND id=? | Tenant A transitions Tenant B's run |
| 7 | `mark_extracted` | 340 | UPDATE | `workflow_runs` | UPDATE ... WHERE tenant=? AND id=? | cross-tenant mutation |
| 8 | `mark_reconciled` | 364 | UPDATE | `workflow_runs` | UPDATE ... WHERE tenant=? AND id=? | cross-tenant mutation |
| 9 | `refresh_reconciliation` | 400 | UPDATE | `workflow_runs` | UPDATE ... WHERE tenant=? AND id=? | cross-tenant mutation |
| 10 | `add_audit_event` | 466 | INSERT | `audit_events` | INSERT tenant; **tenant-consistent FK to workflow_runs** | audit row attached to another tenant's run |
| 11 | `add_security_event` | 494 | INSERT | `security_events` | INSERT tenant | security events pooled across tenants |
| 12 | `claim_operation_action` | 512 | INSERT | `operation_action_claims` | INSERT tenant; conflict target (tenant, action_id) | ### **Tenant A's action_id consumes Tenant B's single-use claim** |
| 13 | `claim_delivery_action` | 539 | INSERT | `delivery_action_claims` | INSERT tenant; conflict target (tenant, action_id) | as above, delivery transport |
| 14 | `operation_commit_claim` | 562 | SELECT | `operation_commit_claims` | WHERE tenant=? AND commit_key=? | ### **Tenant A observes Tenant B's effect reservation** |
| 15 | `legacy_commit_rows` | 585 | SELECT | `operation_commit_claims` | WHERE tenant=? AND ... | ### **cross-tenant history posing as this tenant's compatibility evidence** |
| 16 | `claim_operation_commit` | 635 | INSERT | `operation_commit_claims` | INSERT tenant; conflict target (tenant, commit_key) | ### **Tenant A's commit_key blocks Tenant B's legitimate effect** |
| 17 | `update_operation_commit_payload` | 681 | UPDATE | `operation_commit_claims` | UPDATE ... WHERE tenant=? AND commit_key=? | cross-tenant reservation mutation |
| 18 | `release_operation_commit` | 698 | DELETE | `operation_commit_claims` | DELETE ... WHERE tenant=? AND commit_key=? | ### **Tenant A releases Tenant B's reservation** |
| 19 | `record_operation_token_amount` | 754 | INSERT/UPDATE | `operation_token_amounts` | INSERT tenant; conflict target (tenant, token_fingerprint) | ### **an APPROVED AMOUNT bound in a global namespace** |
| 20 | `operation_token_amount` | 777 | SELECT | `operation_token_amounts` | WHERE tenant=? AND token_fingerprint=? | reads another tenant's approved amount |
| 21 | `audit_events` | 786 | SELECT | `audit_events` | WHERE tenant=? AND run_id=? | cross-tenant history disclosure |
| 22 | `security_events` | 807 | SELECT | `security_events` | WHERE tenant=? | cross-tenant security disclosure |

## The three that make this all-or-nothing
### **`receive_document` · `get_run_by_hash` · `claim_operation_commit`** — document dedup and effect reservation. ### **Scope 19 of 22 and these three still make Tenant B's document a duplicate of Tenant A's, and Tenant A's commit_key block Tenant B's invoice — while the store now LOOKS tenant-safe.** That is why the brief forbids a partial pass, and why this inventory ships with zero methods changed rather than nineteen.

## Schema posture — the reason U2.6B cannot ship alone
The live schema is **pre-migration**: no `tenant` column exists on six of the seven tables. ### **A tenant predicate against today's schema is not a safer query — it is a SQL error.** So U2.6B needs, together and in one pass:
1. `_migrate()` creating the **tenant-first** schema for fresh databases (every fixture then gets it for free);
2. ### **one central schema-readiness check** — a pre-migration or partially-migrated database must fail closed BEFORE any tenant-owned SQL, and must never fall back to legacy SQL, report "not found", or look like success;
3. all 22 methods scoped in the same change;
4. multi-tenant fixtures that deliberately reuse ids, document hashes and Commit Keys across tenants.

> ### **U2.6B may be committed but must NOT be deployed to production before U2.6C schema activation and qualification.**

