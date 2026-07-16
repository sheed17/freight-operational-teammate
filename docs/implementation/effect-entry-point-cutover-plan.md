# Live-Effect Entry-Point Inventory & Cutover Plan

*Derived by **import inspection** (recon §6/§7), not reputation. ### **No write-capable entry point is unclassified.***

## The inventory *(EP-id · file · symbol · effect capability · classification)*
| EP | File | Imports | External system / op | Tenant derivation | Current idempotency | Current commit identity | Verification | Can race? | Bypasses target pipeline? | Prod reachable | Target adapter op | Action Class | ### Class | ### Cutover |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **EP-1** | `run_action_callback_server.py` | `OperatorAgent`, `cdp_actuator` | TMS write (invoice/payable/doc/status) | from client config | commit claim + action claim | ### **amount-keyed** | readback + amount reconcile | ### **yes (EP-3,6,7,9,10)** | yes | ### **YES** | A4-4..8 / A15-w | RAISE_INVOICE, RECORD_PAYABLE, FILE_DOCUMENT, UPDATE_LOAD | **CONVERT_TO_PIPELINE_CLIENT** | ### **SHARED_LEDGER_TRANSITION** → HARD_CUTOVER at P12 |
| **EP-2** | `run_teammate.py` | spawns EP-1/EP-3 | inherits | config | inherits | inherits | inherits | yes | yes | ### **YES** | — | — | **CONVERT_TO_PIPELINE_CLIENT** (supervisor) | follows EP-1 |
| **EP-3** | `propose_ar_from_tms.py` | `cdp_actuator` | TMS read + proposal→invoice | config | commit claim | amount-keyed | readback | ### **yes (EP-1,6,7)** | yes | ### **YES** | A4-1/A4-4 | RAISE_INVOICE | **CONVERT_TO_PIPELINE_CLIENT** | SHARED_LEDGER_TRANSITION |
| **EP-4** | `drive_real_tms.py` | (read) | TMS read | arg | n/a | n/a | n/a | no | n/a | manual | A4-1 | — | **MAKE_READ_ONLY** | READ_ONLY_LEGACY |
| **EP-5** | `discover_tms_screen.py` | (read) | screen map | arg | n/a | n/a | n/a | no | n/a | manual | A4-1 | — | **MAKE_READ_ONLY** | READ_ONLY_LEGACY |
| **EP-6** | `enter_truckingoffice_invoice.py` | ### **`enter_approved_payable`, `truckingoffice_write`** | ### **LIVE invoice write from a terminal** | arg | commit claim | amount-keyed | readback | ### **yes (EP-1,3,7)** | ### **YES** | ### **YES** ⚠️ | A4-4 | RAISE_INVOICE | **CONVERT_TO_PIPELINE_CLIENT or REMOVE** | ### **REMOVE_BEFORE_ENABLE** |
| **EP-7** | `enter_invoice_discovered.py` | `enter_approved_payable`, `truckingoffice_write` | LIVE invoice via screen map | arg | commit claim | amount-keyed | readback | ### **yes** | ### **YES** | ### **YES** ⚠️ | A4-4 | RAISE_INVOICE | **CONVERT_TO_PIPELINE_CLIENT or REMOVE** | ### **REMOVE_BEFORE_ENABLE** |
| **EP-8** | `orient_tms.py` | ### **`cdp_actuator`** ⚠️ | "read-only" **but actuator-capable** | arg | none | none | none | ### **potentially** | ### **YES** | manual | A4-1 | — | ### **MAKE_READ_ONLY** *(structurally — remove the import)* | **REMOVE_BEFORE_ENABLE** (of the actuator import) |
| **EP-9** | `run_operate_request.py` | `OperatorAgent`, `cdp_actuator` | NL request → LIVE write, **terminal-approved** | arg | commit claim | amount-keyed | readback | ### **yes (EP-1,3)** | ### **YES** | ### **YES** ⚠️ | A4/A15 | various | **CONVERT_TO_PIPELINE_CLIENT** | ### **REMOVE_BEFORE_ENABLE** |
| **EP-10** | `run_operator_agent.py` | `OperatorAgent`, `cdp_actuator` | ### **an agent on a live TMS, local approver — the least-gated path** | arg | agent-level only | none | partial | ### **yes (EP-1)** | ### **YES** | ### **YES** ⚠️ | — | — | ### **TEST_ONLY or REMOVE** | ### **REMOVE_BEFORE_ENABLE** |
| **EP-11** | `verify_owner_onboarding.py` | (read) | readiness checks | config | n/a | n/a | n/a | no | n/a | yes | — | — | **KEEP (read-only)** | READ_ONLY_LEGACY |
| **EP-12** | `enter_tms_payable.py` | `enter_approved_payable` (**mock**) | JSON ledger | arg | claim | amount-keyed | mock | no | n/a | ### **no (guarded)** | — | — | **TEST_ONLY** | HARD_CUTOVER (test-scope) |
| **EP-13** | `run_dogfood_pilot.py` | `enter_approved_payable` (**mock**) | JSON ledger | arg | claim | amount-keyed | mock | no | n/a | ### **no (guarded)** | — | — | **TEST_ONLY** | HARD_CUTOVER (test-scope) |

