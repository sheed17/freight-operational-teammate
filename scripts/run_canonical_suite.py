#!/usr/bin/env python3
"""Run the canonical suite under the isolated configuration and record exact per-node outcomes.

H-2 (U-HANDOFF-1C): a hostile reviewer silently removed 31 tests via pytest configuration, with
zero failures and zero deselections. This runner closes every path in that family:

  - executes ONLY under pytest-canonical.ini via an explicit -c path (pyproject / parent-dir /
    tox ini options are ignored by pytest when -c is explicit)
  - clears PYTEST_ADDOPTS from the environment
  - collects first and compares EXACT NODE IDENTITIES against the committed
    TEST-NODE-MANIFEST.json: missing nodes, extra nodes and same-count substitutions all abort
  - runs the verified population with -v and captures the outcome OF EVERY NODE
  - verifies executed set == collected set, and that skips are EXACTLY the approved canonical
    set from APPROVED-SKIPS.yaml
  - records config/runner/manifest hashes into the result

The runner refuses dirty trees: the record must describe a committed checkout, never a
developer-local one. Manifest regeneration NEVER happens here - it is the explicit intentional
act of scripts/regenerate_test_manifest.py.

Exit: the suite's exit status (a red run is recorded truthfully; finalization refuses it).
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from suite_result import (  # noqa: E402
    APPROVED_SKIPS_RELPATH, ARTIFACT_RELPATH, NODE_MANIFEST_RELPATH, file_sha, payload_hash,
)

CANONICAL_CONFIG = ROOT / "pytest-canonical.ini"
CANONICAL_COMMAND = ".venv/bin/python -m pytest -c pytest-canonical.ini -v"

FORBIDDEN_ADDOPT_TOKENS = ("--ignore", "--ignore-glob", "-k", "-m", "--deselect", "--co",
                           "--collect-only", "-p no:")


def canonical_env() -> dict:
    env = dict(os.environ)
    env["PYTEST_ADDOPTS"] = ""  # never inherit ambient filtering
    return env


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def _config_is_clean() -> list[str]:
    """The canonical config itself may not filter. Defense in depth under H-2."""
    text = CANONICAL_CONFIG.read_text(encoding="utf-8")
    addopts = ""
    m = re.search(r"^addopts\s*=\s*(.*)$", text, re.M)
    if m:
        addopts = m.group(1)
    errs = []
    for tok in FORBIDDEN_ADDOPT_TOKENS:
        if tok in addopts and tok != "-p no:":
            errs.append(f"canonical config addopts contains filtering token {tok!r}")
    if "-p no:cacheprovider" not in addopts:
        # cacheprovider-off keeps runs stateless; anything else via -p no: needs review
        pass
    for extra in re.findall(r"-p no:([a-z0-9_]+)", addopts):
        if extra not in ("cacheprovider",):
            errs.append(f"canonical config disables plugin {extra!r} - collection may change silently")
    tp = re.search(r"^testpaths\s*=\s*(.*)$", text, re.M)
    if not tp or tp.group(1).strip() != "eval":
        errs.append(f"canonical config testpaths is {tp.group(1).strip() if tp else 'MISSING'!r}, not 'eval'")
    return errs


def collect_nodes() -> set[str]:
    r = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "-m", "pytest",
         "-c", str(CANONICAL_CONFIG), "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True, env=canonical_env(),
    )
    return {l.strip() for l in r.stdout.split("\n") if re.match(r"^eval/.*::", l.strip())}


def run_suite() -> dict:
    """Execute and return the full result record (not yet hashed). Raises SystemExit on
    population divergence - a run over the wrong population must not even start."""
    cfg_errs = _config_is_clean()
    if cfg_errs:
        raise SystemExit("REFUSED: canonical config is not clean:\n  " + "\n  ".join(cfg_errs))

    manifest = json.loads((ROOT / NODE_MANIFEST_RELPATH).read_text(encoding="utf-8"))
    recorded = set(manifest["node_ids"])
    live = collect_nodes()
    missing = sorted(recorded - live)
    extra = sorted(live - recorded)
    if missing or extra:
        raise SystemExit(
            "REFUSED: collected population diverges from TEST-NODE-MANIFEST by identity "
            f"(missing={missing[:5]}, extra={extra[:5]}). If the change is intentional, run "
            "scripts/regenerate_test_manifest.py and commit the reviewed diff."
        )

    start = time.monotonic()
    proc = subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), "-m", "pytest",
         "-c", str(CANONICAL_CONFIG), "-v"],
        cwd=ROOT, capture_output=True, text=True, env=canonical_env(),
    )
    duration = round(time.monotonic() - start, 1)
    outcomes: dict[str, str] = {}
    for line in proc.stdout.split("\n"):
        m = re.match(r"^(eval/.+?::.+?)\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)(?:\s|$)", line.strip())
        if m:
            outcomes[m.group(1)] = m.group(2)

    executed = set(outcomes)
    unexecuted = sorted(recorded - executed)
    rogue = sorted(executed - recorded)
    skipped_nodes = sorted(n for n, o in outcomes.items() if o == "SKIPPED")
    xfailed = sorted(n for n, o in outcomes.items() if o in ("XFAIL", "XPASS"))

    data = {
        "command": CANONICAL_COMMAND,
        "commit": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "passed": sum(1 for o in outcomes.values() if o == "PASSED"),
        "failed": sum(1 for o in outcomes.values() if o in ("FAILED", "ERROR")),
        "skipped": len(skipped_nodes),
        "deselected": len(re.findall(r"\d+ deselected", proc.stdout)),
        "collected": len(outcomes),
        "duration_seconds": duration,
        "exit_status": proc.returncode,
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config_sha256": file_sha(CANONICAL_CONFIG),
        "runner_sha256": file_sha(Path(__file__)),
        "manifest_sha256": manifest["manifest_sha256"],
        "skipped_nodes": skipped_nodes,
        "unexecuted_nodes": unexecuted,
        "rogue_nodes": rogue,
        "xfail_nodes": xfailed,
        "stdout_tail": proc.stdout[-1500:] if proc.returncode != 0 else "",
    }
    return data


def outcome_errors(data: dict) -> list[str]:
    """Execution-observation errors the runner itself enforces (beyond record consistency)."""
    import yaml
    approved = yaml.safe_load((ROOT / APPROVED_SKIPS_RELPATH).read_text(encoding="utf-8"))
    expected_skips = set(approved["expected_canonical_run_skips"])
    errs = []
    if data["unexecuted_nodes"]:
        errs.append(f"collected nodes did not execute: {data['unexecuted_nodes'][:5]}")
    if data["rogue_nodes"]:
        errs.append(f"nodes executed outside the manifest: {data['rogue_nodes'][:5]}")
    if set(data["skipped_nodes"]) != expected_skips:
        errs.append(
            f"observed skips {sorted(data['skipped_nodes'])} != approved canonical skips "
            f"{sorted(expected_skips)}"
        )
    if data["xfail_nodes"]:
        errs.append(f"xfail/xpass outcomes present and unapproved: {data['xfail_nodes'][:5]}")
    if data["deselected"] != 0:
        errs.append("deselection occurred in a canonical run")
    return errs


def main() -> int:
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        sys.stderr.write(
            "REFUSED: the working tree is dirty. The record must describe a committed checkout;\n"
            "a result recorded from an uncommitted tree is the developer-local false green this\n"
            "runner exists to prevent. Commit first, then run.\n"
        )
        return 2

    data = run_suite()
    errs = outcome_errors(data)
    data["payload_sha256"] = payload_hash(data)
    (ROOT / ARTIFACT_RELPATH).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
    print(f"suite: {data['passed']} passed, {data['failed']} failed, {data['skipped']} skipped "
          f"({data['collected']} nodes) in {data['duration_seconds']}s (exit {data['exit_status']})")
    print(f"record written: {ARTIFACT_RELPATH} (commit {data['commit'][:9]}, tree {data['tree'][:9]})")
    if errs:
        sys.stderr.write("OUTCOME ERRORS (recorded truthfully; finalization will refuse):\n  "
                         + "\n  ".join(errs) + "\n")
        return 3
    return data["exit_status"]


if __name__ == "__main__":
    raise SystemExit(main())
