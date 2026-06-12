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

Build:

- Email/PDF attachment ingestion from local fixtures first.
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
- Add Slack/Teams/email adapter delivery and signed webhook handling.
- Add human action intake to move review decisions into workflow transitions.

## Stage 5 — Human Review Teammate

**Goal:** Let the customer supervise the agent in their normal channel.

Current V0:

- `src/freight_recon/review.py`
- `scripts/run_review.py`
- Pydantic review payloads with severity, reasons, fields, actions, source documents, and audit
  context.
- Plain-text fallback renderer for CLI/email-style review.
- Idempotent `review_payload_created` audit events.
- Synthetic corpus review tests for variance, duplicate, missing POD, missing backup, and matched
  no-review cases.

Build:

- Slack first, email fallback later.
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
.venv/bin/python scripts/run_review.py --record-audit --text
```

Next implementation slice:

- Add a tool permission registry so review-message creation/send tools are allowed only from
  review-appropriate states.
- Add review action intake: approve, edit, dispute, request backup, mark duplicate.
- Then add Slack/Teams/email adapter delivery.

## Stage 6 — TMS Read Adapter

**Goal:** Pull source-of-truth load/rate data from the customer's system.

Build:

- Adapter interface: API first where available, browser session where necessary.
- Mock TMS.
- Browser automation against mock TMS before any real TMS.
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

## Stage 7 — TMS Write Adapter

**Goal:** Execute approved actions only after review and verify the result.

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
