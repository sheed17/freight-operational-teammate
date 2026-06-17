# Design Partner Pilot Playbook

This playbook defines what "ready to deploy for a design partner" means for Neyma's first
teammate family, **Document & Data Entry**, starting with carrier invoice reconciliation.

The first deployment should be supervised. Neyma should prove it can read documents, structure
data, identify issues, and help the human review faster before it is allowed to write into a TMS.

The first deployment should not require a new web app. Neyma should operate in the partner's
existing workspace: email/PDFs/TMS for inputs and Slack, Teams, or email for review and
approvals.

Before the first design partner, run the [Internal Dogfood Pilot](INTERNAL_DOGFOOD_PILOT.md).
Rasheed should experience Neyma as the controller/payables reviewer for a simulated freight
company, including evidence links, packet detail page, action intake, follow-up drafts, aging,
and daily summaries.

## Pilot Goal

Prove that Neyma can save time or catch money-impacting errors in one real freight back-office
workflow:

> Carrier invoice received -> extract fields -> compare against known rate/load data -> flag
> variance or missing backup -> human reviews -> result is logged and used to improve the system.

This starts with carrier invoices, then expands to BOL data entry, rate confirmations, POD
capture/filing, customer invoice generation, fuel receipts, and manifest data entry once the
shared document engine is trusted.

## What Not To Promise Yet

Do not promise these for the first pilot unless they are built and tested:

- Autonomous TMS write-back.
- Fully automated approval.
- All freight document workflows.
- Quoting, tracking, compliance, and admin teammates.
- Zero-touch operation.

Safe promise:

> We will start with one supervised workflow, prove accuracy on your real documents, and expand
> automation as the data earns trust.

## Readiness Levels

### Level 0 - Discovery Ready

Neyma is ready for workflow discovery when:

- You can explain the first workflow clearly.
- You have a sample request email for docs.
- You have the intake questions below.

### Level 1 - Eval Ready

Neyma is ready to evaluate the design partner's documents when:

- Stage 1 extraction code runs locally.
- The eval harness runs.
- The partner provides 20-50 historical carrier invoices.
- Ground truth is labeled for required fields.

Gate:

- Required invoice fields meet the Stage 1 eval gate on partner documents.

### Level 2 - Review Pilot Ready

Neyma is ready for a supervised review pilot when:

- Invoice extraction is passing on partner docs.
- Rate confirmation or TMS fixture data is available for test loads.
- Deterministic reconciliation rules exist.
- State machine and audit log exist.
- Human review output exists through Slack, Teams, or email. CLI/report output is acceptable
  only for internal testing before partner-facing pilot.

Gate:

- A real closed-load invoice can be processed end to end into a reviewable decision:
  matched, variance, missing backup, duplicate, needs review, or failed.

### Level 3 - Live Supervised Pilot Ready

Neyma is ready for live supervised use when:

- Email/PDF ingestion or a controlled upload folder exists.
- Duplicate detection is working.
- Human review is working.
- Every action is logged.
- Failure states are safe and visible.
- No autonomous TMS write is required.

Gate:

- One week of real invoices can be processed with human approval and no unsafe state.

### Level 4 - TMS Read Ready

Neyma is ready to read from the partner's TMS when:

- The adapter interface exists.
- Mock TMS read tests pass.
- Browser-use session rules are defined.
- No credentials are stored.
- No session routes to `WAITING_FOR_SESSION`.

Gate:

- Given a load/PRO, Neyma can read rate/load data and return structured fields.

### Level 5 - TMS Write Ready

Neyma is ready to write into the partner's TMS when:

- TMS read is stable.
- Human approval is required.
- Confirm-before-submit is enabled.
- Verify-by-readback is implemented.
- Retry cannot double-enter.

Gate:

- Approved entries succeed in mock/sandbox and read back correctly before any live write.

## Design Partner Intake Questions

Ask these before building partner-specific logic:

1. What TMS do you use?
2. Where do carrier invoices arrive today: shared inbox, personal inbox, TMS, factoring portal?
3. Roughly how many carrier invoices do you process per week?
4. Who reviews carrier payables today?
5. What are the most common invoice problems?
6. Do you compare every invoice against the rate confirmation?
7. What accessorials cause the most disputes: detention, lumper, layover, TONU, stop-off?
8. Do invoices usually include POD/lumper backup, or are those separate attachments?
9. What fields must be correct before an invoice can be approved?
10. What is the current process when an invoice is wrong?
11. Can you provide 20-50 closed-load invoice PDFs for testing?
12. Can you provide matching rate confirmations or exported load data for those invoices?
13. Are we allowed to use these docs for testing and configuration only?
14. Are any redactions required before sharing?
15. What channel should Neyma use for review: Slack, email, Teams, or a simple report?

