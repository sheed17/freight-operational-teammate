"""R-21 - THE INTEGRATION-TOPOLOGY GUARD.

The two-commit convention permits HEAD to be only the certified content commit or the single
finalizer-generated metadata commit directly above it, and test_status_reality.py resolves both
through FIRST-PARENT lookups (HEAD^, HEAD^^). A standard GitHub pull-request merge appends a commit
whose first parent is the base branch - so HEAD^ stops being the content commit and the repository
lands in the state that guard calls "stale beyond every legal state".

This is not hypothetical. `main` reached 152574e through three PR merge commits and fails
test_status_reality there today. The certified content tree was never corrupted - the whole defect
is topological, which is exactly why nothing about the content looks wrong.

Two mechanisms live here, because a procedure written into a document decays the moment someone
clicks the merge button:

  1. THE LIVE CHECK - neither HEAD nor HEAD^ may be a merge commit. This is the assertion that
     would have caught the defect at the moment it was introduced.
  2. THE HERMETIC REHEARSAL - a synthetic repository reproducing the exact shape (a certified pair,
     plus CI workflow files that arrived on the base branch through a PR merge), put through the
     documented fast-forward-only procedure, asserting every property the procedure claims. The
     rehearsal is re-executed every canonical suite rather than recorded as a past success.

The rejection cases for the predicate are unit tests of the predicate - they ARE the mutation
proofs, run every suite. A guard that only ever sees legal input has not been shown to discriminate.

Correct topology is NECESSARY for integration and is NOT SUFFICIENT: it carries no evidentiary
weight at all. Only scripts/finalize_status.py produces an acceptable receipt, and the payload-hash
guard in suite_result.py rejects a hand-edited one.

See docs/implementation/integration-topology-procedure.md (the procedure) and
docs/implementation/implementation-risk-register.md (R-21).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from finalize_status import STATUS_METADATA_FILES  # noqa: E402

IMPL = ROOT / "docs" / "implementation"
PROCEDURE = IMPL / "integration-topology-procedure.md"
REGISTER = IMPL / "implementation-risk-register.md"
PROTOCOL = IMPL / "PROGRESS-PROTOCOL.md"

# A status file the rehearsal may touch to stand in for the finalizer's output.
A_STATUS_FILE = STATUS_METADATA_FILES[0]


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def parent_count(rev: str, cwd: Path = ROOT) -> int:
    """How many parents `rev` has. A merge commit has two or more."""
    return len(git("log", "-1", "--format=%P", rev, cwd=cwd).split())


# --------------------------------------------------------------- the predicate

def linearity_errors(head_parents: int, first_parent_parents: int) -> list[str]:
    """The rule, as a pure function so its rejection cases are testable.

    `head_parents` is HEAD's parent count; `first_parent_parents` is HEAD^'s. Under the convention
    HEAD is a content commit or a metadata commit and HEAD^ is the other one, so NEITHER may be a
    merge. Anything further down the history is unconstrained - the convention governs the top of
    the branch, not the whole graph, which is why merge commits already in `main`'s ancestry are
    harmless once a fast-forward has restored a legal pair on top of them.
    """
    errs = []
    if head_parents > 1:
        errs.append(
            f"HEAD is a merge commit ({head_parents} parents) - a merge above a certified pair "
            "makes HEAD^ the base branch instead of the content commit"
        )
    if first_parent_parents > 1:
        errs.append(
            f"HEAD^ is a merge commit ({first_parent_parents} parents) - the other half of the "
            "certified pair cannot be a merge"
        )
    return errs


# --------------------------------------------------------------- 1. the live check

def test_neither_head_nor_its_first_parent_is_a_merge_commit():
    """The assertion that would have caught the defect the moment it was introduced."""
    errs = linearity_errors(parent_count("HEAD"), parent_count("HEAD^"))
    assert not errs, (
        "integration topology violated (R-21):\n  "
        + "\n  ".join(errs)
        + "\nSee docs/implementation/integration-topology-procedure.md - `main` advances by "
        "fast-forward only."
    )


# --------------------------------------------------------------- 2. rejection cases (mutation proofs)

def test_the_predicate_rejects_a_merge_commit_at_head():
    """The exact shape `main` is in at 152574e."""
    assert linearity_errors(2, 1), "a merge commit at HEAD was accepted"


def test_the_predicate_rejects_a_merge_commit_as_the_other_half_of_the_pair():
    assert linearity_errors(1, 2), "a merge commit at HEAD^ was accepted"


def test_the_predicate_rejects_an_octopus_merge():
    assert linearity_errors(3, 1), "a three-parent merge at HEAD was accepted"


def test_the_predicate_accepts_a_linear_pair():
    assert linearity_errors(1, 1) == []


def test_the_predicate_accepts_a_pair_above_the_root_commit():
    """HEAD^ is the root commit (no parents) - legal, not a merge."""
    assert linearity_errors(1, 0) == []


# --------------------------------------------------------------- 3. the hermetic rehearsal

def _init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    git("init", "-q", "-b", "main", str(repo), cwd=repo.parent)
    git("config", "user.email", "rehearsal@localhost", cwd=repo)
    git("config", "user.name", "rehearsal", cwd=repo)


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", message, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)


def _build_the_defective_shape(repo: Path) -> tuple[str, str, str]:
    """A certified pair, plus CI files that reached the base branch through a PR merge.

    Returns (content_commit, metadata_commit, base_tip) where base_tip is a MERGE commit - the
    illegal state `main` is actually in.
    """
    _init(repo)
    _write(repo, "src/base.py", "base\n")
    _commit(repo, "base")

    # the CI workflows arrive on their own branch, exactly as PR #1 did
    git("checkout", "-q", "-b", "ci", cwd=repo)
    _write(repo, ".github/workflows/claude.yml", "name: claude\n")
    _write(repo, ".github/workflows/claude-code-review.yml", "name: review\n")
    _commit(repo, "CI workflows")

    # meanwhile the certified pair lands on main
    git("checkout", "-q", "main", cwd=repo)
    _write(repo, "src/unit_p3.py", "p3\n")
    content = _commit(repo, "P3 content")
    _write(repo, A_STATUS_FILE, '{"commit": "recorded"}\n')
    metadata = _commit(repo, "Record executed status (status-metadata commit)")

    # ...and the PR merge button appends a merge commit ON TOP of the pair
    git("merge", "-q", "--no-ff", "-m", "Merge pull request #1", "ci", cwd=repo)
    return content, metadata, git("rev-parse", "HEAD", cwd=repo)


def test_the_rehearsal_reproduces_the_defect_before_it_repairs_it():
    """The synthetic shape must actually be illegal, or the repair below proves nothing."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "neyma"
        _, _, base_tip = _build_the_defective_shape(repo)
        assert parent_count(base_tip, cwd=repo) == 2, "the rehearsal did not build a merge commit"
        errs = linearity_errors(parent_count("HEAD", cwd=repo), parent_count("HEAD^", cwd=repo))
        assert errs, "the rehearsed defect was not detected - the guard proves nothing"


