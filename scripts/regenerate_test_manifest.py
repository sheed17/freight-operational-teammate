#!/usr/bin/env python3
"""Regenerate the exact test-node manifest - an EXPLICIT, INTENTIONAL act.

THE EXACT-POPULATION CORRECTION (U-HANDOFF-1C, H-2). A count can stay identical while 31 tests
are swapped out from under it. docs/implementation/TEST-NODE-MANIFEST.json therefore records the
EXACT collected node identities under the canonical pytest configuration, and every canonical
execution compares its own collection to this manifest by identity: missing nodes, extra nodes
and same-count substitutions all fail.

Regeneration NEVER happens automatically - not during finalization, not during test runs. When
tests legitimately change, a human (or an agent inside an approved unit) runs this script, reviews
the printed diff, and commits the manifest alongside the test change. A finalization against a
stale manifest fails loudly, which is the point: the manifest is the reviewed record of what the
suite is supposed to contain.

Usage: .venv/bin/python scripts/regenerate_test_manifest.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "implementation" / "TEST-NODE-MANIFEST.json"
CANONICAL_CONFIG = ROOT / "pytest-canonical.ini"


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def canonical_env() -> dict:
    env = dict(os.environ)
    env["PYTEST_ADDOPTS"] = ""  # H-2: never inherit ambient filtering
    return env


def collect_node_ids() -> list[str]:
    r = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "-m", "pytest",
         "-c", str(CANONICAL_CONFIG), "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True, env=canonical_env(),
    )
    nodes = [l.strip() for l in r.stdout.split("\n")
             if re.match(r"^eval/.*::", l.strip())]
    if not nodes:
        raise SystemExit(f"collection produced zero nodes - refusing to write an empty manifest\n{r.stdout[-800:]}")
    return sorted(set(nodes))


def main() -> int:
    nodes = collect_node_ids()
    old_nodes: set[str] = set()
    if MANIFEST.exists():
        old_nodes = set(json.loads(MANIFEST.read_text())["node_ids"])
    added = sorted(set(nodes) - old_nodes)
    removed = sorted(old_nodes - set(nodes))

    data = {
        "config": "pytest-canonical.ini",
        "config_sha256": file_sha(CANONICAL_CONFIG),
        "runner_sha256": file_sha(ROOT / "scripts" / "run_canonical_suite.py"),
        "node_count": len(nodes),
        "node_ids": nodes,
    }
    data["manifest_sha256"] = hashlib.sha256(
        json.dumps({k: v for k, v in data.items() if k != "manifest_sha256"},
                   sort_keys=True).encode()
    ).hexdigest()
    MANIFEST.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    print(f"manifest regenerated: {len(nodes)} nodes")
    if added:
        print(f"  +{len(added)} added:   " + " ".join(added[:5]) + (" ..." if len(added) > 5 else ""))
    if removed:
        print(f"  -{len(removed)} removed: " + " ".join(removed[:5]) + (" ..." if len(removed) > 5 else ""))
    if not added and not removed and old_nodes:
        print("  (node set unchanged; hashes refreshed)")
    print("review the diff, then commit the manifest WITH the test change it records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
