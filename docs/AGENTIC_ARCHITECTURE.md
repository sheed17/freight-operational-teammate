# Agentic Architecture

Neyma should be built as a deterministic workflow engine with bounded AI capabilities, not as
a free-roaming chatbot.

## Core Loop

```text
input event
→ classify
→ extract structured data
→ link to load/context
→ validate/reconcile
→ decide safe next state
→ ask human or execute approved action
→ verify
→ audit
→ learn from correction
```

The primary interface should be the customer's existing workspace, not a new portal:

```text
email/PDF/TMS/portal input
→ Neyma works in the background
→ Slack/Teams/email exception or approval request
→ human approves/edits/disputes in-channel
→ Neyma executes approved action by API/browser where appropriate
→ Neyma verifies and posts completion summary
```

## Orchestration And Tooling Stack

For a production agentic system, separate the workflow brain from the tool belt:

```text
LangGraph or explicit state machine = workflow orchestration
LangChain or native model tool calling = optional LLM tool/retrieval layer
Pydantic = typed contracts for documents, state, tools, and messages
Deterministic Python = money decisions and state transitions
Adapters = API/browser/email/Slack/TMS execution
Database/audit log = source of truth
```

LangChain is useful when the LLM needs tools such as:

- `fetch_client_sop(client_id)`
- `search_prior_corrections(carrier, field)`
- `summarize_email_thread(thread_id)`
- `draft_missing_backup_email(invoice, issue)`
- `classify_email_reply(thread_id)`

LangChain is not required for basic extraction or deterministic reconciliation. Use Instructor
and Pydantic for structured extraction; use deterministic Python for comparisons. Add LangChain
or native tool calling when a workflow node truly needs LLM-accessible tools, retrieval, or
drafting.

LangGraph becomes useful when workflows are long-running and branching:

```text
receive_packet
→ classify_docs
→ extract_docs
→ reconcile
→ if variance: human_review
→ if missing_backup: draft_request
→ wait_for_reply
→ reprocess_reply
→ approved_entry
→ verify
→ done
```

Do not let a free-form LLM decide the workflow. The graph/state machine decides which node is
active and which tools are allowed.

## Staged Realism

Production readiness should increase through controlled realism, not through one leap into a
client's live system:

```text
unit tests
→ synthetic documents
→ simulated freight company
→ mock TMS data/screens
→ browser automation against mock TMS
→ Rasheed-operated internal client workflow
→ optional real TMS sandbox/demo account
→ design partner historical closed-load data
→ design partner live supervised pilot
→ limited approved production actions
```

The same workflow contracts must survive every rung: Pydantic outputs, deterministic money
logic, explicit state, tool permissions, human gates, audit events, and readback verification.
If a later rung needs a new shortcut, the earlier architecture is not ready.

## Tool Permission Model

Every tool must have:

- Typed input schema.
- Typed output schema.
- Owning adapter.
- Allowed workflow states.
- Required approval level.
- Timeout and retry policy.
- Audit event.

Example:

```text
tool: draft_missing_backup_email
allowed_states: NEEDS_BACKUP
approval_required: before_send
risk: low

tool: enter_invoice_in_tms
allowed_states: APPROVED_FOR_ENTRY
approval_required: explicit_human_approval
risk: high

tool: submit_tms_entry
allowed_states: READY_TO_SUBMIT
approval_required: explicit_human_approval until trust gate is met
risk: critical
```

Workflow state controls tool access:

```text
NEEDS_BACKUP:
  allowed: fetch_sop, search_prior_corrections, draft_email, send_approved_email
  blocked: enter_invoice_in_tms, submit_tms_entry

APPROVED_FOR_ENTRY:
  allowed: open_tms_load, enter_invoice_amount, upload_invoice_pdf, verify_tms_payable
  gated: submit_tms_entry
```

The LLM may choose among allowed low-risk tools inside a node, but it should not be able to
invoke high-risk tools unless the state and approval record permit it.

