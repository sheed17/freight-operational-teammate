# Neyma Product Roadmap: Stage 0 To Live Deployment

This roadmap keeps the big agentic vision grounded in shippable stages. A prompt will not get
Neyma to production by itself. Each stage has a concrete output, exit gate, and verification
path.

Neyma's strategic product shape:

```text
Ventus-like existing-system operation
+
Pallet-like logistics workflow execution
+
SMB freight/logistics focus
```

The first production motion should prove this blend on one design partner and one narrow
workflow before expanding into the broader teammate family.

## Stage 0 — Workflow Discovery And Design Partner Proof

**Goal:** Prove the workflow is painful, frequent, and valuable before deep buildout.

Build or collect:

- 5-10 discovery calls with freight brokers/logistics teams.
- One mapped workflow per team: inputs, systems, handoffs, exceptions, and current time cost.
- Example documents with permission.
- A target ROI model for carrier invoice reconciliation.

Exit gate:

- At least one design partner agrees to provide sample docs and review results.
- The first workflow has measurable value: recovered margin, reduced payables time, faster
  billing, or fewer disputes.

Verification:

- Documented SOP.
- Sample document set.
- Written approval to use docs for testing/configuration.

Use [Design Partner Pilot Playbook](DESIGN_PARTNER_PILOT.md) for the first partner intake,
data request, pilot scope, and deployment readiness checklist.
Use [When Design Partner Data Arrives](WHEN_DESIGN_PARTNER_DATA_ARRIVES.md) once the partner
provides real docs and workflow details.
Use [Build Supervision Protocol](BUILD_SUPERVISION_PROTOCOL.md) for implementation/review flow
so every build slice is checked by a principal-architect lens before being called done.
Use [Owner-Operator Readiness](OWNER_OPERATOR_READINESS.md) so every build slice is also judged
against whether it would help a real freight owner/controller in supervised daily operations.
Use [Synthetic Freight Corpus](SYNTHETIC_CORPUS.md) when real partner documents are unavailable;
the goal is realistic public-template structure plus fully synthetic data and hidden truth.
Use [Internal Dogfood Pilot](INTERNAL_DOGFOOD_PILOT.md) before any real design-partner
deployment; Rasheed should act as the first simulated client and run Neyma as if he owns a
small freight company.

## Stage 0.5 — Internal Dogfood Pilot

**Goal:** Prove the client experience before installing Neyma for anyone else.

Rasheed acts as the first client: controller/payables reviewer for a fictional freight company
with realistic invoice volume, fake carriers, fake TMS/load data, and synthetic document packets.

Build:

- Review Payload V2 with evidence links, packet detail URL, unambiguous money actions, aging
  metadata, severity routing, and found-money fields.
- Minimal packet detail page for evidence, edit, reconciliation math, documents, and history.
- Review action intake.
- Draft dispute/request-backup emails behind a send gate.
- Daily summary with clean-match trust ramp, oldest/largest unresolved exceptions, and
  month-to-date flagged/recovered money.

Exit gate:

- Rasheed can process a simulated batch without reading raw JSON or acting outside the product.
- Every exception has evidence access.
- Every money-moving button names the amount and consequence.
- Every human action mutates state and audit.
- Aging and daily summary expose unresolved work.

Verification:

- Synthetic one-week pilot run.
- Action/audit tests.
- Packet detail page visual check.
- Daily summary fixture tests.
- Browser automation against mock TMS before any real TMS.
- Mock TMS readback and failure-mode tests.

## Stage 1 — Document Extraction Proof

**Goal:** Prove Neyma can read real carrier invoices into structured fields with honest
confidence.

Current repo status:

- In progress.
- Carrier invoice config, dynamic Pydantic extraction model, PDF rendering, vision extraction,
  synthetic sample, and eval harness exist.

Build:

- Realistic synthetic freight corpus generated from public-template-inspired formats.
- Clean and dirty scan variants.
- Ground-truth labels for required fields.
- Prompt/config iteration loop.

Exit gate:

