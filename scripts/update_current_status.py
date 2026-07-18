#!/usr/bin/env python3
"""Finalize the canonical status record after a content commit.

THE TWO-COMMIT CONVENTION. A commit cannot contain its own hash, so a "current commit" field
written by hand is either stale or a lie. This script is the only writer of the volatile status
fields, and it runs at exactly one moment: AFTER the content commit exists, BEFORE the single
status-metadata commit that records it. It reads the truth from git, never from an argument a
human could typo:

    .venv/bin/python scripts/update_current_status.py --passed N --failed 0 --skipped 1

The suite counts are the ONE input git cannot supply. They must come from a real run of the
canonical suite command on the content commit's tree; eval/tests/test_status_reality.py then
cross-checks them against the live collected-test population, so a fabricated count fails the
build even though this script cannot see the run itself.

Files rewritten (this exact set is what the status-metadata commit may touch, and the guard
verifies the metadata commit touched nothing else):
    docs/implementation/CURRENT.md                    - the fenced status-block
    docs/implementation/IMPLEMENTATION-REGISTRY.yaml  - meta.baseline_commit/validated_tree/suite
    docs/implementation/u-handoff-1a-control-correction-review.md - final-state fields (if present)

This is control-plane tooling. It performs no external effect, touches no production runtime
module, and writes only the status files named above.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs" / "implementation" / "CURRENT.md"
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"
REVIEW = ROOT / "docs" / "implementation" / "u-handoff-1a-control-correction-review.md"

# The exact file set a status-metadata commit may touch. test_status_reality.py imports this,
# so the script and the guard cannot drift apart on what "metadata only" means.
STATUS_METADATA_FILES = (
    "docs/implementation/CURRENT.md",
    "docs/implementation/IMPLEMENTATION-REGISTRY.yaml",
    "docs/implementation/u-handoff-1a-control-correction-review.md",
)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--passed", type=int, required=True)
    ap.add_argument("--failed", type=int, required=True)
    ap.add_argument("--skipped", type=int, required=True)
    args = ap.parse_args()

    commit = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")

    # --- CURRENT.md status-block ---------------------------------------------------------------
    text = CURRENT.read_text(encoding="utf-8")
    block = (
        "```yaml\n"
        "# status-block: maintained by scripts/update_current_status.py - do not edit by hand\n"
        f"branch: {branch}\n"
        f"content_commit: {commit}\n"
        f"content_tree: {tree}\n"
        f"suite_passed: {args.passed}\n"
        f"suite_failed: {args.failed}\n"
        f"suite_skipped: {args.skipped}\n"
        "```"
    )
    new = re.sub(r"```yaml\n# status-block:.*?```", block, text, count=1, flags=re.S)
    if new == text and block not in text:
        print("ERROR: status-block not found in CURRENT.md", file=sys.stderr)
        return 1
    CURRENT.write_text(new, encoding="utf-8")

    # --- registry meta -------------------------------------------------------------------------
    text = REGISTRY.read_text(encoding="utf-8")
    text = re.sub(r"^  baseline_commit: .*$", f"  baseline_commit: {commit}", text, count=1, flags=re.M)
    text = re.sub(r"^  validated_tree: .*$", f"  validated_tree: {tree}", text, count=1, flags=re.M)
    text = re.sub(
        r'^  suite: ".*"$',
        f'  suite: "{args.passed} passed, {args.failed} failed, {args.skipped} conditionally justified skip"',
        text, count=1, flags=re.M,
    )
    REGISTRY.write_text(text, encoding="utf-8")

    # --- review-document final-state fields (optional) -----------------------------------------
    if REVIEW.exists():
        text = REVIEW.read_text(encoding="utf-8")
        text = text.replace("CONTENT_COMMIT_INSERTED_BY_FINALIZER", commit)
        text = text.replace("CONTENT_TREE_INSERTED_BY_FINALIZER", tree)
        text = text.replace(
            "SUITE_INSERTED_BY_FINALIZER",
            f"{args.passed} passed · {args.failed} failed · {args.skipped} skipped",
        )
        REVIEW.write_text(text, encoding="utf-8")

    print(f"status finalized against content commit {commit[:9]} (tree {tree[:9]})")
    print("next: commit ONLY the status files as the single status-metadata commit:")
    print("  git add " + " ".join(STATUS_METADATA_FILES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
