"""Enter an APPROVED payable into the mock TMS through the gated write path (confirm + readback).

QUARANTINE (EP-12, test-only): this fixture targets ONLY the mock JSON write ledger. It constructs
no live actuator and imports no effect-capable adapter that reaches an external system, so it is
structurally production-unreachable — the earned basis for its import-gate quarantine exemption
(proved by AST, not by a substring, in test_import_gate.py). The former ``--browser`` path drove a
real browser-use agent against an operator-supplied base URL; it was a live-write path wearing a
mock label and was removed at P4 (finding F1)."""

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

from freight_recon.cli_tenant import resolve_cli_tenant
from freight_recon.tms_write import ChargeLine, MockTmsWriteLedger, enter_approved_payable  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_workflow import DEFAULT_DB  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "active_workspace" / "tms_payable_ledger.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None,
                        help="Canonical tenant. Omit only when --client-config names one, whose client_id is used. There is no default.")
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
    parser.add_argument("--slack-thread", action="store_true", help="post execution status as threaded replies under the run's Slack review card")
    parser.add_argument("--client-config", default=None, help="client delivery config (needed with --slack-thread)")
    args = parser.parse_args()

    charges = []
    for raw in args.charge:
        name, _, amount = raw.partition("=")
        charges.append(ChargeLine(name=name, amount=amount))

    store = WorkflowStore(args.db, tenant=resolve_cli_tenant(tenant=getattr(args, "tenant", None), client_config=getattr(args, "client_config", None), context="enter_tms_payable.py"))
    # QUARANTINE: the ONLY write target is the mock JSON ledger. There is no live-write path here —
    # the former browser-use path (a live actuator against an operator-supplied base URL) was removed
    # at P4 so the quarantine exemption is structurally earned, not asserted (F1).
    ledger = MockTmsWriteLedger(args.ledger, fail_modes=frozenset(args.fail_mode))

    from freight_recon.ops_control import OpsControl, TmsWritesPausedError

    ops_control = OpsControl(Path(args.db).parent / "ops_control.json")

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
            ops_control=ops_control,
        )
    except TmsWritesPausedError as exc:
        print(json.dumps({"run_id": args.run_id, "final_state": "HELD", "reason": str(exc)}, indent=2))
        return 0
    finally:
        store.close()
    print(json.dumps(outcome.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
