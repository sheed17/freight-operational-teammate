"""Generate local packet detail pages for review payloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.packet_page import build_packet_site  # noqa: E402
from freight_recon.review import ReviewPayload  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_review import DEFAULT_OUTPUT as DEFAULT_REVIEW_PAYLOADS  # noqa: E402
from run_workflow import DEFAULT_CORPUS, DEFAULT_DB, load_synthetic_loads  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE = ROOT / "data" / "active_workspace" / "site"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Synthetic corpus directory")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite workflow DB path")
    parser.add_argument("--payloads", default=str(DEFAULT_REVIEW_PAYLOADS), help="Review payload JSON")
    parser.add_argument("--site", default=str(DEFAULT_SITE), help="Output static site directory")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    payload_path = Path(args.payloads)
    site = Path(args.site)
    loads = {load.load_id: load for load in load_synthetic_loads(corpus)}
    payloads = [
        ReviewPayload.model_validate(item)
        for item in json.loads(payload_path.read_text(encoding="utf-8"))
    ]
    store = WorkflowStore(args.db)
    try:
        pages = build_packet_site(
            output_dir=site,
            corpus_dir=corpus,
            store=store,
            loads=loads,
            payloads=payloads,
        )
    finally:
        store.close()

    print(f"Packet pages: {len(pages)}")
    print(f"Site: {site}")
    print("Serve locally with:")
    print(f"  .venv/bin/python -m http.server 8000 --directory {site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
