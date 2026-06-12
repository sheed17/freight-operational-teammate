# Synthetic Freight Corpus

Neyma should not wait on real client documents to build the core system. We generate a realistic
freight corpus that is close enough to reality to expose extraction, reconciliation, document
classification, and workflow failures before a real pilot.

## Principle

Use real public freight document formats for structure, but never use confidential operational
business data.

Allowed:

- Blank public templates.
- Public sample forms.
- Training forms.
- Public government/industry templates.
- Public sample PDFs where the layout is the only thing used.

Not allowed:

- Real customer/carrier invoices that appear accidentally indexed.
- Private TMS exports.
- Real load data.
- Real shipper/customer/carrier financial details.
- Anything that looks like live confidential business data.

If a public PDF has incidental real data, use it only as a layout reference and replace every
business value with synthetic data.

## Current V0 Generator

Script:

```bash
.venv/bin/python scripts/generate_realistic_corpus.py --loads 18 --seed 42
```

Output:

```text
data/synthetic_corpus/
  clean/
  dirty/
  ground_truth/
    carrier_invoice_extraction.json
    loads_and_scenarios.json
```

The generated corpus includes:

- Carrier invoices.
- Rate confirmations.
- Bills of lading.
- Proofs of delivery.
- Lumper receipts when applicable.
- Fuel receipts on some loads.
- Manifests.
- Clean PDFs.
- Dirty scan-like PDF variants.
- Hidden extraction truth.
- Load-level scenario truth.

Scenarios include:

- Clean match.
- Unauthorized detention.
- Fuel mismatch.
- Linehaul mismatch.
- Missing lumper backup.
- Duplicate invoice candidate.
- Missing POD.
- Extra authorized stop-off.

## Template Pattern Sources

These are examples of public layout patterns to use for template inspiration or future approved
template assets:

- Rate confirmation/load tender structure: public broker/shipper load tender and rate
  confirmation samples.
- BOL short-form structure: public short-form BOL templates from government/industry sources.
- POD structure: public proof-of-delivery templates.
- Lumper/accessorial logic: public carrier instruction docs and accessorial schedules.
- Driver scan mess: public driver-document instructions that describe phone scan issues,
  angled pictures, and document submission problems.

When adding direct template assets later, store only approved blank/sample templates under a
dedicated ignored/source-controlled policy path and document the source URL, license/usage
assumption, and any fields that are overlaid with synthetic data.

Suggested future structure:

```text
data/template_sources/
  approved_public_templates/
  template_registry.json
```

Do not commit downloaded templates unless they are clearly public and appropriate to store in
the repo. Prefer storing source metadata plus generated synthetic outputs.

## Public Template Downloader

To download approved public blank/sample templates for layout reference:

```bash
.venv/bin/python scripts/download_public_freight_templates.py
```

This writes:

```text
data/template_sources/downloaded/          # gitignored raw PDFs
data/template_sources/template_registry.json
```

The downloaded PDFs are for layout analysis only. The generator must supply synthetic data.
Do not use any incidental real business values from downloaded files.

## Corpus Eval

List generated invoice docs:

```bash
.venv/bin/python eval/run_corpus_eval.py --list
```

Validate eval wiring with perfect injected predictions and no API:

```bash
.venv/bin/python eval/run_corpus_eval.py --mock-from-truth
```

Run real vision extraction against the generated clean and dirty invoice corpus:

```bash
.venv/bin/python eval/run_corpus_eval.py --save eval/results/corpus_real.json
```

Run deterministic reconciliation over generated load scenarios:

```bash
.venv/bin/python scripts/run_reconciliation.py
```

This consumes `ground_truth/loads_and_scenarios.json` and classifies generated loads into
`MATCHED`, `VARIANCE`, `NEEDS_REVIEW`, or `DUPLICATE` using deterministic Python logic.

Run the current workflow spine over generated invoice packets:

```bash
.venv/bin/python scripts/run_workflow.py --reset
```

This writes a local SQLite store under `data/active_workspace/`, creates one workflow run per
generated carrier invoice, applies SHA-256 idempotency, routes reconciliation outcomes into
terminal or review states, and records audit events for receive, extract, reconcile, and route.

Generate human-review payloads for workflow cases that require supervision:

```bash
.venv/bin/python scripts/run_review.py --record-audit --text
```

This writes `data/active_workspace/review_payloads.json`, prints plain-text review cards, and
records idempotent review-payload audit events. These payloads are channel-neutral so Slack,
Teams, and email adapters can render them later without changing the workflow core.

## Why Dirty Variants Matter

Real freight paperwork is often:

- Scanned from a phone.
- Slightly skewed.
- Low-resolution.
- Black-and-white.
- Blurry.
- JPEG-compressed.
- Partially washed out.

The generator creates dirty variants by rendering clean PDFs to images and applying:

- grayscale conversion
- slight rotation/skew
- blur
- brightness/contrast variation
- downsample/upsample artifacts
- JPEG compression artifacts

This gives the extraction system a more realistic failure surface.

## Next Improvements

1. Add more template families per document type.
2. Add direct overlay support for approved blank PDF templates.
3. Add multi-page document packets.
4. Add email-thread generation with attachments.
5. Add handwritten/signature/noisy stamp overlays.
6. Add clipped/cropped photo scan variants.
7. Add a fixture runner that evaluates clean vs dirty extraction accuracy separately.
8. Add reconciliation scenario tests that consume `loads_and_scenarios.json`.
9. Add human-review payload fixtures from workflow outcomes.
10. Add Slack/Teams/email adapter fixture delivery for review payloads.
