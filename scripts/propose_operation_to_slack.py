"""Post a real Slack 'Approve & run' button that drives the live browser — the last link of the chain.

This closes "email -> Slack -> live browser" so you can test it end to end:

  1. Run this to post an Approve button into your Slack channel for a bounded operation
     (e.g. invoice a delivered load for a customer at an amount YOU specify).
  2. Tap it in Slack. The action callback (run with --enable-operation-router) verifies your
     signed tap, then the OperationRouter drives the CDP Chrome you have logged into the TMS.
  3. A proof-carrying receipt posts back.

The amount is the figure you pass here (from the rate con / reconciliation) — never model-chosen;
your tap is you approving THAT number. The button is signed, single-use, and channel-bound.

Prereqs: the teammate running with `--enable-operation-router --allowed-slack-user <you>
--allowed-slack-channel <C>`, and a Chrome started with --remote-debugging-port=9222 logged into the TMS.

Example:
  python scripts/propose_operation_to_slack.py --client-config configs/clients/rasheed.json \
      --channel C0123 --lane raise_invoice --customer Acme --load-ref LD-9 --amount 2850.00
"""

from __future__ import annotations

import argparse
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

from freight_recon.channels import build_signer, load_delivery_config  # noqa: E402
from freight_recon.delivery_dispatch import SlackApiPoster  # noqa: E402
from freight_recon.operation_proposal import build_operation_proposal_message, post_operation_proposal  # noqa: E402
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-config", required=True, help="client delivery config (for the signer + Slack token)")
    parser.add_argument("--channel", required=True, help="Slack channel id to post the proposal into")
    parser.add_argument("--lane", required=True, help="bounded lane to run, e.g. raise_invoice / record_payable")
    parser.add_argument("--amount", required=True, help="the human-approvable amount (from the rate con/reconciliation)")
    parser.add_argument("--customer", default=None)
    parser.add_argument("--carrier", default=None)
    parser.add_argument("--load-ref", default=None)
    parser.add_argument("--summary", default=None, help="override the proposal headline")
    args = parser.parse_args()

    config = load_delivery_config(args.client_config)
    if config is None or config.slack is None:
        parser.error("client-config has no Slack config")
    signer = build_signer(config, env=os.environ)
    if signer is None:
        parser.error("could not build a signer from the client-config (delivery secret missing)")
    token = os.environ.get(config.slack.bot_token_env or "")
    if not token:
        parser.error(f"no Slack bot token in env var {config.slack.bot_token_env!r}")

    params: dict = {"lane": args.lane}
    for key, val in (("customer", args.customer), ("carrier", args.carrier), ("load_ref", args.load_ref)):
        if val:
            params[key] = val
    party = args.customer or args.carrier or "the counterparty"
    summary = args.summary or f"Ready to run {args.lane} for {party}" + (f" on {args.load_ref}" if args.load_ref else "")
    intent = CommandIntent(kind=CommandKind.OPERATE, summary=summary, params=params)

    message = build_operation_proposal_message(
        intent, signer, approved_amount=args.amount, channel_id=args.channel,
    )
    result = post_operation_proposal(message, poster=SlackApiPoster(token))
    print(f"Posted proposal to {args.channel}: ok={getattr(result, 'ok', result)}"
          + (f" error={result.error}" if getattr(result, "error", None) else ""))
    print("Tap 'Approve & run' in Slack to drive the live browser (teammate must have --enable-operation-router).")
    return 0 if getattr(result, "ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
