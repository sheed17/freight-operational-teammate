"""Let the embedded Operator Agent drive a live TMS on its own — observe -> reason -> act -> verify.

This is "the system drives it, not the dev in a sidebar": a reasoning model (the brain) plugged into the
real CDP Actuator (the hands), money-fenced and approval-gated. Point it at any TMS already logged into
the CDP Chrome and give it a goal.

Safety defaults are conservative:
  - the model never chooses a money value (the approved amount is substituted),
  - consequential actions (Save/Submit/Pay) ESCALATE unless --approve-consequential is set (supervised),
  - bounded steps; ESCALATE/exhaustion fail closed.

Example (supervised, frontier driver):
  python scripts/run_operator_agent.py --goal "Create a customer invoice for Northbound at the approved amount" \
      --model gpt-4o --approved-amount 2850.00 --url-filter transporters --approve-consequential
"""

from __future__ import annotations

import argparse
import json
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
from freight_recon.operator_agent import LiveAction, OperatorAgent  # noqa: E402
from freight_recon.screen_discovery import openai_completer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goal", required=True, help="what the agent should accomplish")
    parser.add_argument("--cdp-url", default="http://localhost:9222")
    parser.add_argument("--url-filter", default="", help="substring to pick the right tab (e.g. 'transporters')")
    parser.add_argument("--model", default="gpt-4o", help="the DRIVER (brain) model — use a frontier model")
    parser.add_argument("--start-url", default=None, help="navigate here before the agent starts")
    parser.add_argument("--approved-amount", default=None, help="the human-approved amount the money fence binds")
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument(
        "--approve-consequential",
        action="store_true",
        help="SUPERVISED ONLY: auto-approve the committing action. Off = the agent escalates instead of committing.",
    )
    args = parser.parse_args()

    approve = (lambda action: True) if args.approve_consequential else None

    def on_consequential(action: LiveAction) -> bool:
        # Visible audit line before any committing action runs.
        print(f"  [GATE] consequential action requested: {action.kind.value} {action.target!r}"
              f" -> {'APPROVED (supervised)' if approve else 'no approver -> will escalate'}")
        return bool(approve and approve(action))

    with CdpBrowserSession(cdp_url=args.cdp_url, url_filter=args.url_filter or None) as session:
        actuator = CdpActuator(session)
        if args.start_url:
            actuator.navigate(args.start_url)
        agent = OperatorAgent(
            actuator=actuator,
            complete=openai_completer(model=args.model),
            approved_amount=args.approved_amount,
            approve=on_consequential if args.approve_consequential else None,
            max_steps=args.max_steps,
        )
        print(f"Agent driving (model={args.model}) toward: {args.goal}\n")
        result = agent.run(args.goal)

    print("\n=== AGENT RUN ===")
    print(f"status: {result.status}")
    print(f"note:   {result.note}")
    print("steps:")
    for i, step in enumerate(result.steps, 1):
        print(f"  {i}. {json.dumps(step)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
