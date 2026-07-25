# U2.6 — WorkflowStore Construction-Site Inventory *(mechanically derived)*

**146 construction sites across 51 files.** AST-derived: real `WorkflowStore(...)` calls, not text matches.

| # | File | Sites | Runtime | Prod reachable | Current tenant source | Canonical tenant source | Deterministic? | ### Classification |
|---|---|---|---|---|---|---|---|---|
| 1 | `eval/tests/test_action_callback.py` | 11 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 2 | `eval/tests/test_activity_log.py` | 3 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 3 | `eval/tests/test_browser_use_write.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 4 | `eval/tests/test_channels.py` | 2 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 5 | `eval/tests/test_conversational_surface.py` | 3 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 6 | `eval/tests/test_delivery.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 7 | `eval/tests/test_delivery_dispatch.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 8 | `eval/tests/test_email_adapter.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 9 | `eval/tests/test_extraction_bridge.py` | 2 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 10 | `eval/tests/test_follow_up.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 11 | `eval/tests/test_lane_graduation.py` | 7 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 12 | `eval/tests/test_mailbox_workflow.py` | 11 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 13 | `eval/tests/test_mock_tms.py` | 2 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 14 | `eval/tests/test_operation_router.py` | 5 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 15 | `eval/tests/test_ops_control.py` | 4 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 16 | `eval/tests/test_packet_page.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 17 | `eval/tests/test_phase0_migration_guards.py` | 2 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 18 | `eval/tests/test_phase1_commit_key.py` | 16 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 19 | `eval/tests/test_phase1_occurrence_identity.py` | 2 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 20 | `eval/tests/test_propose_ar_autonomous.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 21 | `eval/tests/test_review.py` | 3 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 22 | `eval/tests/test_review_actions.py` | 4 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 23 | `eval/tests/test_roi_ledger.py` | 6 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 24 | `eval/tests/test_slack_adapter.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 25 | `eval/tests/test_summary.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 26 | `eval/tests/test_thread_reply.py` | 6 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 27 | `eval/tests/test_tms_adapter.py` | 2 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 28 | `eval/tests/test_tms_write.py` | 3 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 29 | `eval/tests/test_tool_permissions.py` | 1 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 30 | `eval/tests/test_workflow.py` | 5 | test fixture | no (test) | ### **NONE** | a fixture tenant (never a production value) | yes | **TEST_FIXTURE_EXPLICIT_TENANT** |
| 31 | `scripts/apply_review_action.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 32 | `scripts/deliver_review.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 33 | `scripts/dispatch_review.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 34 | `scripts/enter_invoice_discovered.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 35 | `scripts/enter_tms_payable.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 36 | `scripts/enter_truckingoffice_invoice.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 37 | `scripts/generate_daily_summary.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 38 | `scripts/generate_follow_up_draft.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 39 | `scripts/generate_mock_tms.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 40 | `scripts/generate_packet_pages.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 41 | `scripts/propose_ar_from_tms.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 42 | `scripts/report_legacy_commit_identities.py` | 1 | operator | operator-run | ### **NONE** | --assert-tenant, an operator assertion | yes | **MIGRATION_TOOL_REQUIRES_ASSERTION** |
| 43 | `scripts/run_action_callback_server.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 44 | `scripts/run_dogfood_pilot.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 45 | `scripts/run_first_design_partner.py` | 2 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 46 | `scripts/run_gmail_to_slack_dogfood.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 47 | `scripts/run_review.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 48 | `scripts/run_workflow.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 49 | `scripts/submit_signed_action.py` | 1 | CLI | operator-run | ### **NONE** | client config `client_id` via an explicit --tenant/--client-config | yes | **MIGRATE_EXPLICIT_TENANT** |
| 50 | `src/freight_recon/action_callback.py` | 16 | src | ### **YES** | ### **NONE** | threaded from the caller's client config `client_id` | yes | **MIGRATE_EXPLICIT_TENANT** |
| 51 | `src/freight_recon/mailbox_workflow.py` | 1 | src | ### **YES** | ### **NONE** | threaded from the caller's client config `client_id` | yes | **MIGRATE_EXPLICIT_TENANT** |

**Classification totals:** `TEST_FIXTURE_EXPLICIT_TENANT` = **109** · `MIGRATE_EXPLICIT_TENANT` = **36** · `MIGRATION_TOOL_REQUIRES_ASSERTION` = **1**

> ### **Every one of the 146 sites currently supplies NO tenant. `CallbackAppConfig` has no tenant field, so production has no canonical tenant source reaching the store at all — that is the substance of U2.6, not a detail of it.**


---

## The 22 affected `WorkflowStore` methods *(AST-derived; the earlier "44" was a regex over-count)*

**13 WRITE · 9 READ.** Each must carry the bound tenant structurally.

| Op | Method | Tables |
|---|---|---|
| **W** | `receive_document` | `workflow_runs` — ### **the document-hash dedup entry point** |
| **R** | `get_run` · `get_run_by_hash` · `list_runs` | `workflow_runs` — ### **`get_run_by_hash` IS the cross-tenant defect's read half** |
| **W** | `transition` · `mark_extracted` · `mark_reconciled` · `refresh_reconciliation` | `workflow_runs` |
| **W** | `add_audit_event` · `add_security_event` | `audit_events` · `security_events` |
| **W** | `claim_operation_action` · `claim_delivery_action` | the action-claim tables |
| **R/W** | `operation_commit_claim` · `claim_operation_commit` · `update_operation_commit_payload` · `release_operation_commit` · `legacy_commit_rows` | → `effect_grants` |
| **R/W** | `record_operation_token_amount` · `operation_token_amount` | `operation_token_amounts` |
| **R** | `audit_events` · `security_events` | history reads |
| — | `_migrate` | ### **must create the tenant-first schema on a fresh DB and REFUSE a legacy one** |

## Tenant sources — decided
| Source | Verdict |
|---|---|
| ### **client config `client_id`** *(a tenant-scoped configuration record)* | ### **THE canonical production source.** Present in `configs/clients/*.yaml`; ### **not currently threaded into `CallbackAppConfig` — U2.6 must add it.** |
| operator `--assert-tenant` | the migration tool only |
| fixture tenant | tests only; `require_tenant` refuses `"test"` so a fixture value cannot pose as production |

### Rejected, explicitly
`tenant="default"` · first-tenant-in-DB · env fallback · inference from document hash / load id / email · a tenant read from an unscoped row · singleton-workspace assumption. ### **`require_tenant()` refuses all 20 sentinels structurally.**

### ⛔ Finding: production already hardcodes a sentinel tenant
`ops_control.py` (5 sites) and `action_callback.py:1639` pass ### **`tenant="default"`** — to the **knowledge base**, not to the seven tables, so it is outside Phase 2's scope and was **not** changed. ### **It is exactly the pattern this phase forbids, and it is now recorded rather than discovered later.** Disposition: **ADAPT**, owned by the phase that makes the knowledge base tenant-safe.
