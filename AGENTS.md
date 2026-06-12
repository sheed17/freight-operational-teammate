# Codex Project Instructions

This repo is the **Neyma Freight Ops Agentic Workflow Engine**: an AI operational
teammate for freight and logistics teams with roughly 5-50 employees.

The long-term product is broader than invoice extraction. Neyma should read email/PDF
threads, classify freight documents, extract structured operational data, reconcile it
against source-of-truth systems, route exceptions to humans, and eventually execute
approved work inside the customer's existing tools.

The first teammate family is Document & Data Entry. The first production workflow inside it is
carrier-invoice-to-rate-con reconciliation because it has direct ROI and creates the primitives
needed for adjacent document workflows: BOL data entry, rate confirmation processing, POD
capture/filing, customer invoice generation, fuel receipts, and manifest data entry.

Read these before major planning or architecture work:

- `docs/NEYMA_VISION.md`
- `docs/PRODUCT_ROADMAP.md`
- `docs/AGENTIC_ARCHITECTURE.md`
- `docs/DESIGN_PARTNER_PILOT.md`
- `docs/WHEN_DESIGN_PARTNER_DATA_ARRIVES.md`
- `docs/BUILD_SUPERVISION_PROTOCOL.md`
- `docs/SYNTHETIC_CORPUS.md`
- `docs/MODEL_STRATEGY.md`
- `docs/INTERNAL_DOGFOOD_PILOT.md`

## Current Phase

The project is in **Stage 5 V0 — Human review payloads**, using the realistic synthetic corpus
as the development proving ground.

Stage 1 extraction still needs a real/client-approved document validation gate before live
production claims, but core development should continue through the operational workflow spine.
The next product slice is Review Payload V2 for the internal dogfood pilot: evidence links,
packet detail URL, unambiguous money actions, aging metadata, severity routing, and found-money
fields.

Built now:

- Config-driven carrier invoice extraction.
- Confidence-scored Pydantic models.
- PyMuPDF rendering.
- Instructor-based vision extraction.
- Stage 1 eval harness with synthetic fixtures, mocks, report, and regression tests.
- Realistic synthetic freight corpus generator with clean/dirty PDFs and hidden truth.
- Deterministic reconciliation V0 for generated load scenarios.
- SQLite-backed workflow state/audit/idempotency V0 for carrier invoice reconciliation.
- Channel-agnostic human review payloads for variances, duplicates, missing POD, and missing
  backup.

Not built yet:

- Email/thread ingestion.
- Multi-document packet classification.
- POD, BOL, lumper, accessorial-backup, rate-con, and carrier-packet schemas.
- Slack/Teams/email human-in-the-loop adapter and signed webhooks.
- Minimal packet detail page and internal dogfood client simulation.
- Mock TMS and browser automation against mock TMS before any real TMS.
- Tool permission registry.
- Browser/TMS read or write agent.
- Deployment packaging.

Do not wait on real client documents for core development. Advance Stage 1 using the realistic
synthetic freight corpus while keeping a later real-client validation gate before unsupervised
production use.

## Stage 1 Gate

Stage 1 development is done when extraction on a realistic generated corpus of public-template-
inspired, synthetic carrier invoices is accurate enough on required fields, across clean and dirty
scan variants:

- `load_or_pro_number`
- `linehaul_amount`
- `total_amount`

The eval gate requires:

- Required fields each at least 90% accurate.
- Zero dangerous overconfidence on required fields.
- Overall accuracy at least 85%.
- High-confidence predictions at least 85% actually accurate.

Old tiny mock success is useful harness validation, but it is not enough. The richer synthetic
corpus is the development gate; later design-partner or customer docs become the production
validation gate.

## Commands To Verify

Use the project venv because plain `python` may not be on PATH:

```bash
.venv/bin/python -m pytest eval/tests -q
.venv/bin/python scripts/run_extraction.py --render-only
.venv/bin/python eval/run_eval.py --mock eval/golden_set/mock_v1.json
.venv/bin/python eval/run_eval.py --mock eval/golden_set/mock_v2.json
```

Generate the realistic synthetic freight corpus:

```bash
.venv/bin/python scripts/generate_realistic_corpus.py --loads 18 --seed 42
.venv/bin/python eval/run_corpus_eval.py --mock-from-truth
.venv/bin/python scripts/run_reconciliation.py
.venv/bin/python scripts/run_workflow.py --reset
.venv/bin/python scripts/run_review.py --record-audit
```

Real API eval, after `.env` has `ANTHROPIC_API_KEY`:

```bash
.venv/bin/python eval/run_eval.py --save eval/results/real_$(date +%Y%m%d).json
```

If real/client-approved invoices arrive later, add them to the golden set:

```bash
.venv/bin/python eval/add_to_golden_set.py path/to/real_invoice.pdf
```

## Model Strategy

Runtime extraction defaults to Anthropic with `ANTHROPIC_MODEL=claude-opus-4-8`. Real API evals
should use the same production-candidate model unless intentionally running a bakeoff with
`EVAL_MODEL`.

Mock evals do not use a model and are only harness validation. Use `docs/MODEL_STRATEGY.md` before
changing model defaults or claiming production extraction readiness.

## Non-Negotiable Rules

1. Structured output everywhere: Pydantic + Instructor, never free-text parsing.
2. Matching is deterministic Python, never LLM judgment.
3. Every document outcome must land in a clear bucket with confidence and reason.
4. Variances and low-confidence items require a human gate before consequential action.
5. Idempotency is SHA-256 of file content.
6. TMS automation uses a human-established session, never stored credentials.
7. Never mark entry complete until data is read back and verified.
8. Browser/TMS agents must be bounded by allowlists, timeouts, and early confirm-before-submit.
9. Keep a queryable audit trail for extraction, matching, approvals, disputes, and entry.
10. New doc types or clients should be config changes, not code forks.
11. Keep deployment portable across VM and in-office machine paths.
12. Workflow state controls tool access. Risky tools require explicit approval and audit.
13. LangChain/native tool calling is for LLM-accessible tools and retrieval; LangGraph/state
    machine owns workflow control; deterministic Python owns money decisions.

## Product Build Direction

Build toward workflow packs:

1. Carrier invoice reconciliation.
2. POD packet review.
3. Lumper/accessorial validation.
4. BOL data entry.
5. Rate confirmation processing.
6. Customer invoice generation.
7. Fuel receipt processing.
8. Manifest data entry.
9. Billing-ready packet assembly.
10. Carrier packet completeness.
11. Missing-document follow-up.
12. TMS read/write execution for approved work.

Each workflow pack needs schemas, deterministic rules, review UX, state transitions,
eval fixtures, audit events, and a production gate.

## Known Alignment Watch

The runtime config uses `load_or_pro`; the eval harness uses `load_or_pro_number`.
Before Stage 2 matching, align this naming or add an explicit translation layer so the
money path does not split into two field dialects.

## Codex Posture

When working in this repo, read the code first, run the relevant verification command, and
call out gate status honestly. "Almost" is a failed gate. Browser/TMS work must start against
mock TMS and only graduate to real/sandbox TMS after adapter, permission, audit, and readback
tests pass.

## Build Supervision

Substantial build work should follow `docs/BUILD_SUPERVISION_PROTOCOL.md`.

Use two roles conceptually:

- Implementing agent: builds the feature.
- Principal architect supervisor: audits production readiness, design-partner fit, tool
  permissioning, evals, and architecture.

The supervisor's Codex-facing prompt is `.codex/agents/principal-architect-supervisor.md`.
