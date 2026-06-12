# Internal Dogfood Pilot

Before Neyma is installed for a real customer, Rasheed should be the first simulated client.
Operate Neyma as if Rasheed owns a small freight company and is using Neyma to run supervised
carrier-payables document review.

This is not a demo. Treat it as a real pilot with synthetic company data, realistic documents,
fake carrier emails, review actions, aging, evidence links, and weekly metrics.

## Staged Realism Ladder

Do not jump from unit tests to a real customer's live system. Increase realism one layer at a
time until the only thing left to swap is the customer.

```text
1. Unit tests
2. Synthetic documents and hidden truth
3. Simulated freight company
4. Mock TMS data and screens
5. Browser automation against mock TMS
6. Rasheed-operated internal client workflow
7. Optional real TMS sandbox/free/demo account
8. Design partner historical closed-load data
9. Design partner live supervised pilot
10. Limited approved production actions
```

Each rung should preserve the same contracts: typed documents, deterministic reconciliation,
workflow state, tool permissions, human approvals, audit events, and readback verification.

## Fictional Client

```text
Company: Neyma Test Freight LLC
Team size: 12 employees
Role in pilot: small freight brokerage / trucking operation
Workflow owner: Rasheed acting as controller / payables reviewer
Primary channel: local Slack/Teams/email simulator first, real Slack later
TMS: mock TMS first, browser/API adapter later
Invoice volume: 50-150 invoice packets/week simulated
```

The point is to feel the product as the customer would:

- What messages arrive?
- Are the buttons clear?
- Can the evidence be trusted?
- Does edit have somewhere to go?
- Does dispute/request-backup remove work or hand it back to the human?
- Do unresolved exceptions resurface?
- Does the daily summary make Neyma's value obvious?

## Scope

Start with the first workflow:

```text
carrier invoice packet
→ extraction
→ rate/load reconciliation
→ review card
→ evidence/packet detail page
→ human action
→ drafted dispute or backup request when needed
→ audit log
→ daily/weekly metrics
```

No live TMS write. No real carrier emails. No real customer data.

## TMS Simulation Strategy

Neyma should not try to support every TMS before the first pilot. Build one adapter interface and
move through realism:

```text
MockTMSAdapter
→ browser automation against mock TMS
→ optional real sandbox/demo TMS
→ first design partner's TMS
→ additional TMS adapters only when customers require them
```

The adapter contract should be stable:

```text
read_load(load_id)
read_payables(load_id)
attach_document(load_id, file)
prepare_payable(...)
submit_payable(...)
verify_payable(...)
```

For dogfood, the mock TMS should behave enough like a real system to expose the hard parts:

- load search
- rate/load field lookup
- payable status lookup
- document upload target
- duplicate payable warning
- session expiration
- readback mismatch
- slow page or failed action

Browser-use should first operate only against this mock TMS. The first browser-write path must be
dry-run or confirm-before-submit and must verify by readback before any state can become done.

## Required Simulation Inputs

Use synthetic, internally consistent data:

- Carrier invoices.
- Rate confirmations.
- PODs.
- BOLs.
- Lumper receipts.
- Fuel receipts.
- Manifests.
- Email thread fixtures.
- Mock TMS load/payable records.
- Fake carrier contacts.
- Fake controller/accounting user.

Scenarios must include:

- Clean matches.
- Unauthorized detention.
- Fuel mismatch.
- Linehaul mismatch.
- Missing POD.
- Missing lumper/accessorial backup.
- Duplicate invoice.
- Carrier reply with backup attached.
- Carrier reply disputing Neyma's dispute.
- Human override approving full amount.
- Human edit correcting extracted data.
- Aging exception unresolved for 48+ hours.

## Client-Facing Output Design

Every review card must include:

- Load ID.
- Carrier.
- Invoice number.
- Status and severity.
- Clear issue summary.
- Invoice amount and expected/payable amount.
- One-click evidence access.
- Packet detail page URL.
- Unambiguous money buttons.
- Action history state after a human acts.

