"""Generate the internal dogfood daily summary."""

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
from freight_recon.review import ReviewPayload, ReviewRoute  # noqa: E402
from freight_recon.roi_ledger import build_value_digest, render_value_digest  # noqa: E402
from freight_recon.summary import build_daily_summary, render_daily_summary  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_review import DEFAULT_OUTPUT as DEFAULT_REVIEW_PAYLOADS  # noqa: E402
from run_workflow import DEFAULT_DB  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "active_workspace" / "daily_summary.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None,
                        help="Canonical tenant. Omit only when --client-config names one, whose client_id is used. There is no default.")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--payloads", default=str(DEFAULT_REVIEW_PAYLOADS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--text", action="store_true")
    parser.add_argument("--post-slack", action="store_true", help="post the digest to the configured digest Slack channel")
    parser.add_argument("--client-config", default=None, help="client delivery config (needed with --post-slack)")
    args = parser.parse_args()

    payloads = [
        ReviewPayload.model_validate(item)
        for item in json.loads(Path(args.payloads).read_text(encoding="utf-8"))
    ]
    store = WorkflowStore(args.db, tenant=resolve_cli_tenant(tenant=getattr(args, "tenant", None), client_config=getattr(args, "client_config", None), context="generate_daily_summary.py"))
    try:
        summary = build_daily_summary(store, payloads)
        # Fold the AP reconciliation numbers in with the agent-operation receipts into one ROI digest.
        value_digest = build_value_digest(store, daily=summary)
    finally:
        store.close()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary.model_dump(mode="json"), indent=2), encoding="utf-8")
    print(f"Wrote: {output}")
    text = render_daily_summary(summary) + "\n\n" + render_value_digest(value_digest, period="today")
    if args.text:
        print()
        print(text)

    if args.post_slack:
        if not args.client_config:
            parser.error("--post-slack requires --client-config")
        from freight_recon.channels import load_delivery_config, slack_channel_for_route
        from freight_recon.delivery_dispatch import post_text_to_slack

        config = load_delivery_config(args.client_config)
        if config is None or config.slack is None:
            parser.error("--client-config has no Slack config; cannot post the digest")
        channel = slack_channel_for_route(config.slack, ReviewRoute.DIGEST_ONLY)
        result = post_text_to_slack(text, channel=channel, config=config, env=os.environ)
        print(f"Slack digest post: ok={result.ok}" + (f" error={result.error}" if result.error else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
