# Neyma — Current-State Reconciliation

**Status:** Reconciliation only. This is NOT the target architecture, NOT a specification, NOT an implementation plan. No solutions are proposed here.
**Revision:** 2 (supersedes `docs/RECONCILIATION_REPORT.md`, which is removed)
**Date:** 2026-07-09 · **Branch:** `demos` · **Purpose:** architectural reset prior to Phase 1 freeze.

---

## 0. METHOD & EPISTEMIC STATUS

### 0.1 Evidence label legend (applied to every major finding)

| Label | Meaning |
|---|---|
| `REPO_CONFIRMED` | Directly verified by inspecting code, schema, routes, or the process tree in this repository. |
| `DESIGN_PARTNER_OBSERVED` | Observed **by Rasheed** during the design-partner visit and relayed to me. **I observed nothing myself.** |
| `CONVERSATION_REPORTED` | Stated by Rasheed in conversation history (including the freight-labor description he pasted). Not independently verified. |
| `INFERRED` | My reasoning from the above. Plausible, not evidenced. Treat as a hypothesis. |
| `NEEDS_VALIDATION` | Unknown. Cannot be established from the repository, the conversation, or the relayed observations. |

### 0.2 The controlling caveat

> **I did not observe the design partner. Rasheed did.**
> My only knowledge of their real operation is (a) the **list of systems** he reported and (b) the **general freight-labor description** he pasted. I have **no observed workflow, no volumes, no roles, no exception rates, no tooling specifics, no document samples**.

Accordingly, `DESIGN_PARTNER_OBSERVED` is used **sparingly and only** where Rasheed explicitly reported an observation. Everything that would require field knowledge I do not have is marked `NEEDS_VALIDATION` rather than asserted. This report prefers 30 explicit unknowns to one confident fabrication.

---

## 0.3 ⛔ BLOCKING ISSUE — REPOSITORY HYGIENE (must be resolved before any migration planning)

`REPO_CONFIRMED`

**This is an implementation-blocking defect, not a housekeeping note.** No migration plan, no target architecture, and no Phase 1 freeze should proceed until it is cleared.

| Condition | Detail |
|---|---|
| **Uncommitted working tree** | Branch `demos` carries **uncommitted changes**, including this session's Phase 0 document-upload work and six dogfood defect fixes across `action_callback.py`, `operation_router.py`, `operator_agent.py`, `cdp_session.py`, `cdp_actuator.py`, `ar_collections.py`, `run_action_callback_server.py`. |
| **Mixed authorship in the tree** | The tree **already contained uncommitted changes not authored by this session** (in `cdp_session.py`, `run_action_callback_server.py`, and several test files). These were deliberately **not** committed to avoid bundling unknown work. **Provenance is unresolved.** |
| **Dead code committed to the live module** | `render_exception_radar` and `_is_radar_query` are **defined but never wired** into `route_conversational_message` in `action_callback.py`. |
| **Consequence** | There is **no clean, known-good baseline** to migrate *from*. Any classification (KEEP/MODIFY/DEPRECATE/REMOVE) made against an indeterminate tree is unreliable. A rewrite that forks from an unreconciled working tree will inherit unattributed changes silently. |

**Required before migration planning:** establish a committed, reviewed, test-green baseline commit; attribute or discard the pre-existing uncommitted changes; remove or wire the dead code. `NEEDS_VALIDATION`: what the pre-existing uncommitted changes were, and whether they should be kept.

---

## PART 1 — CURRENT STATE AUDIT

### 1.0 CENTRAL STRUCTURAL FINDING: the repository contains two systems, not one

`REPO_CONFIRMED`

A static import trace from the **actually-supervised process tree** (`run_teammate.py` spawns exactly three children: `run_action_callback_server.py`, `run_gmail_to_slack_loop.py`, `propose_ar_from_tms.py`) yields:

- **42 of 74** modules in `src/freight_recon` are reachable from the live stack.
- **32 of 74** modules are **not** statically reachable from the live stack.

The 32 are **not dead code** — they are reachable from **standalone scripts** (`run_ingestion.py`, `run_extraction.py`, `run_reconciliation.py`, `run_mailbox_intake.py`, `run_mailbox_workflow.py`, `run_review.py`). Two distinct lineages exist:

> **Lineage A — Document Reconciliation Pipeline** (batch, script-driven, **not** in the live teammate)
> `imap_mailbox → ingestion → render → extraction → document_identifier → models → reconciliation → review → delivery/email_adapter → review_actions`
> Shape: a document arrives → extracted with confidence scores → reconciled against an agreed rate → a human reviews via an emailed signed link / packet page.

> **Lineage B — Live Conversational TMS Operator** (what actually runs today)
> `action_callback (Slack) → nl_command/slack_delegate → operation_router (8 lanes) → operator_agent → cdp_actuator → cdp_session → live Chrome → TruckingOffice`
> plus `ar_collections`, `operation_proposal`, `lane_graduation`, `agent_memory`, `ops_control`.
> Shape: an owner speaks in Slack → a bounded goal is handed to a model-in-the-loop agent driving a real browser → gated by approval → verified by readback.

They share only `workflow.py` (state + audit) and `reconciliation.py`. **They were built in different eras, encode different assumptions, and were never unified.** `INFERRED`: this split is the root cause of the recurring "why does this feel duplicated?" experience.

`NEEDS_VALIDATION`: the trace is **static**. Some modules may be reached dynamically. Specifically, `extraction_bridge` is live-reachable while `extraction` is **not** — determine whether the live path performs real extraction or only bridges pre-extracted fixtures.

---

### 1.1 SUBSYSTEM INVENTORY & CLASSIFICATION

