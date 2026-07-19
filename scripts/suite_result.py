"""Suite-result artifact: shared by the canonical runner, the finalizer and the guards.

TRUST MODEL (corrected by U-HANDOFF-1C, H-1). An unkeyed local JSON file cannot prove that tests
ran - its hash proves only that nobody edited the payload after the hash was computed. This
repository therefore does NOT claim the artifact is cryptographic proof of execution:

  - PROOF of execution is that scripts/finalize_status.py itself EXECUTES the suite, the
    clean-clone gate and the acceptance gates in-process and observes their exit statuses
    directly. Status can only be written by that path.
  - The artifact is GENERATED EVIDENCE: an auditable record of what the finalizer observed,
    bound to commit, tree, the exact node manifest, the canonical config and runner hashes.
  - Externally signed CI provenance could strengthen this later; it is deliberately not claimed
    or required in this work unit, and no in-repository secret is invented (a secret in the repo
    is available to the forger too).

Accordingly the validator here is named artifact_consistency_errors - it checks CONSISTENCY of a
record against expectations, and its docstring says exactly what that does and does not prove.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ARTIFACT_RELPATH = "docs/implementation/SUITE-RESULT.json"
GATE_RESULT_RELPATH = "docs/implementation/GATE-RESULT.json"
NODE_MANIFEST_RELPATH = "docs/implementation/TEST-NODE-MANIFEST.json"
APPROVED_SKIPS_RELPATH = "docs/implementation/APPROVED-SKIPS.yaml"

REQUIRED_FIELDS = (
    "command", "commit", "tree", "python_version", "platform",
    "passed", "failed", "skipped", "collected", "deselected",
    "duration_seconds", "exit_status", "completed_at",
    "config_sha256", "runner_sha256", "manifest_sha256", "skipped_nodes",
    "payload_sha256",
)


def payload_hash(data: dict) -> str:
    body = {k: v for k, v in data.items() if k != "payload_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_artifact(root: Path) -> dict:
    path = root / ARTIFACT_RELPATH
    if not path.exists():
        raise FileNotFoundError(f"suite-result artifact missing: {ARTIFACT_RELPATH}")
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_consistency_errors(data: dict, *, expect_commit: str, expect_tree: str,
                                expect_config_sha: str | None = None,
                                expect_runner_sha: str | None = None,
                                expect_manifest_sha: str | None = None,
                                approved_skips: list[str] | None = None,
                                live_collected: int | None = None) -> list[str]:
    """Every reason this RECORD is inconsistent with what it claims to describe. Empty = consistent.

    WHAT THIS PROVES: the record is well-formed, unedited since hashing, bound to the expected
    commit/tree/config/runner/manifest, describes a green unfiltered run whose skips are exactly
    the approved set.
    WHAT THIS DOES NOT PROVE: that any test actually executed. Execution is proven only by the
    finalizer running the suite itself. A handwritten record with correct hashes passes THIS
    function and is still refused by finalization, which never reads a pre-existing artifact.
    """
    errs: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in data:
            errs.append(f"missing field: {f}")
    if errs:
        return errs

    if data["payload_sha256"] != payload_hash(data):
        errs.append("payload hash mismatch - the record was edited after it was produced")
    if data["exit_status"] != 0:
        errs.append(f"exit_status={data['exit_status']} - a failing run cannot back a green record")
    if data["failed"] != 0:
        errs.append(f"failed={data['failed']} - a suite with failures cannot back a green record")
    if data["deselected"] != 0:
        errs.append(f"deselected={data['deselected']} - a filtered run is not the canonical suite")
    if data["passed"] + data["failed"] + data["skipped"] != data["collected"]:
        errs.append("passed+failed+skipped != collected - tests went missing from the run")
    if data["commit"] != expect_commit:
        errs.append(f"record commit {data['commit'][:9]} != expected {expect_commit[:9]} - "
                    "a result from another commit proves nothing about this one")
    if data["tree"] != expect_tree:
        errs.append(f"record tree {data['tree'][:9]} != expected {expect_tree[:9]} - "
                    "a result from another tree proves nothing about this one")
    if "pytest" not in data["command"] or "pytest-canonical.ini" not in data["command"]:
        errs.append(f"command {data['command']!r} is not the canonical isolated-config command")
    if expect_config_sha is not None and data["config_sha256"] != expect_config_sha:
        errs.append("config_sha256 mismatch - the run used a different pytest configuration")
    if expect_runner_sha is not None and data["runner_sha256"] != expect_runner_sha:
        errs.append("runner_sha256 mismatch - the run used a different canonical runner")
    if expect_manifest_sha is not None and data["manifest_sha256"] != expect_manifest_sha:
        errs.append("manifest_sha256 mismatch - the run verified a different node population")
    if data["skipped"] != len(data["skipped_nodes"]):
        errs.append("skipped count disagrees with the skipped_nodes list")
    if approved_skips is not None:
        observed = set(data["skipped_nodes"])
        approved = set(approved_skips)
        if observed != approved:
            errs.append(
                f"observed skips != approved skips (unapproved={sorted(observed - approved)}, "
                f"vanished-approved={sorted(approved - observed)}) - silence changed meaning"
            )
    if live_collected is not None and data["collected"] != live_collected:
        errs.append(f"record collected {data['collected']} != live population {live_collected} - "
                    "tests were added or removed after the recorded run")
    return errs
