#!/usr/bin/env python3
"""THE canonical end-to-end status finalization command (U-HANDOFF-1C, H-1).

The hostile review's decisive finding: a handwritten, structurally perfect green JSON file was
accepted as the basis for status finalization. The root defect was architectural - the finalizer
VALIDATED evidence instead of PRODUCING it. This command inverts that: status can be written only
by this process, and this process EXECUTES everything it attests to, observing every exit status
directly. Evidence files are outputs of the run, never inputs to it.

The pipeline (any failure aborts WITHOUT touching status):

   1. refuse a dirty tracked tree
   2. resolve the current commit and tree
   3. verify the Python floor (scripts/check_env.py logic, in-process)
   4. verify declared dependencies are importable (the websocket lesson)
   5. verify the exact canonical test population against TEST-NODE-MANIFEST.json by identity
   6. DELETE any pre-existing SUITE-RESULT.json and GATE-RESULT.json - a pre-existing receipt is
      never read, so a fabricated one is never consumed
   7. EXECUTE the complete canonical suite (run_canonical_suite.run_suite, in-process result)
   8. EXECUTE the clean-clone gate (scripts/clean_clone_gate.py) and read the gate result IT
      wrote during this run
   9. EXECUTE the documentation/control guards explicitly
  10. EXECUTE AC-SAFE-012, AC-SAFE-013, AC-SEC-001 explicitly
  11. write the suite-result record from the IN-PROCESS run object
  12. update CURRENT.md's status block + the registry meta + review placeholders

This command takes NO arguments beyond --help. There is no count flag, no artifact path, no
"trust this result" flag, no skip-suite flag, no skip-gate flag, and no filtered mode. If you
want status finalized, everything runs, every time. Expect ~20 minutes.

TRUST MODEL, stated honestly: no in-repository secret exists (a local secret is available to a
local forger), so the committed artifacts are GENERATED EVIDENCE of this process's observations,
not independent cryptographic proof. Externally signed CI provenance may be added later; it is
not required by this unit and not claimed.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_env import check as env_check  # noqa: E402
from suite_result import (  # noqa: E402
    ARTIFACT_RELPATH, GATE_RESULT_RELPATH, NODE_MANIFEST_RELPATH, payload_hash,
)
import run_canonical_suite as runner  # noqa: E402
import progress_status as progress  # noqa: E402
from finalizer_lock import FinalizerLockHeld, finalizer_lock  # noqa: E402

CURRENT = ROOT / "docs" / "implementation" / "CURRENT.md"
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"
BUILD_STATUS = ROOT / "docs" / "implementation" / "BUILD-STATUS.yaml"
REVIEWS = (
    ROOT / "docs" / "implementation" / "u-handoff-1a-control-correction-review.md",
    ROOT / "docs" / "implementation" / "u-handoff-1b-clean-clone-correction-review.md",
    ROOT / "docs" / "implementation" / "u-handoff-1c-false-green-and-discovery-correction-review.md",
    ROOT / "docs" / "implementation" / "u-handoff-1d-final-adjudication-review.md",
    ROOT / "docs" / "implementation" / "u-rebaseline-1-product-production-review.md",
)

STATUS_METADATA_FILES = (
    "docs/implementation/SUITE-RESULT.json",
    "docs/implementation/GATE-RESULT.json",
    "docs/implementation/CURRENT.md",
    "docs/implementation/IMPLEMENTATION-REGISTRY.yaml",
    "docs/implementation/u-handoff-1a-control-correction-review.md",
    "docs/implementation/u-handoff-1b-clean-clone-correction-review.md",
    "docs/implementation/u-handoff-1c-false-green-and-discovery-correction-review.md",
    "docs/implementation/u-handoff-1d-final-adjudication-review.md",
    "docs/implementation/u-rebaseline-1-product-production-review.md",
    "docs/implementation/BUILD-STATUS.yaml",
)

# Dependency-injection seam FOR TESTS ONLY: the hostile test replaces these to prove that a
# failing execution aborts finalization even with a perfect forged artifact on disk. Production
# invocation always uses the real functions below.
EXECUTORS = {}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def _refuse(msg: str) -> "SystemExit":
    return SystemExit(f"FINALIZATION REFUSED: {msg}\n(status was NOT updated)")


def _step_dirty_tree():
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        raise _refuse(f"the working tree is dirty:\n{dirty}")


def _step_python_floor():
    if env_check(None) != 0:
        raise _refuse("the active interpreter fails the declared Python floor")


def _step_dependencies():
    for mod in ("pydantic", "instructor", "anthropic", "openai", "fitz", "yaml",
                "dotenv", "reportlab", "PIL", "websocket", "pytest"):
        try:
            importlib.import_module(mod)
        except ImportError as exc:
            raise _refuse(f"declared dependency not importable: {mod} ({exc})")


def _step_population():
    manifest = json.loads((ROOT / NODE_MANIFEST_RELPATH).read_text(encoding="utf-8"))
    live = runner.collect_nodes()
    missing = sorted(set(manifest["node_ids"]) - live)
    extra = sorted(live - set(manifest["node_ids"]))
    if missing or extra:
        raise _refuse(f"test population diverges from the node manifest "
                      f"(missing={missing[:5]}, extra={extra[:5]})")


def _receipt_baselines() -> dict:
    """A pre-existing receipt is NEVER an input - this finalizer never reads SUITE-RESULT.json,
    and it reads GATE-RESULT.json only after invoking the gate and observing exit 0. Deleting the
    tracked receipts (the first design) dirtied the tree mid-run and broke the very guards this
    process executes; instead we record their pre-run hashes and require the gate's record to
    DIFFER afterwards, which proves THIS invocation wrote it (the gate stamps completed_at, so a
    genuine run always differs; a caller-planted file that the gate did not overwrite cannot)."""
    import hashlib
    out = {}
    for rel in (ARTIFACT_RELPATH, GATE_RESULT_RELPATH):
        f = ROOT / rel
        out[rel] = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
    return out


def _step_run_suite() -> dict:
    data = EXECUTORS.get("suite", runner.run_suite)()
    errs = runner.outcome_errors(data)
    if data["exit_status"] != 0 or data["failed"] != 0 or errs:
        raise _refuse("the canonical suite did not pass cleanly:\n  "
                      + "\n  ".join([f"exit={data['exit_status']} failed={data['failed']}"] + errs)
                      + "\n" + data.get("stdout_tail", ""))
    return data


def _step_run_gate(head: str, tree: str, baselines: dict | None = None) -> dict:
    fn = EXECUTORS.get("gate")
    if fn is not None:
        rc = fn()
    else:
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "clean_clone_gate.py")],
                            cwd=ROOT).returncode
    gate_path = ROOT / GATE_RESULT_RELPATH
    if rc != 0:
        raise _refuse(f"the clean-clone gate failed (exit {rc})")
    if not gate_path.exists():
        raise _refuse("the clean-clone gate wrote no result - a PASS with no record is not a PASS")
    if baselines is not None:
        import hashlib
        now = hashlib.sha256(gate_path.read_bytes()).hexdigest()
        if now == baselines.get(GATE_RESULT_RELPATH):
            raise _refuse("the gate result predates this invocation - a pre-existing record "
                          "cannot substitute for running the gate")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("payload_sha256") != payload_hash(gate):
        raise _refuse("the gate result was edited after the gate wrote it")
    if not gate.get("passed"):
        raise _refuse(f"the gate result records failure: {gate.get('reason')}")
    if gate.get("commit") != head or gate.get("tree") != tree:
        raise _refuse("the gate result describes a different commit/tree than the one being finalized")
    return gate


def _step_run_guards_and_gates():
    env = runner.canonical_env()
    checks = [
        ("control guards",
         [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-c", str(ROOT / "pytest-canonical.ini"),
          "eval/tests/test_docs_control_system.py", "eval/tests/test_status_reality.py",
          "eval/tests/test_tool_access_policy.py", "eval/tests/test_bootstrap_hermeticity.py",
          "eval/tests/test_false_green_defenses.py", "-q"]),
        ("AC-SAFE-012/013 + AC-SEC-001",
         [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-c", str(ROOT / "pytest-canonical.ini"),
          "eval/", "-q", "-k", "ac_safe_012 or ac_safe_013 or ac_sec_001"]),
    ]
    for label, cmd in checks:
        rc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        if rc.returncode != 0:
            raise _refuse(f"{label} failed (exit {rc.returncode}):\n{rc.stdout[-1500:]}")


def _write_status(data: dict, head: str, tree: str):
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    text = CURRENT.read_text(encoding="utf-8")
    block = (
        "```yaml\n"
        "# status-block: maintained by scripts/finalize_status.py - do not edit by hand\n"
        f"recorded_authoring_branch: {branch}   # advisory; not verified across bundles/clones\n"
        f"content_commit: {head}\n"
        f"content_tree: {tree}\n"
        f"suite_passed: {data['passed']}\n"
        f"suite_failed: {data['failed']}\n"
        f"suite_skipped: {data['skipped']}\n"
        "```"
    )
    new = re.sub(r"```yaml\n# status-block:.*?```", block, text, count=1, flags=re.S)
    if new == text and block not in text:
        raise _refuse("status-block not found in CURRENT.md")
    CURRENT.write_text(new, encoding="utf-8")

    text = REGISTRY.read_text(encoding="utf-8")
    text = re.sub(r"^  baseline_commit: .*$", f"  baseline_commit: {head}", text, count=1, flags=re.M)
    text = re.sub(r"^  validated_tree: .*$", f"  validated_tree: {tree}", text, count=1, flags=re.M)
    text = re.sub(
        r'^  suite: ".*"$',
        f'  suite: "{data["passed"]} passed, {data["failed"]} failed, {data["skipped"]} conditionally justified skip"',
        text, count=1, flags=re.M,
    )
    REGISTRY.write_text(text, encoding="utf-8")

    for review in REVIEWS:
        if review.exists():
            text = review.read_text(encoding="utf-8")
            text = text.replace("CONTENT_COMMIT_INSERTED_BY_FINALIZER", head)
            text = text.replace("CONTENT_TREE_INSERTED_BY_FINALIZER", tree)
            text = text.replace("SUITE_INSERTED_BY_FINALIZER",
                                f"{data['passed']} passed · {data['failed']} failed · {data['skipped']} skipped")
            review.write_text(text, encoding="utf-8")


def _step_progress(head: str, tree: str):
    """Derive the founder progress snapshot mechanically, WRITE it into BUILD-STATUS.yaml, then
    REFUSE if any integrity condition fails (PROGRESS-PROTOCOL.md sec 8). content_commit is the
    content baseline `head` (two-commit convention), matching CURRENT.md's block."""
    w = progress.load_weights()
    werrs = progress.program_weight_errors(w)
    if werrs:
        raise _refuse("PROGRAM-WEIGHTS.yaml invalid:\n  " + "\n  ".join(werrs))
    units = progress.registry_units()
    derived = progress.derive(head, tree, head)
    block = "\n".join(
        ["# derived-block: maintained by scripts/finalize_status.py - do not edit by hand",
         "derived:"] +
        [f"  {k}: {derived[k]}" if derived[k] is not None else f"  {k}: null" for k in
         ("content_commit", "content_tree", "active_phase", "single_ready_unit",
          "cli_switch_readiness_percent", "overall_program_percent", "current_phase_percent",
          "user_visible_maturity_percent", "production_readiness_percent", "readiness_tier")] +
        ["# end-derived-block"]
    )
    text = BUILD_STATUS.read_text(encoding="utf-8")
    new = re.sub(r"# derived-block:.*?# end-derived-block", block, text, count=1, flags=re.S)
    if new == text and "# derived-block:" not in text:
        raise _refuse("BUILD-STATUS.yaml has no derived-block markers")
    BUILD_STATUS.write_text(new, encoding="utf-8")
    bs = yaml.safe_load(BUILD_STATUS.read_text(encoding="utf-8"))["derived"]
    berrs = progress.build_status_errors(bs, derived, units)
    if berrs:
        raise _refuse("BUILD-STATUS integrity failed:\n  " + "\n  ".join(berrs))


