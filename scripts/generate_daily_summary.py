"""Generate the internal dogfood daily summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.review import ReviewPayload  # noqa: E402
from freight_recon.summary import build_daily_summary, render_daily_summary  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_review import DEFAULT_OUTPUT as DEFAULT_REVIEW_PAYLOADS  # noqa: E402
from run_workflow import DEFAULT_DB  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "active_workspace" / "daily_summary.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--payloads", default=str(DEFAULT_REVIEW_PAYLOADS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--text", action="store_true")
    args = parser.parse_args()

    payloads = [
        ReviewPayload.model_validate(item)
        for item in json.loads(Path(args.payloads).read_text(encoding="utf-8"))
    ]
    store = WorkflowStore(args.db)
    try:
        summary = build_daily_summary(store, payloads)
    finally:
        store.close()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary.model_dump(mode="json"), indent=2), encoding="utf-8")
    print(f"Wrote: {output}")
    if args.text:
        print()
        print(render_daily_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