- Required fields each at least 90% accurate on realistic synthetic clean and dirty invoices.
- Zero dangerous overconfidence on required fields.
- Overall accuracy at least 85%.
- High-confidence bucket at least 85% accurate.

Later, repeat this gate on design-partner/customer-approved documents before claiming production
readiness for a live client.

Verification:

```bash
.venv/bin/python -m pytest eval/tests -q
.venv/bin/python scripts/generate_realistic_corpus.py --loads 18 --seed 42
.venv/bin/python scripts/run_extraction.py --render-only
.venv/bin/python eval/run_eval.py --save eval/results/real_$(date +%Y%m%d).json
```

## Stage 2 — Document And Data Entry Packet Intelligence

**Goal:** Move from one PDF to freight email/PDF packets for the first teammate family:
Document & Data Entry.

Current V0:

- `src/freight_recon/email_corpus.py` + `scripts/generate_email_corpus.py` — synthetic inbound-email
  corpus: real `.eml` emails with attached PDF bytes plus a hidden-truth manifest (true doc type +
  true linked load per attachment), across complete / trickle / extra-unrelated / wrong-load /
  missing-POD / forwarded-thread scenarios.
- `src/freight_recon/ingestion.py` + `scripts/run_ingestion.py` — parse `.eml` → classify each
  attachment (confidence + reason) → link to a known load (load id / invoice / PRO / BOL) → assemble
  a typed packet with delivered/missing required docs, extraneous-attachment flags, and
  `needs_human`. The load linker is the safety mechanism: a wrong-load or unrelated attachment fails
  to link and is flagged, never contaminating the packet. Scored against hidden truth (link
  accuracy, doc-type accuracy, noise rejection, missing-doc detection). Deterministic, no model
  spend; a vision classifier slots in behind the `DocClassification` contract later.
- `src/freight_recon/mailbox_intake.py` + `scripts/run_mailbox_intake.py` — controlled mailbox
  intake V0 for Phase A owner-readiness. It watches a local inbound directory of real `.eml` files,
  preserves raw messages, dedupes by content hash and `Message-ID`, records sender/subject/date/
  thread/attachment/load-hint metadata, and reprocesses all preserved messages for each touched
  load through the existing packet ingestion pipeline. This proves the "agent waits in the inbox"
  shape without Gmail/IMAP secrets; real mailbox transports should feed the same contract later.
- `src/freight_recon/mailbox_workflow.py` + `scripts/run_mailbox_workflow.py` — mailbox-to-workflow
  orchestration V0. It turns local inbound packet runs into durable workflow runs, deterministic
  reconciliation outcomes, human review payloads, and signed Slack-shaped delivery messages. Packet
  ingestion findings are first-class safety signals: missing POD, extraneous attachments, and
  wrong-load/noise flags force review even if the dollar reconciliation is clean. Unlinked inbound
  emails become review items, and review evidence points at the mailbox packet that actually
  arrived.

Build:

- Email/PDF attachment ingestion from local fixtures first. **V0 built (local `.eml`).**
- Controlled mailbox intake that preserves/dedupes/reprocesses inbound `.eml`. **V0 built.**
- Mailbox-to-workflow bridge that creates/updates packet-scoped workflow runs and review delivery
  artifacts. **V0 built.**
- Document classifier for invoice, POD, BOL, lumper receipt, accessorial backup, rate con,
  fuel receipt, manifest, customer invoice draft inputs, carrier packet docs, and unknown.
- Per-document-type extraction configs.
- Load-linking logic: load number, PRO, BOL, invoice reference, carrier, date, amount.

Exit gate:

- Given a sample email packet, Neyma identifies each document type, extracts typed data, and
  links documents to the same load or flags uncertainty.

Verification:

- Fixture packet tests.
- Eval report by document type.
- Unknown-document safe handling.
- Mailbox intake tests for new messages, duplicates, trickle-in packet updates, and CLI smoke.
- Mailbox workflow tests for review/delivery creation, retry idempotency, packet-flag review
  routing, requested-backup refresh, duplicate stability, unlinked-email surfacing, mailbox evidence
  links, token redaction, and CLI smoke.

