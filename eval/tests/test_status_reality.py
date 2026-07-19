"""The status-reality guard: the canonical status record must match the checked-out repository
AND be backed by an actual suite run.

Two rehearsals shaped this file. The first (non-independent) found CURRENT.md stale by one commit
with nothing noticing. The second (independent, clean-clone) found the deeper defect: the guard
verified that recorded passed+failed+skipped equalled the COLLECTED test population - which proves
how many tests exist, not that they passed. A clean clone produced 46 failures under a green
record.

The corrected design:

  - scripts/run_canonical_suite.py is the only producer of the result artifact
    (docs/implementation/SUITE-RESULT.json), written from a REAL run on a CLEAN checkout;
  - scripts/update_current_status.py records status ONLY from a valid artifact;
  - this guard validates the whole chain: the two-commit relationship, the registry mirror, the
    artifact's integrity (hash, exit status, zero failures, zero deselection, right commit, right
    tree, canonical command), consistency between artifact and record, and - at rest - that the
    artifact's population matches the live test population.

Repository states the relationship check recognises (a commit cannot contain its own hash, so
"recorded == HEAD" cannot be the only legal state):

  FINALIZED  recorded == HEAD^ and the top commit touched only the declared status files.
             The at-rest state. Artifact REQUIRED and fully validated.
  PRODUCING  recorded == HEAD^^, HEAD^ is a pure status-metadata commit, HEAD is the next content
             commit. This state exists exactly while run_canonical_suite.py produces the next
             artifact on the fresh content commit; artifact checks apply once it exists.
  BASELINE   recorded == HEAD (pre-convention history only).

Anything else - including a metadata commit that smuggled in a substantive change - fails.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "docs" / "implementation" / "CURRENT.md"
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"

sys.path.insert(0, str(ROOT / "scripts"))
from suite_result import ARTIFACT_RELPATH, payload_hash, validation_errors  # noqa: E402
from update_current_status import STATUS_METADATA_FILES  # noqa: E402


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def status_block() -> dict:
    text = CURRENT.read_text(encoding="utf-8")
    m = re.search(r"```yaml\n(# status-block:.*?)```", text, re.S)
    assert m, "CURRENT.md has no machine-maintained status-block"
    return yaml.safe_load(m.group(1))


def repo_state() -> str:
    """FINALIZED | PRODUCING | BASELINE - or an assertion failure naming the drift."""
    blk = status_block()
    recorded = blk["content_commit"]
    head = git("rev-parse", "HEAD")
    # The recorded tree must be the recorded commit's tree in EVERY state - a wrong tree under a
    # correct commit is a forgery, and the first mutation pass proved the old guard only checked
    # the tree when the commit also mismatched.
    assert blk["content_tree"] == git("rev-parse", f"{recorded}^{{tree}}"), (
        "recorded content_tree is not the recorded commit's tree"
    )
    if recorded == head:
        return "BASELINE"
    if recorded == git("rev-parse", "HEAD^"):
        changed = [f for f in git("diff", "--name-only", "HEAD^", "HEAD").split("\n") if f]
        stray = [f for f in changed if f not in STATUS_METADATA_FILES]
        assert not stray, (
            f"the status-metadata commit changed non-status files: {stray} - a metadata commit "
            "that carries substantive changes defeats the convention"
        )
        return "FINALIZED"
    if recorded == git("rev-parse", "HEAD^^"):
        changed = [f for f in git("diff", "--name-only", "HEAD^^", "HEAD^").split("\n") if f]
        stray = [f for f in changed if f not in STATUS_METADATA_FILES]
        assert not stray, (
            "HEAD^ is not a pure status-metadata commit - this is not the producing state, "
            "it is two unfinalized content commits, which the convention forbids"
        )
        return "PRODUCING"
    raise AssertionError(
        f"CURRENT.md records {recorded[:9]} but HEAD is {head[:9]} - the status authority is "
        "stale beyond every legal state. Run the finalization cycle "
        "(run_canonical_suite.py, then update_current_status.py, then the metadata commit)."
    )


def working_tree_clean() -> bool:
    return not subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()


# ------------------------------------------------------------------ 1. relationship

def test_recorded_commit_and_tree_match_a_legal_repository_state():
    state = repo_state()
    assert state in {"FINALIZED", "PRODUCING", "BASELINE"}


# ------------------------------------------------------------------ 2. the artifact backs the record

def test_the_status_record_is_backed_by_a_real_suite_result():
    """The record's counts must come from a validated artifact, not from anyone's memory.

    At rest (FINALIZED), the artifact is REQUIRED - a status record with no run behind it is
    exactly the false green the clean-clone rehearsal found. In the transient PRODUCING state the
    next artifact may not exist yet; consistency is enforced the moment it does.
    """
    state = repo_state()
    blk = status_block()
    path = ROOT / ARTIFACT_RELPATH
    if not path.exists():
        assert state != "FINALIZED", (
            "FINALIZED state with no suite-result artifact - the recorded status has no run "
            "behind it"
        )
        return
    art = json.loads(path.read_text(encoding="utf-8"))
    errs = validation_errors(art, expect_commit=blk["content_commit"], expect_tree=blk["content_tree"])
    assert not errs, "the suite-result artifact cannot back the recorded status:\n  " + "\n  ".join(errs)
    assert (art["passed"], art["failed"], art["skipped"]) == (
        blk["suite_passed"], blk["suite_failed"], blk["suite_skipped"]
    ), "CURRENT.md's recorded counts disagree with the artifact they claim to come from"
    assert blk["suite_failed"] == 0, "the recorded status admits failing tests - not a green baseline"


def test_at_rest_the_artifact_population_matches_the_live_test_population():
    """Adding or removing a test without re-finalizing must fail the build - at rest.

    Collection alone can never prove a green suite (the corrected lesson), but population drift
    is still real drift: an artifact describing 1180 tests is stale evidence in a repository that
    now contains 1200. Skipped while the tree is dirty or producing - development in progress is
    exactly the window in which the next finalization will re-prove everything.
    """
    state = repo_state()
    if state != "FINALIZED" or not working_tree_clean():
        return
    art = json.loads((ROOT / ARTIFACT_RELPATH).read_text(encoding="utf-8"))
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "eval/", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )
    m = re.search(r"(\d+) tests? collected", r.stdout)
    assert m, f"could not parse collected-test count:\n{r.stdout[-500:]}"
    collected = int(m.group(1))
    assert collected > 1000, f"only {collected} tests collected - the population itself is implausible"
    assert art["collected"] == collected, (
        f"the artifact describes a suite of {art['collected']} tests but {collected} exist - "
        "re-run the finalization cycle"
    )


# ------------------------------------------------------------------ 3. registry meta mirror

def test_registry_meta_mirrors_current_md_exactly():
    blk = status_block()
    meta = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["meta"]
    assert meta["baseline_commit"] == blk["content_commit"], (
        "IMPLEMENTATION-REGISTRY.yaml meta.baseline_commit disagrees with CURRENT.md"
    )
    assert meta["validated_tree"] == blk["content_tree"], (
        "IMPLEMENTATION-REGISTRY.yaml meta.validated_tree disagrees with CURRENT.md"
    )
    expect = f"{blk['suite_passed']} passed, {blk['suite_failed']} failed, {blk['suite_skipped']} conditionally justified skip"
    assert meta["suite"] == expect, (
        f"registry meta.suite {meta['suite']!r} != CURRENT.md-derived {expect!r}"
    )


# ------------------------------------------------------------------ 4. no secondary volatile claims

def _strip_historical(text: str) -> str:
    """Quarantined <details> blocks exist precisely to hold stale figures. Exempt them."""
    return re.sub(r"<details>.*?</details>", "", text, flags=re.S)


def test_no_secondary_file_carries_its_own_volatile_status_claim():
    """Volatile commit/tree/suite figures live in CURRENT.md's block and nowhere else."""
    files = [ROOT / n for n in ("README.md", "PRODUCT.md", "AGENTS.md", "CLAUDE.md", "ARCHITECTURE.md")]
    files += sorted(ROOT.glob(".claude/agents/*.md")) + sorted(ROOT.glob(".codex/agents/*.md"))
    assert len(files) >= 10, "the scan population collapsed - this guard would pass vacuously"
    offenders = []
    for f in files:
        text = _strip_historical(f.read_text(encoding="utf-8"))
        for m in re.finditer(r"\b\d{3,5}\s+(?:tests?\s+)?(?:passed|passing)\b", text, re.I):
            line = text[: m.start()].count("\n") + 1
            offenders.append(f"{f.relative_to(ROOT)}:{line}: {m.group(0)!r}")
    assert not offenders, (
        "volatile suite figures outside CURRENT.md's status-block (each one is a future H-1): "
        f"{offenders}"
    )