### Summary: ### **6 production-reachable live-write paths — EP-1, EP-3, EP-6, EP-7, EP-9, EP-10** *(EP-2 is the supervisor that spawns EP-1/EP-3; it adds no independent write capability, so it is counted with them, not as a seventh)*. Plus **3 read-only (EP-4, EP-5, EP-11)**, **2 test-only (EP-12, EP-13)**, and ### **1 misclassified-until-this-recon (EP-8 — read-only by convention, actuator-capable by import).**

## Cutover strategies *(one per capability)*
| Capability | Old path | New path | ### Mutual-exclusion mechanism | Trigger | Rollback | Old code deleted | Required before enable | Brake posture |
|---|---|---|---|---|---|---|---|---|
| **TMS invoice write** | EP-1/3/6/7/9 | pipeline → A4-4 | ### **the SHARED Effect Grant Ledger: `UNIQUE(tenant, commit_key) WHERE state='CLAIMED'` — one row can be claimed, by anyone** | P12 | disable the capability flag ⇒ back to human-executed | ### **at P12, physically** | `AC-SAFE-001..014`, `AC-ADPT-*`, `AC-WF8-*` | armed |
| **TMS payable write** | EP-1/9 | pipeline → A4-5 | shared ledger | P12+ | as above | P12 | + `AC-WF9-*` | armed |
| **Document file** | EP-1 | pipeline → A4-7/A11-3 | shared ledger (occ = digest) | P12 | as above | P12 | `AC-SAFE-013`, `AC-WF6-*` | armed |
| **Terminal direct writes** | ### **EP-6,7,9,10** | ### **none — these do not survive** | ### **REMOVE_BEFORE_ENABLE: the code is DELETED before the pipeline write is enabled** | P4 | ### **rollback does NOT restore them** | ### **P4** | `AC-SEC-013` (import gate ON) | n/a |
| **Actuator import in a "read-only" script** | EP-8 | read-only client | ### **the import is removed; the CI gate then makes it unrepeatable** | P4 | — | P4 | `AC-ADPT-002` | n/a |
| **Mock ledger paths** | EP-12,13 | test-scoped only | the existing `test_no_mock_effect_in_production` guard | already | — | — | (already green) | n/a |

> ### **"No one should call the old path" is NOT a mutual-exclusion mechanism.** The only two accepted here are: **(1) the shared ledger's unique index** (during any coexistence) and **(2) physical deletion** (for EP-6,7,9,10). ### **Interim, until P4: the runbook's one-writer-at-a-time discipline — which is operator discipline, NOT a mechanism, and is recorded as such.**
