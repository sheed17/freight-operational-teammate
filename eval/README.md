# Stage 1 Eval Harness

The golden-set scorer that decides whether carrier-invoice extraction is accurate enough
to move from Stage 1 to Stage 2. PDF in → extracted fields out → compare to known-correct
→ score → actionable report. No state machine, DB, Slack, or Browser Use — eval only.

## Layout

```
eval/
├── golden_set/
│   ├── documents/          # invoice PDFs (3 synthetic fixtures now; add real ones)
│   ├── ground_truth.json   # human-verified correct values per filename
│   ├── make_synthetic.py   # regenerates the synthetic fixtures + mock runs (no deps beyond PyMuPDF)
│   ├── mock_v1.json         # injected extractions w/ deliberate errors (harness self-test)
│   └── mock_v2.json         # "tuned prompt" run — two required-field errors fixed
├── configs/carrier_invoice.yaml   # fields, descriptions, extraction prompt, threshold
├── extraction.py           # PyMuPDF render + Instructor/Anthropic vision → validated Pydantic
├── evaluator.py            # per-field scoring, confidence calibration, failure categorization
├── report.py               # 6-section Rich report + pass/fail gate, plus compare view
├── run_eval.py             # entry point
├── add_to_golden_set.py    # interactive ground-truth builder
└── requirements.txt
```

## Setup

```bash
pip install -r eval/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # needed only for real extraction (not --mock)
# Model defaults to EVAL_MODEL, then ANTHROPIC_MODEL, then claude-opus-4-8.
```

> Model note: real eval should use the same production-candidate model as runtime extraction.
> Override `EVAL_MODEL` only for intentional bakeoffs. Mock evals do not use a model.

## Add a real document to the golden set

```bash
python eval/add_to_golden_set.py path/to/real_invoice.pdf
# renders each page to a PNG you open, prompts for each field's verified value,
# copies the PDF into golden_set/documents/, appends to ground_truth.json.
```

## Run the full eval

```bash
python eval/run_eval.py                          # full eval over the golden set
python eval/run_eval.py --doc invoice_007.pdf    # single document (debugging)
python eval/run_eval.py --save eval/results/run_$(date +%Y%m%d).json
python eval/run_eval.py --compare a.json b.json  # compare two saved runs (prompt v1 vs v2)
```

Exit code is `0` when the production gate passes, `1` when it doesn't — usable in CI.

## Test the harness itself (no API key)

```bash
python eval/golden_set/make_synthetic.py                       # 3 synthetic PDFs + ground truth + mocks
python eval/run_eval.py --mock eval/golden_set/mock_v1.json    # score injected extractions
python eval/run_eval.py --mock eval/golden_set/mock_v1.json --save eval/results/v1.json
python eval/run_eval.py --mock eval/golden_set/mock_v2.json --save eval/results/v2.json
python eval/run_eval.py --compare eval/results/v1.json eval/results/v2.json
```

`--mock` runs the full scoring/report path on hand-written extractions, so you can confirm the
math before trusting it on real accuracy numbers. The two mock files are designed to exercise
every report section: a clean doc, an overconfident wrong required field, a truncated PRO, a
missed fuel surcharge, a partially-missed accessorial list — and v2 shows the gate flipping to
PASS once the required-field errors are fixed.

## Test the harness's own math

The scoring/calibration/categorization logic is regression-protected by `pytest`:

```bash
python -m pytest eval/tests -q
```

These tests anchor the numbers the Stage 1 gate depends on — per-field scoring (including the
identifier exact-match rule and numeric tolerance), accessorial matching, failure-mode
categorization, and the end-to-end gate verdict on the committed `mock_v1`/`mock_v2` fixtures
(v1 must fail with exactly two required-field overconfidence cases; v2 must pass). If a refactor
changes how a field is scored, these break before the harness can silently report wrong accuracy.

## What the report tells you (6 sections)

1. **Overall summary** — docs, failures, fields, overall accuracy, production-ready verdict.
2. **Per-field accuracy** — correct/wrong/missing, accuracy, avg confidence, status per field.
3. **Confidence calibration** — accuracy by confidence bucket + an explicit **overconfidence
   alert** (confidence ≥0.85 but wrong) — the dangerous failure mode for a money system.
4. **Failure-mode breakdown** — NOT_FOUND / WRONG_VALUE / FORMAT_ERROR / LABEL_VARIATION /
   LAYOUT_UNUSUAL / MULTI_PAGE_MISS / MODEL_ERROR, by field.
5. **Actionable recommendations** — what to tune, weakest fields first.
6. **Document-level results** — per-file correct/total and which fields failed.

## Production-readiness gate (Stage 1 → Stage 2)

All must hold:
- Required fields (`load_or_pro_number`, `linehaul_amount`, `total_amount`) each **≥90%**.
- **Zero** dangerous overconfidence (confidence ≥0.85 AND wrong) on a required field.
- Overall accuracy across all fields **≥85%**.
- High-confidence bucket **≥85%** actually accurate.

Optional fields (`fuel_surcharge`, `accessorials`) below 80% are flagged for tuning but do not
block. The synthetic `mock_v1` run intentionally **fails** the gate (overconfident wrong
required fields); `mock_v2` **passes** it.

## Scoring rules

- Numeric fields: `$0.01` tolerance. Strings like `"$1,150.00"` are parsed before comparing.
- Dates: normalized to `YYYY-MM-DD` (several input formats accepted) before comparing.
- Descriptive strings (`carrier_name`): stripped + lowercased; near-matches count as correct.
- **Identifier strings (`load_or_pro_number`, `invoice_number`): exact match required** — a
  truncated reference (`L-449` vs `L-44982`) is a real error, not a near-match.
- Accessorials: matched by name regardless of order, amount within tolerance.