# ------------------------------------------------------------------ 5. fresh but also RIGHT

def test_the_status_record_still_states_the_canonical_facts():
    text = CURRENT.read_text(encoding="utf-8")
    assert re.search(r"\*\*P2\*\*.*COMPLETE", text), "P2 no longer recorded COMPLETE"
    assert re.search(r"\*\*P3\*\*.{0,80}NOT STARTED", text, re.S), "P3 no longer recorded NOT STARTED"
    assert re.search(r"ZERO-CONTEXT CLI HANDOFF REHEARSAL", text), (
        "the current work program is no longer the independent rehearsal/readiness gate"
    )
    assert re.search(r"INDEPENDENT", text), (
        "the status must record that the owed rehearsal is the INDEPENDENT one"
    )
    units = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]
    p3 = next(u for u in units if u["unit_id"] == "P3")
    assert p3["status"] == "BLOCKED", f"P3 is {p3['status']} in the registry - must be BLOCKED"


# ------------------------------------------------------------------ 6. the validator itself is load-bearing

def _forged(base_overrides: dict) -> dict:
    data = {
        "command": ".venv/bin/python -m pytest eval/ -q",
        "commit": "a" * 40, "tree": "b" * 40,
        "python_version": "3.12.0", "platform": "test",
        "passed": 100, "failed": 0, "skipped": 1, "collected": 101, "deselected": 0,
        "duration_seconds": 1.0, "exit_status": 0, "completed_at": "2026-01-01T00:00:00+00:00",
    }
    data.update(base_overrides)
    data["payload_sha256"] = payload_hash(data)
    return data