## Data Request

Ask for:

- 20-50 historical carrier invoice PDFs.
- Matching rate confirmations or load/payable exports for those invoices.
- A few invoices with accessorials.
- A few messy/scanned invoices.
- A few clean PDFs.
- Examples of current dispute/rejection emails if available.

Permission language:

```text
We will use these documents only to evaluate and configure the Neyma pilot for your workflow.
We do not use your documents for model training unless separately agreed in writing.
You may redact customer names, addresses, bank details, or sensitive references as long as
invoice number, load/PRO, carrier, linehaul, fuel, accessorials, total, and invoice date remain
visible.
```

## First Pilot Scope

Recommended v0 scope:

- Carrier invoices only.
- Closed historical loads first.
- No autonomous TMS writes.
- Reconciliation against supplied rate-con fixtures or exported load data.
- Human-reviewed results delivered through Slack, Teams, or email.
- Daily/weekly pilot summary.

Recommended success metrics:

- Extraction accuracy by required field.
- Review time per invoice before vs after.
- Variances caught.
- Missing backup caught.
- Duplicate invoices caught.
- Human correction rate.
- False positive rate.
- Partner trust level after one week.

## Deployment Shape For First Partner

Start with the simplest safe deployment:

1. Local or private VM running Neyma.
2. Partner sends/uploads historical PDFs.
3. Neyma processes invoices in the background.
4. Neyma posts review messages into the agreed channel.
5. Human approves, edits, disputes, or requests missing backup from that channel.
6. Neyma logs the decision and posts completion/exception summaries.
7. Corrections become eval cases.
8. After trust, connect mailbox ingestion.
9. After mailbox trust, add TMS read by API/browser session.
10. After TMS read trust, consider approved TMS write.

No partner-facing dashboard is required for the first pilot.

## Weekly Pilot Loop

Each week:

- Process a batch of invoices.
- Review every exception with the partner.
- Record false positives and false negatives.
- Add corrected labels to eval data.
- Update prompts/config/rules.
- Compare new eval run against prior run.
- Decide whether to expand scope or stay put.

## Ready-To-Deploy Checklist

Before telling a design partner Neyma is ready for pilot deployment:

- [ ] Internal dogfood pilot completed with Rasheed as simulated client.
- [ ] Every review card has evidence access and packet detail page link.
- [ ] Money buttons include exact approval/dispute amounts.
- [ ] Dispute/request-backup actions create draft follow-up messages behind a send gate.
- [ ] Aging and daily summary work.
- [ ] Partner workflow is documented.
- [ ] Partner data-use permission is clear.
- [ ] 20-50 historical invoices are collected.
- [ ] Ground truth labels exist.
- [ ] Stage 1 eval passes on partner docs.
- [ ] Reconciliation rules exist for the partner's rate-con/load data.
- [ ] Duplicate detection exists.
- [ ] Human review path exists.
- [ ] Audit log exists.
- [ ] Safe failure states exist.
- [ ] No live TMS write is enabled.
- [ ] Pilot success metrics are agreed.

When the design partner data arrives, use [When Design Partner Data Arrives](WHEN_DESIGN_PARTNER_DATA_ARRIVES.md)
as the execution plan for the build.

For deployment packaging, use [Design Partner Deployment Package](DESIGN_PARTNER_DEPLOYMENT_PACKAGE.md).
It contains the config template, secrets checklist, deployment commands, success metrics,
rollback plan, and customer-system screen-mapping workflow.

## First Call Script

```text
We're building Neyma as an operational teammate for freight back-office work. I do not want to
start by automating everything. I want to start with one painful workflow and prove it on your
real documents.

The first workflow is carrier invoice reconciliation: Neyma reads the invoice, extracts the key
fields, compares them against the rate/load data, flags discrepancies or missing backup, and
shows your team what needs review.

For the first pilot, it will be supervised. Nothing gets entered into your TMS automatically.
We will use a small set of historical closed-load invoices, measure accuracy, collect your
corrections, and only expand automation when the results are trustworthy.
```
