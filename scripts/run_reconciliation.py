"""Run deterministic reconciliation over the generated synthetic freight corpus."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.reconciliation import FreightLoadForReconciliation, reconcile_many  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRUTH = ROOT / "data" / "synthetic_corpus" / "ground_truth" / "loads_and_scenarios.json"


def load_corpus(path: Path) -> list[FreightLoadForReconciliation]:
    if not path.exists():
        raise FileNotFoundError(f"load scenario truth not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", default=str(DEFAULT_TRUTH), help="loads_and_scenarios.json path")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text report")
    args = parser.parse_args()

    truth_path = Path(args.truth)
    loads = load_corpus(truth_path)
    results = reconcile_many(loads)

    if args.json:
        print(json.dumps([result.model_dump(mode="json") for result in results], indent=2))
        return 0

    counts = Counter(result.outcome.value for result in results)
    print(f"Reconciled {len(results)} load(s) from {truth_path}")
    print("Outcomes:", ", ".join(f"{key}={counts[key]}" for key in sorted(counts)))
    print()
    for result in results:
        print(f"{result.outcome.value:<12} {result.load_id:<10} {result.invoice_number:<12} {result.carrier}")
        for reason in result.reasons:
            print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
