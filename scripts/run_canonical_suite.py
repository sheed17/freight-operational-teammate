#!/usr/bin/env python3
"""Run the canonical suite and write the machine-readable result artifact.

This is the ONLY sanctioned producer of docs/implementation/SUITE-RESULT.json. It is a standalone
runner - never invoked from inside pytest - so validating results cannot recurse into running the
suite. The finalizer (update_current_status.py) refuses to record status from anything except this
artifact, and the status-reality guard re-validates it on every run.

The artifact records the run's commit and tree from git at run time. Under the two-commit
convention that means: run this AFTER the content commit, on its clean checkout, so the artifact
truthfully names the content baseline it validated; the artifact then lands in the single
status-metadata commit alongside CURRENT.md.

Usage: .venv/bin/python scripts/run_canonical_suite.py
Exit:  the suite's own exit status (artifact is written either way - a red artifact is a truthful
       record of a red run, and the finalizer will refuse it).
"""

from __future__ import annotations

import datetime
import json
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from suite_result import ARTIFACT_RELPATH, payload_hash  # noqa: E402

CANONICAL_COMMAND = ".venv/bin/python -m pytest eval/ -q"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        sys.stderr.write(
            "REFUSED: the working tree is dirty. The artifact must describe a committed checkout;\n"
            "a result recorded from an uncommitted tree is exactly the developer-local false green\n"
            "this runner exists to prevent. Commit first, then run.\n"
        )
        return 2

    start = time.monotonic()
    proc = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "-m", "pytest", "eval/", "-q",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )
    duration = round(time.monotonic() - start, 1)
    out = proc.stdout

    def count(kind: str) -> int:
        m = re.search(rf"(\d+) {kind}", out)
        return int(m.group(1)) if m else 0

    data = {
        "command": CANONICAL_COMMAND,
        "commit": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "passed": count("passed"),
        "failed": count("failed"),
        "skipped": count("skipped"),
        "deselected": count("deselected"),
        "duration_seconds": duration,
        "exit_status": proc.returncode,
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    data["collected"] = data["passed"] + data["failed"] + data["skipped"]
    data["payload_sha256"] = payload_hash(data)

    (ROOT / ARTIFACT_RELPATH).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
    print(f"suite: {data['passed']} passed, {data['failed']} failed, {data['skipped']} skipped "
          f"in {duration}s (exit {proc.returncode})")
    print(f"artifact written: {ARTIFACT_RELPATH} (commit {data['commit'][:9]}, tree {data['tree'][:9]})")
    if proc.returncode != 0:
        sys.stderr.write("NOTE: red run recorded truthfully; the finalizer will refuse it.\n")
        sys.stderr.write(out[-2000:] + "\n")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
