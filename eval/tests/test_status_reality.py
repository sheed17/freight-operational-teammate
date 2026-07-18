"""The status-reality guard: the canonical status record must match the checked-out repository.

The zero-context rehearsal's HIGH finding: CURRENT.md — the single status authority, the first
file the work-unit protocol tells an agent to read — recorded the previous commit, the previous
tree and the previous suite count, the stale figure had been copied into four more files, and no
guard had an opinion about any of it. The control system failed at its primary function and the
failure was invisible.

These guards make that class of drift a build failure:

  1. CURRENT.md's machine-maintained status-block must name the checked-out content baseline,
     under the documented two-commit convention (a commit cannot contain its own hash, so the
     record either names HEAD itself or names HEAD^ with the top commit touching ONLY the
     declared status-metadata files).
  2. The recorded suite population must match the live collected-test population - so a recorded
     count survives only as long as the test suite it counted.
  3. The registry's meta mirror must agree with CURRENT.md exactly.
  4. No secondary control or auto-loaded file may carry its own volatile commit/tree/suite claim.
  5. The stable status facts (P2 COMPLETE, P3 not started, the rehearsal gate as the current
     program) must be present - a status file that is fresh but wrong is worse than stale.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "docs" / "implementation" / "CURRENT.md"
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"

sys.path.insert(0, str(ROOT / "scripts"))
from update_current_status import STATUS_METADATA_FILES  # noqa: E402  single source of the allowed set


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def status_block() -> dict:
    text = CURRENT.read_text(encoding="utf-8")
    m = re.search(r"```yaml\n(# status-block:.*?)```", text, re.S)
    assert m, "CURRENT.md has no machine-maintained status-block"
    return yaml.safe_load(m.group(1))


# ------------------------------------------------------------------ 1. commit + tree vs git

def test_recorded_commit_and_tree_match_the_checked_out_repository():
    """The two-commit convention, verified structurally.

    PASS states:
      (a) recorded == HEAD                    - the content baseline is checked out directly
      (b) recorded == HEAD^ AND the diff HEAD^..HEAD touches ONLY the declared status files
          - the finalized state: content commit + exactly one status-metadata commit
    Everything else - including a metadata commit that smuggled in a substantive change - fails.
    """
    blk = status_block()
    recorded_commit = blk["content_commit"]
    recorded_tree = blk["content_tree"]
    head = git("rev-parse", "HEAD")

    if recorded_commit == head:
        assert recorded_tree == git("rev-parse", "HEAD^{tree}"), (
            "recorded content_tree does not match the recorded commit's tree"
        )
        return

    parent = git("rev-parse", "HEAD^")
    assert recorded_commit == parent, (
        f"CURRENT.md records {recorded_commit[:9]} but HEAD is {head[:9]} and HEAD^ is "
        f"{parent[:9]} - the status authority is stale. This is the rehearsal's H-1 defect; "
        "run scripts/update_current_status.py after the content commit."
    )
    assert recorded_tree == git("rev-parse", "HEAD^^{tree}"), (
        "recorded content_tree does not match the content baseline's tree"
    )
    changed = git("diff", "--name-only", "HEAD^", "HEAD").split("\n")
    stray = [f for f in changed if f and f not in STATUS_METADATA_FILES]
    assert not stray, (
        f"the status-metadata commit changed non-status files: {stray} - a metadata commit that "
        "carries substantive changes defeats the whole convention"
    )


# ------------------------------------------------------------------ 2. suite counts vs reality

def test_recorded_suite_population_matches_the_live_test_population():
    """A recorded count is only evidence while the suite it counted still exists.

    The guard cannot re-run the full suite inside the suite (recursion), so it verifies the
    invariant that actually decays: recorded passed+failed+skipped must equal the number of tests
    that exist right now. Adding or removing a single test without re-finalizing the status fails
    the build - which is exactly how the 1073-vs-1141 drift would have been caught. The recorded
    pass/fail split itself is proven by the final-validation run recorded in the review document.
    """
    blk = status_block()
    recorded_total = blk["suite_passed"] + blk["suite_failed"] + blk["suite_skipped"]
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "eval/", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )
    m = re.search(r"(\d+) tests? collected", r.stdout)
    assert m, f"could not parse collected-test count:\n{r.stdout[-500:]}"
    collected = int(m.group(1))
    assert collected > 1000, f"only {collected} tests collected - the population itself is implausible"
    assert recorded_total == collected, (
        f"CURRENT.md records a suite of {recorded_total} tests but {collected} exist - "
        "the status authority describes a different repository than the one checked out"
    )
    assert blk["suite_failed"] == 0, "the recorded status admits failing tests - not a green baseline"


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
    """Volatile commit/tree/suite figures live in CURRENT.md's block and nowhere else.

    The rehearsal found the stale suite count copied into four more files. Stable architectural
    counts (134 transitions, 98 events, 31 edges...) are not volatile and are deliberately not
    matched here - only suite-result-shaped figures are.
    """
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
        "the status must record that the owed rehearsal is the INDEPENDENT one - a non-independent "
        "rehearsal already ran and cannot close the gate"
    )
    units = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]
    p3 = next(u for u in units if u["unit_id"] == "P3")
    assert p3["status"] == "BLOCKED", f"P3 is {p3['status']} in the registry - must be BLOCKED"
