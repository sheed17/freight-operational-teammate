# Neyma Freight Ops Agentic Workflow Engine

Neyma is an AI operational teammate for freight and logistics teams with roughly
5–50 employees. It is being built to automate the messy, document-heavy
back-office workflows that today live across email threads, PDF packets, carrier
documents, rate confirmations, TMS screens, and human tribal knowledge.

The long-term product is an **agentic freight-ops workflow engine**: it reads
documents and emails, extracts structured operational data, reconciles that data
against source-of-truth records, routes exceptions to humans, and eventually
executes approved actions inside the tools the team already uses.

Strategically, Neyma is the SMB freight/logistics blend of two AI-agent patterns:
Ventus-like operation inside existing systems plus Pallet-like logistics workflow
execution, narrowed for freight teams that need value without enterprise-scale
implementation projects.

The first teammate family is **Document & Data Entry**. It starts with the highest-ROI
workflow: **carrier-invoice-to-rate-con reconciliation** — catching invoices with line items
that do not match the rate confirmation and reducing carrier-payables review time. From there,
the same engine expands to BOL data entry, rate confirmation processing, POD capture/filing,
customer invoice generation, fuel receipts, and manifest data entry.

For the broader product map, see:

- [Neyma Vision](docs/NEYMA_VISION.md)
- [Product Roadmap](docs/PRODUCT_ROADMAP.md)
- [Agentic Architecture](docs/AGENTIC_ARCHITECTURE.md)
- [Design Partner Pilot Playbook](docs/DESIGN_PARTNER_PILOT.md)
- [When Design Partner Data Arrives](docs/WHEN_DESIGN_PARTNER_DATA_ARRIVES.md)
- [Build Supervision Protocol](docs/BUILD_SUPERVISION_PROTOCOL.md)
- [Synthetic Freight Corpus](docs/SYNTHETIC_CORPUS.md)
- [Model Strategy](docs/MODEL_STRATEGY.md)
- [Internal Dogfood Pilot](docs/INTERNAL_DOGFOOD_PILOT.md)

Build phases should end with a code-review handoff to the principal architect supervisor. See
[Build Supervision Protocol](docs/BUILD_SUPERVISION_PROTOCOL.md) and
[.codex/agents/phase-code-reviewer.md](.codex/agents/phase-code-reviewer.md).

## Architecture Direction

Neyma should be a deterministic workflow engine with bounded AI capabilities:

- **Deterministic Python chassis** — ingestion, idempotency, workflow state,
  database, extraction calls, reconciliation/matching logic, human review,
  orchestration, audit log, and safe routing.
- **Document intelligence layer** — vision extraction and classification using
  structured Pydantic outputs with confidence.
- **Human review layer** — Slack/email review for low-confidence fields,
  variances, missing backup, and consequential actions.
- **Bounded action adapters** — later-stage API/browser/TMS adapters that read
  source-of-truth data and write only approved actions, with verify-by-readback.

Intelligence is concentrated where it belongs: reading messy operational inputs,
drafting communication, and operating bounded external tools. Money decisions,
state transitions, idempotency, and reconciliation remain deterministic because
freight payments need to be predictable and auditable.

## What's Built Now

The repo currently implements the first operational spine for Workflow 1:
carrier invoice extraction, synthetic-corpus evaluation, deterministic
reconciliation, workflow state/audit/idempotency V0, and channel-agnostic human
review payloads.

- **Config system** — [configs/doc_types/carrier_invoice.yaml](configs/doc_types/carrier_invoice.yaml)
  → validated Pydantic config ([src/freight_recon/config.py](src/freight_recon/config.py)).
  Doc-type config is reusable across clients; a per-client overlay merges on top.
- **Confidence-scored extraction models** — every field carries `{value,
  confidence}`; the concrete model is built *from config*
  ([src/freight_recon/models.py](src/freight_recon/models.py)).