## Stage 3 — Deterministic Reconciliation Engine

**Goal:** Turn extracted fields into business decisions.

Build:

- Rate-confirmation fixture model.
- Deterministic matching rules.
- Money comparison with Decimal and configured tolerances.
- Accessorial backup validation.
- Duplicate invoice detection.
- Outcome object: matched, variance, missing backup, duplicate, failed, needs review.

Current V0:

- `src/freight_recon/reconciliation.py`
- `scripts/run_reconciliation.py`
- Synthetic corpus scenario tests.

Exit gate:

- Known invoice/rate-con pairs classify correctly across clean matches, amount variance,
  missing fuel, extra accessorial, duplicate invoice, and missing backup.

Verification:

- Unit tests for every rule.
- Fixture-based scenario tests.
- No LLM calls inside matching.

## Stage 4 — Workflow State Machine, Store, And Audit Log

**Goal:** Build the operational spine.

Current V0:

- `src/freight_recon/workflow.py`
- `scripts/run_workflow.py`
- SQLite workflow runs and audit events.
- SHA-256 file-content idempotency.
- Explicit state transitions for receive, extract, reconcile, review routing, done, and failed.
- Synthetic corpus workflow tests.

Build:

- LangGraph or explicit state-machine orchestration decision.
- Tool permission registry.
- SQLite or Postgres-compatible persistence.
- Content hash idempotency.
- Lifecycle states.
- Workflow run records.
- Audit event table.
- Retry and failure handling.

Core states:

```text
RECEIVED
CLASSIFIED
EXTRACTED
RECONCILED
NEEDS_REVIEW
APPROVED
READY_FOR_ENTRY
ENTERING
ENTERED
DONE
FAILED
WAITING_FOR_SESSION
```

Exit gate:

- Same document processed twice does not double-create or double-enter.
- Crash/retry resumes safely.
- Every decision has an audit event.

Verification:

- Idempotency tests.
- State-transition tests.
- Audit-log assertions.
- Tool permission tests: blocked tools cannot run in the wrong state.

Current command:

```bash
.venv/bin/python scripts/run_workflow.py --reset
```

Next implementation slice:

- Add the tool permission registry.
- Move tool gating into workflow execution paths before real outbound messages or browser actions.

## Stage 5 — Human Review Teammate

**Goal:** Let the customer supervise the agent in their normal channel.

Current V2:

- `src/freight_recon/review.py`
- `scripts/run_review.py`
- `configs/clients/neyma_test_freight.yaml`
- Pydantic review payloads with severity, reasons, fields, actions, source documents, and audit
  context.
- Evidence links, packet detail URL, money-specific action labels, aging metadata, severity
  routing, and found-money fields.
- Dogfood client defaults: Neyma Test Freight LLC, Rasheed as owner/operator, short/direct
  carrier follow-up tone, local packet/evidence URLs.
- Plain-text fallback renderer for CLI/email-style review.
- Idempotent `review_payload_created` audit events.
- Synthetic corpus review tests for variance, duplicate, missing POD, missing backup, and matched
  no-review cases.
- Packet detail page V0: `src/freight_recon/packet_page.py` and
  `scripts/generate_packet_pages.py` generate local evidence pages under
  `data/active_workspace/site`.
- Review action intake V0: `src/freight_recon/review_actions.py` and
  `scripts/apply_review_action.py` apply local approve/edit/dispute/request-backup/duplicate
  decisions to workflow state and audit events.
- Follow-up drafts V0: `src/freight_recon/follow_up.py` and
  `scripts/generate_follow_up_draft.py` create short/direct carrier dispute, backup-request, and
  duplicate-check drafts behind a `PENDING_APPROVAL` send gate.
- Daily summary V0: `src/freight_recon/summary.py` and `scripts/generate_daily_summary.py`
  generate auto-cleared, needs-review, duplicate, missing-backup, oldest/largest unresolved,
  and flagged/recovered money counters.
