# Owner-Operator Readiness

This doc answers a stricter question than "does the code work?":

> If I owned a 5-50 person freight/logistics company, would this phase make Neyma useful in the
> real back office tomorrow morning?

Neyma's first useful shape is not a dashboard. It is an operational teammate that sits in the
company's inbound workstream, asks for judgment in Slack, and operates existing systems after
approval.

## Production Mental Model

For the first workflow, Neyma should feel like a trained carrier-payables/back-office teammate:

```text
Inbox worker waits for carrier/customer emails
→ document packet worker classifies and links attachments to loads
→ extraction worker reads invoice/POD/BOL/rate/accessorial fields with evidence
→ reconciliation worker compares against source of truth
→ Slack review worker asks the owner/controller only when judgment is needed
→ browser/TMS operator performs approved work in the customer's system
→ readback verifier confirms the system state
→ audit/summary worker records and reports what happened
```

Channel roles are fixed:

- **Email:** inbound workspace where documents and messy operational threads arrive.
- **Slack:** human approval, evidence, exception, and completion surface.
- **Browser/API/TMS:** execution layer for approved work.
- **Carrier-facing email:** follow-up channel for disputes/missing backup after Slack approval.

## Who Does This Work Today

In small freight companies this work is usually split across titles, not owned by one perfect role:

- **Owner/operator or controller:** approves exceptions, short-pay/full-pay decisions, cash impact,
  and disputed carrier charges.
- **Carrier payables/AP clerk:** checks invoices against rate confirmations, confirms POD/backup,
  catches duplicates, prepares or enters carrier payable data.
- **Billing specialist:** assembles billing-ready packets, confirms POD/BOL/rate docs, prepares
  customer invoices.
- **Operations coordinator/dispatcher:** chases missing PODs, carrier docs, lumper receipts,
  detention backup, and weird carrier replies when back office needs help.
- **Back-office/accounting generalist:** lives between inbox, TMS, accounting, documents, and
  carrier/customer follow-up.

Neyma should reduce the low-judgment work these people do, not pretend judgment disappears.

## Serious-Use Gates For The First Flow

The first production flow is carrier invoice + supporting document reconciliation. It becomes
seriously useful only when it clears these gates in order.

### Phase A — Inbound Work Intake

Owner question: "Is Neyma actually sitting where the work arrives?"

Build:

- Watch a real or controlled mailbox/alias.
- Parse threads and attachments.
- Preserve source email, attachment bytes, sender, timestamps, subject, and thread context.
- Deduplicate documents by hash.
- Create or update a workflow run per load/invoice packet.

Current V0:

- Controlled local mailbox directory over real `.eml` files.
- Raw message preservation.
- Durable dedupe by content hash and `Message-ID`.
- Sender/subject/date/thread/attachment/load-hint metadata.
- Reprocessing of preserved messages for each touched load, so trickle-in POD/backup updates the
  packet instead of creating a disconnected task.
- Mailbox-to-workflow bridge that creates one durable operational run per load/invoice packet,
  routes deterministic reconciliation outcomes, and produces signed Slack-shaped review artifacts.
- Packet ingestion safety flags force human review for missing required docs, wrong-load/noise
  attachments, and ambiguous packet conditions even when the invoice dollars match.
- Unlinked inbound emails become reviewable exceptions so the inbox cannot hide ambiguous work.
- Review evidence reflects the received mailbox packet, giving the owner/controller one-click
  context for the documents that actually arrived.

Not yet:

- Gmail/IMAP/API watcher.
- Long-running daemon mode.
- Carrier replies routed back to an existing Slack thread/action.

Gate:

- Given a realistic inbox batch, Neyma finds the work without manual upload.
- Wrong-load, unrelated, duplicate, and trickle-in attachments are safely bucketed.
- Nothing consequential happens from email alone.

### Phase B — Packet Understanding

Owner question: "Can Neyma tell whether this packet is complete and belongs to the right load?"

Build:

- Classify invoice, POD, BOL, rate confirmation, lumper, fuel, manifest, accessorial backup, and
  unknown documents.
- Link each document to a load using load id, PRO, BOL, invoice number, carrier, date, and amount.
- Identify missing required docs and extra/unlinked docs.
- Capture evidence references for each important field.

Gate:

- Neyma can say: complete, missing POD, missing backup, wrong load, duplicate, or needs human.
- The owner can inspect why with one click from Slack.

### Phase C — Money And Rule Reconciliation

