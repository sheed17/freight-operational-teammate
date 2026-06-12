# Neyma Vision

Neyma is an **agentic freight-ops teammate** for small and mid-sized freight and logistics
teams, especially brokerages and operators with roughly 5-50 employees.

The product is not just a document extractor. The document extractor is the first sense organ.
The real product is a workflow engine that can read messy operational inputs, reconcile them
against source-of-truth systems, ask humans for judgment when needed, and eventually execute
approved actions inside the tools the team already uses.

## Target Customer

Neyma is built for freight teams that are too small for enterprise transformation projects but
busy enough that back-office work is painful:

- 5-50 employees.
- High email/PDF volume.
- Manual billing and carrier-payables review.
- TMS usage is inconsistent, under-integrated, or too expensive to customize.
- One or two ops people carry a large amount of tribal knowledge.
- Errors are expensive, but full automation is scary.

## Product Thesis

Freight operations are full of repetitive but judgment-sensitive workflows:

- Read an email thread.
- Open attached PDFs.
- Figure out which load the packet belongs to.
- Extract invoice, POD, lumper, accessorial, carrier, and rate details.
- Compare those details against the TMS, rate con, SOP, or customer rule.
- Decide whether the load is billing-ready, payable-ready, disputed, or missing backup.
- Update a human, request missing documents, or enter approved data.

Neyma should turn those workflows into **auditable, human-supervised agents**.

Neyma should not require customers to live in a new web app. The teammate operates in the
customer's existing workspace:

- Reads email threads and attachments.
- Uses APIs where available.
- Uses bounded browser/session agents where APIs are unavailable.
- Notifies and asks for approval through Slack, Teams, or email.
- Writes back only approved actions after verification.
- Sends summaries, exceptions, and requests for help in the channels the team already checks.

## Positioning

Use this external framing as inspiration, not as something to copy:

- Ventus-style "AI teammate": operates inside existing systems, communicates in the channels
  people already use, follows SOPs, asks for help, and deploys around real workflows.
- Pallet-style logistics workforce: logistics-specific workflow execution for high-volume,
  exception-heavy work, with validation, escalation, enterprise memory, and agent builders.
- Navix-style workflow arc: parse inbound communication, structure data, execute steps,
  keep the team in control.

Neyma's position is the SMB freight/logistics version of that blend:

```text
Ventus-like existing-system operation
+
Pallet-like logistics workflow depth
+
5-50 employee freight/logistics focus
```

Neyma should feel like an employee who works where the team already works, but its knowledge,
schemas, rules, and workflows are freight-native from day one.

Neyma's wedge is narrow and practical:

> Start with the highest-ROI freight back-office workflow, prove it on the customer's real
> documents, then expand into adjacent document-heavy workflows.

## First Teammate Family: Document And Data Entry

The first teammate family is **Document & Data Entry** for freight operations. This is where
Neyma starts because freight teams spend enormous time reading PDFs/emails and keying the same
data into TMS, accounting, billing, and document folders.

This phase includes:

- Carrier invoice processing: extract, reconcile, and prepare/enter into TMS/accounting.
- Bill of lading data entry.
- Rate confirmation processing.
- Proof of delivery capture and filing.
- Customer invoice generation.
- Fuel receipt processing.
- Manifest data entry.

Within this family, the first production workflow is **carrier invoice reconciliation**:

1. Read carrier invoice PDFs.
2. Extract invoice number, carrier, load/PRO, linehaul, fuel, accessorials, total, and date.
3. Match against a rate confirmation or TMS record.
4. Detect variance, missing backup, duplicate invoices, and low-confidence fields.
5. Route exceptions to a human.
6. Enter or prepare approved payable data only after verification.

This wedge is high ROI because it protects margin, reduces carrier-payables drag, and creates
the extraction, reconciliation, review, and audit primitives every later workflow needs.

## Expansion Workflows

After the first carrier-invoice workflow is trusted, expand inside Document & Data Entry before
moving into more operationally dynamic teammates like tracking, quoting, sales, compliance, and
admin:

- **POD packet review:** detect POD, extract delivery date/time/signature, verify load match,
  mark billing-ready or request missing POD.
- **Lumper/accessorial validation:** extract receipts, match against invoice accessorials,
  verify amount/date/load, route missing backup.
- **BOL data entry:** extract shipper, consignee, pickup/delivery dates, BOL number, commodity,
  weight, pieces/pallets, references, and special instructions.
- **Rate confirmation processing:** extract agreed lane, equipment, linehaul, fuel, accessorial
  rules, pickup/delivery requirements, and carrier terms.
- **Customer invoice generation:** assemble billing-ready data from load, POD, BOL, rate, and
  accessorial backup, then prepare customer invoice draft.
- **Fuel receipt processing:** extract gallons, amount, date, truck/driver/load reference, and
  match to trip or reimbursement rules where applicable.
- **Manifest data entry:** extract shipment rows, references, weights, pieces, stops, and carrier
  assignments.
- **Carrier packet completeness:** W-9, insurance, authority, factoring notice, payment setup,
  compliance checklist.
- **Billing-ready load review:** assemble invoice, POD, BOL, accessorial backup, customer
  references, and billing status.
- **Missing-document follow-up:** draft and send carrier/customer follow-ups for missing POD,
  lumper receipt, revised invoice, or accessorial backup.
- **TMS execution:** read load data, write approved updates, upload documents, verify by
  reading back.

## Product Principles

1. **Workflow before model.** The model is a component; the product is the full operational loop.
2. **Evidence before autonomy.** Every stage earns more autonomy through evals and audits.
3. **Structured data everywhere.** Documents, emails, decisions, and actions become typed records.
4. **Deterministic money logic.** LLMs read and draft; Python rules compare money and state.
5. **Human control by default.** Humans approve consequential actions until real data proves trust.
6. **Operate where the customer already works.** Email, Slack/Teams, TMS, portals, and PDFs.
   Do not require a dashboard for the core workflow unless one becomes necessary later.
7. **State controls tools.** The agent only gets access to tools appropriate for the current
   workflow state, customer permissions, and approval level.
8. **Client memory is configuration first.** SOPs, thresholds, mappings, and carrier quirks live
   in config and evals before considering fine-tuning.
9. **Audit trail is product, not plumbing.** Freight teams need to know what happened, why, and
   who approved it.

## What This Repo Should Represent

This repo should be the execution core for Neyma:

- Document and email ingestion.
- Document classification.
- Structured extraction.
- Reconciliation and validation.
- State machine and audit trail.
- Human review.
- TMS/browser/API action adapters.
- Workflow packs for freight-specific jobs.

The current code implements the beginning of this core: carrier invoice extraction and the
Stage 1 eval harness.
