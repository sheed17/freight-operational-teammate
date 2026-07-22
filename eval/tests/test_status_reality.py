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

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "docs" / "implementation" / "CURRENT.md"
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"

sys.path.insert(0, str(ROOT / "scripts"))
from suite_result import ARTIFACT_RELPATH, artifact_consistency_errors, payload_hash  # noqa: E402
from finalize_status import STATUS_METADATA_FILES  # noqa: E402


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
    if not working_tree_clean():
        # M-4: same rule as the population check - a dirty authoring tree cannot be measured, and
        # measuring-nothing must be SKIPPED (machine-visible), never PASSED. Absent from the
        # approved canonical-run skips, so a canonical run (always clean) can never skip here.
        pytest.skip("NOT-RUN: dirty working tree - committed-state consistency cannot be "
                    "measured here; canonical finalization refuses dirty trees")
    blk = status_block()
    path = ROOT / ARTIFACT_RELPATH
    if not path.exists():
        assert state != "FINALIZED", (
            "FINALIZED state with no suite-result artifact - the recorded status has no run "
            "behind it"
        )
        return
    art = json.loads(path.read_text(encoding="utf-8"))
    if repo_state() == "PRODUCING":
        # The in-flight finalization is producing this artifact's REPLACEMENT; the committed one
        # describes the PREVIOUS baseline (and, across format migrations, the previous format).
        # It was fully validated when that baseline finalized. Here the true, still-mandatory
        # property is binding: it must describe the recorded baseline, not some other commit.
        # Full validation re-engages at FINALIZED - which is the only at-rest state, the state
        # clean clones see, and the state finalization must end in.
        assert art.get("commit") == blk["content_commit"], (
            "the committed artifact does not describe the recorded content baseline"
        )
        return
    errs = artifact_consistency_errors(art, expect_commit=blk["content_commit"], expect_tree=blk["content_tree"])
    assert not errs, "the suite-result artifact cannot back the recorded status:\n  " + "\n  ".join(errs)
    assert (art["passed"], art["failed"], art["skipped"]) == (
        blk["suite_passed"], blk["suite_failed"], blk["suite_skipped"]
    ), "CURRENT.md's recorded counts disagree with the artifact they claim to come from"
    assert blk["suite_failed"] == 0, "the recorded status admits failing tests - not a green baseline"


def test_at_rest_the_artifact_population_matches_the_live_test_population():
    """H-2 + M-4 (U-HANDOFF-1C): the live collected NODE IDENTITIES must equal the committed
    TEST-NODE-MANIFEST exactly - missing nodes, extra nodes and same-count substitutions all
    fail, in FINALIZED and PRODUCING states alike (the manifest travels with the content commit,
    so it is current in both). At rest (FINALIZED) the artifact must additionally describe the
    manifest's population. A count comparison is retained only as a derived readability check.
    """
    state = repo_state()
    if not working_tree_clean():
        # M-4: this used to `return` here - a PASS that measured nothing. A dirty tree now
        # produces an EXPLICIT machine-visible SKIPPED. It can never appear in a canonical
        # finalization run: the finalizer refuses dirty trees before pytest starts, and this
        # node is deliberately absent from APPROVED-SKIPS expected_canonical_run_skips, so if it
        # ever shows up as a canonical-run skip, finalization fails.
        pytest.skip("NOT-RUN: dirty working tree - the committed state cannot be measured here; "
                    "canonical finalization refuses dirty trees and treats this skip as failure")
    manifest = json.loads((ROOT / "docs" / "implementation" / "TEST-NODE-MANIFEST.json").read_text())
    recorded_nodes = set(manifest["node_ids"])
    assert len(recorded_nodes) > 1000, "the node manifest collapsed - implausible population"
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-c", str(ROOT / "pytest-canonical.ini"),
         "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True,
        env={**__import__("os").environ, "PYTEST_ADDOPTS": ""},
    )
    live_nodes = {l.strip() for l in r.stdout.split("\n") if re.match(r"^eval/.*::", l.strip())}
    assert live_nodes, f"live collection produced zero nodes:\n{r.stdout[-500:]}"
    missing = sorted(recorded_nodes - live_nodes)
    extra = sorted(live_nodes - recorded_nodes)
    assert not missing and not extra, (
        f"the live test population diverged from the committed node manifest by IDENTITY "
        f"(missing={missing[:5]}{'...' if len(missing) > 5 else ''}, "
        f"extra={extra[:5]}{'...' if len(extra) > 5 else ''}) - run "
        "scripts/regenerate_test_manifest.py intentionally and commit the reviewed diff"
    )
    if state == "FINALIZED":
        art = json.loads((ROOT / ARTIFACT_RELPATH).read_text(encoding="utf-8"))
        assert art["collected"] == len(recorded_nodes), (
            f"the artifact describes {art['collected']} tests but the manifest records "
            f"{len(recorded_nodes)} - the recorded run predates the current population"
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
    sys.path.insert(0, str(ROOT / "eval"))
    from control import inventory as _inv
    files = [ROOT / f for f in _inv.root_control_like_documents() if f.endswith(".md")]
    files += [ROOT / f for f in _inv.agent_files() + _inv.compatibility_agent_files()]
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
    # REPLACED, not deleted (this guard's own instruction, two asserts below). P3 has started, so
    # "NOT STARTED" became false. The fact that must stay recorded is the one that is still load-
    # bearing and still easy to lose: P3 is NOT COMPLETE. Its kernel is implemented, but
    # independent_review and final_adjudication are PENDING and cannot be supplied by the session
    # that wrote the code, so the phase table must not quietly promote it.
    assert re.search(r"\*\*P3\*\*.{0,120}NOT COMPLETE", text, re.S), (
        "P3 is no longer recorded NOT COMPLETE - it may only be recorded COMPLETE once the "
        "registry says so on independent evidence"
    )
    assert re.search(r"the next approved unit is `P3`", text, re.I), (
        "the current work program is no longer P3 - if the program moved on, this guard must be "
        "REPLACED with the new truth, not deleted (U-REBASELINE-1A closed both gates)"
    )
    assert re.search(r"BOTH GATES ARE CLOSED", text, re.I), (
        "the status must record that both gates closed (U-HANDOFF-1D on the independent "
        "U-HANDOFF-2B evidence; U-REBASELINE-1A on the independent U-REBASELINE-REVIEW-1) - "
        "losing that record un-explains why P3 is READY"
    )
    units = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]
    by = {u["unit_id"]: u for u in units}
    # U-REBASELINE-1A: P3 is now READY (both gates closed on independent evidence). READY is NOT
    # implemented - the absence guards prove no P3 symbol exists in src/, and CURRENT.md must keep
    # saying so. Replaced, not deleted, from the P3-must-be-BLOCKED assertion.
    assert by["P3"]["status"] == "READY", f"P3 is {by['P3']['status']} - expected READY"
    assert not by["P3"].get("validation_blockers"), (
        "P3 is READY while validation blockers remain recorded"
    )
    for later in ("P4", "P5", "P14"):
        assert by[later]["status"] == "BLOCKED", (
            f"{later} is {by[later]['status']} - every phase after P3 must stay BLOCKED"
        )
    # REPLACED at P3 (see the same replacement in test_docs_control_system.test_24b). The original
    # required "P3 is READY ... NOT IMPLEMENTED", which was true only while READY meant not-begun.
    # P3 is now implemented AND still READY, because implementation is not adjudication. The
    # distinction CURRENT.md must still draw is the one that can still mislead a fresh session:
    # READY plus working code does NOT mean the unit is COMPLETE.
    assert re.search(r"P3\b.{0,200}NOT COMPLETE", text, re.I | re.S), (
        "CURRENT.md must state that P3, though READY and implemented, is NOT COMPLETE"
    )