## Main Components

## Strategic Architecture Pattern

Neyma should combine two product patterns:

- **Existing-system operator:** the teammate works inside email, PDFs, portals, TMS screens,
  accounting tools, Slack, Teams, and browser sessions without forcing a new daily dashboard.
- **Freight-native workflow executor:** the teammate understands logistics-specific workflows,
  documents, SOPs, exceptions, validation rules, and escalation paths.

This means the architecture should be built around explicit workflow execution, not open-ended
chat:

```text
freight workflow definition
→ document/email intelligence
→ client memory and SOP retrieval
→ deterministic validation
→ human escalation
→ bounded API/browser action
→ readback verification
→ audit and learning loop
```

For 5-50 person freight teams, speed to trusted value matters more than enterprise feature
surface. Build narrow, useful teammates before broad platform controls.

### 1. Ingestion

Inputs:

- Forwarded email threads.
- Mailbox watcher.
- Uploaded PDF packets.
- Later: TMS event feed or API webhook.

Responsibilities:

- Preserve original files.
- Compute content hash.
- Split attachments.
- Create a workflow run.
- Avoid duplicate processing.

### 2. Document Intelligence

Responsibilities:

- Render documents.
- Classify document type.
- Extract fields with Pydantic schemas and confidence.
- Store raw extraction, normalized data, and confidence.
- Route unknown or low-confidence items safely.

Document types:

- Carrier invoice.
- Rate confirmation.
- POD.
- BOL.
- Lumper receipt.
- Fuel receipt.
- Manifest.
- Detention/accessorial backup.
- Customer invoice draft inputs.
- Carrier packet docs.
- Unknown.

### 3. Context And Memory

Use config and retrieval before fine-tuning:

- Client SOPs.
- Carrier-specific quirks.
- TMS field mappings.
- Approval thresholds.
- Accessorial rules.
- Customer billing rules.
- Prior human corrections.

Keep this memory auditable. The agent should be able to cite which rule or correction influenced
a decision.

### 4. Deterministic Decision Engine

Responsibilities:

- Money comparison.
- Duplicate detection.
- Required-document checks.
- Match invoice to load/rate con.
- Accessorial backup validation.
- State transition decisions.

LLMs should not make money decisions. They may extract, summarize, draft messages, and explain
why a deterministic rule fired.

### 5. Human Review

Human review is part of the product:

- Approve.
- Edit.
- Dispute.
- Request missing document.
- Mark duplicate.
- Mark not relevant.

Corrections become:

- Audit events.
- Golden-set labels.
- Client memory candidates.
- Future eval cases.

Default surfaces:

- Slack messages and interactive webhooks.
- Email approvals or reply-based workflows when Slack is not available.
- Daily summaries.
- Escalation messages for missing documents, failed sessions, and uncertain matches.

A web dashboard is optional later for admin, audit search, or configuration. It is not the core
operator experience.

### 6. Action Adapters

Adapters execute approved actions:

- Slack/email messages.
- TMS read.
- TMS write.
- Document upload.
- Carrier/customer follow-up.

Adapter rules:

- API first when available.
- Browser/session adapter only when needed.
- Never store user passwords.
- Domain allowlist and timeouts.
- Verify-by-readback before marking complete.