Legend: **KEEP** · **MODIFY** · **DEPRECATE** · **REMOVE** · **UNKNOWN**

---

#### A. WORKFLOW CORE / STATE MACHINE — **MODIFY**
`workflow.py` (902 L), `workflow_direction.py` · `REPO_CONFIRMED`

- **What it does:** Deterministic state machine with an explicit transition table, audit-event log, idempotency/commit-once, security-event log. States: `RECEIVED → EXTRACTED → RECONCILED → {NEEDS_REVIEW, READY_FOR_ENTRY, DONE} → APPROVED/DISPUTED/REQUESTED_BACKUP → READY_FOR_ENTRY → ENTERING → ENTERED → DONE|FAILED`, plus `WAITING_FOR_SESSION`. `workflow_direction` has exactly two values: `CARRIER_PAYABLE (AP)` and `CUSTOMER_INVOICE (AR)`.
- **Why it exists:** To make money-touching work auditable, replayable, and non-duplicating.
- **Alignment:** The **discipline** (explicit states, allowed transitions, audit, idempotency) is correct and should survive. The **shape** is document-and-money-specific.
- **Assumptions:** (1) the unit of work is a **document that becomes one financial record**; (2) work has exactly **two directions**; (3) the lifecycle **ends at "entered into the TMS."**
- **Debt:** `INFERRED` — this state machine has no representation for work that is not a money-document flow (a quote, a negotiation, a tracking exception, an appointment, a claim, a carrier onboarding). Whether those flows belong in the same state machine is **`NEEDS_VALIDATION`** (that is a design question, deliberately not answered here).

---

#### B. PERSISTENT DATA MODEL — **MODIFY** *(most consequential finding)*
SQLite: `workflow_runs`, `audit_events`, `security_events` · `REPO_CONFIRMED`

Verbatim schema:
```
workflow_runs:   id, load_id, document_hash, state, invoice_number, carrier, outcome, reason, created_at, updated_at
audit_events:    id, run_id, event_type, actor, from_state, to_state, payload_json, created_at
security_events: id, event_type, actor, payload_json, created_at
```

**Finding (`REPO_CONFIRMED`):** the only persistent domain object is a **workflow run keyed by `(load_id, document_hash)`** — i.e. *"a document we processed."* There is **no Customer, Carrier, Load/Shipment, Quote, Bid, Driver, Appointment, Communication, Document, Exception, or rate-history entity.** `carrier` and `invoice_number` are **denormalized strings on the run**, not entities.

**Consequence (`REPO_CONFIRMED`):** Neyma cannot answer "what do we know about this carrier?", "what did we quote this lane before?", "what have we said to this customer?", "which loads are in transit?" except by **re-reading an external system live through a browser on every request**. There is no retained state — only a run log.

**Implication — stated precisely, per correction (1):**

> `INFERRED` + `NEEDS_VALIDATION` — An operational teammate that spans email, portals, SMS, load boards, a TMS, and accounting **likely requires a persistent cross-system operational model** in order to correlate artifacts and events across those systems at all.
>
> **However, the *authority relationship* between Neyma, the TMS, and external systems remains `NEEDS_VALIDATION`.** This report makes **no claim** that Neyma must become the authoritative source of truth, nor that it must not. Whether Neyma's persistent model is (a) a derived correlation/index over externally-authoritative systems, (b) authoritative for some domains and derived for others, or (c) authoritative broadly, is an **open architectural and product question** that requires validation and is explicitly **out of scope for this reconciliation.**

---

#### C. DOCUMENT EXTRACTION PIPELINE — **KEEP** (currently **not** in the live path)
`render.py`, `extraction.py`, `models.py`, `document_identifier.py`, `extraction_bridge.py` · `REPO_CONFIRMED`

- Template-free, vision-based extraction with per-field confidence.
- **Alignment:** `INFERRED` — strongly aligned; freight documents are non-uniform and rigid templates fail (`CONVERSATION_REPORTED`).
- **Status:** **Not reachable from the live teammate**; script-invoked (`run_extraction.py`).
- `NEEDS_VALIDATION`: measured field-level accuracy and confidence calibration on **real partner documents**. Never measured.

---

#### D. RECONCILIATION ENGINE — **KEEP**
`reconciliation.py` · `REPO_CONFIRMED`

- Deterministic comparison of a carrier invoice against an agreed rate: `agreed_rate_total`, accessorial normalization, amount deltas, duplicate-invoice detection, `requires_backup` / `has_backup`.
- **Evidence it functions (`REPO_CONFIRMED`, on seeded data only):** the live unresolved list surfaced unauthorized detention $300 not on the rate con; fuel $572 vs $447; linehaul $3,775 vs $3,575; missing lumper backup $175. **These were seeded invoices, not partner data.**
- **Limitation (`REPO_CONFIRMED`):** it reconciles **invoice ↔ rate-con only**. It has no representation of authorization that occurred **outside a document** (e.g. detention approved by phone or text). `NEEDS_VALIDATION`: how the partner actually authorizes accessorials in the moment, and where that authorization is recorded.

---

#### E. INBOUND INTAKE / MAILBOX — **MODIFY**
`imap_mailbox.py`, `ingestion.py`, `mailbox_intake.py`, `mailbox_workflow.py`, `inbox_brain.py`, `inbox_discovery.py`, `email_triage.py`, `email_corpus.py` · `REPO_CONFIRMED`

