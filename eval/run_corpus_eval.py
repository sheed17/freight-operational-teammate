"""Run the Stage 1 invoice extraction eval against the generated freight corpus.

This bridges `scripts/generate_realistic_corpus.py` into the existing eval harness.

Usage:
    .venv/bin/python eval/run_corpus_eval.py --list
    .venv/bin/python eval/run_corpus_eval.py --mock-from-truth
    .venv/bin/python eval/run_corpus_eval.py --save eval/results/corpus_real.json

Real extraction requires ANTHROPIC_API_KEY. `--mock-from-truth` validates the eval wiring with
perfect injected predictions and no API call.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extraction import ExtractionResult, coerce_mock, extract_document, load_config  # noqa: E402
from evaluator import evaluate  # noqa: E402
import report as report_mod  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data" / "synthetic_corpus"
CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "carrier_invoice.yaml"


def _truth_path(corpus: Path) -> Path:
    return corpus / "ground_truth" / "carrier_invoice_extraction.json"


def _load_truth(corpus: Path) -> dict:
    path = _truth_path(corpus)
    if not path.exists():
        raise FileNotFoundError(
            f"Corpus truth not found: {path}. Run scripts/generate_realistic_corpus.py first."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Older generator versions used bare filenames. Current generated files are still unique, so
    # resolve them by searching clean/dirty directories.
    return raw


def _resolve_pdf(corpus: Path, filename: str) -> Path:
    candidates = [
        corpus / "clean" / filename,
        corpus / "dirty" / filename,
        corpus / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No PDF found for {filename} under {corpus}/clean or {corpus}/dirty")


def _as_mock_extraction(truth: dict) -> dict:
    return {
        "invoice_number": {"value": truth.get("invoice_number"), "confidence": 0.99},
        "carrier_name": {"value": truth.get("carrier_name"), "confidence": 0.99},
        "load_or_pro_number": {"value": truth.get("load_or_pro_number"), "confidence": 0.99},
        "linehaul_amount": {"value": truth.get("linehaul_amount"), "confidence": 0.99},
        "fuel_surcharge": {"value": truth.get("fuel_surcharge"), "confidence": 0.99},
        "accessorials": [
            {"name": item["name"], "amount": item["amount"], "confidence": 0.99}
            for item in truth.get("accessorials", [])
        ],
        "total_amount": {"value": truth.get("total_amount"), "confidence": 0.99},
        "invoice_date": {"value": truth.get("invoice_date"), "confidence": 0.99},
    }


def _run_real(corpus: Path, truth: dict, config, only_doc: str | None) -> list[ExtractionResult]:
    names = [only_doc] if only_doc else sorted(truth)
    results: list[ExtractionResult] = []
    for name in names:
        pdf = _resolve_pdf(corpus, name)
        print(f"  extracting {pdf.relative_to(corpus)} ...", file=sys.stderr)
        result = extract_document(pdf, config)
        # The eval truth keys include dirty/clean-distinguishing filenames; keep exact key.
        result.filename = name
        results.append(result)
    return results


def _run_mock(truth: dict, config, only_doc: str | None) -> list[ExtractionResult]:
    names = [only_doc] if only_doc else sorted(truth)
    return [
        coerce_mock(name, _as_mock_extraction(truth[name]), config)
        for name in names
        if name in truth
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Generated corpus directory")
    parser.add_argument("--doc", help="Run a single corpus invoice filename")
    parser.add_argument("--list", action="store_true", help="List corpus invoice docs and exit")
    parser.add_argument("--mock-from-truth", action="store_true", help="Score perfect injected predictions; no API")
    parser.add_argument("--save", help="Save eval report JSON")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    truth = _load_truth(corpus)
    config = load_config(CONFIG_PATH)

    if args.list:
        for name in sorted(truth):
            pdf = _resolve_pdf(corpus, name)
            print(f"{name}\t{pdf.relative_to(corpus)}")
        return 0

    if args.mock_from_truth:
        print(f"  (mock-from-truth mode — {len(truth)} document(s), no API calls)\n", file=sys.stderr)
        results = _run_mock(truth, config, args.doc)
    else:
        results = _run_real(corpus, truth, config, args.doc)

    eval_report = evaluate(results, truth, config)
    report_mod.render(eval_report)

    if args.save:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(eval_report.to_dict(), indent=2), encoding="utf-8")
        print(f"Saved results to {out}", file=sys.stderr)

    return 0 if eval_report.production_ready() else 1


if __name__ == "__main__":
    raise SystemExit(main())
