"""Suite-result artifact: shared by the canonical runner, the status finalizer and the guard.

THE RESULT-TRUTHFULNESS CORRECTION (U-HANDOFF-1B). The previous status-reality design verified
that recorded passed+failed+skipped equalled the live collected-test population. That proves how
many tests EXIST - it says nothing about whether they PASSED. The clean-clone rehearsal proved the
gap concretely: 46 tests failed on a clean clone while the recorded status stayed green, because
the record descended from a developer-local run the collection count could not distinguish from a
healthy one.

The correction: the canonical suite runner (scripts/run_canonical_suite.py) writes a
machine-readable result artifact from an ACTUAL run; the finalizer refuses to record status except
from a valid artifact; and the status-reality guard validates the artifact - command, commit,
tree, exit status, zero failures, zero deselection, payload hash - against the checked-out
repository. Validation logic lives HERE, once, imported by all three, so the runner, the finalizer
and the guard cannot drift apart on what a valid result means. It is also unit-tested directly
with forged artifacts (green-with-failures, stale commit, stale tree, nonzero exit), so weakening
this module is caught by tests that feed it exactly those forgeries.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ARTIFACT_RELPATH = "docs/implementation/SUITE-RESULT.json"

REQUIRED_FIELDS = (
    "command", "commit", "tree", "python_version", "platform",
    "passed", "failed", "skipped", "collected", "deselected",
    "duration_seconds", "exit_status", "completed_at", "payload_sha256",
)


def payload_hash(data: dict) -> str:
    body = {k: v for k, v in data.items() if k != "payload_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def load_artifact(root: Path) -> dict:
    path = root / ARTIFACT_RELPATH
    if not path.exists():
        raise FileNotFoundError(f"suite-result artifact missing: {ARTIFACT_RELPATH}")
    return json.loads(path.read_text(encoding="utf-8"))


def validation_errors(data: dict, *, expect_commit: str, expect_tree: str,
                      live_collected: int | None = None) -> list[str]:
    """Every reason this artifact may NOT back a green status record. Empty list = valid.

    Each rejection below is one of the forgeries the rehearsal showed the old design accepted.
    """
    errs: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in data:
            errs.append(f"missing field: {f}")
    if errs:
        return errs

    if data["payload_sha256"] != payload_hash(data):
        errs.append("payload hash mismatch - the artifact was edited after it was produced")
    if data["exit_status"] != 0:
        errs.append(f"exit_status={data['exit_status']} - a failing run cannot back a green record")
    if data["failed"] != 0:
        errs.append(f"failed={data['failed']} - a suite with failures cannot back a green record")
    if data["deselected"] != 0:
        errs.append(f"deselected={data['deselected']} - a filtered run is not the canonical suite")
    if data["passed"] + data["failed"] + data["skipped"] != data["collected"]:
        errs.append("passed+failed+skipped != collected - tests went missing from the run")
    if data["commit"] != expect_commit:
        errs.append(f"artifact commit {data['commit'][:9]} != expected {expect_commit[:9]} - "
                    "a result from another commit proves nothing about this one")
    if data["tree"] != expect_tree:
        errs.append(f"artifact tree {data['tree'][:9]} != expected {expect_tree[:9]} - "
                    "a result from another tree proves nothing about this one")
    if "pytest" not in data["command"] or "eval/" not in data["command"]:
        errs.append(f"command {data['command']!r} is not the canonical suite command")
    if live_collected is not None and data["collected"] != live_collected:
        errs.append(f"artifact collected {data['collected']} != live population {live_collected} - "
                    "tests were added or removed after the recorded run")
    return errs
