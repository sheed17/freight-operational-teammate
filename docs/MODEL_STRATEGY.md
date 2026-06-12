# Model Strategy

Neyma should evaluate the same model it intends to deploy. Mock evals are useful for testing the
scoring harness, but they are not evidence that the production extraction model is ready.

## Current Repo Default

Runtime extraction defaults to:

```text
EXTRACTION_PROVIDER=anthropic
ANTHROPIC_MODEL=claude-opus-4-8
```

The older eval harness now follows the same Anthropic production-candidate model by default:

```text
EVAL_MODEL -> ANTHROPIC_MODEL -> claude-opus-4-8
```

Mock eval commands still make zero API calls and do not use the model.

## How To Navigate Model Choice

Use three lanes:

1. **Harness and workflow development**
   - Use mocks and synthetic ground truth.
   - Goal: prove schemas, scoring, reconciliation, workflow state, review payloads, and audit.
   - This does not prove model accuracy.

2. **Production-candidate extraction validation**
   - Run real API evals with the exact model configured for deployment.
   - Save the model name, provider, prompt/config version, and eval report.
   - No model can be called production-ready until it passes the gate on realistic clean and dirty
     documents, then later on client-approved documents.

3. **Bakeoff lane**
   - Compare model candidates on the same PDFs, same prompts, same fields, and same scorer.
   - Select the cheapest/fastest model that clears the required-field and overconfidence gates.
   - Keep a stronger model available as a fallback for low-confidence or failed extractions.

## Recommended Initial Policy

Start with the strongest reliable vision model as the primary extraction candidate so the system
earns trust first. Optimize cost only after the workflow is correct and the eval set is large
enough to measure tradeoffs.

For this repo today:

- Primary candidate: `anthropic/claude-opus-4-8`.
- Cost/latency challenger: `anthropic/claude-sonnet-4-6`.
- OpenAI challenger: configure `EXTRACTION_PROVIDER=openai` and `OPENAI_MODEL` only after the
  OpenAI extraction path is evaluated against the same corpus.

Do not fine-tune yet. First use better prompts, schemas, rendering, document-type routing,
client config, and deterministic validation. Fine-tuning only becomes attractive after we have
hundreds or thousands of labeled examples and can prove it beats prompting/retrieval/config on
field accuracy, overconfidence, cost, or latency.

## Production Gate

For whichever model is selected:

- Required fields each at least 90% accurate.
- Zero dangerous overconfidence on required money/reference fields.
- Overall accuracy at least 85%.
- High-confidence bucket at least 85% actually accurate.
- Dirty scans must be evaluated separately from clean PDFs.
- Every low-confidence or variance case routes to human review.

The production model choice is an eval-backed configuration decision, not a belief.
