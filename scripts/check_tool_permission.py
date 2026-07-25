"""Check whether a tool is allowed in a workflow state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.tool_permissions import ToolContext, evaluate_tool_permission  # noqa: E402
from freight_recon.workflow import WorkflowState  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool_name")
    parser.add_argument("workflow_state", choices=[state.value for state in WorkflowState])
    parser.add_argument("--approval-granted", action="store_true")
    parser.add_argument("--outbound-enabled", action="store_true")
    parser.add_argument("--tms-write-enabled", action="store_true")
    parser.add_argument("--actor", default="system")
    args = parser.parse_args()

    decision = evaluate_tool_permission(
        args.tool_name,
        ToolContext(
            workflow_state=WorkflowState(args.workflow_state),
            actor=args.actor,
            approval_granted=args.approval_granted,
            outbound_enabled=args.outbound_enabled,
            tms_write_enabled=args.tms_write_enabled,
        ),
    )
    print(json.dumps(decision.model_dump(mode="json"), indent=2))
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
