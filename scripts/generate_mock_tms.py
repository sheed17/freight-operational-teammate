"""Generate the local mock TMS UI/data from the synthetic freight world."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.mock_tms import build_mock_tms_site  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_workflow import load_synthetic_loads  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data" / "synthetic_corpus"
DEFAULT_DB = ROOT / "data" / "active_workspace" / "neyma_workflow.sqlite3"
DEFAULT_OUT = ROOT / "data" / "active_workspace" / "site" / "tms"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    loads = load_synthetic_loads(Path(args.corpus))
    store = WorkflowStore(args.db)
    try:
        site = build_mock_tms_site(
            output_dir=Path(args.out),
            corpus_dir=Path(args.corpus),
            loads=loads,
            store=store,
        )
    finally:
        store.close()

    print(f"Mock TMS: {site.output_dir}")
    print(f"Records: {len(site.records)}")
    print(f"Index: {Path(site.output_dir) / 'index.html'}")
    print(f"Data: {Path(site.output_dir) / 'data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
