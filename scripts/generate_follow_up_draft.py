"""Generate a carrier follow-up draft behind a send gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.follow_up import build_follow_up_draft, record_follow_up_draft  # noqa: E402
from freight_recon.review import ReviewPayload  # noqa: E402
from freight_recon.review_actions import ReviewDecision  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_review import DEFAULT_OUTPUT as DEFAULT_REVIEW_PAYLOADS  # noqa: E402
from run_workflow import DEFAULT_CORPUS, DEFAULT_DB, load_synthetic_loads  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=int)
    parser.add_argument("decision", choices=[decision.value for decision in ReviewDecision])
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--payloads", default=str(DEFAULT_REVIEW_PAYLOADS))
    parser.add_argument("--record-audit", action="store_true")
    args = parser.parse_args()

    loads = {load.load_id: load for load in load_synthetic_loads(Path(args.corpus))}
    raw_payloads = json.loads(Path(args.payloads).read_text(encoding="utf-8"))
    payload_by_run = {
        payload.run_id: payload
        for payload in (ReviewPayload.model_validate(item) for item in raw_payloads)
    }
    payload = payload_by_run[args.run_id]
    draft = build_follow_up_draft(payload, loads[payload.load_id], ReviewDecision(args.decision))
    if args.record_audit:
        store = WorkflowStore(args.db)
        try:
            record_follow_up_draft(store, draft)
        finally:
            store.close()
    print(json.dumps(draft.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