Owner question: "Would I trust this to catch margin leakage before I pay?"

Build:

- Compare invoice linehaul, fuel, detention, lumper, accessorials, and total against rate/load data.
- Validate backup requirements and approval rules.
- Detect unauthorized charges, duplicates, overbilling, missing rate data, and low-confidence fields.
- Use deterministic Python for every money decision.

Gate:

- Clean matches are quiet but countable.
- Exceptions are routed with exact dollars, reason, and evidence.
- No LLM judgment decides whether money is owed.

### Phase D — Slack Review Desk

Owner question: "Can I approve or dispute this in under 30 seconds without opening five systems?"

Build:

- Slack cards with load, carrier, invoice, variance, exact amount, evidence links, and packet link.
- Money-specific buttons: approve expected amount, approve full amount, dispute charge, request
  backup, edit, mark duplicate.
- Message mutation after action.
- Aging, re-pings, daily summary, and found-money counters.

Gate:

- The owner/controller can make the normal payables decision from Slack.
- The Slack thread becomes a readable audit trail.

### Phase E — Follow-Up Handling

Owner question: "Does Neyma handle the annoying next step, or just tell me there is a problem?"

Build:

- Draft carrier emails for missing POD, missing lumper receipt, unauthorized detention, duplicate
  invoice, and short-pay dispute.
- Attach/cite the relevant rate-con or packet evidence.
- Keep send gated until trust is earned.
- Ingest carrier replies back into the same packet.

Gate:

- A dispute/request-backup click produces a ready-to-send carrier follow-up.
- Replies re-enter the workflow instead of becoming another manual task.

### Phase F — TMS Read

Owner question: "Can Neyma look up the source of truth like my employee would?"

Build:

- Read load/rate/payable data from mock TMS first.
- Map customer-specific TMS screens later.
- Use API where available, browser-use where not.
- No stored credentials; human-established session only.
- Domain allowlist, timeout, selector/screen map, and failure-state handling.

Gate:

- Neyma can retrieve the data needed to reconcile without a human exporting spreadsheets.
- Session expiry, missing load, and changed screens fail safely.

### Phase G — Approved TMS Execution

Owner question: "After I approve, can Neyma do the data entry correctly and prove it?"

Build:

- Browser-use/API entry for approved payable data only.
- Confirm-before-submit during early pilot.
- Upload/store supporting docs where required.
- Add TMS note explaining the decision.
- Verify by readback before marking done.
- Idempotency prevents duplicate payable entry.

Gate:

- After Slack approval, Neyma enters or prepares the payable, reads it back, and posts completion.
- Any mismatch stops the workflow and escalates.

### Phase H — Measured Pilot

Owner question: "Did this save time, catch money, and reduce chaos?"

Build:

- One-week supervised pilot metrics.
- Daily digest: clean processed, needs review, oldest unresolved, dollars flagged, dollars confirmed
  recovered, carrier follow-ups pending.
- Manual comparison against the owner's current process.

Gate:

- The owner says Neyma saved real time or caught real errors.
- The team knows which cases still need human judgment.
- No unsafe autonomous send/write occurred.

## Owner Usefulness Checklist

Every meaningful build slice should answer these before it is approved:

- What manual task did this remove or shorten?
- Which person today does that task?
- What information did Neyma need, and where did it come from?
- What is the money, timing, or compliance risk if Neyma is wrong?
- What evidence does the human see before approving?
- What happens if the document is missing, wrong-load, low-confidence, duplicate, or disputed?
- What happens if the browser/TMS session expires or the screen changes?
- Is there a clear audit trail a controller could defend later?
- Did this reduce Slack noise or create more work?
- Would a freight owner trust this enough to use it daily in supervised mode?

## Expansion Rule

Do not expand to a second workflow until the first workflow proves:

- Inbound work arrives automatically.
- Exceptions reach Slack with evidence.
- Approved follow-up or TMS work is executed safely.
- Readback and audit prove completion.
- The owner can describe the value in plain business terms.

Then expand to the next adjacent workflow using the same chassis:

1. POD packet review.
2. Lumper/accessorial validation.
3. BOL data entry.
4. Rate confirmation processing.
5. Billing-ready packet assembly.
6. Customer invoice generation.
7. Fuel receipt processing.
8. Manifest data entry.

Each new workflow needs its own schemas, rules, Slack decisions, state transitions, eval fixtures,
audit events, browser/API actions, and owner-usefulness gate.
