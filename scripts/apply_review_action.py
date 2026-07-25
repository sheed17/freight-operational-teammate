"""Apply a local dogfood review action to a workflow run."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.cli_tenant import resolve_cli_tenant
from freight_recon.review_actions import ReviewActionRequest, ReviewDecision, apply_review_action  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_workflow import DEFAULT_DB  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None,
                        help="Canonical tenant. Omit only when --client-config names one, whose client_id is used. There is no default.")
    parser.add_argument("run_id", type=int)
    parser.add_argument("decision", choices=[decision.value for decision in ReviewDecision])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--actor", default="Rasheed")
    parser.add_argument("--amount", type=Decimal)
    parser.add_argument("--note")
    args = parser.parse_args()

    store = WorkflowStore(args.db, tenant=resolve_cli_tenant(tenant=getattr(args, "tenant", None), client_config=getattr(args, "client_config", None), context="apply_review_action.py"))
    try:
        result = apply_review_action(
            store,
            ReviewActionRequest(
                run_id=args.run_id,
                decision=ReviewDecision(args.decision),
                actor=args.actor,
                amount=args.amount,
                note=args.note,
            ),
        )
    finally:
        store.close()
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
