"""Submit a signed delivery action token back into the workflow (local dogfood)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.cli_tenant import resolve_cli_tenant
from freight_recon.delivery import DeliverySigner, submit_signed_action  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_workflow import DEFAULT_CORPUS, DEFAULT_DB, load_synthetic_loads  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None,
                        help="Canonical tenant. Omit only when --client-config names one, whose client_id is used. There is no default.")
    parser.add_argument("token", help="Signed action token from a delivery message button")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument(
        "--no-follow-up",
        action="store_true",
        help="Do not draft a follow-up even when the action requires one",
    )
    args = parser.parse_args()

    signer = DeliverySigner.from_env(allow_local_dev=True)
    follow_up_loads = None
    if not args.no_follow_up:
        follow_up_loads = {load.load_id: load for load in load_synthetic_loads(Path(args.corpus))}

    store = WorkflowStore(args.db, tenant=resolve_cli_tenant(tenant=getattr(args, "tenant", None), client_config=getattr(args, "client_config", None), context="submit_signed_action.py"))
    try:
        outcome = submit_signed_action(
            store,
            args.token,
            signer=signer,
            follow_up_loads=follow_up_loads,
        )
    finally:
        store.close()
    print(json.dumps(outcome.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