Variance actions must include amounts:

```text
Approve $3,334.50 and dispute $300 detention
Approve full $3,634.50
Request detention backup
Edit fields
```

Missing-backup actions:

```text
Request backup from carrier
Approve anyway
Mark backup not required
Edit packet
```

Duplicate actions:

```text
Mark duplicate
Open prior record
Dispute
```

## Minimal Packet Detail Page

Slack/Teams/email is the notification and quick-action layer. The packet detail page is the
evidence canvas.

The first packet page should show:

- Document viewer or thumbnails.
- Invoice and rate confirmation side by side.
- Highlighted evidence anchors where possible.
- Extracted fields with confidence.
- Expected rate/load values.
- Reconciliation math.
- Source documents.
- Decision history.
- Draft carrier email for dispute or backup request.
- Audit events.

This page should be narrow and operational. It is not a dashboard-first product.

## Follow-Up Drafting

Dispute and request-backup actions should not hand the work back to the human. They should create
a draft carrier email behind a send gate:

```text
Neyma drafted a dispute email for INV-2026003.
Reason: detention $300 is not authorized on rate confirmation.
Attachment/evidence: rate confirmation excerpt + invoice excerpt.
Action: Approve Send / Edit Draft / Cancel
```

Sending remains gated until the trust ramp supports more autonomy.

## Message Mutation And Threading

After a human action, the original message should mutate:

```text
Disputed by Rasheed at 2:14pm
Backup requested by Rasheed at 9:08am
Approved $3,334.50 by Rasheed
```

All follow-ups should live in the same packet thread:

- Backup requested.
- Carrier responded.
- Backup received.
- Reprocessed.
- Approved.
- Entered or marked done.

## Aging And Routing

Severity routing:

```text
critical = immediate post + ping
medium = posted, no ping
low = digest only
```

Default thresholds:

- Critical: duplicate invoice, unauthorized accessorial, money variance above $100, missing POD
  blocking billing/payables.
- Medium: missing backup, variance from $25-$100, low-confidence required field.
- Low: optional field uncertainty, variance below client threshold.

Aging:

- 24 hours unresolved: daily digest reminder.
- 48 hours unresolved: re-surface with aging marker.
- 72 hours unresolved critical: direct re-ping.

## Daily Summary

During the trust ramp, show clean matches as visible evidence:

```text
Neyma Daily Payables Summary

Processed: 42 invoice packets
Auto-cleared: 31
Needs review: 9
Duplicates: 1
Missing backup: 3
Potential overbilling flagged: $1,275
Month to date: $4,310 flagged · $2,950 confirmed recovered

Clean matches: 31 — view
Oldest/largest unresolved:
- INV-2026003: unauthorized detention $300, 2 days old
- INV-2026014: linehaul $200 over rate con, 1 day old
```

After trust is earned, clean matches can collapse to counts.

## Internal Pilot Gates

Neyma is ready to show a design partner only after the internal pilot proves:

- Rasheed can process a simulated batch without touching raw JSON.
- Every review card has evidence access.
- Edit opens a packet detail page, not a dead end.
- Money buttons include explicit amounts.
- Dispute/request-backup creates a draft follow-up.
- Human action mutates the message state.
- Aging and daily summary work.
- Found-money metrics are visible.
- All actions are audited.
- Browser automation has been tested against mock TMS before any real TMS.
- Mock TMS readback verification works.
- No autonomous TMS write exists.

## Build Order From Here

1. Review Payload V2: evidence links, packet URL, money-specific action labels, aging metadata,
   routing rules, and found-money fields.
2. Packet detail page V0 for local/internal use.
3. Review action intake: approve, edit, dispute, request backup, mark duplicate.
4. Draft follow-up email generator with send gate.
5. Daily summary generator with aging and found-money counters.
6. Slack/Teams/email adapter.
7. Mock TMS read adapter.
8. Internal one-week simulated pilot.
9. Only then design-partner deployment planning.
