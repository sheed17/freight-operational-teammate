"""Drive the Slack bot the way Slack does — send SIGNED slash commands to the live callback and print
the exact response. Lets us test interactivity ourselves (catch UX/routing bugs) without typing in Slack.

Signs each request with the client's Slack signing secret and posts to the running callback's
/slack/commands, as the authorized owner/channel, so authorization passes just like a real command.

Examples:
  python scripts/slack_probe.py --client-config configs/clients/rasheed_first_design_partner.yaml \
      --user U0BBZ5RS9G8 --channel C0BB8KG21J8 "commands"
  python scripts/slack_probe.py --client-config ... --user ... --channel ... --smoke
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
except Exception:  # pragma: no cover
    pass

from freight_recon.channels import load_delivery_config  # noqa: E402

# A standard interaction sweep — the command surface a user actually types.
_SMOKE = ["commands", "help", "status", "roi", "audit", "know", "autonomy",
          "graduate raise_invoice 2500", "supervise raise_invoice", "show unresolved",
          "sop raise_invoice: always include the load reference", "know about raise_invoice",
          "invoice today's delivered loads", "frobnicate the widget"]


def probe(text: str, *, secret: bytes, url: str, user: str, channel: str, timeout: float = 8.0) -> tuple[int, str]:
    body = urlencode({"command": "/neyma", "text": text, "user_id": user, "channel_id": channel})
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(secret, f"v0:{ts}:{body}".encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        url, data=body.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read().decode() or "{}")
        return resp.status, str(data.get("text", data))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("text", nargs="*", help="the /neyma command text (omit with --smoke)")
    p.add_argument("--client-config", required=True)
    p.add_argument("--user", required=True, help="authorized Slack user id")
    p.add_argument("--channel", required=True, help="authorized Slack channel id")
    p.add_argument("--url", default="http://127.0.0.1:8001/slack/commands")
    p.add_argument("--smoke", action="store_true", help="run the standard command sweep")
    args = p.parse_args()

    config = load_delivery_config(args.client_config)
    if config is None or config.slack is None:
        p.error("client-config has no Slack config")
    secret = os.environ.get(config.slack.signing_secret_env or "")
    if not secret:
        p.error(f"no signing secret in env var {config.slack.signing_secret_env!r}")
    secret_b = secret.encode()

    texts = _SMOKE if args.smoke else [" ".join(args.text)]
    worst = 0
    for t in texts:
        status, reply = probe(t, secret=secret_b, url=args.url, user=args.user, channel=args.channel)
        flag = "OK " if status == 200 else "!! "
        worst = max(worst, 0 if status == 200 else 1)
        first = reply.split("\n")[0][:88]
        print(f"  {flag}[{status}] /neyma {t!r:45} -> {first}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
