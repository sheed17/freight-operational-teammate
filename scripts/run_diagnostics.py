#!/usr/bin/env python3
"""Diagnose a stored Neyma operation run trace.

Input is a JSON file shaped like one of the operation receipts/audit artifacts:

{
  "status": "FAILED",
  "note": "did not finish within 20 steps",
  "steps": [{"action": "CLICK", "target": "Save", "ok": false}]
}

The command is intentionally read-only. It turns the trace into the same owner-readable diagnosis used
inside Slack receipts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon.run_diagnostics import diagnose_run, render_diagnosis  # noqa: E402


def _load_trace(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"trace file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("trace JSON must be an object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_json", help="path to a JSON trace with status/note/steps")
    parser.add_argument("--json", action="store_true", help="emit structured diagnosis JSON")
    args = parser.parse_args(argv)

    try:
        trace = _load_trace(Path(args.trace_json))
    except Exception as exc:  # noqa: BLE001
        print(f"diagnostics: {exc}", file=sys.stderr)
        return 2

    diag = diagnose_run(
        trace.get("steps") or [],
        status=str(trace.get("status") or "UNKNOWN"),
        note=str(trace.get("note") or ""),
    )
    if args.json:
        print(json.dumps({
            "outcome": diag.outcome,
            "summary": diag.summary,
            "repeated_failures": diag.repeated_failures,
            "dead_ends": diag.dead_ends,
            "exhausted_steps": diag.exhausted_steps,
            "suggested_fixes": diag.suggested_fixes,
        }, indent=2, sort_keys=True))
    else:
        print(render_diagnosis(diag))
    return 0 if diag.is_clean() else 1


if __name__ == "__main__":
    raise SystemExit(main())
