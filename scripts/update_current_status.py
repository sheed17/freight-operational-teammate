#!/usr/bin/env python3
"""Finalize the canonical status record from an ACTUAL suite run.

THE TWO-COMMIT CONVENTION, RESULT-BACKED (U-HANDOFF-1B). A commit cannot contain its own hash, so
a hand-written "current commit" field is either stale or a lie - and U-HANDOFF-1B added the second
half of the lesson: a hand-supplied SUITE COUNT is just as untrustworthy, because the 1A finalizer
accepted `--passed 1179` on faith while a clean clone produced 46 failures.

This finalizer therefore takes NO count arguments. The only accepted source of suite truth is the
machine-readable artifact written by scripts/run_canonical_suite.py from a real run on a clean
checkout. The cycle:

    1. land every substantive change in a CONTENT COMMIT
    2. .venv/bin/python scripts/run_canonical_suite.py     (runs the suite, writes the artifact)
    3. .venv/bin/python scripts/update_current_status.py   (this script - validates the artifact,
       records commit/tree/counts in CURRENT.md + the registry meta + review placeholders)
    4. commit ONLY the status files below as the single STATUS-METADATA COMMIT

The finalizer refuses: a missing artifact, a tampered artifact (hash), a red run, a filtered run,
or an artifact from any commit other than the currently checked-out HEAD.

Files rewritten (this exact set is what the status-metadata commit may touch; the guard imports it
so script and guard cannot disagree):
    docs/implementation/SUITE-RESULT.json
    docs/implementation/CURRENT.md
    docs/implementation/IMPLEMENTATION-REGISTRY.yaml
    docs/implementation/u-handoff-1a-control-correction-review.md   (placeholders, if present)
    docs/implementation/u-handoff-1b-clean-clone-correction-review.md (placeholders, if present)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from suite_result import ARTIFACT_RELPATH, load_artifact, validation_errors  # noqa: E402

CURRENT = ROOT / "docs" / "implementation" / "CURRENT.md"
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"
REVIEWS = (
    ROOT / "docs" / "implementation" / "u-handoff-1a-control-correction-review.md",
    ROOT / "docs" / "implementation" / "u-handoff-1b-clean-clone-correction-review.md",
)

STATUS_METADATA_FILES = (
    "docs/implementation/SUITE-RESULT.json",
    "docs/implementation/CURRENT.md",
    "docs/implementation/IMPLEMENTATION-REGISTRY.yaml",
    "docs/implementation/u-handoff-1a-control-correction-review.md",
    "docs/implementation/u-handoff-1b-clean-clone-correction-review.md",
)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")

    try:
        art = load_artifact(ROOT)
    except FileNotFoundError as exc:
        sys.stderr.write(f"REFUSED: {exc}\nRun scripts/run_canonical_suite.py on the content "
                         "commit first - status is recorded only from an actual run.\n")
        return 1

    errs = validation_errors(art, expect_commit=head, expect_tree=tree)
    if errs:
        sys.stderr.write("REFUSED: the suite-result artifact cannot back a green status record:\n")
        for e in errs:
            sys.stderr.write(f"  - {e}\n")
        return 1

    passed, failed, skipped = art["passed"], art["failed"], art["skipped"]

    text = CURRENT.read_text(encoding="utf-8")
    block = (
        "```yaml\n"
        "# status-block: maintained by scripts/update_current_status.py - do not edit by hand\n"
        f"branch: {branch}\n"
        f"content_commit: {head}\n"
        f"content_tree: {tree}\n"
        f"suite_passed: {passed}\n"
        f"suite_failed: {failed}\n"
        f"suite_skipped: {skipped}\n"
        "```"
    )
    new = re.sub(r"```yaml\n# status-block:.*?```", block, text, count=1, flags=re.S)
    if new == text and block not in text:
        sys.stderr.write("ERROR: status-block not found in CURRENT.md\n")
        return 1
    CURRENT.write_text(new, encoding="utf-8")

    text = REGISTRY.read_text(encoding="utf-8")
    text = re.sub(r"^  baseline_commit: .*$", f"  baseline_commit: {head}", text, count=1, flags=re.M)
    text = re.sub(r"^  validated_tree: .*$", f"  validated_tree: {tree}", text, count=1, flags=re.M)
    text = re.sub(
        r'^  suite: ".*"$',
        f'  suite: "{passed} passed, {failed} failed, {skipped} conditionally justified skip"',
        text, count=1, flags=re.M,
    )
    REGISTRY.write_text(text, encoding="utf-8")

    for review in REVIEWS:
        if review.exists():
            text = review.read_text(encoding="utf-8")
            text = text.replace("CONTENT_COMMIT_INSERTED_BY_FINALIZER", head)
            text = text.replace("CONTENT_TREE_INSERTED_BY_FINALIZER", tree)
            text = text.replace("SUITE_INSERTED_BY_FINALIZER",
                                f"{passed} passed · {failed} failed · {skipped} skipped")
            review.write_text(text, encoding="utf-8")

    print(f"status finalized from artifact: {passed}/{failed}/{skipped} on {head[:9]} ({tree[:9]})")
    print("next: commit ONLY the status files as the single status-metadata commit:")
    print("  git add " + " ".join(STATUS_METADATA_FILES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
