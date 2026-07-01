"""Give the agent its 'first day' in a TMS — explore it and learn the layout, before any money task.

Read-only reconnaissance over the CDP browser: walk the main navigation, summarize what each section is
for, and store it as SYSTEM knowledge in the shared per-client KnowledgeBase. After this, every task
run recalls the layout, so the agent starts from understanding instead of the deep end.

Example (transporters.io, already logged into the CDP Chrome):
  python scripts/orient_tms.py --url-filter transporters \
      --start-url https://neyma.transporters.io/dashboard/index \
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
from freight_recon.cdp_actuator import CdpActuator  # noqa: E402
from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402
from freight_recon.knowledge import FactKind, KnowledgeBase  # noqa: E402
from freight_recon.screen_discovery import openai_completer  # noqa: E402
from freight_recon.system_orientation import orient_system  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp-url", default="http://localhost:9222")
    parser.add_argument("--url-filter", default="transporters")
    parser.add_argument("--start-url", default=None, help="navigate here before exploring (a stable home)")
    parser.add_argument("--workspace", default="data/active_workspace/gmail_to_slack_service")
    parser.add_argument("--tenant", default="default")
    parser.add_argument("--model", default="gpt-5.4", help="summary model (a cheaper one is fine here)")
    parser.add_argument("--sections", type=int, default=8)
    parser.add_argument("--record-url", default=None,
                        help="a sample record's detail URL (e.g. an order) to go DEEPER and learn its "
                             "action menus — where invoicing/dispatch live")
    args = parser.parse_args()

    kb = KnowledgeBase(Path(args.workspace) / "agent_memory.json")
    completer = openai_completer(model=args.model)

    with CdpBrowserSession(cdp_url=args.cdp_url, url_filter=args.url_filter or None) as session:
        actuator = CdpActuator(session)
        if args.start_url:
            actuator.navigate(args.start_url)
        domain = domain_of(session.evaluate("location.href"))
        print(f"Orienting on {domain} — walking the system (read-only)...\n")
        facts = orient_system(actuator, completer, sections_limit=args.sections, record_url=args.record_url)

    learned = 0
    for f in facts:
        if kb.learn(f, tenant=args.tenant, kind=FactKind.SYSTEM, subject=domain, source="orientation"):
            learned += 1
            print("  learned:", f)
    print(f"\nStored {learned} orientation fact(s) for {domain}. Future tasks will recall these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