def finalize() -> int:
    _step_dirty_tree()
    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    _step_python_floor()
    _step_dependencies()
    _step_population()
    baselines = _receipt_baselines()

    print(f"finalizing {head[:9]} - executing the complete canonical suite ...")
    data = _step_run_suite()
    print(f"  suite: {data['passed']}/{data['failed']}/{data['skipped']} - executing clean-clone gate ...")
    _step_run_gate(head, tree, baselines)
    print("  gate: PASS - executing control guards and AC gates ...")
    _step_run_guards_and_gates()

    data["payload_sha256"] = payload_hash(data)
    (ROOT / ARTIFACT_RELPATH).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
    _write_status(data, head, tree)
    _step_progress(head, tree)
    print("  progress: BUILD-STATUS.yaml derived and validated")
    print(f"status finalized from EXECUTED results: {data['passed']}/{data['failed']}/{data['skipped']} "
          f"on {head[:9]} ({tree[:9]})")
    print("next: commit ONLY the status files as the single status-metadata commit:")
    print("  git add " + " ".join(STATUS_METADATA_FILES))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="End-to-end status finalization. No options: "
                                             "everything runs, every time.")
    ap.parse_args()

    # Exactly one finalizer per repository, enforced before finalize() runs a
    # suite, deletes a receipt or writes any status file. Two concurrent
    # finalizers delete each other's receipts and certify a tree that is moving
    # underneath them; the losing one must exit non-zero having modified
    # nothing. See scripts/finalizer_lock.py for why the lock — and never the
    # presence or absence of a log file — decides whether one is already running.
    try:
        with finalizer_lock(ROOT, target_commit=git("rev-parse", "HEAD")):
            return finalize()
    except FinalizerLockHeld as exc:
        print(f"REFUSED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
