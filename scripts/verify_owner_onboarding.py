"""Verify whether Neyma is ready for owner-driven Slack onboarding.

Dry mode checks config/secrets/allowlists. With ``--require-running`` it also checks the live workspace
heartbeat/DB/supervisor/browser session. With ``--callback-url`` it signs a Slack slash-command request
to the callback server and verifies that `/neyma status` returns the readiness surface.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional runtime convenience
    pass

from freight_recon.owner_onboarding import evaluate_owner_onboarding, render_owner_onboarding  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "data" / "active_workspace" / "gmail_to_slack_service"
DEFAULT_CLIENT_CONFIG = ROOT / "configs" / "clients" / "rasheed_first_design_partner.yaml"


def _probe(text: str, secret: bytes, url: str, user: str, channel: str) -> tuple[int, str]:
    body = urlencode({"command": "/neyma", "text": text, "user_id": user, "channel_id": channel})
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(secret, f"v0:{ts}:{body}".encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        url,
        data=body.encode(),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read().decode() or "{}")
        return resp.status, str(data.get("text", data))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:500]
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--client-config", default=str(DEFAULT_CLIENT_CONFIG))
    parser.add_argument("--allowed-slack-user", action="append", default=[], help="owner Slack user id allowed to command Neyma")
    parser.add_argument("--allowed-slack-channel", default=os.environ.get("NEYMA_ALLOWED_SLACK_CHANNEL"))
    parser.add_argument("--operation-cdp-url", default=os.environ.get("NEYMA_OPERATION_CDP_URL", "http://localhost:9222"))
    parser.add_argument("--operation-url-filter", default=os.environ.get("NEYMA_OPERATION_URL_FILTER", ""))
    parser.add_argument("--require-running", action="store_true", help="require run_teammate heartbeat/supervisor/DB/browser to be live")
    parser.add_argument("--callback-url", default=None, help="optional callback URL ending in /slack/commands to smoke-test /neyma status")
    parser.add_argument(
        "--require-public-ingress",
        action="store_true",
        help="require --callback-url to be the public HTTPS Slack Request URL, not localhost",
    )
    args = parser.parse_args()

    readiness = evaluate_owner_onboarding(
        workspace=args.workspace,
        client_config=args.client_config,
        env=os.environ,
        allowed_slack_users=tuple(args.allowed_slack_user),
        allowed_slack_channel=args.allowed_slack_channel,
        require_running=args.require_running,
        cdp_url=args.operation_cdp_url,
        operation_url_filter=args.operation_url_filter or None,
        callback_url=args.callback_url,
        require_public_ingress=args.require_public_ingress,
        probe=_probe if args.callback_url else None,
    )
    print(render_owner_onboarding(readiness))
    return 0 if readiness.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
