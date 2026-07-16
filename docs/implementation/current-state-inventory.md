# Current-State Inventory — Mechanical Repository Reconnaissance

**Method:** ### **direct inspection of the repository at `6057dfe`, NOT a re-read of prior inventories.** Every number below is grep-derived and reproducible.
**Date:** 2026-07-16 · **No code modified.**

## 1. REPOSITORY SHAPE
| Metric | Value |
|---|---|
| Python files | **208** |
| `src/freight_recon/` modules | **73** |
| `scripts/` | **50** |
| `eval/tests/` | **78** |
| LOC (src) | **~20,700** |
| Test suite | 677 passing at baseline `f0e801b` |

## 2. ENTRY POINTS — **50 script entry points** (all with `main`/argparse/`__main__`)
Application/worker/CLI: `run_teammate` (supervisor) · `run_action_callback_server` (Slack callback) · `run_gmail_to_slack_loop` · `run_mailbox_intake` · `run_workflow` · `run_ingestion` · `run_extraction` · `run_reconciliation` · `run_review` · `run_operate_request` · `run_operator_agent` · `run_dogfood_pilot` · `run_first_design_partner` · `run_internal_pilot_session` · `run_sunday_readiness` · `run_diagnostics`. Effect-capable: `enter_truckingoffice_invoice` · `enter_invoice_discovered` · `enter_tms_payable` · `propose_ar_from_tms` · `drive_real_tms` · `discover_tms_screen` · `orient_tms` · `record_tms_observation` · `read_tms_browser_use`. Support/verify/generate: the remaining ~25.
### **No webhook handler, no API route, no scheduled-job framework exists** — the runtime is script-supervised (`run_teammate` spawns children). ### **This is a finding: there is no HTTP surface to contain, but also no durable job runtime — Phase 5 introduces the outbox/inbox that replaces ad-hoc loops.**

## 3. DEPRECATED-TERM SURFACE *(the semantic-migration debt, measured)*
| Term | Hits | Files | Notes |
|---|---|---|---|
| ### `lane` (word) | ### **310** | many | ### **the largest surface; means Action Class AND freight lane — must NOT be find-and-replaced** |
| ### `CommandIntent` | ### **92** | **16** | ### **named after an entity ADR-008 DELETED; the code follows the OLD spec** |
| `MockTmsWriteLedger` | 27 | 10 | test-only after `974031d`; guarded by `test_no_mock_effect_in_production` |
| `workflow_runs` | 22 | 8 | table + code — the Pipeline Instance ancestor |
| ### `commit_identity` | ### **16** | ### **2** | ### **`operation_router.py` (producer+11 consumers) + 1 test — SMALL, CONTAINED, fixable first** |
| `operation_action_claims` | 2 | 1 | `workflow.py` table |
| `claim` (word) | 11 | — | overloaded (binding vs grant) — **qualify, never rename** |

## 4. ⛔ THE DEFECT — CONFIRMED AT CODE **AND** SCHEMA LEVEL
**`src/freight_recon/operation_router.py:335`**
```
def _commit_identity(tenant, lane, intent, amount) -> dict | None:
    if not amount: return None                                    # ⛔ (B) non-money ⇒ NO commit identity
    ...
    return {"tenant","lane","load_ref","party",
            "approved_amount": normalize_money_amount(amount)}    # ⛔ (A) the AMOUNT is in the identity
```
**`src/freight_recon/workflow.py`** — `operation_commit_key(tenant, lane, load_ref, party, approved_amount)` **hashes the amount into the key**, and:
```
CREATE TABLE operation_commit_claims (
    commit_key TEXT PRIMARY KEY,        # ⛔ (C) NOT tenant-first
    tenant, lane, load_ref, party,
    approved_amount TEXT NOT NULL,      # ⛔ identity-bearing column
    payload_json, created_at)
```
### **(A)+(B) are Migration Safety Task #1 (AC-SAFE-012/013 fail by design). (C) is a NEW finding from this reconnaissance: the commit index is not tenant-first.**

## 5. 🔎 NEW FINDING — TENANT SCOPING IS ABSENT FROM 6 OF 8 TABLES
| Table | Primary key | Tenant-first? |
|---|---|---|
| `workflow_runs` · `audit_events` · `security_events` | `id INTEGER AUTOINCREMENT` | ### ❌ |
| `operation_action_claims` · `delivery_action_claims` | `action_id TEXT` | ### ❌ |
| `operation_commit_claims` | `commit_key TEXT` | ### ❌ |
| `operation_token_amounts` | `token_fingerprint TEXT` | ### ❌ |
| `autonomous_run_counters` | `(tenant, lane, day)` | ✅ |
### **AC-SEC-001 requires `tenant_id` NOT NULL and FIRST in every key/index across nine surfaces. The current model satisfies this in ONE of eight tables. This is a Phase-2 blocker, larger than the earlier inventories implied.**