- **Vision extraction** — PyMuPDF renders pages → Instructor + Pydantic coerces
  the vision model's output into the structured model. Provider (Anthropic /
  OpenAI) is env-driven for the Claude-vs-GPT bake-off
  ([src/freight_recon/extraction.py](src/freight_recon/extraction.py),
  [src/freight_recon/render.py](src/freight_recon/render.py)).
- **Sample invoice + golden seed** — generates a realistic carrier invoice PDF
  plus its known-answer JSON
  ([scripts/generate_sample_invoice.py](scripts/generate_sample_invoice.py)).
- **Stage 1 eval harness** — scores extraction against golden-set labels and
  reports accuracy, calibration, overconfidence, and failure modes
  ([eval/README.md](eval/README.md)).
- **Realistic freight corpus** — generates clean and dirty synthetic freight
  PDFs plus hidden truth for invoices, rate confirmations, BOLs, PODs, fuel
  receipts, lumper receipts, and manifests
  ([scripts/generate_realistic_corpus.py](scripts/generate_realistic_corpus.py),
  [docs/SYNTHETIC_CORPUS.md](docs/SYNTHETIC_CORPUS.md)).
- **Deterministic reconciliation V0** — classifies generated invoice/rate/load
  scenarios into matched, variance, needs-review, and duplicate outcomes without
  LLM judgment ([src/freight_recon/reconciliation.py](src/freight_recon/reconciliation.py)).
- **Workflow store V0** — SQLite-backed workflow runs, SHA-256 idempotency,
  state transitions, reconciliation routing, and audit events
  ([src/freight_recon/workflow.py](src/freight_recon/workflow.py)).
- **Human review payloads V2** — typed review cards with evidence links,
  packet detail URLs, money-specific action labels, aging/routing metadata,
  found-money counters, and dogfood client defaults for Neyma Test Freight LLC
  ([src/freight_recon/review.py](src/freight_recon/review.py),
  [configs/clients/neyma_test_freight.yaml](configs/clients/neyma_test_freight.yaml)).
- **Packet detail pages V0** — local static evidence pages with side-by-side
  invoice/rate confirmation PDFs, reconciliation math, extracted fields,
  action options, follow-up draft preview, and audit history
  ([src/freight_recon/packet_page.py](src/freight_recon/packet_page.py),
  [scripts/generate_packet_pages.py](scripts/generate_packet_pages.py)).
- **Review action intake V0** — local dogfood action handler that applies
  approve/edit/dispute/request-backup/duplicate decisions to workflow state and
  audit events ([src/freight_recon/review_actions.py](src/freight_recon/review_actions.py),
  [scripts/apply_review_action.py](scripts/apply_review_action.py)).
- **Follow-up drafts V0** — short/direct carrier dispute, backup-request, and
  duplicate-check drafts behind a pending send gate
  ([src/freight_recon/follow_up.py](src/freight_recon/follow_up.py),
  [scripts/generate_follow_up_draft.py](scripts/generate_follow_up_draft.py)).
- **Daily summary V0** — dogfood daily payables summary with auto-cleared,
  needs-review, duplicate, missing-backup, oldest/largest unresolved, and
  flagged/recovered money counters
  ([src/freight_recon/summary.py](src/freight_recon/summary.py),
  [scripts/generate_daily_summary.py](scripts/generate_daily_summary.py)).
- **Dogfood pilot runner V0** — one-command local internal pilot flow for
  Neyma Test Freight LLC: regenerate corpus, process workflow, build review
  packets, generate packet pages, apply one gated money action, draft the
  carrier follow-up, and write the daily summary
  ([scripts/run_dogfood_pilot.py](scripts/run_dogfood_pilot.py)).
- **Mock TMS UI/data V0** — local browser-training surface modeled on common
  freight TMS patterns: load board, dispatch navigation, carrier payables queue,
  load detail tabs, accounting fields, documents, notes, and stable selectors for
  browser-use tests ([src/freight_recon/mock_tms.py](src/freight_recon/mock_tms.py),
  [scripts/generate_mock_tms.py](scripts/generate_mock_tms.py)).
