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
    """Quarantined <details> blocks exist precisely to hold stale figures. Exempt them - but only
    when the block SAYS SO.

    DELEGATED at the R-01/R-02 remediation to the one label-aware definition in
    `control.status_claims`. An UNLABELLED `<details>` block is not a quarantine, and exempting one
    is how a stale figure hides from the very guard that exists to find it."""
    sys.path.insert(0, str(ROOT / "eval"))
    from control import status_claims

    return status_claims.strip_historical_blocks(text)


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
    """REPLACED at the P4 ACCEPTANCE/STATUS CLOSURE (CLAUDE.md sec 5 rule 20 - replaced, not
    deleted; the function NAME is frozen to preserve its node identity in TEST-NODE-MANIFEST.json).

    Every prior version pinned a moment in one phase's life: P3 NOT STARTED, then P3
    READY-but-NOT-COMPLETE, then P4 READY-but-NOT-COMPLETE. P4 has now been adjudicated COMPLETE
    from independent evidence, so the P4-specific literals became false and could only be deleted
    or re-pointed. Re-pointed. The load-bearing invariants are unchanged in kind:

      * a phase reaches COMPLETE only when the registry says so, and that completion is legitimate
        only with independent_review AND final_adjudication PASS - the two criteria a phase's own
        author structurally cannot supply (THE anti-self-adjudication fact). Asserted for BOTH
        adjudicated phases now, P3 and P4, not just the newest one;
      * the single READY unit is now P5, whose only dependency (P4) is COMPLETE;
      * every phase after the READY one stays BLOCKED;
      * ### R-07 IS NOW CONTAINED - AND COMPLETING P4 IS NOT WHAT DID IT. Recording R-07 CONTAINED
        lives in phase-0-baseline-manifest.yaml, which is not a status file, so it took its own
        later content commit after both finalization passes. This guard is still the reason a
        session cannot quietly conflate "P4 COMPLETE" with "R-07 closed": it requires the status
        authority to record CONTAINED **and** to state the bound - containment is not
        production-write enablement - so an unbounded CONTAINED cannot be read as an enablement.

    THE ANTI-VACUOUS ANCHORS ARE DELIBERATE. A registry that failed to parse, a phase whose
    criteria block went missing, or an empty READY scan would otherwise let every negative
    assertion below pass over nothing at all - the exact false green this file exists to prevent.
    """
    text = CURRENT.read_text(encoding="utf-8")
    assert re.search(r"\*\*P2\*\*.*COMPLETE", text), "P2 no longer recorded COMPLETE"
    assert re.search(r"BOTH GATES ARE CLOSED", text, re.I), (
        "the status must record that both gates closed (U-HANDOFF-1D on the independent "
        "U-HANDOFF-2B evidence; U-REBASELINE-1A on the independent U-REBASELINE-REVIEW-1) - "
        "losing that record un-explains how P3 became READY, then COMPLETE"
    )
    assert re.search(r"R-07.{0,200}CONTAINED", text, re.S), (
        "CURRENT.md must record R-07 CONTAINED - neither completing P3 nor completing P4's "
        "weighted acceptance closed it; the manifest recording was a separate content commit, and "
        "the status authority must state its outcome"
    )
    assert not re.search(r"R-07[^\n]{0,60}?\b(?:is|stays|remains)\s+\*{0,3}OPEN\b", text, re.I), (
        "CURRENT.md still describes R-07 as OPEN after the containment record was written"
    )
    units = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]
    assert units, "the registry parsed to no units - every assertion below would be vacuous"
    by = {u["unit_id"]: u for u in units}
    # POSITIVE ANCHOR: the phases this guard reasons about must actually be present.
    for required in ("P3", "P4", "P5", "P14"):
        assert required in by, f"{required} vanished from the registry"

    # An adjudicated phase is COMPLETE only on a fully-PASS weighted contract summing to 100, whose
    # independent_review + final_adjudication were supplied by a session other than the author.
    for phase in ("P3", "P4"):
        assert by[phase]["status"] == "COMPLETE", (
            f"{phase} is {by[phase]['status']} - expected COMPLETE"
        )
        criteria = by[phase].get("acceptance_criteria")
        assert criteria, f"{phase} is COMPLETE with no weighted acceptance contract at all"
        assert sum(int(c["weight"]) for c in criteria) == 100, (
            f"{phase}'s acceptance weights sum to "
            f"{sum(int(c['weight']) for c in criteria)}, not 100"
        )
        crits = {c["criterion"]: str(c["result"]).upper() for c in criteria}
        assert len(crits) == len(criteria), f"{phase} has duplicate criterion names"
        assert crits.get("independent_review") == "PASS" and crits.get("final_adjudication") == "PASS", (
            f"{phase} is COMPLETE without independent_review + final_adjudication PASS - a "
            "self-adjudicated completion is exactly what this guard exists to forbid"
        )
        assert all(v == "PASS" for v in crits.values()), (
            f"{phase} is COMPLETE while some criteria are not PASS: "
            f"{sorted(k for k, v in crits.items() if v != 'PASS')}"
        )

    # the single READY unit is now P5, and its dependency P4 is COMPLETE
    ready = [u["unit_id"] for u in units if u["status"] == "READY"]
    assert ready == ["P5"], f"expected P5 as the sole READY unit, found {ready}"
    assert by["P5"]["dependencies"], "P5 records no dependencies - its readiness proves nothing"
    for dep in by["P5"]["dependencies"]:
        assert by[dep]["status"] == "COMPLETE", (
            f"P5 is READY while dependency {dep} is {by[dep]['status']}"
        )
    # READY is SELECTION, never execution: P5 must not have started.
    assert by["P5"]["execution_state"] == "NOT_STARTED", (
        f"P5 is READY and already {by['P5']['execution_state']} - the closure commit was allowed "
        "to begin the next phase, which the control boundary forbids"
    )
    assert not by["P5"].get("landed_checkpoints"), "P5 records landed work while NOT_STARTED"
    later_phases = [u["unit_id"] for u in units
                    if re.fullmatch(r"P\d+", u["unit_id"]) and int(u["unit_id"][1:]) >= 6]
    assert later_phases, "no post-P5 phases found - the BLOCKED sweep would be vacuous"
    for later in later_phases:
        assert by[later]["status"] == "BLOCKED", (
            f"{later} is {by[later]['status']} - every phase after the READY P5 must stay BLOCKED"
        )
    # CURRENT.md must name P5 as the approved next unit and state P5 is not thereby complete.
    assert re.search(r"the next approved unit is `P5`", text, re.I), (
        "CURRENT.md must record P5 as the next approved unit - if the program moves on again, "
        "this guard must be REPLACED with the new truth, not deleted"
    )
    assert re.search(r"P5\b.{0,200}NOT COMPLETE", text, re.I | re.S), (
        "CURRENT.md must state that P5, though READY, is NOT COMPLETE"
    )
    # The record must be spelled out AND bounded. An unqualified "R-07 CONTAINED" next to "P4
    # COMPLETE" invites exactly two wrong inferences: that completing P4 closed it, and that closing
    # it enabled something. Both must be refused in the status authority's own words.
    assert re.search(r"R-07\s+is\s+(?:now\s+)?\*{0,3}CONTAINED", text, re.I), (
        "CURRENT.md must spell out that R-07 is CONTAINED"
    )
    assert re.search(r"(?:did|does)\s+\*{0,3}NOT\*{0,3}\s+close\s+(?:it|R-07)|"
                     r"not\s+what\s+did\s+it|is\s+NOT\s+what\s+did\s+it", text, re.I), (
        "CURRENT.md must state that completing P4 did NOT close R-07 - a separate content commit "
        "did; without that sentence a reader infers the conflation this guard exists to prevent"
    )
    assert re.search(r"CONTAINED\s*(?:≠|!=)\s*ENABLED|not mean production writes are enabled|"
                     r"no production write is enabled|enables no production write", text, re.I), (
        "CURRENT.md records R-07 CONTAINED without stating the bound - containment forces external "
        "effects through the governed boundary or fails them closed; it enables nothing"
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
