"""Render channel-neutral delivery messages (with signed action tokens) from review payloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.cli_tenant import resolve_cli_tenant
from freight_recon.delivery import (  # noqa: E402
    DeliveryChannel,
    DeliverySigner,
    build_delivery_message,
    record_delivery_message,
    render_delivery_message,
    redact_delivery_message,
)
from freight_recon.review import ReviewPayload  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_review import DEFAULT_OUTPUT as DEFAULT_REVIEW_PAYLOADS  # noqa: E402
from run_workflow import DEFAULT_DB  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None,
                        help="Canonical tenant. Omit only when --client-config names one, whose client_id is used. There is no default.")
    parser.add_argument("--payloads", default=str(DEFAULT_REVIEW_PAYLOADS))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--channel", default=DeliveryChannel.LOCAL.value, choices=[c.value for c in DeliveryChannel])
    parser.add_argument("--actor", default="Rasheed")
    parser.add_argument("--run-id", type=int, help="Render only this run id")
    parser.add_argument("--record-audit", action="store_true", help="Audit delivered messages")
    parser.add_argument("--text", action="store_true", help="Print rendered messages")
    parser.add_argument("--ttl-seconds", type=int, default=None, help="Override token TTL")
    parser.add_argument(
        "--show-tokens",
        action="store_true",
        help="Print raw signed action tokens for local manual testing",
    )
    args = parser.parse_args()

    signer = DeliverySigner.from_env(allow_local_dev=True)
    raw = json.loads(Path(args.payloads).read_text(encoding="utf-8"))
    payloads = [ReviewPayload.model_validate(item) for item in raw]
    if args.run_id is not None:
        payloads = [p for p in payloads if p.run_id == args.run_id]

    store = WorkflowStore(args.db, tenant=resolve_cli_tenant(tenant=getattr(args, "tenant", None), client_config=getattr(args, "client_config", None), context="deliver_review.py")) if args.record_audit else None
    messages = []
    try:
        for payload in payloads:
            message = build_delivery_message(
                payload,
                signer,
                channel=DeliveryChannel(args.channel),
                actor=args.actor,
                ttl_seconds=args.ttl_seconds,
            )
            if store is not None:
                record_delivery_message(store, message)
            messages.append(message if args.show_tokens else redact_delivery_message(message))
            if args.text:
                print()
                print(render_delivery_message(messages[-1]))
                print("-" * 80)
    finally:
        if store is not None:
            store.close()

    print(json.dumps([m.model_dump(mode="json") for m in messages], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