Production browser-use agents should use [`browser-use/browser-use`](https://github.com/browser-use/browser-use)
behind Neyma's adapter boundary. Keep the role names separate from the implementation:

- `tms_read_adapter` may be an API client, `browser-use/browser-use` agent, Playwright/mock
  adapter, or fixture.
- `tms_write_adapter` may be an API client, `browser-use/browser-use` agent, Playwright/mock
  adapter, or stub.
- `email_adapter` may use Gmail/IMAP/API.
- `review_adapter` may use Slack, Teams, or email.

Playwright remains the cheap local verification layer for generated mock TMS and deterministic
selector/readback tests. `browser-use/browser-use` is the intended production browser-agent
implementation when Neyma needs to operate a customer's browser/TMS like a human. It still must
run behind Neyma's state machine, tool permission registry, domain allowlist, approval gates,
timeouts, action trace, and verify-by-readback rules.

Reference systems such as AscendTMS are useful for learning freight UI patterns and making the
mock TMS more realistic. They are not the assumed production target. Production browser-use agents
operate inside each customer's actual systems with a customer-specific screen map, allowlist,
session policy, permission gates, and readback contract.

Adapter calls should be wrapped as tools only through the permission model above. Browser tools
need extra controls:

- Session profile belongs to the customer.
- No credential typing or password storage.
- Domain allowlist.
- Screenshot/action trace.
- Dry-run or confirm-before-submit mode for early pilots.
- Readback verification after writes.
- Stop-and-escalate on ambiguity.

TMS support should start with an adapter interface, not a pile of one-off browser scripts:

```text
read_load(load_id)
read_payables(load_id)
attach_document(load_id, file)
prepare_payable(...)
submit_payable(...)
verify_payable(...)
```

Build the adapters in this order:

```text
MockTMSAdapter
→ Playwright/local BrowserTMSAdapter against mock TMS
→ browser-use/browser-use adapter against mock TMS
→ optional reference/sandbox TMS screen mapping
→ customer-specific screen map for the design partner's actual system
→ first design partner browser/API TMS adapter
→ additional TMS adapters only when customer demand requires them
```

The mock TMS must simulate real failure modes: session expiration, duplicate payable warning,
slow pages, missing load, readback mismatch, and failed document upload.

### 7. Audit And Observability

Every workflow needs:

- Original document reference.
- Extraction result.
- Confidence.
- Rule decisions.
- Human actions.
- System actions.
- External-system read/write evidence.
- Final state and reason.

Every tool call also needs:

- Tool name and version.
- Inputs and normalized outputs.
- Actor: LLM, human, scheduler, adapter.
- Approval id when applicable.
- Screenshots or external evidence when applicable.
- Failure/error details.
- Retry count.

Metrics:

- Accuracy by field and document type.
- Overconfidence rate.
- Review rate.
- Automation rate.
- Cycle time.
- Cost per workflow.
- Failure categories.

## Workflow Pack Shape

Each workflow pack should include:

- Input trigger.
- Document types required.
- Extraction schemas.
- Validation rules.
- State transitions.
- Human review card.
- Action adapters.
- Eval fixtures.
- Production gate.

Example: carrier invoice reconciliation

```text
trigger: invoice email/PDF received
docs: carrier invoice, rate con, optional POD/lumper/accessorial backup
extract: invoice fields and charge lines
validate: total math, rate-con match, duplicate, backup required
review: approve/edit/dispute/request backup
action: prepare payable or enter approved data
gate: required fields >=90%, no dangerous overconfidence, deterministic scenario tests pass
```

First teammate family: Document & Data Entry

```text
workflows:
  - carrier invoice processing
  - bill of lading data entry
  - rate confirmation processing
  - POD capture and filing
  - customer invoice generation
  - fuel receipt processing
  - manifest data entry

shared capabilities:
  - classify document/email packet
  - extract typed fields
  - link to load/customer/carrier
  - validate against available source data
  - ask human when confidence or rules require it
  - file/upload/enter approved data by API or browser adapter
```

## Repository Direction

Suggested future layout:

```text
src/freight_recon/
  ingestion/
  documents/
  extraction/
  workflows/
    carrier_invoice_reconciliation/
    pod_packet_review/
    accessorial_validation/
    carrier_packet_completeness/
  reconciliation/
  review/
  adapters/
    slack/
    email/
    tms/
  state/
  audit/
  evals/
configs/
  doc_types/
  workflows/
  clients/
eval/
  golden_set/
  workflow_scenarios/
docs/
```

Do not reorganize into this all at once. Let the layout emerge as stages are implemented, but
keep the direction clear.