def test_the_validator_rejects_every_forgery_the_rehearsal_identified():
    """Unit-proof of the shared validator - so weakening suite_result.py is caught HERE even
    though no real artifact in the repository is red. Each forgery below is a case the old
    collection-only design silently accepted."""
    ok = _forged({})
    assert validation_errors(ok, expect_commit="a" * 40, expect_tree="b" * 40) == []

    red = _forged({"failed": 1, "passed": 99})
    assert any("failed=1" in e for e in validation_errors(red, expect_commit="a" * 40, expect_tree="b" * 40)), (
        "a suite with one failure was accepted as a green record"
    )
    crashed = _forged({"exit_status": 2})
    assert any("exit_status" in e for e in validation_errors(crashed, expect_commit="a" * 40, expect_tree="b" * 40))
    other_commit = _forged({})
    assert any("commit" in e for e in validation_errors(other_commit, expect_commit="c" * 40, expect_tree="b" * 40)), (
        "a result from another commit was accepted"
    )
    other_tree = _forged({})
    assert any("tree" in e for e in validation_errors(other_tree, expect_commit="a" * 40, expect_tree="d" * 40)), (
        "a result from another tree was accepted"
    )
    filtered = _forged({"deselected": 40})
    assert any("deselected" in e for e in validation_errors(filtered, expect_commit="a" * 40, expect_tree="b" * 40)), (
        "a filtered run was accepted as the canonical suite"
    )
    tampered = _forged({})
    tampered["passed"] = 999  # edited after hashing
    assert any("hash" in e for e in validation_errors(tampered, expect_commit="a" * 40, expect_tree="b" * 40)), (
        "an edited artifact passed the integrity check"
    )
    missing = _forged({"collected": 150})
    assert any("went missing" in e for e in validation_errors(missing, expect_commit="a" * 40, expect_tree="b" * 40)), (
        "a run with vanished tests was accepted"
    )
