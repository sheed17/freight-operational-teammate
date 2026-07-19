#!/usr/bin/env python3
"""The clean-clone reproducibility gate.

THE GATE THE INDEPENDENT REHEARSAL PROVED WAS MISSING (U-HANDOFF-1B). The authoring checkout
carried gitignored state (a workspace database, a warmed venv, globally-satisfied dependencies)
that made the suite green locally and red everywhere else. This gate answers the only question
that matters for handoff: does the COMMITTED repository, alone, produce the recorded result?

Mechanically:
  1. creates a fresh temporary directory
  2. `git clone` of THIS repository's committed state (a local clone carries no ignored or
     untracked files by construction)
  3. creates a fresh venv with the current (compliant) interpreter
  4. runs scripts/check_env.py inside it (fail-fast Python floor)
  5. installs ONLY the declared dependencies (`pip install -e ".[dev]"`)
  6. verifies data/active_workspace does not exist in the clone
  7. runs the complete canonical suite
  8. runs the documentation/control guards and the AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001 gates
  9. verifies the clone's working tree is still clean
 10. reports the exact clean-clone result and compares it to the committed status record

Exit 0 only if every step passes. `--keep` retains the temp directory for debugging; default is
deletion. The final handoff may not proceed unless this gate passes.

This is a standalone command, never invoked from inside pytest (no recursion).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd, label, env=None):
    print(f"--- {label}")
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        print(proc.stdout[-3000:])
        print(proc.stderr[-3000:])
        raise SystemExit(f"CLEAN-CLONE GATE FAILED at: {label} (exit {proc.returncode})")
    return proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="retain the temp clone for debugging")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="neyma-clean-clone-"))
    clone = tmp / "clone"
    print(f"clean-clone gate: {clone}")
    try:
        run(["git", "clone", "--quiet", str(ROOT), str(clone)], ROOT, "1. clone committed state")

        ws = clone / "data" / "active_workspace"
        if ws.exists():
            raise SystemExit("CLEAN-CLONE GATE FAILED: data/active_workspace exists in a fresh "
                             "clone - developer-local state is being tracked")
        print("--- 2. no active_workspace in clone: OK")

        py = sys.executable
        run([py, str(clone / "scripts" / "check_env.py")], clone, "3. python floor (host interpreter)")
        run([py, "-m", "venv", str(clone / ".venv")], clone, "4. fresh venv")
        vpy = str(clone / ".venv" / "bin" / "python")
        run([vpy, str(clone / "scripts" / "check_env.py")], clone, "5. python floor (venv interpreter)")
        run([vpy, "-m", "pip", "install", "-q", "-e", ".[dev]"], clone, "6. install declared deps only")

        out = run([vpy, "-m", "pytest", "eval/", "-q", "-p", "no:cacheprovider"], clone,
                  "7. complete canonical suite (clean clone)")
        tail = [l for l in out.strip().split("\n") if re.search(r"\d+ passed", l)]
        summary = tail[-1] if tail else "(unparsed)"
        print(f"    clean-clone suite: {summary}")
        m = re.search(r"(\d+) passed", summary)
        passed = int(m.group(1)) if m else 0
        failed = int(re.search(r"(\d+) failed", summary).group(1)) if "failed" in summary else 0
        if failed:
            raise SystemExit(f"CLEAN-CLONE GATE FAILED: {failed} failures on a clean clone")

        run([vpy, "-m", "pytest",
             "eval/tests/test_docs_control_system.py", "eval/tests/test_status_reality.py",
             "eval/tests/test_tool_access_policy.py", "eval/tests/test_bootstrap_hermeticity.py",
             "-q", "-p", "no:cacheprovider"], clone, "8. control guards (clean clone)")
        run([vpy, "-m", "pytest", "eval/", "-q", "-k",
             "ac_safe_012 or ac_safe_013 or ac_sec_001", "-p", "no:cacheprovider"],
            clone, "9. AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001")

        status = run(["git", "status", "--porcelain"], clone, "10. clone tree still clean")
        if status.strip():
            raise SystemExit(f"CLEAN-CLONE GATE FAILED: the clone dirtied itself:\n{status}")

        art = clone / "docs" / "implementation" / "SUITE-RESULT.json"
        if art.exists():
            rec = json.loads(art.read_text())
            print(f"--- 11. committed record: {rec['passed']}/{rec['failed']}/{rec['skipped']} "
                  f"| clean clone: {summary}")
            if rec["failed"] == 0 and passed and passed != rec["passed"]:
                print("    NOTE: pass-count differs from the committed record - re-finalize "
                      "against a clean-clone-verified run before relying on the record.")
        print("\nCLEAN-CLONE GATE: PASS")
        return 0
    finally:
        if args.keep:
            print(f"kept: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
