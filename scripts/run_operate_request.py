"""The full Version-B loop, live: a natural-language REQUEST -> bounded goal -> agent drives -> receipt.

This is what "a request comes in and the agent performs it" looks like end to end, on a real TMS:

    request text  ->  interpret_command (intent)  ->  OperationRouter picks a KNOWN lane
                  ->  OperatorAgent drives the live TMS (money-fenced + approval-gated)  ->  receipt

Boundaries enforced (all reused, none new):
  - a request that matches no known lane is REFUSED, not improvised;
  - a money lane with no --approved-amount ESCALATES at the door (the model never picks a figure);
  - the committing action ESCALATES unless --approve-consequential is set (supervised).

Example (supervised):
  python scripts/run_operate_request.py --request "invoice today's delivered load for Acme" \
      --customer Acme --model gpt-5.5 --approved-amount 2850.00 --url-filter transporters \
      --approve-consequential
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.cdp_actuator import CdpActuator  # noqa: E402
from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402
from freight_recon.operation_router import OperationRouter, freight_lanes  # noqa: E402
from freight_recon.operator_agent import LiveAction, OperatorAgent  # noqa: E402
from freight_recon.screen_discovery import openai_completer  # noqa: E402
from freight_recon.slack_delegate import interpret_command  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, help="the owner's natural-language request")
    parser.add_argument("--cdp-url", default="http://localhost:9222")
    parser.add_argument("--url-filter", default="", help="substring to pick the right tab (e.g. 'transporters')")
    parser.add_argument(
        "--model",
        default=os.getenv("NEYMA_OPERATION_MODEL", "gpt-5.5"),
        help="the DRIVER (brain) model — use a frontier agentic model",
    )
    parser.add_argument("--customer", default=None, help="customer param for an invoice lane")
    parser.add_argument("--carrier", default=None, help="carrier param for a payable lane")
    parser.add_argument("--load-ref", default=None, help="the load reference")
    parser.add_argument("--approved-amount", default=None, help="the human-approved amount (binds the money fence)")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument(
        "--approve-consequential", action="store_true",
        help="SUPERVISED ONLY: auto-approve the committing action. Off = the agent escalates instead.",
    )
    args = parser.parse_args()

    approve = (lambda action: True) if args.approve_consequential else None

    def on_consequential(action: LiveAction) -> bool:
        print(f"  [GATE] consequential: {action.kind.value} {action.target!r}"
              f" -> {'APPROVED (supervised)' if approve else 'no approver -> escalate'}")
        return bool(approve and approve(action))

    completer = openai_completer(model=args.model)
    intent = interpret_command(args.request, complete=completer)
    # Surface request params the lanes use to render a precise goal.
    for key, val in (("customer", args.customer), ("carrier", args.carrier), ("load_ref", args.load_ref)):
        if val:
            intent.params[key] = val

    print(f"Request:  {args.request!r}")
    print(f"Intent:   {intent.kind.value} — {intent.summary!r}\n")

    with CdpBrowserSession(cdp_url=args.cdp_url, url_filter=args.url_filter or None) as session:
        actuator = CdpActuator(session)

        def build_agent(*, approved_amount=None, approve=None, prepare_only=False):
            return OperatorAgent(
                actuator=actuator, complete=completer, approved_amount=approved_amount,
                approve=on_consequential if approve else None, max_steps=args.max_steps,
                prepare_only=prepare_only,
            )

        router = OperationRouter(
            lanes=freight_lanes(), build_agent=build_agent,
            approved_amount_for=lambda _i: args.approved_amount,
        )
        result = router.run(intent, approve=approve)

    print("\n=== OPERATION RESULT ===")
    print(result.to_slack())
    print(f"\nstatus: {result.status}  lane: {result.lane}")
    for i, step in enumerate(result.steps, 1):
        print(f"  {i}. {json.dumps(step)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
