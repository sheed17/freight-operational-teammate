"""Stage 1 eval entry point.

Usage:
    python eval/run_eval.py                         # full eval over the golden set
    python eval/run_eval.py --doc invoice_007.pdf   # single document (debugging)
    python eval/run_eval.py --save results/run.json # run and save results
    python eval/run_eval.py --compare a.json b.json # compare two saved runs
    python eval/run_eval.py --mock mock.json        # score injected extractions (no API)

--mock takes a JSON file mapping filename -> raw extraction dict (same shape the model
returns). It runs the full scoring/report path with zero API calls — this is how the
harness is tested before trusting it on real accuracy numbers, and works with no key.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python eval/run_eval.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from extraction import DEFAULT_MODEL, ExtractionResult, coerce_mock, extract_document, load_config  # noqa: E402
from evaluator import evaluate  # noqa: E402
import report as report_mod  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
CONFIG_PATH = EVAL_DIR / "configs" / "carrier_invoice.yaml"
DOCS_DIR = EVAL_DIR / "golden_set" / "documents"
GROUND_TRUTH_PATH = EVAL_DIR / "golden_set" / "ground_truth.json"


def _load_ground_truth() -> dict:
    if not GROUND_TRUTH_PATH.exists():
        return {}
    return json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))


def _run_full(ground_truth: dict, config, only_doc: str | None) -> list[ExtractionResult]:
    results: list[ExtractionResult] = []
    names = [only_doc] if only_doc else sorted(ground_truth.keys())
    for name in names:
        pdf = DOCS_DIR / name
        if not pdf.exists():
            results.append(ExtractionResult(name, "FAILED", error="PDF not found in golden_set/documents"))
            continue
        print(f"  extracting {name} ...", file=sys.stderr)
        results.append(extract_document(pdf, config))
    return results


def _run_mock(mock_path: str, ground_truth: dict, config, only_doc: str | None) -> list[ExtractionResult]:
    mock = json.loads(Path(mock_path).read_text(encoding="utf-8"))
    names = [only_doc] if only_doc else sorted(mock.keys())
    return [coerce_mock(name, mock[name], config) for name in names if name in mock]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--doc", help="Run a single document by filename")
    parser.add_argument("--save", help="Save results JSON to this path")
    parser.add_argument("--compare", nargs=2, metavar=("OLD", "NEW"), help="Compare two saved result JSONs")
    parser.add_argument("--mock", help="Score injected extractions from a JSON file (no API calls)")
    args = parser.parse_args()

    if args.compare:
        old = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        new = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        report_mod.render_compare(old, new, Path(args.compare[0]).name, Path(args.compare[1]).name)
        return 0

    config = load_config(CONFIG_PATH)
    ground_truth = _load_ground_truth()
    if not ground_truth:
        print("No ground truth found. Add documents with add_to_golden_set.py first.", file=sys.stderr)
        return 2

    if args.mock:
        results = _run_mock(args.mock, ground_truth, config, args.doc)
        print(f"  (mock mode — {len(results)} document(s), no API calls, model={DEFAULT_MODEL} unused)\n",
              file=sys.stderr)
    else:
        results = _run_full(ground_truth, config, args.doc)

    eval_report = evaluate(results, ground_truth, config)
    report_mod.render(eval_report)

    if args.save:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(eval_report.to_dict(), indent=2), encoding="utf-8")
        print(f"Saved results to {out}", file=sys.stderr)

    return 0 if eval_report.production_ready() else 1


if __name__ == "__main__":
    raise SystemExit(main())
