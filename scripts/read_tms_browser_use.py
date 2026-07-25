"""Read mock TMS through the Browser Use adapter.

Requires optional dependency:
    .venv/bin/python -m pip install '.[browser-agent]'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.browser_use_adapter import BrowserUseConfig, BrowserUseTmsAdapter  # noqa: E402
from freight_recon.tool_permissions import ToolContext  # noqa: E402
from freight_recon.workflow import WorkflowState  # noqa: E402


async def _run(args: argparse.Namespace) -> None:
    adapter = BrowserUseTmsAdapter(
        config=BrowserUseConfig(
            base_url=args.base_url,
            allowed_domains=tuple(args.allowed_domain),
            headless=args.headless,
        ),
        tool_context=ToolContext(workflow_state=WorkflowState(args.workflow_state), actor=args.actor),
    )
    result = await adapter.read_payable(args.load_id) if args.payable else await adapter.read_load(args.load_id)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("load_id")
    parser.add_argument("--payable", action="store_true")
    parser.add_argument("--base-url", default="http://localhost:8000/tms")
    parser.add_argument("--allowed-domain", action="append", default=["localhost", "127.0.0.1"])
    parser.add_argument("--workflow-state", default=WorkflowState.NEEDS_REVIEW.value)
    parser.add_argument("--actor", default="browser-use")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
