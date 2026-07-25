# Live-Effect Entry Point Inventory

**Purpose:** precise inventory of every entry point that can reach the **live** TMS (review finding **F-07** / audit **R-02**).
**Constraint honoured:** **no entry point was altered**, except the approved D2 mock-path removal.
**Date:** 2026-07-09

> **F-07 was written as a *migration* risk. It is not. It is a present one.** These entry points exist today, share no commit-key namespace, and **two of them can bill the same load from a terminal.**

---

## 1. THE INVENTORY

| # | File / command | R/W | Exact effects it can produce | Through the safety spine? | Idempotency | Approval | Can conflict? | Used for | Disposition |
|---|---|---|---|---|---|---|---|---|---|
| **1** | `run_action_callback_server.py` | **WRITE** | Slack-approved operation → `OperationRouter` → `OperatorAgent` → **live TMS write** (invoice, payment, adjustment, payable, document file, status, load) | ✅ **Yes** — money fence, document fence, consequential gate, verify-by-readback, commit-once | **Commit key** (`_commit_identity`, `WorkflowStore`) | **Slack signed Approve button**, per-action, channel+user allowlisted | ✅ **Yes — with 2, 3, 6, 7, 9, 10** | **PRODUCTION** | **ROUTE_THROUGH_SPINE** *(already is; becomes the canonical pipeline under ADR-004)* |
| **2** | `run_teammate.py` | **WRITE** *(supervises #1, #3)* | Everything #1 and #3 can do. Spawns them. | ✅ Inherits | Inherits | Inherits | ✅ Yes | **PRODUCTION** | **KEEP** *(the supervisor; but see §3 — it passed the mock flag by default until this pass)* |
| **3** | `propose_ar_from_tms.py` | **WRITE** *(via proposal → approval)* | Reads live `/loads`; posts ready-to-bill digest → on Approve, a **live customer invoice** | ✅ Yes — amount is TMS-derived (deterministic), fenced | Commit key | Slack Approve / **[Approve all N]** batch token | ✅ **Yes — with 1, 6, 7** | **PRODUCTION** | **ROUTE_THROUGH_SPINE** |
| **4** | `drive_real_tms.py` | **READ-ONLY** | *"Capture READ-ONLY observations from a human-established session."* No write path. | n/a | n/a | n/a | ❌ No | Manual ops / discovery | **MAKE_READ_ONLY** *(assert it; today it is read-only by convention, not by construction)* |
| **5** | `discover_tms_screen.py` | **READ-ONLY** | Points the discovery agent at a form to build a screen map. Does not submit. | n/a | n/a | n/a | ❌ No | Manual ops / onboarding | **MAKE_READ_ONLY** |
| **6** | `enter_truckingoffice_invoice.py` | **WRITE** ⚠️ | *"Drive ONE approved run through the gated spine into a **REAL** TruckingOffice invoice."* **A direct, live financial write from a terminal.** | ✅ Yes — drops into `enter_approved_payable` (the gated driver) with a **real** ledger | Commit key via `WorkflowStore` | **A pre-existing APPROVED run** — *not* an interactive approval. **Whoever runs the script supplies the authority.** | ✅ **Yes — with 1, 3, 7** | Manual ops / the original live-write proof | **ROUTE_THROUGH_SPINE** or **REMOVE** — ⚠️ *see §2* |
| **7** | `enter_invoice_discovered.py` | **WRITE** ⚠️ | Gated invoice write driven by a discovered screen map → live TMS | ✅ Yes — same gated driver | Commit key | Same as #6 (pre-approved run) | ✅ **Yes — with 1, 3, 6** | Manual ops / generalization proof | **ROUTE_THROUGH_SPINE** or **REMOVE** |
| **8** | `orient_tms.py` | **READ-ONLY** | *"First day"* exploration of a TMS. | n/a | n/a | n/a | ❌ No | Onboarding | **MAKE_READ_ONLY** |
| **9** | `run_operate_request.py` | **WRITE** ⚠️ | *"The full Version-B loop, live"* — a natural-language request → router → agent → **live TMS write** | ✅ Yes | Commit key | **Local approval callback** — *not* Slack. **A terminal user is the approver.** | ✅ **Yes — with 1, 3** | Manual ops / dev driving | **ROUTE_THROUGH_SPINE** |
| **10** | `run_operator_agent.py` | **WRITE** ⚠️ | *"Let the embedded Operator Agent drive a live TMS on its own."* | ⚠️ **Partial** — money fence + gate exist, but this is the **rawest** path: an agent pointed at a live TMS with a local approver | Agent-level commit-once only | **Local approve callback** | ✅ **Yes — with 1** | Dev / debugging | **TEST_ONLY** or **REMOVE** — ⚠️ *the least-gated live-write path in the repo* |
| **11** | `verify_owner_onboarding.py` | **READ-ONLY** | Readiness checks. | n/a | n/a | n/a | ❌ No | Ops verification | **KEEP** |

### Mock-only writers *(not live — listed for completeness, they are **not** in the 11)*
`enter_tms_payable.py` · `run_dogfood_pilot.py` — write to `MockTmsWriteLedger`. **TEST_ONLY.**

---

## 2. THE CONFLICT SURFACE — stated plainly

**Six entry points can produce a live financial write: #1, #3, #6, #7, #9, #10.**

They share `WorkflowStore` commit keys **only when they operate on the same run id**. They do **not** share a reservation on a *business entity*. Therefore:

> **Nothing prevents `propose_ar_from_tms` (#3) from billing load 4471 while an operator runs `enter_truckingoffice_invoice` (#6) for the same load from a terminal.** Both pass their gates. Both are audited. **Each is invisible to the other. The customer gets two invoices.**

This is **exactly F-10** (no entity-level concurrency control) and **exactly F-07** (multiple runtimes, one effect) — **already real, with no migration required.**

**#10 (`run_operator_agent.py`) is the sharpest edge:** an agent pointed at a live TMS, gated only by a local terminal approver. It is a development tool that **retains full production effect capability.**

---

## 3. WHAT THIS PASS CHANGED (D2 only)

**Before:** `run_teammate.py` set `auto_enter_mock_tms: bool = True` and appended `--auto-enter-approved-mock-tms` to the callback command. **`run_client1.sh` — the documented production launch — did not disable it.**

**So the production supervisor ran with the mock financial path ENABLED BY DEFAULT**, and a human-approved payable would be written to a **JSON file**, driven to an externally-completed state, and reported to the owner as entered.

**Removed in this pass.** No entry point can now select a mock financial adapter. See `test_no_mock_effect_in_production.py`.

---

## 4. RECOMMENDED DISPOSITION — **NOT EXECUTED** (per instruction)

| Disposition | Entry points |
|---|---|
| **KEEP** | 2, 11 |
| **ROUTE_THROUGH_SPINE** *(become clients of the ADR-004 Action Pipeline; the Effect Grant is the shared mutual-exclusion namespace)* | 1, 3, 6, 7, 9 |
| **MAKE_READ_ONLY** *(enforce structurally, not by convention)* | 4, 5, 8 |
| **TEST_ONLY / REMOVE** | 10 |

> **Under ADR-004 this problem solves itself and does not need a refactor decision:** an adapter refuses to act without a claimed Effect Grant, and only the Action Pipeline can mint one. **Entry points #6, #7, #9, #10 simply stop working until they are refactored into pipeline clients — which is the correct and desirable outcome.**
>
> **Recommendation: do not refactor these by hand now.** Let ADR-004's capability boundary retire them. **The interim risk is operational discipline: do not run #6, #7, #9, or #10 against a live TMS while #1/#2 are running.**