- **Mock TMS read adapter V0** — bounded read-only adapter that parses the local
  mock TMS surface into typed load/payable readback models, enforces local-root
  path safety, and fails closed on bad load ids or missing fields
  ([src/freight_recon/tms_adapter.py](src/freight_recon/tms_adapter.py),
  [scripts/read_mock_tms.py](scripts/read_mock_tms.py)).
- **Browser-shaped TMS readback V0** — a Playwright/browser-use-compatible page
  contract for reading the same mock TMS values through stable selectors, with
  fake-page regression coverage and live Playwright MCP verification against the
  local mock TMS ([eval/tests/test_browser_tms_adapter.py](eval/tests/test_browser_tms_adapter.py)).
- **Browser Use production adapter V0** — optional `browser-use[core]==0.13.1`
  dependency plus a read-only `BrowserUseTmsAdapter` skeleton for mock TMS that is
  permission-gated, allowlisted, and validates strict JSON into existing readback models
  ([src/freight_recon/browser_use_adapter.py](src/freight_recon/browser_use_adapter.py),
  [scripts/read_tms_browser_use.py](scripts/read_tms_browser_use.py)).
- **Production browser-agent direction** — use
  [`browser-use/browser-use`](https://github.com/browser-use/browser-use) behind Neyma's adapter,
  permission, audit, and readback boundaries when operating customer TMS screens like a human.
  Playwright stays the cheap local verification layer.
- **Tool permission registry V0** — deterministic workflow-state gate for LLM/tool
  calls with risk tiers, approval requirements, outbound/TMS-write feature gates,
  and auditable allow/block decisions
  ([src/freight_recon/tool_permissions.py](src/freight_recon/tool_permissions.py),
  [scripts/check_tool_permission.py](scripts/check_tool_permission.py)).
- **Delivery adapter V0 with signed action intake** — channel-neutral review
  messages (evidence links, packet URL, exact money buttons, aging, routing/severity,
  found-money) carrying HMAC-signed, expiring, single-use action tokens. Intake verifies
  the signature, rejects tampered/expired tokens, is idempotent on duplicate action ids,
  applies actions through the existing review intake so workflow state cannot be bypassed,
  mutates the message state text, triggers the send-gated follow-up draft, and audits every
  step ([src/freight_recon/delivery.py](src/freight_recon/delivery.py),
  [scripts/deliver_review.py](scripts/deliver_review.py),
  [scripts/submit_signed_action.py](scripts/submit_signed_action.py)).
- **Slack + email transports V0** — Slack Block Kit rendering with `v0` request-signature
  verification and interactive-button intake
  ([src/freight_recon/slack_adapter.py](src/freight_recon/slack_adapter.py)), and multipart
  review emails with signed action links plus a gated local outbox
  ([src/freight_recon/email_adapter.py](src/freight_recon/email_adapter.py)). Both sit on top of
  the signed action intake; neither posts to a real workspace or SMTP server yet.
- **Mock TMS realism** — carrier authority (MC#/USDOT#/SCAC), AP settlement/voucher status
  (PENDING/APPROVED/ON_HOLD/SHORT_PAY/PAID), payment terms, fuel basis, accessorial terms, and a
  required-document checklist, added without changing the read-adapter selector contract
  ([src/freight_recon/mock_tms.py](src/freight_recon/mock_tms.py)).
- **Repeatable channel onboarding V0** — a per-customer `delivery:` block in the client config
  declares channels, severity routing, and env-var **names** for secrets (never secrets). Preflight
  with [scripts/verify_channels.py](scripts/verify_channels.py); build live transports per customer
  with `build_channel_adapters`. Onboarding a customer is a config + secrets runbook
  ([src/freight_recon/channels.py](src/freight_recon/channels.py),
  [docs/CHANNEL_ONBOARDING.md](docs/CHANNEL_ONBOARDING.md)).
- **Inbound email ingestion V0 (Stage 2)** — a synthetic inbound-email corpus (real `.eml` with
  attached PDFs + hidden truth) and an ingestion pipeline that parses each email, classifies
  attachments with confidence, and links them to a known load. The load linker is the safety
  mechanism: a wrong-load or unrelated attachment fails to link and is flagged extraneous, never
  contaminating the packet. Scored against hidden truth (link accuracy, doc-type accuracy, noise
  rejection, missing-doc detection) via [scripts/run_ingestion.py](scripts/run_ingestion.py)
  ([src/freight_recon/email_corpus.py](src/freight_recon/email_corpus.py),
  [src/freight_recon/ingestion.py](src/freight_recon/ingestion.py)).

- **TMS write path V0 (Stage 7)** — enters an already-approved payable into a mock TMS ledger with
  confirm-before-submit, verify-by-readback (only a verified readback reaches `DONE`), per-action
  idempotency, action trace, and tool-permission gating. Injectable failure modes (duplicate →
  `FAILED`, session-expired → `WAITING_FOR_SESSION`, readback-mismatch → `FAILED`). Deterministic
  Python owns the money; this only enters an approved amount
  ([src/freight_recon/tms_write.py](src/freight_recon/tms_write.py),
  [scripts/enter_tms_payable.py](scripts/enter_tms_payable.py)).

Not yet built: a live mailbox watcher (V0 ingests local `.eml`), a vision/content document
classifier (V0 uses filename/subject signals), POD/lumper/accessorial/carrier-packet extraction
schemas, real Slack workspace posting / SMTP send (live egress) on top of the dispatch layer, and
the browser-use execution layer that operates a real/sandbox TMS screen behind the write interface,
plus deployment packaging.

The project should expand into those pieces by stage, not by one giant rewrite.
Before any real client deployment, Neyma should pass an internal dogfood ladder: synthetic
documents, simulated freight company, mock TMS, browser automation against mock TMS, Rasheed as
the first simulated client, and only then design-partner historical/live data.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env   # then fill in your API key
```

Install the production browser-agent extra when working on Browser Use adapters:

```bash
.venv/bin/python -m pip install -e '.[browser-agent]'
```

Set your provider + key in `.env`:

```
EXTRACTION_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

Model selection is configuration-driven. The current production-candidate default is
`anthropic/claude-opus-4-8`; see [Model Strategy](docs/MODEL_STRATEGY.md) before changing model
defaults or treating mock evals as production evidence.

## Run the Phase 1 demo

```bash
# 1. Generate the sample invoice PDF + known-answer JSON
.venv/bin/python scripts/generate_sample_invoice.py

# 2a. Validate the pipeline WITHOUT an API key (render only, no LLM call)
.venv/bin/python scripts/run_extraction.py --render-only

# 2b. Full run: render -> vision extraction -> structured output w/ per-field confidence
#     (requires the API key from step "Setup")
.venv/bin/python scripts/run_extraction.py
```

The full run prints each extracted field with its confidence, flags any field
below the configured `confidence_threshold` (which would route to `NEEDS_REVIEW`
in later phases), and lists accessorial line items individually.

To run against your own invoice PDF:

```bash
.venv/bin/python scripts/run_extraction.py path/to/invoice.pdf
```

## Run the synthetic workflow spine

```bash
.venv/bin/python scripts/generate_realistic_corpus.py --loads 18 --seed 42
.venv/bin/python eval/run_corpus_eval.py --mock-from-truth
.venv/bin/python scripts/run_reconciliation.py
.venv/bin/python scripts/run_workflow.py --reset
.venv/bin/python scripts/run_review.py --record-audit --text --age-hours 48
.venv/bin/python scripts/generate_packet_pages.py
.venv/bin/python scripts/apply_review_action.py 3 APPROVE_EXPECTED_AMOUNT --amount 3334.50
.venv/bin/python scripts/generate_follow_up_draft.py 3 APPROVE_EXPECTED_AMOUNT --record-audit
.venv/bin/python scripts/deliver_review.py --record-audit --text
.venv/bin/python scripts/submit_signed_action.py "<signed-token-from-a-delivered-button>"
.venv/bin/python scripts/generate_daily_summary.py --text
```

`deliver_review.py` renders each review payload into a channel-neutral message with
HMAC-signed, single-use action buttons. `submit_signed_action.py` posts one token back through
signature verification into the workflow, mutating message state and auditing the action — the
same path a real Slack/Teams/email transport will use once added.

The workflow run writes a local SQLite store at
`data/active_workspace/neyma_workflow.sqlite3` and proves that generated carrier
invoice packets move through receive, extract, reconcile, route, and audit steps
without duplicate processing. The review run writes typed payloads to
`data/active_workspace/review_payloads.json` and records an idempotent
`review_payload_created` audit event for each review case. The packet page run writes
`data/active_workspace/site`; serve it locally with:

```bash
.venv/bin/python -m http.server 8000 --directory data/active_workspace/site
```

For the local internal dogfood flow in one command:

```bash
.venv/bin/python scripts/run_dogfood_pilot.py --text
```

That command also writes the mock TMS surface at `data/active_workspace/site/tms`.

To smoke-test TMS readback:

```bash
.venv/bin/python scripts/read_mock_tms.py LD-560003
.venv/bin/python scripts/read_mock_tms.py LD-560003 --payable
.venv/bin/python -m pytest eval/tests/test_browser_tms_adapter.py -q
.venv/bin/python -m pytest eval/tests/test_browser_use_adapter.py -q
.venv/bin/python scripts/read_tms_browser_use.py --help
.venv/bin/python scripts/check_tool_permission.py read_tms_load NEEDS_REVIEW
```

## Adding a document type or a client

- **New document type:** add `configs/doc_types/<type>.yaml`. No code change.
- **New client:** add `configs/clients/<client>.yaml` with a `doc_types:` mapping
  of per-type overrides (e.g. `entry_mapping`, `confidence_threshold`), then run
  with `--client <client>`.

Future workflow packs should follow the same principle: new freight workflows
should add configs, schemas, rules, review surfaces, evals, and adapters without
forking the core engine.

## Layout

```
configs/doc_types/carrier_invoice.yaml   # doc-type config (the spec's format)
src/freight_recon/
  config.py        # YAML -> validated Pydantic config (+ client overlay merge)
  models.py        # Confident[...] fields; dynamic model built from config
  render.py        # PyMuPDF: PDF -> page PNGs
  extraction.py    # Instructor vision extraction (Anthropic/OpenAI), 3-bucket-ready
  reconciliation.py # deterministic invoice/rate/load matching
  workflow.py      # SQLite workflow state, idempotency, and audit events
  review.py        # typed human-review payloads and fallback text renderer
  packet_page.py   # local static packet detail page generator
  review_actions.py # local dogfood review action intake
  follow_up.py     # carrier follow-up drafts behind send gate
  summary.py       # daily dogfood summary
  delivery.py      # channel-neutral delivery adapter + signed action intake
  slack_adapter.py # Slack Block Kit transport over the signed intake
  email_adapter.py # email MIME transport + signed action links + gated outbox
scripts/
  generate_sample_invoice.py   # realistic sample PDF + known-answer JSON
  generate_realistic_corpus.py  # synthetic freight corpus with clean/dirty PDFs
  run_extraction.py            # the Phase 1 demo
  run_reconciliation.py        # deterministic scenario reconciliation
  run_workflow.py              # workflow state/audit/idempotency runner
  run_review.py                # human-review payload generator
  generate_packet_pages.py     # local packet detail site generator
  apply_review_action.py       # local action intake CLI
  generate_follow_up_draft.py  # local send-gated follow-up draft generator
  generate_daily_summary.py    # daily summary generator
  deliver_review.py            # render channel-neutral messages + signed action tokens
  submit_signed_action.py      # verify + apply a signed action token
  run_dogfood_pilot.py         # one-command local internal dogfood pilot
  generate_mock_tms.py         # local mock TMS UI/data generator
  read_mock_tms.py             # bounded mock TMS readback CLI
  read_tms_browser_use.py      # optional browser-use TMS readback CLI
  check_tool_permission.py     # workflow-state tool permission check
data/samples/                  # generated sample + expected answer (golden seed)
```
# freight-operational-teammate
