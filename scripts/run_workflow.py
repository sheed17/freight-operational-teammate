"""Run the synthetic freight corpus through workflow state/audit V0."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.workflow import WorkflowStore, process_load_packet  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data" / "synthetic_corpus"
DEFAULT_DB = ROOT / "data" / "active_workspace" / "neyma_workflow.sqlite3"


def load_synthetic_loads(corpus: Path) -> list[FreightLoadForReconciliation]:
    truth = corpus / "ground_truth" / "loads_and_scenarios.json"
    if not truth.exists():
        raise FileNotFoundError(f"synthetic load truth not found: {truth}")
    raw = json.loads(truth.read_text(encoding="utf-8"))
    return [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Synthetic corpus directory")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite workflow DB path")
    parser.add_argument("--reset", action="store_true", help="Delete existing DB before run")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    db = Path(args.db)
    if args.reset and db.exists():
        db.unlink()

    loads = load_synthetic_loads(corpus)
    store = WorkflowStore(db)
    seen_invoice_keys: set[tuple[str, str]] = set()
    try:
        for load in loads:
            rel = load.documents.get("carrier_invoice")
            if not rel:
                raise RuntimeError(f"load {load.load_id} has no carrier_invoice document")
            process_load_packet(
                store,
                load,
                primary_document_path=corpus / rel,
                seen_invoice_keys=seen_invoice_keys,
            )

        runs = store.list_runs()
        counts = Counter(run.state.value for run in runs)
        outcomes = Counter(run.outcome or "UNSET" for run in runs)
        print(f"Workflow DB: {db}")
        print(f"Runs: {len(runs)}")
        print("States:", ", ".join(f"{key}={counts[key]}" for key in sorted(counts)))
        print("Outcomes:", ", ".join(f"{key}={outcomes[key]}" for key in sorted(outcomes)))
        print(f"Audit events: {len(store.audit_events())}")
        print()
        for run in runs:
            print(f"{run.state.value:<12} {run.load_id:<10} {run.outcome or '-':<12} {run.reason or ''}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