def test_the_documented_procedure_produces_a_legal_integrable_pair():
    """Replay onto the base tip -> one content commit -> one metadata commit -> fast-forward.

    Asserts every property docs/implementation/integration-topology-procedure.md claims.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "neyma"
        _, pair_tip, base_tip = _build_the_defective_shape(repo)

        # the unit is built on the certified pair, as P4 is
        git("checkout", "-q", "-b", "unit", pair_tip, cwd=repo)
        _write(repo, "src/unit_p4/a.py", "a\n")
        _commit(repo, "unit work 1")
        _write(repo, "src/unit_p4/b.py", "b\n")
        _commit(repo, "unit work 2")

        # STEP 1+2: replay onto the base tip, collapse to exactly ONE content commit
        git("rebase", "-q", "--onto", base_tip, pair_tip, "unit", cwd=repo)
        git("reset", "-q", "--soft", base_tip, cwd=repo)
        content = _commit(repo, "unit: content commit")

        # STEP 4: the single status-metadata commit, touching only status files
        _write(repo, A_STATUS_FILE, '{"commit": "%s"}\n' % content)
        metadata = _commit(repo, "Record executed status (status-metadata commit)")

        # -- the content commit carries BOTH the CI files and the unit's work
        tree = git("ls-tree", "-r", "--name-only", content, cwd=repo).split("\n")
        assert ".github/workflows/claude.yml" in tree, "the CI workflow files were dropped"
        assert ".github/workflows/claude-code-review.yml" in tree, "a CI workflow file was dropped"
        assert "src/unit_p4/a.py" in tree and "src/unit_p4/b.py" in tree, "the unit's work was lost"
        assert "src/unit_p3.py" in tree, "previously certified content was lost"

        # -- exactly one content commit, exactly one metadata commit, neither a merge
        assert git("rev-list", "--count", f"{base_tip}..{content}", cwd=repo) == "1", (
            "the unit did not collapse to exactly one content commit"
        )
        assert linearity_errors(
            parent_count(metadata, cwd=repo), parent_count(content, cwd=repo)
        ) == [], "the procedure produced a merge commit in the pair"

        # -- the metadata commit touches ONLY status files
        changed = [
            f for f in git("diff", "--name-only", content, metadata, cwd=repo).split("\n") if f
        ]
        stray = [f for f in changed if f not in STATUS_METADATA_FILES]
        assert changed and not stray, f"the metadata commit carried non-status files: {stray}"

        # -- test_status_reality's own relationship holds: the recorded commit is HEAD^
        assert git("rev-parse", "HEAD^", cwd=repo) == content, (
            "HEAD^ is not the content commit - test_status_reality would reject this"
        )

        # -- shared history is not rewritten, and the base fast-forwards with NO new commit
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", base_tip, metadata],
            cwd=repo, check=True,
        )
        git("checkout", "-q", "main", cwd=repo)
        git("merge", "-q", "--ff-only", "unit", cwd=repo)
        assert git("rev-parse", "HEAD", cwd=repo) == metadata, "the base did not fast-forward"
        assert git("rev-list", "--count", "--merges", f"{base_tip}..HEAD", cwd=repo) == "0", (
            "integration introduced a merge commit"
        )

        # -- and the live predicate now accepts the integrated base
        assert linearity_errors(
            parent_count("HEAD", cwd=repo), parent_count("HEAD^", cwd=repo)
        ) == [], "the integrated base is still illegal"


# --------------------------------------------------------------- 4. the obligation stays recorded

def test_the_integration_procedure_is_recorded():
    assert PROCEDURE.exists(), "the integration procedure document is missing"
    text = PROCEDURE.read_text(encoding="utf-8")
    for required in ("fast-forward", "R-21", "STATUS_METADATA_FILES", "test_status_reality"):
        assert required in text, f"the procedure no longer records: {required}"
    assert re.search(r"FAST[- ]FORWARD ONLY|fast-forward only", text, re.I), (
        "the procedure no longer states the fast-forward-only invariant"
    )


def test_r21_is_recorded_with_a_mechanism_and_an_owner():
    """A mitigation that reads 'remember to use the right merge button' is not a mitigation."""
    register = REGISTER.read_text(encoding="utf-8")
    row = next(
        (l for l in register.split("\n") if re.match(r"^\|\s*(###\s*)?\*\*R-21\*\*", l)), None
    )
    assert row, "R-21 is no longer recorded in the risk register"
    cells = row.split("|")
    assert "fast-forward" in cells[5].lower(), "R-21's mitigation no longer names the mechanism"
    assert "integration-topology-procedure" in cells[5], "R-21 no longer points at the procedure"
    assert cells[7].strip(), "R-21 has no owner"


def test_the_progress_protocol_states_the_invariant():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "Integration topology" in text, "PROGRESS-PROTOCOL.md no longer covers integration topology"
    assert "integration-topology-procedure.md" in text, (
        "PROGRESS-PROTOCOL.md no longer points at the procedure"
    )
    assert re.search(r"fast[- ]forward only", text, re.I), (
        "PROGRESS-PROTOCOL.md no longer states the fast-forward-only invariant"
    )
