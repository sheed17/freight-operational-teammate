"""Generate human-review payloads from the synthetic workflow run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.review import build_review_payload, record_review_payload, render_text_review  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore  # noqa: E402
from run_workflow import DEFAULT_CORPUS, DEFAULT_DB, load_synthetic_loads  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "active_workspace" / "review_payloads.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Synthetic corpus directory")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite workflow DB path")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="JSON output path")
    parser.add_argument("--record-audit", action="store_true", help="Record review payload audit events")
    parser.add_argument("--text", action="store_true", help="Print plain-text review cards")
    parser.add_argument("--age-hours", type=int, default=0, help="Simulated unresolved age for review items")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    db = Path(args.db)
    output = Path(args.output)

    loads = {load.load_id: load for load in load_synthetic_loads(corpus)}
    store = WorkflowStore(db)
    payloads = []
    try:
        for run in store.list_runs():
            if run.state != WorkflowState.NEEDS_REVIEW:
                continue
            load = loads.get(run.load_id)
            if not load:
                raise RuntimeError(f"load context not found for workflow run {run.id}: {run.load_id}")
            payload = build_review_payload(run, load, age_hours=args.age_hours)
            if payload is None:
                continue
            if args.record_audit:
                record_review_payload(store, payload)
            payloads.append(payload)

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps([payload.model_dump(mode="json") for payload in payloads], indent=2),
            encoding="utf-8",
        )
        print(f"Review payloads: {len(payloads)}")
        print(f"Wrote: {output}")
        if args.text:
            for payload in payloads:
                print()
                print(render_text_review(payload))
                print("-" * 80)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
