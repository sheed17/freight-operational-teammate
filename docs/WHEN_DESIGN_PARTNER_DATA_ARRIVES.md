# When Design Partner Data Arrives

This is the execution plan for the next build phase after the design partner provides workflow
answers, sample documents, and permission.

## Inputs Needed From User

Required:

- Design partner workflow notes.
- TMS/system name.
- Where invoices arrive today.
- 20-50 closed-load carrier invoice PDFs.
- Matching rate confirmations or load/payable export data.
- Permission to use the documents for testing and configuration.
- Review channel preference: Slack, Teams, or email.
- Agreement that the first pilot is supervised with no autonomous TMS write.

Strongly preferred:

- Accessorial-heavy invoices.
- Invoice dispute examples.
- Approval rules.
- Weekly invoice volume.
- Exception approver names/roles.
- Sample PODs, BOLs, fuel receipts, manifests, and rate confirmations for expansion.

## Build Goal

Build the first design-partner version of Neyma's **Document & Data Entry teammate**, starting
with supervised carrier invoice reconciliation.

The partner-facing behavior should be:

```text
invoice/email/PDF arrives
→ Neyma extracts structured fields
→ Neyma compares against rate/load data
→ Neyma posts matched/variance/missing-backup/duplicate/failed result to review channel
→ human approves/edits/disputes/requests backup
→ Neyma logs correction and outcome
```

No live TMS write in the first pilot.

## Step 1 — Normalize Partner Data

Tasks:

- Store partner sample docs in a local ignored data area.
- Add ground-truth entries for the invoices.
- Normalize rate-con/load export shape.
- Identify field naming differences such as `load_or_pro` vs `load_or_pro_number`.
- Redaction check before committing anything.

Expected repo work:

- Extend `eval/golden_set/` process or add partner-specific ignored fixture path.
- Add partner config under `configs/clients/<partner>.yaml` when safe.
- Create partner notes outside committed repo if sensitive.

Gate:

- We can run extraction eval on partner invoices without leaking sensitive data.

## Step 2 — Partner Extraction Eval

Tasks:

- Run Stage 1 eval on partner docs.
- Identify field failures and overconfidence.
- Tune carrier invoice prompt/config.
- Save baseline and tuned eval reports.

Commands:

```bash
.venv/bin/python -m pytest eval/tests -q
.venv/bin/python eval/run_eval.py --save eval/results/partner_baseline.json
.venv/bin/python eval/run_eval.py --compare eval/results/partner_baseline.json eval/results/partner_tuned.json
```

Gate:

- Required fields meet gate on partner docs:
  - load/PRO
  - linehaul
  - total
  - fuel if it is frequent enough to be business-critical for the partner
- Zero dangerous overconfidence on required money/reference fields.

## Step 3 — Reconciliation V0

Tasks:

- Define rate confirmation/load data model.
- Compare invoice to expected rate/load data.
- Detect:
  - clean match
  - linehaul variance
  - fuel variance
  - accessorial variance
  - total mismatch
  - missing backup
  - duplicate invoice
  - missing rate/load match
- Return structured outcome with reason.

Expected repo work:

- Add `src/freight_recon/reconciliation/`.
- Add models for invoice extraction normalization and rate/load fixtures.
- Add fixture tests for partner-like cases.

Gate:

- Historical closed-load invoices classify correctly against known answers.

## Step 4 — State, Audit, And Idempotency

Tasks:

- Decide whether v0 uses a simple explicit state machine or LangGraph for orchestration.
- Add content-hash idempotency.
- Add workflow run state.
- Add audit events.
- Add a basic tool permission registry even if v0 only has review-message tools.
- Ensure retries do not double-process.

Expected states:

```text
RECEIVED
EXTRACTED
RECONCILED
NEEDS_REVIEW
APPROVED
DISPUTED
REQUESTED_BACKUP
FAILED
DONE
```

Expected repo work:

- Add `src/freight_recon/state/`.
- Add `src/freight_recon/tools/` or equivalent when tool calling starts.
- Add simple SQLite-backed store or file-backed pilot store.
- Add tests for duplicate and state transitions.
- Add tests proving risky tools cannot run from the wrong state.

Gate:

- Every invoice gets a durable state and audit trail.
- Duplicate document does not create duplicate payable work.

## Step 5 — Human Review Channel

Tasks:

- Generate partner-facing review messages.
- Start with Slack if available; email if not.
- Include clear reason, extracted fields, expected fields, confidence, and action buttons or
  reply instructions.

Actions:

- Approve.
- Edit.
- Dispute.
- Request backup.
- Mark duplicate.

Expected repo work:

- Add `src/freight_recon/review/`.
- Add message rendering tests.
- Add Slack/email adapter only after review format is stable.
- If using LLM tools for drafting, validate inputs/outputs with Pydantic and log every tool call.

Gate:

- Partner can understand and act on Neyma's message without using a new dashboard.

## Step 6 — Historical Pilot Run

Tasks:

- Run partner's historical invoices through the full v0 workflow.
- Review results together.
- Record corrections.
- Turn corrections into eval fixtures and config/rule updates.

Success metrics:

- Accuracy by required field.
- Variances found.
- Missing backup found.
- Duplicate candidates.
- False positives.
- Human correction rate.
- Estimated time saved.

Gate:

- Partner agrees the output is useful enough for a supervised live pilot.

## Step 7 — Live Supervised Pilot

Tasks:

- Configure controlled input: forwarded emails, upload folder, or mailbox watcher.
- Process new invoices.
- Post review messages.
- Require human approval for every consequential action.
- No autonomous TMS write.

Gate:

- One week of real invoice flow completes without unsafe actions.
- Every failed/uncertain case routes to a human-visible state.

## Step 8 — Then TMS Read, Then TMS Write

TMS read:

- API first if available.
- Browser-use session if API is not available.
- No credential storage.
- Read rate/load/payable data.

TMS write:

- Only after read is stable.
- Approval required.
- Confirm-before-submit.
- Verify-by-readback.
- Retry-safe.

## Implementation Priority On Return

When the user returns with partner data, start here:

1. Inspect sample docs and data shape.
2. Add partner-safe evaluation path.
3. Run extraction eval.
4. Fix field naming alignment.
5. Build reconciliation V0.
6. Build state/audit/idempotency V0.
7. Build review message renderer.
8. Run historical pilot.

Do not start browser/TMS write work until the historical pilot proves the workflow.

Tooling note:

- Use LangGraph if the workflow needs explicit branching, waiting, retries, and human-in-the-loop
  resume behavior.
- Use LangChain or native tool calling only for LLM-accessible tools such as SOP retrieval,
  prior-correction search, email thread summarization, and message drafting.
- Keep money comparison, approval requirements, and state transitions deterministic.