# ------------------------------------------------------------------ 6. the validator itself is load-bearing

def _forged(base_overrides: dict) -> dict:
    data = {
        "command": ".venv/bin/python -m pytest -c pytest-canonical.ini -v",
        "commit": "a" * 40, "tree": "b" * 40,
        "python_version": "3.12.0", "platform": "test",
        "passed": 100, "failed": 0, "skipped": 1, "collected": 101, "deselected": 0,
        "duration_seconds": 1.0, "exit_status": 0, "completed_at": "2026-01-01T00:00:00+00:00",
        "config_sha256": "c" * 64, "runner_sha256": "d" * 64, "manifest_sha256": "e" * 64,
        "skipped_nodes": ["eval/tests/test_x.py::test_skip_one"],
    }
    data.update(base_overrides)
    data["payload_sha256"] = payload_hash(data)
    return data


def test_the_validator_rejects_every_forgery_the_rehearsal_identified():
    """Unit-proof of the shared validator - so weakening suite_result.py is caught HERE even
    though no real artifact in the repository is red. Each forgery below is a case the old
    collection-only design silently accepted."""
    ok = _forged({})
    assert artifact_consistency_errors(ok, expect_commit="a" * 40, expect_tree="b" * 40) == []

    red = _forged({"failed": 1, "passed": 99})
    assert any("failed=1" in e for e in artifact_consistency_errors(red, expect_commit="a" * 40, expect_tree="b" * 40)), (
        "a suite with one failure was accepted as a green record"
    )
    crashed = _forged({"exit_status": 2})
    assert any("exit_status" in e for e in artifact_consistency_errors(crashed, expect_commit="a" * 40, expect_tree="b" * 40))
    other_commit = _forged({})
    assert any("commit" in e for e in artifact_consistency_errors(other_commit, expect_commit="c" * 40, expect_tree="b" * 40)), (
        "a result from another commit was accepted"
    )
    other_tree = _forged({})
    assert any("tree" in e for e in artifact_consistency_errors(other_tree, expect_commit="a" * 40, expect_tree="d" * 40)), (
        "a result from another tree was accepted"
    )
    filtered = _forged({"deselected": 40})
    assert any("deselected" in e for e in artifact_consistency_errors(filtered, expect_commit="a" * 40, expect_tree="b" * 40)), (
        "a filtered run was accepted as the canonical suite"
    )
    tampered = _forged({})
    tampered["passed"] = 999  # edited after hashing
    assert any("hash" in e for e in artifact_consistency_errors(tampered, expect_commit="a" * 40, expect_tree="b" * 40)), (
        "an edited artifact passed the integrity check"
    )
    missing = _forged({"collected": 150})
    assert any("went missing" in e for e in artifact_consistency_errors(missing, expect_commit="a" * 40, expect_tree="b" * 40)), (
        "a run with vanished tests was accepted"
    )
