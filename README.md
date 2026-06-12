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
- **Human review payloads V0** — typed review cards and actions for variances,
  duplicates, missing PODs, and missing backup, ready for a Slack/Teams/email
  adapter ([src/freight_recon/review.py](src/freight_recon/review.py)).

Not yet built: email/thread ingestion, multi-document packet classification,
POD/lumper/accessorial/carrier-packet extraction schemas, Slack/Teams/email
HITL adapter and signed webhooks, bounded TMS adapters, tool permission
registry, packet detail page, internal dogfood pilot runner, and deployment packaging.

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
.venv/bin/python scripts/run_review.py --record-audit --text
```

The workflow run writes a local SQLite store at
`data/active_workspace/neyma_workflow.sqlite3` and proves that generated carrier
invoice packets move through receive, extract, reconcile, route, and audit steps
without duplicate processing. The review run writes typed payloads to
`data/active_workspace/review_payloads.json` and records an idempotent
`review_payload_created` audit event for each review case.

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
scripts/
  generate_sample_invoice.py   # realistic sample PDF + known-answer JSON
  generate_realistic_corpus.py  # synthetic freight corpus with clean/dirty PDFs
  run_extraction.py            # the Phase 1 demo
  run_reconciliation.py        # deterministic scenario reconciliation
  run_workflow.py              # workflow state/audit/idempotency runner
  run_review.py                # human-review payload generator
data/samples/                  # generated sample + expected answer (golden seed)
```
# freight-operational-teammate
