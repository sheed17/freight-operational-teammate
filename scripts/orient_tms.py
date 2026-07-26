"""Give the agent its 'first day' in a TMS — observe it and learn the layout, before any money task.

STRUCTURALLY read-only (P4 EP-8, R-07 containment). This tool observes the page the CDP browser is
already showing, summarizes the operational layout, and stores it as SYSTEM knowledge in the shared
per-client KnowledgeBase. After this, every task run recalls the layout, so the agent starts from
understanding instead of the deep end.

It holds a `ReadOnlyCdpObserver` [[cdp_readonly]], which has no evaluate, command, navigate, click,
type or upload method. This script therefore CANNOT actuate the TMS — not "must not", cannot. That
is the point of EP-8: it was previously read-only BY CONVENTION while importing `CdpActuator`, and
a convention one edit away from a live write is not containment.

What that costs, stated plainly: it no longer walks INTO each section, and no longer expands a
record's action menus to find where invoicing lives. Both need clicks, and a model-chosen click on
an unfamiliar TMS can be a money action rather than a tour stop. That deeper walk is RETAINED in
`system_orientation.orient_system` / `orient_record_actions` for the authorized actuator-capable
caller behind the effect boundary — it is not deleted, it is out of THIS tool's reach.

Point the browser at the page you want understood (a stable home/dashboard) before running.

Example (transporters.io, already logged into the CDP Chrome):
  python scripts/orient_tms.py --url-filter transporters \
      --workspace data/active_workspace/gmail_to_slack_service --model gpt-5.4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.agent_memory import domain_of  # noqa: E402
from freight_recon.cdp_readonly import ReadOnlyCdpObserver  # noqa: E402
from freight_recon.knowledge import FactKind, KnowledgeBase  # noqa: E402
from freight_recon.screen_discovery import openai_completer  # noqa: E402
from freight_recon.system_orientation import orient_observed  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp-url", default="http://localhost:9222")
    parser.add_argument("--url-filter", default="transporters")
    parser.add_argument("--workspace", default="data/active_workspace/gmail_to_slack_service")
    parser.add_argument("--tenant", default="default")
    parser.add_argument("--model", default="gpt-5.4", help="summary model (a cheaper one is fine here)")
    parser.add_argument("--sections", type=int, default=8)
    args = parser.parse_args()

    kb = KnowledgeBase(Path(args.workspace) / "agent_memory.json")
    completer = openai_completer(model=args.model)

    with ReadOnlyCdpObserver(cdp_url=args.cdp_url, url_filter=args.url_filter or None) as observer:
        domain = domain_of(observer.current_url())
        print(f"Orienting on {domain} — observing the system (read-only)...\n")
        facts = orient_observed(observer, completer, sections_limit=args.sections)

    learned = 0
    for f in facts:
        if kb.learn(f, tenant=args.tenant, kind=FactKind.SYSTEM, subject=domain, source="orientation"):
            learned += 1
            print("  learned:", f)
    print(f"\nStored {learned} orientation fact(s) for {domain}. Future tasks will recall these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