## 6. LIVE-EFFECT-CAPABLE PATHS *(by import, not by reputation)*
Scripts importing effect machinery (`enter_approved_payable` / `truckingoffice_write` / `OperatorAgent` / `cdp_actuator`):
`enter_truckingoffice_invoice` · `enter_invoice_discovered` · `enter_tms_payable`(mock) · `run_dogfood_pilot`(mock) · `propose_ar_from_tms` · `run_action_callback_server` · `run_operate_request` · `run_operator_agent` · ### **`orient_tms`**.
> ### 🔎 **NEW FINDING: `orient_tms.py` imports `cdp_actuator`.** The frozen inventory classified it **MAKE_READ_ONLY**. It is read-only **by convention**, actuator-capable **by import**. ### **Convention is not containment — it is reclassified below and must be structurally constrained.**

## 7. DIRECT ADAPTER IMPORT SITES — **13 files** *(every one violates the future import-graph gate)*
**src (4):** `multistep_write.py` · `discovered_write.py` · `truckingoffice_write.py` · `brain_runtime.py`
**scripts (9):** `propose_ar_from_tms` · `run_operate_request` · `run_action_callback_server` · `enter_truckingoffice_invoice` · `enter_tms_payable` · `orient_tms` · `run_dogfood_pilot` · `run_operator_agent` · `enter_invoice_discovered`
### **These 13 are the exact work-list for Phase 4 (adapter containment). The CI gate cannot be enabled until all 13 are converted or removed — it is the gate's own acceptance oracle.**

## 8. CURRENT MECHANISMS *(what exists vs what the target needs)*
| Mechanism | Current | Assessment |
|---|---|---|
| Orchestration | `operation_router.py` + `OperatorAgent`; script loops | **PRESENT_BUT_NONCANONICAL** — the Pipeline Instance ancestor |
| State | `workflow_runs` + explicit states + an allowed-transition table | ### **PRESENT_BUT_NONCANONICAL — the discipline is right, the shape is document-shaped (13 machines needed)** |
| Events | `audit_events`, `security_events` (append rows) | **PARTIAL** — no envelope, no outbox, no inbox, no versioning |
| Identity | `email_triage` deterministic-ID-first linker | ### **PRESENT_AND_COMPATIBLE in spirit — the ancestor of §10.1; lacks `provenance_class`** |
| Authorization | Slack signed HMAC single-use token; channel/user allowlist | **PARTIAL** — transport layer of ADR-005 §3.15 exists; no fingerprint, no witness |
| Idempotency | `operation_commit_claims` + `*_action_claims` | ### **PRESENT_BUT_UNSAFE — the amount is in the key; non-money uncovered; not tenant-first** |
| Tenant routing | a `tenant` string threaded through; **6/8 tables not tenant-first** | ### **PRESENT_BUT_UNSAFE** |
| Approval | Slack button → callback → resume | PARTIAL — no Material-Facts Fingerprint, no drift check |
| Retry/timeout | ad-hoc; some bounded | **PARTIAL** — no TRANSIENT/PERMANENT classification |
| Audit | `audit_events` + `security_events` | PARTIAL — no pinned decision context, no explainability query |
| Replay | ### **none** | ### **ABSENT** |
| Verification | readback + amount reconcile in the browser agent; `invoices_table_present` | ### **PARTIAL — the instinct is right; no positive health control, ~2 outcomes not 8** |
| Brake | `pause tms writes` flag in `ops_control` | ### **PRESENT_BUT_UNSAFE — a flag checked BY CONVENTION; would not stop `enter_truckingoffice_invoice.py`** |

## 9. WHAT TO KEEP *(the ancestors — generalize, do not discard)*
`enter_approved_payable` (the gated write driver — **the spine, R-03**) · `WorkflowStore`'s states+transition table+audit · the single-use HMAC Slack token · the `email_triage` deterministic-first linker · `invoices_table_present` (a proto positive-health control) · the document fence (`set_file_input` + runtime-supplied file) · the browser reliability work (settle-detection, amount reconcile, macro replay).