- Pulls mail (IMAP), classifies **attachments** into a fixed taxonomy (`carrier_invoice`, `rate_confirmation`, `pod`, `bol`, `manifest`, `lumper`, `fuel`, `unknown`), links them to a load, assembles a "packet," emits `unlinked_packet` when binding fails.
- **Assumptions (`REPO_CONFIRMED`):** an email's value is its **attachment**; there is **one** inbox and it is a **billing** inbox (`email_triage` docstring: "face a REAL billing inbox"); emails map to documents, documents map to loads.
- **Reality gap (`DESIGN_PARTNER_OBSERVED` — the shared-inbox observation is Rasheed's; `INFERRED` — the consequence):** the partner runs on a **shared inbox** carrying conversation, not only documents. This pipeline has no destination for an email with no attachment and no load.
- **Supporting evidence (`REPO_CONFIRMED`):** in the live unresolved list, **5 of 11 open items were `UNLINKED — inbound email could not be linked to a known load`.** `INFERRED`: this is the model failing at the front door, not an anomaly.
- **Status:** not reachable from the live teammate.

---

#### F. BROWSER ACTUATION — **KEEP (core) / MODIFY (framing)**
`cdp_session.py`, `cdp_actuator.py`, `browser_lock.py`, `browser_failures.py`, `browser_session_health.py`, `screen_discovery.py`, `screen_mapping.py`, `system_orientation.py`, `browser_learning.py`, `flow_recipe.py`, `agent_memory.py` · `REPO_CONFIRMED`

- Real hands on a live browser via CDP (click, type, select, read, **upload**, screenshot), page-failure taxonomy, settle-detection, unknown-screen discovery, crystallized replayable recipes.
- **Alignment:** `INFERRED` — the highest-value asset in the repository. It is, however, **named and framed** as "operate **a TMS**"; the reported operational graph contains many non-TMS web systems (`DESIGN_PARTNER_OBSERVED`).
- **Hard-coded assumptions (`REPO_CONFIRMED`):**
  - **One** browser, **one** Chrome, **one** logged-in session — `browser_lock` is a single global "browser busy" mutex.
  - `session_policy: human_established_session_only` — Neyma **never logs in** and stores **no credentials**.
  - `url_filter` pins the agent to **one domain** per run.
- **Debt (`REPO_CONFIRMED` + `INFERRED`):** a single global browser lock **serializes all work on one browser**. Concurrent observation of multiple systems is not possible under the present design.

---

#### G. AGENT / ORCHESTRATION LAYER — **MODIFY + consolidate**
`operator_agent.py` · `operation_router.py` · `operator_brain.py` · `brain_operator.py` · `brain_runtime.py` · `run_diagnostics.py` · `REPO_CONFIRMED`

- **`operator_agent` — KEEP (crown jewel).** Model-in-the-loop, one action per step, carrying the **safety spine**: money fence (model never chooses an amount), **document fence** (runtime supplies the file; model never names a path), consequential-action approval gate, **verify-by-readback**, **commit-once** (crash-safe), fail-closed escalation.
- **`operation_router` — MODIFY.** Maps a request to one of **8 bounded lanes** (`raise_invoice`, `record_payment`, `adjust_invoice`, `record_payable`, `file_document`, `create_load`, `update_status`, `check_call`), enforcing `requires_amount` / `requires_document` at the front door plus graduation policy. **Every lane is a TMS write** (`REPO_CONFIRMED`).
- **`operator_brain` / `brain_operator` / `brain_runtime` — UNKNOWN.** `operator_brain` is live-reachable; `brain_operator` and `brain_runtime` are **not**. Three overlapping orchestrator abstractions coexist. `NEEDS_VALIDATION`: **which is canonical?** Unresolved duplication.

---

#### H. HUMAN OVERSIGHT — **DEPRECATE (the duplicate implementation only)**
`REPO_CONFIRMED`

Two human-in-the-loop surfaces exist:
- **Surface 1 (legacy):** `review.py`, `review_actions.py`, `delivery.py`, `delivery_dispatch.py`, `email_adapter.py`, `packet_page.py`, `operator_console.py` — signed-link **emailed** review with static packet pages, and its **own approval-token scheme**.
- **Surface 2 (in use):** `action_callback.py` — Slack proposals with signed Approve buttons, conversational routing, in-thread resume, and a **different** approval-token scheme.

**Finding, stated precisely per correction (3):**
- **DEPRECATE the duplicate legacy *implementation* and its parallel approval-token system.** Two concurrent token schemes, two audit paths, and two renderers are a correctness and security liability (`INFERRED`).
- **This is NOT a finding that email should cease to be a human-approval channel.** Email may well remain a legitimate — possibly essential — approval and notification surface. **The future channel strategy (Slack, email, SMS, web, or several) is `NEEDS_VALIDATION`** and is deliberately not decided here.
- `NEEDS_VALIDATION`: does anything still depend on the legacy review surface today?

**Additional debt (`REPO_CONFIRMED`):** `action_callback.py` is a **1,983-line god-module** combining HTTP routing, signature verification, Slack payload parsing, proposal construction, approval verification, background execution, conversational routing, TMS readers, and Slack rendering. `INFERRED`: the worst structural debt in the live path.

---

#### I. SLACK / CHANNEL SURFACE — **KEEP (concept) / MODIFY (implementation)**
`slack_adapter.py`, `slack_delegate.py`, `nl_command.py`, `channels.py`, `alert_channel.py` · `REPO_CONFIRMED`

- **Assumption:** **one owner, one channel** (`allowed_slack_user`, `allowed_slack_channel`). No role model, no per-user authority, no team routing. `NEEDS_VALIDATION`: the partner's roles and who may approve what.

---

#### J. AR / COLLECTIONS — **KEEP**
`ar_collections.py`, `propose_ar_from_tms.py` · `REPO_CONFIRMED`
Aged receivables, terms-aware past-due, top debtors, ready-to-bill digest. Proven live. Fails closed on an unreadable page (a blind page must never render as "all paid").

---

#### K. KNOWLEDGE / TRIBAL KNOWLEDGE — **MODIFY**
`knowledge.py` · `REPO_CONFIRMED` (exists, live-reachable)
- Self-described as "the shared company knowledge base — Neyma's one memory that every surface reads and writes."
- `NEEDS_VALIDATION`: **its actual storage and retrieval model is unverified.** Flat fact list? Keyword lookup? Embedding index? Is it injected into agent prompts today, and how is token budget governed? Not established by this audit.

---

#### L. LANE GRADUATION / PERMISSIONS — **KEEP**
`lane_graduation.py`, `tool_permissions.py`, `ops_control.py` · `REPO_CONFIRMED`
Per-(tenant, lane) supervised→autonomous graduation with dollar/party/daily caps; workflow-state-gated tool permissions; an owner brake ("pause tms writes").

---

#### M. MOCK TMS INFRASTRUCTURE — **CORRECTED 2026-07-09**

> ## ⚠️ CORRECTION — the original classification of `tms_write.py` was **WRONG**
>
> **This section previously classified `tms_write.py` as mock infrastructure to be removed. That was incorrect.**
> **Deleting `tms_write.py` wholesale would have removed PRODUCTION SAFETY BEHAVIOUR.**
>
> Established by the repository baseline audit (finding **R-03**), `REPO_CONFIRMED`: `tms_write.py` **conflates three different concerns in one module**, and its name and docstring describe only one of them.
>
> | Concern | What it actually is | Correct disposition |
> |---|---|---|
> | **`enter_approved_payable`** + the write-driver contracts (`PayableWriteResult`, `PayableWriteStatus`, `ChargeLine`, `ExecutionStatusUpdate`, `approved_amount_for_run`) | **The production safety spine**: approved-amount binding, idempotency, the `APPROVED → … → DONE` state machine, and **verify-by-readback**. **`truckingoffice_write.py` "drops into `enter_approved_payable` unchanged" with a REAL ledger.** | **KEEP / EXTRACT** |
> | **`MockTmsWriteLedger`** and mock-only adapters | A **mock adapter behind a ledger port** | **TEST_ONLY** |
> | **The conflated module boundary and misleading naming** (*"Bounded TMS write path against the mock TMS (Stage 7)"*) | The module is **named for its mock** while **containing the production driver**. This is why it is live-reachable, why this reconciliation misread it, and why an implementer would misread it too. | **MODIFY** |
> | **Any production path that selects a mock ledger** | *(Found: `--auto-enter-approved-mock-tms`, enabled **by default** in the production supervisor, writing approved payables to a JSON file and reporting them complete.)* | **REMOVE IMMEDIATELY** *(done — see `test_no_mock_effect_in_production.py`)* |
>
> **The ledger is a port. Mock and TruckingOffice are two adapters. The defect is the module boundary, not the driver.**

**Remaining genuine mock infrastructure** (the original classification stands for these):
`mock_tms.py` (634 L), `mock_tms_write_server.py`, `tms_adapter.py` (mock read adapter), `read_mock_tms.py`, `generate_mock_tms.py` · `REPO_CONFIRMED`

**Finding, stated precisely per correction (2) — this is a two-part classification:**

1. **REMOVE from all production and live runtime paths.** `tms_write.py` is self-described as "bounded TMS write path against the **mock** TMS (Stage 7)" and is **still statically reachable from the live stack** (`REPO_CONFIRMED`). A mock write path reachable from a production runtime is **active risk** and must be severed regardless of what happens next.

2. **EVALUATE — do not blanket-delete.** Portions of this estate may have durable value as:
   - **Deterministic test fixtures** — a stable, offline TMS surface for repeatable tests without a live browser or a live account.
   - **Contract-test infrastructure** — asserting that an actuator/adapter honors an expected interaction contract.
   - **Failure-injection tooling** — deliberately producing hostile page states (stale DOM, partial render, session expiry, submit failure) to exercise the fail-closed, verify-by-readback, and commit-once guarantees, which cannot be reliably provoked against a live system.

   `NEEDS_VALIDATION`: **which specific portions** carry that value (a writable mock surface? the data generator? the adapter contract?) and which are pure scaffolding. That determination requires a test-strategy decision that is **out of scope for this reconciliation.**

---

#### N. PILOT / DOGFOOD INSTRUMENTATION — **DEPRECATE**
`pilot_session.py`, `summary.py`, `operator_console.py`, `packet_page.py`, `design_partner_package.py`, `first_design_partner.py`, `owner_onboarding.py`, `run_sunday_readiness.py` · `REPO_CONFIRMED`
Built to run and measure **an internal dogfood pilot for one person**.
`NEEDS_VALIDATION`: `roi_ledger.py`, `teammate_health.py`, `activity_log.py` — is owner-facing ROI/health reporting a **product requirement** or a **pilot artifact**? Not established.

---

#### O. CONFIG / TENANCY — **MODIFY**
`config.py` (**not live-reachable**), `configs/clients/*.yaml` · `REPO_CONFIRMED`
Config assumes **one** operator, **one** TMS, **one** review channel. **Single-tenant by construction**: one workspace directory, one Chrome, one Slack channel, one database.

---

#### P. SECOND-TMS EVIDENCE — **KEEP (as evidence)**
`transporters.io` (8 references) · `REPO_CONFIRMED` — evidence that discovery/actuation generalizes beyond TruckingOffice (n=2).

---

### 1.2 API SURFACE (complete) · `REPO_CONFIRMED`

```
POST /slack/actions     — Slack interactivity (signed)
POST /slack/commands    — Slash commands (signed)
POST /slack/events      — Slack events (signed)
POST /email/action      — legacy email-link action intake
POST /actions/signed    — legacy signed-action intake
```
**There is no domain API.** No `/loads`, `/carriers`, `/quotes`, `/documents`. `INFERRED`: nothing can integrate with Neyma except Slack and signed email links.

---

### 1.3 BACKGROUND WORKERS (complete) · `REPO_CONFIRMED`

`run_teammate.py` — a self-healing supervisor (crash counting, backoff, degraded-state reporting) spawning **exactly three children**:
1. `run_action_callback_server.py` (Slack/HTTP surface + operation router + heartbeat watchdog thread)
2. `run_gmail_to_slack_loop.py` (mail loop)
3. `propose_ar_from_tms.py` (periodic AR trigger)

Outside the supervisor: **ngrok** — required for Slack to reach the local server. `INFERRED`: not a production posture.

---

### 1.4 INTEGRATIONS · `REPO_CONFIRMED`

**Present:** OpenAI (45 refs), Anthropic (15), TruckingOffice via **CDP browser** (30), transporters.io (8), IMAP/SMTP, Slack API, ngrok.

**Absent** — every row below appears in the reported operational graph (`DESIGN_PARTNER_OBSERVED`):

| System in the operational graph | Integration status |
|---|---|
| Load boards (DAT, Truckstop) | **NONE** |
| Carrier portals | **NONE** |
| Appointment portals | **NONE** |
| Driver SMS / texting | **NONE** (no SMS transport at all) |
| Phone calls / voice transcripts | **NONE** |
| Accounting systems | **NONE** |
| Internal spreadsheets | **NONE** |
| Google Drive / file stores | **NONE** |
| Factoring | **NONE** (not even a concept) |
| FMCSA / carrier vetting | **NONE** |
| Shared Outlook inbox | **NONE** (IMAP/Gmail only) |
| Geo / ELD / tracking data | **NONE** |

**Neyma today integrates with exactly two things: a Slack workspace, and a browser pointed at one TMS.**

---

### 1.5 EMBEDDED ASSUMPTIONS

| # | Assumption | Where it is baked in | Evidence | Verdict |
|---|---|---|---|---|
| A1 | The unit of work is a **document** becoming **one financial record** | `workflow.py` | `REPO_CONFIRMED` | Misaligned with the reported graph (`INFERRED`) |
| A2 | Neyma holds **no domain state**; the TMS is the record | only `workflow_runs` persists | `REPO_CONFIRMED` | Insufficient for cross-system correlation (`INFERRED`); **authority model `NEEDS_VALIDATION`** |
| A3 | There is **one inbox**, and it is a **billing** inbox | `email_triage`, `ingestion` | `REPO_CONFIRMED` | Contradicted by the shared-inbox report (`DESIGN_PARTNER_OBSERVED`) |
| A4 | **One** browser / session / domain | `browser_lock`, `url_filter` | `REPO_CONFIRMED` | Blocks concurrent multi-system work (`INFERRED`) |
| A5 | All work is **AP or AR** | `workflow_direction` (2 values) | `REPO_CONFIRMED` | Incomplete (`INFERRED`) |
| A6 | **One human owner**, **one channel** | `allowed_slack_user/channel` | `REPO_CONFIRMED` | Role model `NEEDS_VALIDATION` |
| A7 | Every action is a **TMS write** | all 8 lanes | `REPO_CONFIRMED` | Incomplete (`INFERRED`) |
| A8 | **Loads already exist** in the TMS | readers scrape `/loads` | `REPO_CONFIRMED` | `NEEDS_VALIDATION` (how loads originate at the partner) |
| A9 | Documents **arrive**; they are not **chased** | intake is passive | `REPO_CONFIRMED` | Chasing reported as core work (`CONVERSATION_REPORTED`) |
| A10 | **Single tenant** | one workspace/Chrome/channel/DB | `REPO_CONFIRMED` | Blocks a multi-customer product (`INFERRED`) |
| A11 | An email's value is its **attachment** | `ingestion` | `REPO_CONFIRMED` | Contradicted by shared-inbox report (`DESIGN_PARTNER_OBSERVED`) |
| A12 | The job **ends at "entered into the TMS"** | `ENTERED → DONE` | `REPO_CONFIRMED` | `INFERRED`: the business job ends at money collected / exception closed |

---

### 1.6 SOURCES OF TRUTH — as they stand today · `REPO_CONFIRMED`

| Fact | Where truth lives today |
|---|---|
| Loads, statuses, customers, invoices, balances | **The TMS**, re-scraped live via browser on each read |
| Documents | TMS FileSafe (after filing) + local `workspace/documents/` |
| What Neyma did | `workflow_runs` + `audit_events` (SQLite) |
| Agreed rates | The rate-confirmation **document** |
| Company rules / tribal knowledge | `knowledge.py` (shape `NEEDS_VALIDATION`) |
| Autonomy policy | `lane_graduation.json` |
| Carriers, quotes, communications, appointments | **Nothing. Not tracked.** |

> Note per correction (1): this table describes **the present state**. It is **not** a claim about where truth *should* live. The target authority model is `NEEDS_VALIDATION`.

---

## PART 2 — DESIGN-PARTNER RECONCILIATION

### 2.1 What can and cannot be asserted

I can assert **what the repository assumes** (`REPO_CONFIRMED`). I can restate **the categories of systems Rasheed reported** (`DESIGN_PARTNER_OBSERVED`). I **cannot** assert what the partner actually does day to day — no observed workflow, volumes, roles, exception taxonomy, or tooling detail. Everything requiring that is `NEEDS_VALIDATION`.

### 2.2 Assumptions contradicted by the reported operational graph

1. **"The TMS is the center."** `REPO_CONFIRMED` (the entire actuation layer, all 8 lanes, both readers, and `url_filter` are TMS-shaped) vs. `DESIGN_PARTNER_OBSERVED` (the TMS is one node in a larger graph). **The framing is the defect.**
2. **"Work arrives as documents."** `REPO_CONFIRMED` (intake is a document pipeline) vs. `DESIGN_PARTNER_OBSERVED` (shared inbox carrying conversation). Supporting: **5 of 11** live unresolved items were unlinkable emails (`REPO_CONFIRMED`).
3. **"Work has two directions (AP/AR)."** `REPO_CONFIRMED` (`workflow_direction` has two enum values). `INFERRED`: quoting, covering, negotiating, appointment-setting, tracking, claims, and onboarding are none of them.
4. **"One human approves."** `REPO_CONFIRMED`. Partner role structure `NEEDS_VALIDATION`.
5. **"Neyma needs no state of its own."** `REPO_CONFIRMED`. `INFERRED`: cross-system correlation is impossible without persistent entities. **Authority model remains `NEEDS_VALIDATION`** (correction 1).

### 2.3 Incomplete assumptions

1. **The safety spine is money-scoped.** `REPO_CONFIRMED`: money fence, document fence, verify-by-readback, commit-once, fail-closed all exist. There is **no equivalent guard for outbound communication** (an email to a customer, a rate quoted to a carrier, an SMS to a driver). `follow_up.py` exists behind a send gate — `NEEDS_VALIDATION`: is it wired to anything live?
2. **Reconciliation reads one document.** `REPO_CONFIRMED`. Authorization occurring by phone/text is invisible to it. `NEEDS_VALIDATION`: how the partner authorizes accessorials in the moment.
3. **Identity resolution is narrow.** `REPO_CONFIRMED`: `ingestion` links attachments to loads. There is no general entity-resolution capability binding an arbitrary artifact (email, SMS, PDF, portal row, spreadsheet line) to the same work item across load #, order #, trip #, PRO, BOL #, customer reference, or carrier invoice #. `NEEDS_VALIDATION`: which identifiers the partner actually keys on.

### 2.4 Missing — entities, loops, state machines, integrations, concepts

**Missing persistent entities** (`REPO_CONFIRMED` absent): Customer, Shipper, Consignee, Carrier, Driver, the load-family concepts (see **Part 3.1** — deliberately **not** collapsed into one), Stop, Quote, Bid/Offer, rate/lane history, Document, Communication, Appointment, Exception, Claim, Invoice (AR), Payable (AP), Settlement, Insurance/Authority, User/Role.

**Missing loops** (`INFERRED` from `CONVERSATION_REPORTED` labor description): quote intake & pricing · load covering & carrier negotiation · carrier sourcing & vetting · appointment booking · track & trace / check calls · delay detection & customer notification · OS&D / claims · carrier onboarding & compliance · **outbound document chasing** · accounting/factoring sync · short-pay & dunning.

**Missing state machines** (`REPO_CONFIRMED` absent): any lifecycle that is not "document → financial record."

**Missing integrations:** the entire table in §1.4.

**Missing business concepts** (`REPO_CONFIRMED` absent from the repo; `CONVERSATION_REPORTED` as real): margin (buy vs sell rate) · lane pricing history · carrier scorecard · double-broker / fraud risk · accessorial **authorization** as distinct from **billing** · appointment windows · HOS/driver constraints · factoring status · credit limits.

**Missing auditability** (`REPO_CONFIRMED`): there is a strong log of **what Neyma did** and **no log of what Neyma said or was told** — no Communication entity. `INFERRED`: in a business run on email and text, that is the majority of the record.

**Missing ownership boundaries** (`REPO_CONFIRMED`): no role model, no per-user authority, no team routing, no multi-tenancy.

### 2.5 What does not belong in the next generation

**Sever from production immediately** (`REPO_CONFIRMED`):
- The **mock-TMS write path** (`tms_write.py`) is reachable from the live stack. Remove from all live runtime paths. **Retention as test/contract/failure-injection infrastructure is a separate, open question** — see §1.1(M).
- **ngrok** as any part of a production posture.

**Deprecate** (`REPO_CONFIRMED` + `INFERRED`):
- The **duplicate legacy email-review implementation and its parallel approval-token scheme**. *(Not a judgment on email as a channel — see §1.1(H) and correction 3.)*
- **Pilot instrumentation** (`pilot_session`, `summary`, `design_partner_package`, `first_design_partner`, `owner_onboarding`, `run_sunday_readiness`).
- **Orchestrator duplication** — two of {`operator_brain`, `brain_operator`, `brain_runtime`, `operation_router`} must go. `NEEDS_VALIDATION`: which is canonical.

**Framings that must not be carried forward** (`INFERRED`):
- "**A TMS agent**" — the framing itself encodes the wrong center.
- "**The document is the unit of work.**"
- "**One owner, one channel, one browser, one tenant.**"
- "**The workflow ends when the TMS row is written.**"

**Assets that should be carried forward** (`REPO_CONFIRMED` they exist; `INFERRED` they are valuable):
- The **safety spine** — money fence, document fence, approve-to-act, verify-by-readback, commit-once, fail-closed, and the injection boundary (**inbound content is data, never instructions**).
- The **CDP actuation core** (real hands on a web system, including file upload).
- The **deterministic reconciliation engine**.
- The **template-free, confidence-scored extraction stack**.
- The **explicit state-machine + audit + idempotency discipline**.
- The **lane graduation / autonomy-cap model**.
- The **live-dogfood method** (drive it as the owner; every miss is a defect).

---

## PART 3 — DOMAIN MODEL (the business, not the software)

> Grounding: `CONVERSATION_REPORTED` (the freight-labor description), `DESIGN_PARTNER_OBSERVED` (the systems list), and entities implied by the repo. **No implementation. No proposed schema.**

### 3.1 ⚠️ The "load" family — six potentially distinct concepts, NOT one

Per correction (4), this report **explicitly refuses to collapse "Shipment" and "Load" into a single concept.** The following are listed as **candidate distinct concepts requiring validation**, not as a proposed model:

| Candidate concept | Working description | Evidence |
|---|---|---|
| **Customer shipment / order** | What the customer believes they are buying — their order, with their own reference number. May span multiple movements. | `NEEDS_VALIDATION` |
| **Brokerage load** | The unit the brokerage sells, prices, and books margin on. May or may not be 1:1 with the customer's order. | `NEEDS_VALIDATION` |
| **Carrier movement** | The unit a carrier agrees to haul and invoices against. May differ from the brokerage load (e.g. a re-brokered or partial movement). | `NEEDS_VALIDATION` |
| **Load leg** | A segment of a movement (e.g. drayage → linehaul → delivery), each potentially with its own carrier and rate. | `NEEDS_VALIDATION` |
| **Stop** | An individual pickup or delivery event, with its own appointment, window, and paperwork. | `NEEDS_VALIDATION` |
| **TMS load record** | Whatever row the TMS happens to store. **A system artifact, not a business concept**, and not necessarily aligned with any of the above. | `REPO_CONFIRMED` (the repo treats this as the load) |

**Finding (`REPO_CONFIRMED`):** the current system recognizes **only the last one** — a TMS load record, referenced by `load_id` — and implicitly assumes it is the same thing as all the others. **Whether these are distinct at the partner, and how they relate (1:1, 1:N, N:M), is `NEEDS_VALIDATION` and is the single most important modeling question to resolve before any schema is designed.**

### 3.2 External actors

**Customer / Shipper** — has freight to move; tenders it; approves billing. *Outputs:* quote requests, tenders, appointment constraints, payment. *Inputs:* quotes, status, invoices, PODs. `NEEDS_VALIDATION`: how tenders arrive at the partner (email / EDI / portal / phone).

**Consignee / Receiver** — accepts the freight. *Outputs:* signed BOL/POD, OS&D notations, dock appointments, lumper demands. `INFERRED`: the consignee is the origin of the document needed to bill, yet is rarely reachable by the broker. `NEEDS_VALIDATION`: how the partner actually obtains PODs.

**Carrier** — moves the load. *Outputs:* counter-offers, dispatch confirmation, check-call updates, invoices with backup, POD. *Risks:* fraud / double-brokering (`CONVERSATION_REPORTED`). `NEEDS_VALIDATION`: the partner's carrier mix (regular vs spot).

**Driver** — physically executes. *Outputs:* status via **SMS/phone**, photos of BOL/POD, exception reports (breakdown, HOS, detention). `INFERRED`: the driver is a **human, text-based endpoint**, not a system — a channel Neyma has **zero** integration with (`REPO_CONFIRMED`).

**Broker staff** (dispatcher / ops / controller / owner) — the humans Neyma augments, with distinct authorities. `NEEDS_VALIDATION`: the partner's roles, headcount, and approval rights.

**Factoring company** — buys receivables. `NEEDS_VALIDATION`: does the partner factor at all?

### 3.3 System actors (nodes in the operational graph)

`DESIGN_PARTNER_OBSERVED` (the list) · `INFERRED` (the characterizations)

- **TMS** — holds load/invoice/payable records today. **Not** the record for quotes, communications, or appointments.
- **Shared email inbox** — the true front door; carries both documents and conversation.
- **SMS / phone** — the carrier/driver channel. Unstructured, high-signal, **currently invisible** to Neyma.
- **Load boards (DAT / Truckstop)** — capacity discovery and rate benchmarking.
- **Carrier portals** — status/tracking, sometimes documents.
- **Appointment portals** — dock scheduling; a hard gate on delivery.
- **Accounting** — where money actually settles.
- **Spreadsheets** — the shadow system holding whatever the TMS cannot. `NEEDS_VALIDATION`: **what the partner keeps in spreadsheets and why.** `INFERRED`: **this is the highest-value unknown in the report** — a business's real model tends to live in its spreadsheets.
- **FMCSA / vetting sources** — carrier legitimacy, insurance, authority.
- **Tribal knowledge (human memory)** — the rules no system holds.

---

## PART 4 — SYSTEM BOUNDARIES

*(A reconciliation of what is true today and what the reported graph implies. **No target design.**)*

### 4.1 Corrected statement on Neyma's state and authority (per correction 1)

> `INFERRED` + `NEEDS_VALIDATION`
>
> **Neyma likely requires a persistent cross-system operational model** — some retained structure that can correlate artifacts, parties, work items, and actions observed across email, SMS, portals, load boards, the TMS, and accounting. Without it, cross-system correlation is not possible (`REPO_CONFIRMED`: today, no such structure exists).
>
> **The authority relationship between Neyma, the TMS, and external systems remains `NEEDS_VALIDATION`.** This report does **not** claim Neyma must be the authoritative source of truth. Whether Neyma's model is a **derived index** over externally-authoritative systems, **authoritative for some domains only**, or **authoritative more broadly**, is an open product and architecture question and is **out of scope here.**

### 4.2 What Neyma OBSERVES today (`REPO_CONFIRMED`)
The TMS (via browser scrape) and an email inbox. **Nothing else.**

### 4.3 What Neyma ACTS UPON today (`REPO_CONFIRMED`)
TMS writes via 8 bounded lanes, and Slack messages. **Nothing else.** No outbound email, SMS, or portal action is in the live path (`follow_up.py` exists; wiring `NEEDS_VALIDATION`).

### 4.4 Systems whose authority is externally held (present state, `REPO_CONFIRMED`)

| Domain | Where authority sits today | Should Neyma's relationship change? |
|---|---|---|
| Email / SMS conversation record | The mail/SMS provider | `NEEDS_VALIDATION` |
| Loads, invoices, payables of record | The TMS | `NEEDS_VALIDATION` |
| Money actually settled | Accounting / bank | `NEEDS_VALIDATION` |
| Carrier authority & insurance | FMCSA / insurer | `NEEDS_VALIDATION` |
| Dock appointments | The facility's portal | `NEEDS_VALIDATION` |
| The signed POD | The physical document / consignee | `NEEDS_VALIDATION` |
| Credentials / sessions | The human (`human_established_session_only`) | `NEEDS_VALIDATION` — see below |

### 4.5 Unresolved boundary tension (flagged, not solved)

`REPO_CONFIRMED` — the current design **stores no credentials and never logs in**. That is a strong safety property. `INFERRED` — it also makes a 24/7 unattended, multi-system teammate impossible. **This is a product decision for Rasheed, not an implementation detail.** `NEEDS_VALIDATION`.

---

## PART 5 — OPEN QUESTIONS (`NEEDS_VALIDATION`)

### 5.0 Blocking (must clear before migration planning)
1. **Repository hygiene** — see §0.3. Uncommitted tree, unattributed pre-existing changes, dead code in a live module. **No clean baseline exists to migrate from.**

### 5.1 About the design partner (zero observed data on my side)
2. Actual daily **volumes** (loads/day, emails/day, quotes/day, carrier invoices/week)?
3. **Roles, headcount**, and who may approve money / send to a customer?
4. **What is in their spreadsheets, and why isn't it in the TMS?** *(Highest-value unknown.)*
5. How do loads **enter** the business — email tender, EDI, portal, phone?
6. **How is pricing decided** — gut, history, load board, rule? What is the quote→win rate?
7. How are **carriers sourced** — regular list vs load board vs network?
8. How are **counter-offers** negotiated, and **where is the agreed rate recorded** before the rate con?
9. How do **PODs actually arrive** — carrier email, driver text photo, portal?
10. What **share of carrier invoices** carry a discrepancy, and what happens today?
11. How are **detention/lumper/accessorials authorized in the moment**, and where is that authorization recorded?
12. Which **appointment portals**, and how often does an appointment fail?
13. Do they **factor**? What **accounting system**? How does data reach it today?
14. What is their **actual TMS** (TruckingOffice was our test rig — is it theirs)?
15. Top **three pains, in their words**. And: what would they **never** let software do unattended?
16. **The load-family question (§3.1):** are customer order, brokerage load, carrier movement, leg, stop, and TMS record distinct at this partner — and how do they relate?

### 5.2 About the repository
17. Is the **legacy email/packet review surface** still used by anything?
18. Which orchestrator is **canonical** — `operation_router`, `operator_brain`, or `brain_operator`?
19. **Why is `tms_write.py` (mock write path) reachable from the live stack**, and what breaks if it is severed?
20. Which portions of the **mock-TMS estate** have durable value as test fixtures / contract tests / failure-injection tooling (§1.1 M)?
21. What is `knowledge.py`'s **actual retrieval model**, and is it injected into prompts today?
22. Does the **live** teammate ever run **extraction**, or only file pre-supplied files?
23. Is `follow_up.py` (gated outbound draft) wired to anything live?
24. **Measured accuracy** of extraction and of load-linking on partner-like documents — never established.

### 5.3 Product decisions (Rasheed's, not mine)
25. **Credentials:** is `human_established_session_only` permanent? *(Blocks unattended multi-system operation.)*
26. **Authority model:** what is Neyma authoritative for, if anything? *(See §4.1 — this is the central open question.)*
27. **Multi-tenancy:** one partner, or a platform — and by when?
28. **Channel strategy:** Slack only, or email/SMS/web as first-class approval channels? *(See §1.1 H.)*
29. **Autonomy ceiling:** what may Neyma *never* do without a human, permanently?
30. **Outbound comms:** will Neyma ever send to a customer/carrier without approval, and under what rule?
31. Is the product **the whole back office**, or does the partner visit narrow the scope?

---

## SUMMARY

`REPO_CONFIRMED` — Neyma today is **a Slack-commanded browser agent that operates one TMS**, carrying an unusually strong safety spine and **no persistent domain model**, alongside **a second, parallel, script-driven document-reconciliation pipeline that is not part of the live system**.

The assets worth carrying forward are the safety spine, the CDP actuation core, the deterministic reconciliation engine, the template-free extraction stack, the state/audit/idempotency discipline, and the lane-graduation model.

The framings that must not survive are *TMS-as-center*, *document-as-unit-of-work*, and *one owner / one browser / one tenant*. The mock-TMS estate must leave the production runtime, though parts may earn a second life as test and failure-injection infrastructure (`NEEDS_VALIDATION`). The duplicate legacy review implementation and its parallel token scheme should go — **which says nothing about whether email remains a human-approval channel** (`NEEDS_VALIDATION`).

`INFERRED` — the largest gap is not a missing feature. It is that **Neyma has no persistent model of the business it is meant to run**, and integrates with **two** of the systems the work actually flows through. Whether that model should be **authoritative**, **derived**, or **mixed** is the central unanswered question, and it is **`NEEDS_VALIDATION`** — not something this reconciliation is entitled to decide.

**Nothing in this document constitutes a target architecture. No entities, workflows, or solutions are proposed.**
