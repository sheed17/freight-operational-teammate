"""Read ready-to-bill loads from the LIVE TMS and post AR invoice Approve buttons to Slack.

The AR trigger, real-TMS sourced (vs the synthetic corpus): navigate the human-logged-in TMS to its
loads page, read which loads are delivered-but-not-invoiced and their Total, and post one signed
"Invoice [Approve & run]" button per load at that Total. A tap then drives the PROVEN raise_invoice
write — so the proposed load_ref always matches a writable record.

Runs once, or continuously with --interval-seconds. Coordinated + idempotent:
- --lock-path: DEFER a cycle while the write-agent holds the shared browser (never navigate mid-write).
- --db: dedup so a still-un-invoiced load isn't re-proposed every cycle (recorded as invoice_proposal_posted).

Prereqs: the teammate running with --enable-operation-router + allowlist; a Chrome on
--remote-debugging-port=9222 logged into the TMS. Amounts are the loads' Totals (deterministic).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.browser_lock import BrowserLock  # noqa: E402
from freight_recon.cdp_actuator import CdpActuator  # noqa: E402
from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402
from freight_recon.channels import load_delivery_config, slack_channel_for_route  # noqa: E402
from freight_recon.delivery_dispatch import SlackApiPoster  # noqa: E402
from freight_recon.operation_proposal import post_operation_proposal, proposals_from_tms_loads  # noqa: E402
from freight_recon.review import ReviewRoute  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_gmail_to_slack_dogfood import _delivery_signer  # noqa: E402

_INVOICE_PROPOSED_EVENT = "invoice_proposal_posted"


def _cycle(*, act, signer, channel, loads_url, store, lock, live, poster) -> int:
    """One pass: defer if the browser is busy; else read /loads, build + post AR invoice buttons."""
    if lock is not None and lock.is_busy():
        print("propose-ar-from-tms: browser busy (a write is in progress) — deferring this cycle.")
        return 0
    act.session.evaluate(f"location.href={loads_url!r}")
    time.sleep(2.5)
    proposals = proposals_from_tms_loads(act.observe(), signer=signer, channel_id=channel)
    if store is not None:
        already = {
            e["payload"].get("load_ref")
            for e in store.security_events()
            if e["event_type"] == _INVOICE_PROPOSED_EVENT
        }
        proposals = [m for m in proposals if m.get("load_ref") not in already]
    if not proposals:
        print("propose-ar-from-tms: no new ready-to-bill loads.")
        return 0
    if not live:
        for m in proposals:
            print("   -", m.get("text"))
        print(f"(dry-run: would post {len(proposals)} button(s))")
        return 0
    posted = 0
    for message in proposals:
        result = post_operation_proposal(message, poster=poster)
        if getattr(result, "ok", False):
            posted += 1
            if store is not None:
                store.add_security_event(
                    _INVOICE_PROPOSED_EVENT, actor="system",
                    payload={"load_ref": message.get("load_ref"), "channel_id": channel},
                )
    print(f"propose-ar-from-tms: posted {posted}/{len(proposals)} invoice button(s) to {channel}.")
    return posted


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client-config", required=True)
    p.add_argument("--cdp-url", default="http://localhost:9222")
    p.add_argument("--url-filter", default="truckingoffice")
    p.add_argument("--loads-url", default="https://secure.truckingoffice.com/loads")
    p.add_argument("--allow-local-dev-secret", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="read + build proposals but do not post")
    p.add_argument("--db", default=None, help="WorkflowStore path for dedup (don't re-propose a load)")
    p.add_argument("--lock-path", default=None, help="browser-busy marker to defer to an in-progress write")
    p.add_argument("--interval-seconds", type=int, default=0, help="0 = run once; >0 = loop on this interval")
    args = p.parse_args()

    config = load_delivery_config(args.client_config)
    if config is None or config.slack is None:
        p.error("client-config has no Slack config")
    channel = slack_channel_for_route(config.slack, ReviewRoute.CHANNEL_POST)
    signer = _delivery_signer(args.client_config, args.allow_local_dev_secret)
    live = not args.dry_run
    poster = None
    if live:
        token = os.environ.get(config.slack.bot_token_env or "")
        if not token:
            p.error(f"no Slack bot token in env var {config.slack.bot_token_env!r}")
        poster = SlackApiPoster(token)
    lock = BrowserLock(args.lock_path) if args.lock_path else None

    with CdpBrowserSession(cdp_url=args.cdp_url, url_filter=args.url_filter or None) as session:
        act = CdpActuator(session)
        while True:
            store = WorkflowStore(args.db) if args.db else None
            try:
                _cycle(act=act, signer=signer, channel=channel, loads_url=args.loads_url,
                       store=store, lock=lock, live=live, poster=poster)
            finally:
                if store is not None:
                    store.close()
            if args.interval_seconds <= 0:
                break
            time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
