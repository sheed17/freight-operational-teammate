#!/usr/bin/env python3
"""The clean-clone reproducibility gate - decisive, machine-readable, self-recording.

M-5 (U-HANDOFF-1C): the previous gate printed a NOTE on suite-count mismatch and passed anyway -
advisory where it must be decisive. Every check below now FAILS the gate, and the gate itself
writes docs/implementation/GATE-RESULT.json from its own in-process observations - a caller
cannot hand it a result, and the finalizer verifies the file was produced by the gate run it
launched (it deletes any pre-existing gate result before invoking).

Mechanics:
  1. fresh temp dir; `git clone` of THIS repository's committed state
  2. verify data/active_workspace absent in the clone
  3. Python floor (host + fresh venv), declared-deps-only install
  4. verify the clone's canonical config and node manifest match the authoring commit's
  5. run the COMPLETE canonical suite in the clone under the canonical config with per-node
     outcomes - fail on ANY failure, any node-manifest divergence, any unapproved skip or xfail,
     any deselection
  6. run the control guards and AC-SAFE-012/013 + AC-SEC-001 gates - fail on any failure
  7. verify the clone tree is still clean
  8. write GATE-RESULT.json binding: commit, tree, node-manifest hash, config hash, runner hash,
     every executed step with its exit status, and the exact clean-clone counts

Exit 0 only if every step passed. --keep retains the clone for debugging.
Standalone command; never invoked from inside pytest (no recursion).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from suite_result import GATE_RESULT_RELPATH, NODE_MANIFEST_RELPATH, file_sha, payload_hash  # noqa: E402

STEPS: list[dict] = []


def step(label: str, cmd, cwd, env=None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    STEPS.append({"step": label, "exit_status": proc.returncode})
    print(f"--- {label} (exit {proc.returncode})")
    if proc.returncode != 0:
        print(proc.stdout[-2500:])
        print(proc.stderr[-2500:])
        _write_result(passed=False, reason=f"step failed: {label}")
        raise SystemExit(f"CLEAN-CLONE GATE FAILED at: {label} (exit {proc.returncode})")
    return proc.stdout


def _fail(reason: str):
    STEPS.append({"step": reason, "exit_status": 1})
    _write_result(passed=False, reason=reason)
    raise SystemExit(f"CLEAN-CLONE GATE FAILED: {reason}")


_result_meta: dict = {}


def _write_result(*, passed: bool, reason: str = "", counts: dict | None = None):
    data = {
        "gate": "clean_clone_gate",
        "passed": passed,
        "reason": reason,
        "commit": _result_meta.get("commit", ""),
        "tree": _result_meta.get("tree", ""),
        "node_manifest_sha256": _result_meta.get("manifest_sha", ""),
        "config_sha256": _result_meta.get("config_sha", ""),
        "runner_sha256": _result_meta.get("runner_sha", ""),
        "steps": STEPS,
        "clean_clone_counts": counts or {},
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    data["payload_sha256"] = payload_hash(data)
    (ROOT / GATE_RESULT_RELPATH).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                                            encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="retain the temp clone for debugging")
    args = ap.parse_args()

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    _result_meta.update({"commit": head, "tree": tree})

    tmp = Path(tempfile.mkdtemp(prefix="neyma-clean-clone-"))
    clone = tmp / "clone"
    print(f"clean-clone gate: {clone} (committed {head[:9]})")
    try:
        step("clone committed state", ["git", "clone", "--quiet", str(ROOT), str(clone)], ROOT)

        if (clone / "data" / "active_workspace").exists():
            _fail("data/active_workspace exists in a fresh clone - developer-local state is tracked")
        print("--- no active_workspace in clone: OK")

        # NB: in-clone pytest invocations use the RELATIVE config name with cwd=clone. An
        # absolute -c path through the macOS /var->/private/var symlink makes pytest compute a
        # rootdir whose node IDs print as ../../..-style paths, which parse as zero outcomes -
        # the gate then fails closed (as it did, correctly, when this was discovered).
        cfg = clone / "pytest-canonical.ini"
        man = clone / NODE_MANIFEST_RELPATH
        if not cfg.exists() or not man.exists():
            _fail("the clone lacks the canonical config or the node manifest")
        # H-2 binding: the clone's config/manifest must be exactly the authoring commit's
        if file_sha(cfg) != file_sha(ROOT / "pytest-canonical.ini"):
            _fail("the clone's canonical pytest config differs from the authoring commit's")
        manifest = json.loads(man.read_text())
        _result_meta.update({
            "manifest_sha": manifest["manifest_sha256"],
            "config_sha": file_sha(cfg),
            "runner_sha": file_sha(clone / "scripts" / "run_canonical_suite.py"),
        })

        py = sys.executable
        step("python floor (host)", [py, str(clone / "scripts" / "check_env.py")], clone)
        step("fresh venv", [py, "-m", "venv", str(clone / ".venv")], clone)
        vpy = str(clone / ".venv" / "bin" / "python")
        step("python floor (venv)", [vpy, str(clone / "scripts" / "check_env.py")], clone)
        step("install declared deps only", [vpy, "-m", "pip", "install", "-q", "-e", ".[dev]"], clone)

        # complete suite, canonical config, per-node outcomes, in the clone
        import os
        env = dict(os.environ); env["PYTEST_ADDOPTS"] = ""
        out = step("complete canonical suite (clean clone)",
                   [vpy, "-m", "pytest", "-c", "pytest-canonical.ini", "-v"], clone, env=env)
        outcomes = {}
        for line in out.split("\n"):
            m = re.match(r"^(eval/.+?::.+?)\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)(?:\s|$)", line.strip())
            if m:
                outcomes[m.group(1)] = m.group(2)
        counts = {
            "passed": sum(1 for o in outcomes.values() if o == "PASSED"),
            "failed": sum(1 for o in outcomes.values() if o in ("FAILED", "ERROR")),
            "skipped": sum(1 for o in outcomes.values() if o == "SKIPPED"),
            "collected": len(outcomes),
        }
        print(f"    clean-clone: {counts}")
        if counts["failed"]:
            _fail(f"{counts['failed']} failures on a clean clone")
        recorded = set(manifest["node_ids"])
        missing = sorted(recorded - set(outcomes))
        extra = sorted(set(outcomes) - recorded)
        if missing or extra:
            _fail(f"clean-clone population diverged from the node manifest by identity "
                  f"(missing={missing[:5]}, extra={extra[:5]})")
        import yaml
        approved = set(yaml.safe_load((clone / "docs/implementation/APPROVED-SKIPS.yaml")
                                      .read_text())["expected_canonical_run_skips"])
        observed_skips = {n for n, o in outcomes.items() if o == "SKIPPED"}
        if observed_skips != approved:
            _fail(f"clean-clone skips {sorted(observed_skips)} != approved {sorted(approved)}")
        if any(o in ("XFAIL", "XPASS") for o in outcomes.values()):
            _fail("unapproved xfail/xpass outcomes in the clean clone")
        if re.search(r"\d+ deselected", out):
            _fail("deselection occurred in the clean-clone run")

        step("control guards (clean clone)",
             [vpy, "-m", "pytest", "-c", "pytest-canonical.ini",
              "eval/tests/test_docs_control_system.py", "eval/tests/test_status_reality.py",
              "eval/tests/test_tool_access_policy.py", "eval/tests/test_bootstrap_hermeticity.py",
              "eval/tests/test_false_green_defenses.py", "-q"], clone, env=env)
        step("AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001",
             [vpy, "-m", "pytest", "-c", "pytest-canonical.ini", "eval/", "-q", "-k",
              "ac_safe_012 or ac_safe_013 or ac_sec_001"], clone, env=env)

        status = subprocess.run(["git", "status", "--porcelain"], cwd=clone,
                                capture_output=True, text=True).stdout.strip()
        STEPS.append({"step": "clone tree still clean", "exit_status": 0 if not status else 1})
        if status:
            _fail(f"the clone dirtied itself:\n{status}")

        _write_result(passed=True, counts=counts)
        print("\nCLEAN-CLONE GATE: PASS")
        return 0
    finally:
        if args.keep:
            print(f"kept: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
