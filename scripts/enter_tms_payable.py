"""Enter an APPROVED payable into the mock TMS through the gated write path (confirm + readback)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.tms_write import ChargeLine, MockTmsWriteLedger, enter_approved_payable  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_workflow import DEFAULT_DB  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "active_workspace" / "tms_payable_ledger.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=int)
    parser.add_argument("--amount", required=True)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--charge", action="append", default=[], help="name=amount (repeatable)")
    parser.add_argument(
        "--fail-mode",
        action="append",
        default=[],
        choices=["duplicate", "session_expired", "readback_mismatch"],
        help="inject a mock TMS failure mode for drills",
    )
    parser.add_argument("--no-write-enabled", action="store_true", help="simulate the TMS-write feature gate being off")
    parser.add_argument("--browser", action="store_true", help="execute the write through browser-use against a writable mock TMS (not the JSON ledger)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8012", help="writable mock TMS base URL (with --browser)")
    parser.add_argument("--model", default=None, help="browser-use LLM model (with --browser)")
    parser.add_argument("--no-headless", action="store_true", help="show the browser window (with --browser)")
    parser.add_argument("--browser-verify", action="store_true", help="verify-by-readback via the agent instead of a deterministic read (less reliable)")
    parser.add_argument("--slack-thread", action="store_true", help="post execution status as threaded replies under the run's Slack review card")
    parser.add_argument("--client-config", default=None, help="client delivery config (needed with --slack-thread)")
    args = parser.parse_args()

    charges = []
    for raw in args.charge:
        name, _, amount = raw.partition("=")
        charges.append(ChargeLine(name=name, amount=amount))

    store = WorkflowStore(args.db)
    if args.browser:
        from freight_recon.browser_use_adapter import (
            BrowserUseWriteLedger,
            NativeBrowserUseRunner,
            http_payable_readback,
        )

        # Agent operates the form (write); verify-by-readback is a deterministic, independent read.
        readback_fn = None if args.browser_verify else (lambda lid: http_payable_readback(args.base_url, lid))
        ledger = BrowserUseWriteLedger(
            runner=NativeBrowserUseRunner(model=args.model),
            base_url=args.base_url,
            headless=not args.no_headless,
            readback_fn=readback_fn,
        )
    else:
        ledger = MockTmsWriteLedger(args.ledger, fail_modes=frozenset(args.fail_mode))

    on_status = None
    if args.slack_thread:
        if not args.client_config:
            parser.error("--slack-thread requires --client-config")
        from freight_recon.channels import load_delivery_config
        from freight_recon.delivery_dispatch import slack_thread_status_poster

        config = load_delivery_config(args.client_config)
        if config is None or config.slack is None:
            parser.error("--client-config has no Slack delivery config; cannot post thread status")
        on_status = slack_thread_status_poster(store, config, env=os.environ)

    try:
        outcome = enter_approved_payable(
            store,
            ledger,
            args.run_id,
            amount=args.amount,
            charges=charges,
            tms_write_enabled=not args.no_write_enabled,
            on_status=on_status,
        )
    finally:
        store.close()
    print(json.dumps(outcome.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