- Mock TMS UI/data V0: `src/freight_recon/mock_tms.py` and `scripts/generate_mock_tms.py`
  generate a local source-of-truth surface modeled on common freight TMS modules: load board,
  dispatch navigation, carrier payables, load detail tabs, accounting, documents, and notes.
- Mock TMS read adapter V0: `src/freight_recon/tms_adapter.py` and
  `scripts/read_mock_tms.py` parse the local mock TMS HTML into typed load/payable readback
  models with local-root allowlisting and fail-closed validation.
- Browser-shaped mock TMS readback V0: `BrowserMockTmsReadAdapter` reads through a stable
  selector/page contract for Playwright/browser-use implementations, with fake-page regression
  tests and live Playwright MCP verification against the generated local mock TMS.
- Production browser-agent direction: use
  [`browser-use/browser-use`](https://github.com/browser-use/browser-use) behind Neyma's adapter,
  permission, audit, and readback boundaries when operating customer TMS screens like a human.
- Browser Use adapter V0: optional `browser-use[core]==0.13.1` dependency, lazy native runner,
  read-only `BrowserUseTmsAdapter` for mock TMS, strict JSON output validation, permission gate,
  allowlisted base URL, and CLI wrapper.
- Tool permission registry V0: `src/freight_recon/tool_permissions.py` and
  `scripts/check_tool_permission.py` define workflow-state tool access, risk tiers, approval
  requirements, outbound/TMS-write feature gates, and auditable allow/block decisions.
- Delivery adapter V0 with signed action intake: `src/freight_recon/delivery.py`,
  `scripts/deliver_review.py`, and `scripts/submit_signed_action.py`. Renders review payloads into
  channel-neutral `DeliveryMessage`s (evidence links, packet URL, exact money buttons, aging,
  routing/severity, found-money) carrying HMAC-signed, expiring, single-use action tokens. Intake
  verifies the signature, rejects tampered/expired tokens, is idempotent on duplicate action ids,
  applies the action through `apply_review_action` (workflow state cannot be bypassed), mutates the
  message state text, triggers the send-gated follow-up draft, and audits every step.
  Persisted/audited/local-rendered messages redact tokens to fingerprints; raw tokens are only for
  live outbound buttons or explicit `--show-tokens` local testing. Production signing fails closed
  unless a real delivery secret is configured.
- Slack transport V0 plus local email-link fixture support: `src/freight_recon/slack_adapter.py` renders Block Kit, verifies the
  Slack `v0` request signature (HMAC + 5-minute replay window), and feeds the button token into the
  signed intake; `src/freight_recon/email_adapter.py` is retained for local/dev review artifacts and
  callback-link tests. Product review goes to Slack; carrier-facing email follow-up is a separate
  send-gated workflow. Two independent HMAC layers (Slack request + Neyma action token). Real
  workspace posting is gated.
- Delivery dispatch V0: `src/freight_recon/delivery_dispatch.py` and `scripts/dispatch_review.py`
  route review messages through per-customer Slack config in `DRY_RUN`, `LOCAL_OUTBOX`, or
  `LIVE` mode. Dispatch attempts are audited, token-bearing payloads are redacted in logs/artifacts,
  live Slack posting is blocked unless outbound is enabled and tool permissions allow it, and live
  user-review email is blocked by product contract.
- Mock TMS realism: `src/freight_recon/mock_tms.py` now models carrier authority (MC#/USDOT#/SCAC),
  AP settlement/voucher status (PENDING/APPROVED/ON_HOLD/SHORT_PAY/PAID), payment terms, fuel basis,
  accessorial authorization terms, and a required-document checklist — additive, preserving the
  read-adapter selector and payable-queue contract.

Build:

- Slack is the headless review UI; no user review email fallback.
- Review cards for extraction confidence, reconciliation variance, missing docs, and duplicates.
- Approve, edit, dispute, request docs, and mark not relevant.
- Signed webhook verification.
- Human corrections saved back to eval data.
- Tool calls that send messages or draft follow-ups are gated by workflow state and audit.

Exit gate:

- A real invoice packet routes to a human with the right context.
- Human action advances workflow state correctly.
- Corrections are captured as future evaluation data.

Verification:

- Local webhook tests.
- Slack signature tests.
- End-to-end fixture workflow.

Current command:

```bash
.venv/bin/python scripts/run_review.py --record-audit --text --age-hours 48
.venv/bin/python scripts/generate_packet_pages.py
.venv/bin/python scripts/apply_review_action.py 3 APPROVE_EXPECTED_AMOUNT --amount 3334.50
.venv/bin/python scripts/generate_follow_up_draft.py 3 APPROVE_EXPECTED_AMOUNT --record-audit
.venv/bin/python scripts/generate_daily_summary.py --text
.venv/bin/python scripts/generate_mock_tms.py
.venv/bin/python scripts/read_mock_tms.py LD-560003
.venv/bin/python scripts/read_mock_tms.py LD-560003 --payable
.venv/bin/python -m pytest eval/tests/test_browser_tms_adapter.py -q
.venv/bin/python -m pytest eval/tests/test_browser_use_adapter.py -q
.venv/bin/python scripts/read_tms_browser_use.py --help
.venv/bin/python scripts/check_tool_permission.py read_tms_load NEEDS_REVIEW
.venv/bin/python scripts/deliver_review.py --text
.venv/bin/python scripts/dispatch_review.py --mode DRY_RUN --allow-local-dev-secret --text
.venv/bin/python scripts/submit_signed_action.py "<signed-token>"
.venv/bin/python scripts/run_dogfood_pilot.py --text
```

Next implementation slice:

- Run the internal one-week simulated pilot over the signed delivery + dispatch flow, then wire the
  real Slack app/callback endpoint. Add carrier-facing email send only through its own follow-up
  gate, not as a user review channel.

## Stage 6 — TMS Read Adapter

**Goal:** Pull source-of-truth load/rate data from the customer's system.

Current V1:

- `src/freight_recon/tms_adapter.py`
- `scripts/read_mock_tms.py`
- Read-only `MockTmsReadAdapter` for generated local mock TMS HTML.
- Typed `TmsLoadReadback` and `TmsPayableReadback`.
- Local-root path allowlist, load id validation, missing-field failures, and no writes.
- `BrowserMockTmsReadAdapter` for Playwright/browser-use-style page readback through stable
  selectors.
- Browser adapter tests cover allowlisted navigation, field readback, payable queue readback, and
  unsafe URL/load blocking.
- Live Playwright MCP verification has read `LD-560003` from the local mock TMS payables queue and
  load detail page.
- Production browser agent implementation target is `browser-use/browser-use`; Playwright remains
  the cheap deterministic local verification layer.
- Optional `browser-use[core]==0.13.1` extra is wired through `BrowserUseTmsAdapter`; tests use a
  fake runner so normal CI does not need a browser session or LLM key.

Build:

- Adapter interface: API first where available, browser session where necessary.
- Mock TMS. **Built for local dogfood.**
- Browser automation against mock TMS before any real TMS. **Playwright readback and Browser Use
  adapter skeleton built for local dogfood.**
- Optional sandbox/free/demo TMS only after mock TMS passes.
- Session-based browser profile.
- Domain allowlist and timeout controls.
- No credential storage.
- No session routes to `WAITING_FOR_SESSION`.

Exit gate:

- Given a load/PRO, Neyma reliably reads rate con/load fields from mock TMS and one sandbox or
  design-partner test environment.

Verification:

- Adapter contract tests.
- Mock TMS browser tests.
- Session-expired tests.
- Readback schema validation.

## Safety Layer — Tool Permission Registry

**Goal:** Ensure workflow state controls every tool before outbound messages or TMS write paths.

Current V0:

- `src/freight_recon/tool_permissions.py`
- `scripts/check_tool_permission.py`
- Registry entries for SOP retrieval, prior corrections, email summarization, carrier follow-up
  draft/send, TMS read, TMS payable preparation/upload/submit, and TMS payable verification.
- Blocks unknown tools, wrong workflow states, missing human approval, disabled outbound email,
  and disabled TMS write.
- Records allow/block decisions into the workflow audit log.

## Stage 7 — TMS Write Adapter

**Goal:** Execute approved actions only after review and verify the result.

Current V0 (mock TMS):

- `src/freight_recon/tms_write.py` + `scripts/enter_tms_payable.py` — enter an APPROVED payable into
  a mock TMS ledger with confirm-before-submit, verify-by-readback, per-action idempotency, and an
  action trace. Driver advances APPROVED → READY_FOR_ENTRY → ENTERING → ENTERED → DONE only on a
  verified readback; duplicate-payable → FAILED, session-expired → WAITING_FOR_SESSION,
  readback-mismatch → FAILED. Each step is gated by the tool permission registry (prepare/submit
  require explicit human approval + `tms_write_enabled`) and audited. Deterministic Python owns the
  money; this only enters an already-approved amount. The browser-use execution layer ("operate the
  TMS screen like a human") implements this same interface against a real/sandbox TMS later.

Build:

- Approved payable entry workflow.
- Document upload workflow.
- Confirm-before-submit mode.
- Verify-by-readback.
- Idempotency key per action.

Exit gate:

- Approved action writes to mock TMS, reads back the result, and only then marks entered.
- Retry cannot double-enter.

Verification:

- Mock TMS write tests.
- Forced crash during `ENTERING`.
- Readback mismatch routes to review/failed.
- Confirm-before-submit screenshot/action trace.

## Stage 8 — Pilot Deployment

**Goal:** Run one supervised live workflow for one design partner.

Build:

- Docker package.
- Environment configuration.
- Email forwarding or mailbox watcher.
- Secrets handling.
- Basic metrics: docs processed, success rate, review rate, latency, cost.
- Daily summary.

Exit gate:

- One real customer workflow runs for one week under supervision.
- Every unhappy path lands in a safe state.
- Customer says the workflow saves time or catches errors.
- Owner-operator reviewer says the workflow is useful enough for daily supervised use.

Verification:

- Pilot runbook.
- Daily audit review.
- Manual comparison against current process.

## Stage 9 — Workflow Pack Expansion

**Goal:** Add adjacent high-ROI workflows using the same chassis.

Candidate order inside Document & Data Entry:

1. Carrier invoice reconciliation.
2. POD packet review.
3. Lumper/accessorial validation.
4. BOL data entry.
5. Rate confirmation processing.
6. Billing-ready packet assembly.
7. Customer invoice generation.
8. Fuel receipt processing.
9. Manifest data entry.
10. Carrier packet completeness.
11. Missing-document follow-up.
12. Customer billing review.

Later teammate families:

- Tracking and exception operations.
- Quoting and sales.
- Compliance and admin.
- Finance/reconciliation beyond carrier payables.

Exit gate:

- Each new workflow has its own eval set, state transitions, review UX, and audit trail.

Verification:

- Workflow-specific fixture tests.
- Real customer sample run.
- Human correction loop.

## Stage 10 — Production Hardening And Scale

**Goal:** Turn a supervised pilot into a reliable product.

Build:

- Multi-tenant isolation.
- Role-based access.
- Better observability.
- Cost controls.
- Carrier/client-specific eval slices.
- Client configuration UI or controlled config workflow.
- Deployment playbooks.
- Data retention policies.
- Security review.
- Tool registry and permission review.
- Secrets management and customer-session handling.
- Regression tests for browser/API adapters.

Exit gate:

- Repeatable onboarding for new customers.
- Clear workflow SLA.
- Measured accuracy and escalation rates by workflow.

Verification:

- Regression eval suite.
- Production incident drill.
- Customer onboarding checklist.

## Autonomy Ladder

Autonomy should increase only when evidence earns it:

1. **Observe only:** extract and summarize.
2. **Recommend:** suggest decision, human approves.
3. **Prepare:** fill draft action, human submits.
4. **Execute with confirmation:** agent submits after explicit approval.
5. **Exceptions-only:** agent executes low-risk, high-confidence cases; humans review exceptions.

Neyma starts at levels 1-2. It should not jump to level 5 until a workflow has real measured
accuracy, auditability, and customer trust.
