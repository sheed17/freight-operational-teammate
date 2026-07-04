"""Read ready-to-bill loads from the LIVE TMS and post AR invoice Approve buttons to Slack.

The AR trigger, real-TMS sourced (vs the synthetic corpus): it navigates the human-logged-in TMS to its
loads page, reads which loads are delivered-but-not-invoiced and their Total, and posts one signed
"Invoice [Approve & run]" button per load at that Total. A tap then drives the PROVEN raise_invoice
write — so the proposed load_ref always matches a writable record.

Prereqs: the teammate running with --enable-operation-router + allowlist; a Chrome on
--remote-debugging-port=9222 logged into the TMS. Amounts are the loads' Totals (deterministic, from the
TMS) — never model-chosen; your tap approves that figure.

Example:
  python scripts/propose_ar_from_tms.py --client-config configs/clients/rasheed_first_design_partner.yaml \
      --url-filter truckingoffice --loads-url https://secure.truckingoffice.com/loads
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.cdp_actuator import CdpActuator  # noqa: E402
from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402
from freight_recon.channels import load_delivery_config, slack_channel_for_route  # noqa: E402
from freight_recon.delivery_dispatch import SlackApiPoster  # noqa: E402
from freight_recon.operation_proposal import post_operation_proposal, proposals_from_tms_loads  # noqa: E402
from freight_recon.review import ReviewRoute  # noqa: E402

try:
    from run_gmail_to_slack_dogfood import _delivery_signer  # reuse the same signer path
except Exception:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from run_gmail_to_slack_dogfood import _delivery_signer


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client-config", required=True)
    p.add_argument("--cdp-url", default="http://localhost:9222")
    p.add_argument("--url-filter", default="truckingoffice")
    p.add_argument("--loads-url", default="https://secure.truckingoffice.com/loads")
    p.add_argument("--allow-local-dev-secret", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="read + build proposals but do not post to Slack")
    args = p.parse_args()

    config = load_delivery_config(args.client_config)
    if config is None or config.slack is None:
        p.error("client-config has no Slack config")
    channel = slack_channel_for_route(config.slack, ReviewRoute.CHANNEL_POST)
    signer = _delivery_signer(args.client_config, args.allow_local_dev_secret)

    with CdpBrowserSession(cdp_url=args.cdp_url, url_filter=args.url_filter or None) as session:
        act = CdpActuator(session)
        session.evaluate(f"location.href={args.loads_url!r}")
        time.sleep(2.5)
        proposals = proposals_from_tms_loads(act.observe(), signer=signer, channel_id=channel)

    if not proposals:
        print("propose-ar-from-tms: no ready-to-bill loads found (all invoiced, or none delivered).")
        return 0
    print(f"propose-ar-from-tms: {len(proposals)} ready-to-bill load(s) -> invoice button(s):")
    for m in proposals:
        print(f"   - {m.get('text')}")
    if args.dry_run:
        print("(dry-run: not posting)")
        return 0
    token = os.environ.get(config.slack.bot_token_env or "")
    if not token:
        p.error(f"no Slack bot token in env var {config.slack.bot_token_env!r}")
    poster = SlackApiPoster(token)
    posted = 0
    for message in proposals:
        result = post_operation_proposal(message, poster=poster)
        if getattr(result, "ok", False):
            posted += 1
    print(f"propose-ar-from-tms: posted {posted}/{len(proposals)} invoice button(s) to {channel}.")
    return 0 if posted == len(proposals) else 1


if __name__ == "__main__":
    raise SystemExit(main())
