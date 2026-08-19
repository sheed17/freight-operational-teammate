"""R-21 - THE INTEGRATION-TOPOLOGY GUARD.

The two-commit convention permits HEAD to be only the certified content commit or the single
finalizer-generated metadata commit directly above it, and test_status_reality.py resolves both
through FIRST-PARENT lookups (HEAD^, HEAD^^). A standard GitHub pull-request merge appends a commit
whose first parent is the base branch - so HEAD^ stops being the content commit and the repository
lands in the state that guard calls "stale beyond every legal state".

This is not hypothetical. `main` reached 152574e through three PR merge commits and fails
test_status_reality there today. The certified content tree was never corrupted - the whole defect
is topological, which is exactly why nothing about the content looks wrong.

THE PROCEDURE-REPAIR CORRECTION (R-21b). The first version of this guard expressed the invariant as
a PARENT COUNT: neither HEAD nor HEAD^ may be a merge. That is STRICTER than the invariant the
procedure actually states, and the excess strictness made integration unreachable. Procedure
section 2 says, verbatim:

    "No merge commit may sit ABOVE a certified content commit. Between the content commit and
     HEAD there is exactly one commit - the finalizer-generated metadata commit - and IT has
     exactly one parent."

Section 2 constrains the METADATA commit's parent count and the binding of the first-parent chain.
It says nothing about the CONTENT commit's parent count. The old predicate additionally rejected a
merge at HEAD^, which in the FINALIZED state is the content commit - and integrating a diverged
`origin/main` requires exactly that shape, because:

  - a REBASE makes origin/main an ancestor but rewrites the recorded commit's SHA, so
    repo_state() goes stale at every position, permanently; and
  - a MERGE keeps the first-parent chain intact and repo_state() binding, but was rejected purely
    on parent count.

Any history in which origin/main becomes an ancestor without rewriting the certified pair contains
a merge on the first-parent chain, so under the old predicate the recorded anchor was TRAPPED
BELOW that merge: every position where repo_state() bound was a position the predicate rejected,
and every position the predicate accepted was stale. finalize_status.py validates before it writes,
so it could never be run at the one position that would have produced the legal state. The
documented procedure could not execute its own Step 4.

The corrected predicate asserts the two properties that actually matter, both of which the old one
either missed or expressed only by proxy:

  1. THE CHAIN BINDS - repo_state() resolves HEAD's first-parent chain to the recorded certified
     pair. This is what the GitHub merge button breaks, and it is the real content of "a merge
     above a certified pair makes HEAD^ the base branch instead of the content commit".
  2. THE METADATA COMMIT IS NOT A MERGE - section 2's literal requirement. This is NOT redundant
     with (1): repo_state() checks the metadata commit's DIFF for purity but never its parent
     count, and a merge whose first parent is the recorded content commit and whose second parent
     touches only status files passes repo_state() cleanly. test_the_predicate_and_the_real_guards
     _reject_a_merge_used_as_the_metadata_commit proves that against the real guard.

The content commit may be a merge, provided its FIRST parent is the previous metadata commit -
which is precisely what (1) enforces. That is the shape integration takes, and it is a
fast-forward for `main`: nothing is rewritten and no commit is lost.

Three mechanisms live here, because a procedure written into a document decays the moment someone
clicks the merge button:

  1. THE LIVE CHECK - the chain binds and the metadata commit is not a merge.
  2. THE PURE PREDICATE'S REJECTION CASES - unit tests of the predicate. They ARE the mutation
     proofs, run every suite. A guard that only ever sees legal input has not been shown to
     discriminate.
  3. THE HERMETIC SCENARIOS - synthetic repositories reproducing each real shape (the historical
     defect, the documented-but-unexecutable Step 1+2 state, the integrating merge, a forged merge
     metadata commit), put through the REAL repo_state() and the real predicate, asserting the
     properties at the FINALIZER-TIME state and not only at rest. The previous rehearsal
     hand-wrote its metadata commit and evaluated the predicate only on the final pair, so it
     built the illegal intermediate state and never looked at it.

Correct topology is NECESSARY for integration and is NOT SUFFICIENT: it carries no evidentiary
weight at all. Only scripts/finalize_status.py produces an acceptable receipt, and the payload-hash
guard in suite_result.py rejects a hand-edited one.

See docs/implementation/integration-topology-procedure.md (the procedure) and
docs/implementation/implementation-risk-register.md (R-21).
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from finalize_status import STATUS_METADATA_FILES  # noqa: E402
import test_status_reality as tsr  # noqa: E402
from test_status_reality import repo_state  # noqa: E402

IMPL = ROOT / "docs" / "implementation"
PROCEDURE = IMPL / "integration-topology-procedure.md"
REGISTER = IMPL / "implementation-risk-register.md"
PROTOCOL = IMPL / "PROGRESS-PROTOCOL.md"

# A status file the hermetic scenarios may touch to stand in for the finalizer's output.
A_STATUS_FILE = STATUS_METADATA_FILES[0]
CURRENT_RELPATH = "docs/implementation/CURRENT.md"
assert CURRENT_RELPATH in STATUS_METADATA_FILES, (
    "CURRENT.md must be a status-metadata file or the two-commit convention cannot be written"
)


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def parent_count(rev: str, cwd: Path = ROOT) -> int:
    """How many parents `rev` has. A merge commit has two or more."""
    return len(git("log", "-1", "--format=%P", rev, cwd=cwd).split())


# --------------------------------------------------------------- the predicate

# Which commit is the finalizer-generated status-metadata commit, per repo_state() verdict.
# BASELINE is pre-convention history: there is no metadata commit above the recorded commit.
METADATA_COMMIT_REV = {"FINALIZED": "HEAD", "PRODUCING": "HEAD^", "BASELINE": None}

# Where the CONTENT commit sits on the first-parent chain, per repo_state() verdict. In BASELINE
# the recorded commit IS HEAD; in PRODUCING HEAD is the new, not-yet-finalized content commit.
CONTENT_COMMIT_REV = {"FINALIZED": "HEAD^", "PRODUCING": "HEAD", "BASELINE": "HEAD"}

# A content commit may integrate ONE other lineage - `origin/main` - and no more. Two parents is
# the integrating merge the procedure prescribes; three or more is an octopus carrying a lineage
# no first-parent diff displays, which is the class R-21b's relaxation would otherwise admit.
MAX_CONTENT_PARENTS = 2


def topology_errors(
    state: str, metadata_parents: int | None, content_parents: int | None
) -> list[str]:
    """The rule, as a pure function so its rejection cases are testable.

    `state` is repo_state()'s verdict - or any other string, standing for "the first-parent chain
    does not bind to the recorded pair", which is the state a PR merge commit produces.
    `metadata_parents` is the parent count of the status-metadata commit named by
    METADATA_COMMIT_REV[state], or None in BASELINE where no such commit exists.
    `content_parents` is the parent count of the content commit named by CONTENT_COMMIT_REV[state].

    Anything below the pair is unconstrained - the convention governs the top of the branch, not
    the whole graph, which is why merge commits already in `main`'s ancestry are harmless once a
    fast-forward has restored a legal pair on top of them, and why the CONTENT commit may itself
    be the merge that integrated them - a merge of exactly two lineages, never more.
    """
    errs = []
    if state not in METADATA_COMMIT_REV:
        errs.append(
            f"the first-parent chain from HEAD does not bind to the recorded certified pair "
            f"(state={state!r}) - which is exactly what a merge commit above a certified pair "
            "does: HEAD^ becomes the base branch instead of the content commit"
        )
        return errs
    rev = METADATA_COMMIT_REV[state]
    if rev is None:
        pass  # BASELINE: no metadata commit exists, so there is nothing to constrain here
    elif metadata_parents is None:
        errs.append(
            f"state {state} has a status-metadata commit at {rev} but no parent count was supplied"
        )
    elif metadata_parents > 1:
        errs.append(
            f"the status-metadata commit ({rev}) is a merge ({metadata_parents} parents) - "
            "procedure section 2 requires the single finalizer-generated metadata commit to have "
            "exactly one parent, so HEAD's first parent is the certified content commit"
        )
    elif metadata_parents < 1:
        errs.append(
            f"the status-metadata commit ({rev}) has no parent - it cannot sit above a content commit"
        )

    crev = CONTENT_COMMIT_REV[state]
    if content_parents is None:
        errs.append(
            f"state {state} has a content commit at {crev} but no parent count was supplied"
        )
    elif content_parents > MAX_CONTENT_PARENTS:
        errs.append(
            f"the content commit ({crev}) has {content_parents} parents - it may integrate at "
            f"most {MAX_CONTENT_PARENTS} lineages (itself and `origin/main`). An octopus content "
            "commit carries a lineage no first-parent diff displays, so the independent review "
            "the relaxation leans on cannot see it"
        )
    return errs


# --------------------------------------------------------------- 1. the live check

def test_the_chain_binds_and_the_status_metadata_commit_is_not_a_merge():
    """The assertion that would have caught the defect the moment it was introduced."""
    try:
        state = repo_state()
    except AssertionError as exc:
        raise AssertionError(
            "integration topology violated (R-21): the first-parent chain from HEAD does not "
            "bind to the recorded certified pair - which is what a merge commit above a certified "
            "pair does.\n  " + str(exc)
        ) from exc
    rev = METADATA_COMMIT_REV[state]
    errs = topology_errors(
        state,
        None if rev is None else parent_count(rev),
        parent_count(CONTENT_COMMIT_REV[state]),
    )
    assert not errs, (
        "integration topology violated (R-21):\n  "
        + "\n  ".join(errs)
        + "\nSee docs/implementation/integration-topology-procedure.md - `main` advances by "
        "fast-forward only."
    )


# --------------------------------------------------------------- 2. rejection cases (mutation proofs)

def test_the_predicate_rejects_a_merge_used_as_the_metadata_commit_when_finalized():
    """The forged shape a merge-metadata commit takes at rest."""
    assert topology_errors("FINALIZED", 2, 1), "a merge used as the metadata commit was accepted"


def test_the_predicate_rejects_a_merge_used_as_the_metadata_commit_when_producing():
    """In PRODUCING the metadata commit is HEAD^, and it may not be a merge either."""
    assert topology_errors("PRODUCING", 2, 1), "a merge metadata commit at HEAD^ was accepted"


def test_the_predicate_rejects_an_octopus_metadata_commit():
    assert topology_errors("FINALIZED", 3, 1), "a three-parent metadata commit was accepted"


def test_the_predicate_rejects_a_chain_that_does_not_bind():
    """The exact shape `main` is in at 152574e: repo_state() resolves to no legal state."""
    assert topology_errors("STALE", 1, 1), "an unbound first-parent chain was accepted"
    assert topology_errors("anything else", 1, 1), "an unknown state was accepted"


def test_the_predicate_rejects_a_parentless_metadata_commit():
    assert topology_errors("FINALIZED", 0, 1), "a metadata commit with no parent was accepted"


def test_the_predicate_accepts_a_single_parent_metadata_commit():
    assert topology_errors("FINALIZED", 1, 1) == []
    assert topology_errors("PRODUCING", 1, 1) == []


def test_the_predicate_accepts_baseline_which_has_no_metadata_commit():
    """BASELINE is pre-convention history - there is no metadata commit to constrain."""
    assert topology_errors("BASELINE", None, 1) == []


def test_the_predicate_bounds_the_content_commits_parent_count_at_two():
    """REPLACES test_the_predicate_no_longer_constrains_the_content_commits_parent_count.

    That test asserted only `topology_errors("FINALIZED", 1) == []`, which is byte-identical in
    effect to test_the_predicate_accepts_a_single_parent_metadata_commit: it could not fail for
    the property its name claimed. It is replaced rather than preserved (CLAUDE.md section 5,
    rule 20) - a test that cannot fail for its own property is a decoration with a passing status.

    The rule the predicate actually enforces: the CONTENT commit is no longer required to be a
    non-merge - that requirement is what made integration unreachable - but it may integrate at
    most ONE other lineage. Two parents is the prescribed integrating merge; three or more is an
    octopus carrying a lineage that `git show` renders as an empty patch, which the independent
    review the relaxation leans on would not see.
    """
    for state, metadata_parents in (("FINALIZED", 1), ("PRODUCING", 1), ("BASELINE", None)):
        # a plain content commit and the prescribed integrating merge are both legal
        assert topology_errors(state, metadata_parents, 1) == [], (
            f"a single-parent content commit was rejected in {state}"
        )
        assert topology_errors(state, metadata_parents, 2) == [], (
            f"the prescribed two-parent integrating merge was rejected in {state}"
        )
        # an octopus is not, in any state that has a content commit
        for octopus in (3, 4):
            errs = topology_errors(state, metadata_parents, octopus)
            assert errs, f"an octopus content commit ({octopus} parents) was accepted in {state}"
            assert any("content commit" in e for e in errs), (
                f"rejected for the wrong reason in {state}: {errs}"
            )


# --------------------------------------------------------------- 3. hermetic scenarios

def _init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "user.email", "rehearsal@neyma.test", cwd=repo)
    git("config", "user.name", "rehearsal", cwd=repo)


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", message, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)


def _write_status_block(repo: Path, content_commit: str) -> None:
    """The machine-maintained status block, exactly as scripts/finalize_status.py writes it."""
    tree = git("rev-parse", f"{content_commit}^{{tree}}", cwd=repo)
    _write(repo, CURRENT_RELPATH,
           "# CURRENT\n\n```yaml\n"
           "# status-block: maintained by scripts/finalize_status.py - do not edit by hand\n"
           f"content_commit: {content_commit}\n"
           f"content_tree: {tree}\n"
           "suite_passed: 1\nsuite_failed: 0\nsuite_skipped: 0\n"
           "```\n")


def _finalize_like(repo: Path, content_commit: str) -> str:
    """The status-metadata commit: touches ONLY status-metadata files, exactly one parent.

    This SIMULATES finalize_status.py's output for topology purposes only. It carries no
    evidentiary weight whatsoever - only a real finalizer run produces an acceptable receipt.
    """
    _write_status_block(repo, content_commit)
    _write(repo, A_STATUS_FILE, '{"commit": "%s"}\n' % content_commit)
    return _commit(repo, "Record executed status (status-metadata commit)")


@contextlib.contextmanager
def _real_repo_state_against(repo: Path):
    """Run the REAL repo_state() against a synthetic repository.

    The scenarios must exercise the guard the repository actually ships, not a reimplementation
    of it - a rehearsal that re-derives the rule proves only that the rehearsal agrees with
    itself.
    """
    old_root, old_current = tsr.ROOT, tsr.CURRENT
    tsr.ROOT, tsr.CURRENT = repo, repo / CURRENT_RELPATH
    try:
        yield
    finally:
        tsr.ROOT, tsr.CURRENT = old_root, old_current


def _state_and_errors(repo: Path) -> tuple[str, list[str]]:
    """(repo_state verdict or 'STALE', topology_errors) for the synthetic repo's current HEAD."""
    with _real_repo_state_against(repo):
        try:
            state = repo_state()
        except (AssertionError, FileNotFoundError, subprocess.CalledProcessError):
            # No status block, an unresolvable revision, or a chain that does not bind: all are
            # "not a legal repository state", which is what the guard must reject.
            state = "STALE"
    rev = METADATA_COMMIT_REV.get(state)
    crev = CONTENT_COMMIT_REV.get(state)
    return state, topology_errors(
        state,
        None if rev is None else parent_count(rev, cwd=repo),
        None if crev is None else parent_count(crev, cwd=repo),
    )


def _build_defective_main(repo: Path) -> tuple[str, str, str]:
    """`main`'s REAL shape at 152574e - verified against the live repository, not assumed.

    origin/main's first-parent spine is a throwaway history (`a8c6fde` "first commit" ->
    `1c7cecc` "yessir"); ALL real work, including the certified pair `857cdc1cd`, arrived as the
    SECOND parent of three PR merge commits. That is why repo_state() is unbound there: the
    recorded commit is an ancestor of `main` but sits at no first-parent depth, so HEAD^ is
    another merge and HEAD^^ is the spine.

    An earlier draft of this scenario merged the CI branch directly onto the certified pair, which
    LEFT THE FIRST-PARENT CHAIN INTACT and bound as PRODUCING - it did not reproduce the defect at
    all. Returns (old_content, old_metadata, main_tip).
    """
    _init(repo)
    _write(repo, "README.md", "first commit\n")
    _commit(repo, "first commit")
    spine = git("rev-parse", "HEAD", cwd=repo)

    # the real work happens on a feature branch and lands as a certified pair
    git("checkout", "-q", "-b", "feature", cwd=repo)
    _write(repo, "src/base.py", "base\n")
    _commit(repo, "base")
    _write(repo, "src/unit_p3.py", "p3\n")
    old_content = _commit(repo, "P3 content")
    old_metadata = _finalize_like(repo, old_content)

    # the CI workflows arrive on their own branch, exactly as PR #1 did
    git("checkout", "-q", "-b", "ci", spine, cwd=repo)
    _write(repo, ".github/workflows/claude.yml", "name: claude\n")
    _write(repo, ".github/workflows/claude-code-review.yml", "name: review\n")
    _commit(repo, "CI workflows")

    # ...and the merge button merges each INTO main: first parent is main, second is the branch,
    # so the certified pair never joins main's first-parent chain
    git("checkout", "-q", "main", cwd=repo)
    git("merge", "-q", "--no-ff", "-m", "Merge pull request #1", "ci", cwd=repo)
    git("merge", "-q", "--no-ff", "-m", "Merge pull request #2", "feature", cwd=repo)
    return old_content, old_metadata, git("rev-parse", "HEAD", cwd=repo)


def _build_unit_pair(repo: Path, old_metadata: str) -> tuple[str, str]:
    """The CURRENT certified pair, built on the previous one and NOT contained in `main`.

    This is the live situation: the working branch is ahead of `main` by its own finalized pairs
    and behind it by the commits that reached `main` through the merge button.
    """
    git("checkout", "-q", "-B", "unit", old_metadata, cwd=repo)
    _write(repo, "src/unit_p4/a.py", "a\n")
    content = _commit(repo, "unit work (content commit)")
    return content, _finalize_like(repo, content)


def _build_the_real_shape(repo: Path) -> tuple[str, str, str]:
    """(unit_content, unit_pair_tip, main_tip) - the exact live divergence, hermetically."""
    _, old_metadata, main_tip = _build_defective_main(repo)
    unit_content, unit_metadata = _build_unit_pair(repo, old_metadata)
    return unit_content, unit_metadata, main_tip


def test_the_scenario_reproduces_the_historical_defect_before_it_repairs_it():
    """NEGATIVE CONTROL: the GitHub merge button, in the shape `main` is actually in."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "neyma"
        old_content, _, main_tip = _build_defective_main(repo)
        assert parent_count(main_tip, cwd=repo) == 2, "the scenario did not build a merge commit"
        assert parent_count(f"{main_tip}^", cwd=repo) == 2, (
            "main's first parent should itself be a PR merge, as it is at 152574e"
        )
        # the certified pair IS an ancestor - it is simply not on the first-parent chain
        subprocess.run(["git", "merge-base", "--is-ancestor", old_content, main_tip],
                       cwd=repo, check=True)
        git("checkout", "-q", "--detach", main_tip, cwd=repo)
        state, errs = _state_and_errors(repo)
        assert state == "STALE", (
            f"the historical defect must leave repo_state() unbound, got {state}"
        )
        assert errs, "the historical defect was accepted - the guard proves nothing"


def test_the_documented_rebase_and_collapse_state_is_illegal():
    """THE PROCEDURE DEFECT ITSELF, asserted so it cannot silently return.

    The superseded procedure said: rebase the unit onto `main`'s tip, collapse to ONE content
    commit, THEN finalize. With `main`'s tip a merge commit that intermediate state is the state
    finalize_status.py must run in - and it fails BOTH guards, so Step 4 was unreachable. This is
    the assertion the old rehearsal omitted: it built this exact state and never evaluated it.
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "neyma"
        _, pair_tip, main_tip = _build_the_real_shape(repo)
        base = git("merge-base", pair_tip, main_tip, cwd=repo)

        git("rebase", "-q", "--onto", main_tip, base, "unit", cwd=repo)
        git("reset", "-q", "--soft", main_tip, cwd=repo)
        _commit(repo, "unit: collapsed content commit")

        assert parent_count("HEAD^", cwd=repo) == 2, "HEAD^ should be the merge tip of the base"
        state, errs = _state_and_errors(repo)
        assert state == "STALE", (
            "the rebase-and-collapse state must be unbound - a rebase rewrites the recorded SHA"
        )
        assert errs, (
            "the rebase-and-collapse state was accepted; it is the state the finalizer would have "
            "had to run in, and it is illegal - this is the procedure defect"
        )


def _integrate(repo: Path, pair_tip: str, main_tip: str) -> tuple[str, str]:
    """THE CORRECTED PROCEDURE: merge `main`'s tip INTO the branch as ONE content commit.

    The merge's FIRST parent is the branch's metadata commit, so the first-parent chain still
    resolves to the certified pair and repo_state() keeps binding. Returns (content, metadata).
    """
    git("checkout", "-q", "-B", "unit", pair_tip, cwd=repo)
    git("merge", "-q", "--no-ff", "-m", "Integrate main (content commit)", main_tip, cwd=repo)
    content = git("rev-parse", "HEAD", cwd=repo)
    return content, _finalize_like(repo, content)


def test_the_corrected_procedure_is_legal_at_the_finalizer_time_state():
    """POSITIVE CONTROL + THE MISSING FINALIZER-TIME ASSERTION.

    This is the state finalize_status.py must run in. The old rehearsal never evaluated the
    predicate here; it hand-wrote a metadata commit and looked only at the resulting pair.
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "neyma"
        _, pair_tip, main_tip = _build_the_real_shape(repo)
        git("checkout", "-q", "-B", "unit", pair_tip, cwd=repo)
        git("merge", "-q", "--no-ff", "-m", "Integrate (content commit)", main_tip, cwd=repo)

        assert parent_count("HEAD", cwd=repo) == 2, "the content commit should be the merge"
        state, errs = _state_and_errors(repo)
        assert state == "PRODUCING", (
            f"the finalizer-time state must bind as PRODUCING, got {state} - a merge whose first "
            "parent is the metadata commit keeps the chain intact"
        )
        assert errs == [], (
            "the finalizer-time state is illegal - the procedure cannot be executed:\n  "
            + "\n  ".join(errs)
        )


def test_the_corrected_procedure_produces_a_legal_integrable_pair():
    """The whole procedure: integrate -> finalize -> fast-forward, asserting every claim it makes."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "neyma"
        _, pair_tip, main_tip = _build_the_real_shape(repo)
        content, metadata = _integrate(repo, pair_tip, main_tip)

        # -- the content commit carries BOTH the CI files and the unit's work
        tree = git("ls-tree", "-r", "--name-only", content, cwd=repo).split("\n")
        assert ".github/workflows/claude.yml" in tree, "the CI workflow files were dropped"
        assert ".github/workflows/claude-code-review.yml" in tree, "a CI workflow file was dropped"
        assert "src/unit_p4/a.py" in tree, "the unit's work was lost"
        assert "src/unit_p3.py" in tree, "previously certified content was lost"

        # -- at rest the chain binds and the metadata commit is not a merge
        state, errs = _state_and_errors(repo)
        assert state == "FINALIZED", f"the integrated pair must be FINALIZED, got {state}"
        assert errs == [], f"the integrated pair is illegal: {errs}"
        assert parent_count(metadata, cwd=repo) == 1, "the metadata commit must have one parent"

        # -- the metadata commit touches ONLY status files
        changed = [
            f for f in git("diff", "--name-only", content, metadata, cwd=repo).split("\n") if f
        ]
        stray = [f for f in changed if f not in STATUS_METADATA_FILES]
        assert changed and not stray, f"the metadata commit carried non-status files: {stray}"

        # -- shared history is not rewritten, and the base fast-forwards with NO new commit
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", main_tip, metadata], cwd=repo, check=True
        )
        git("checkout", "-q", "main", cwd=repo)
        git("merge", "-q", "--ff-only", "unit", cwd=repo)
        assert git("rev-parse", "HEAD", cwd=repo) == metadata, "the base did not fast-forward"
        assert git("rev-list", "--count", f"{main_tip}..HEAD", "--not", "unit", cwd=repo) == "0", (
            "integration introduced a commit the branch did not already contain"
        )
        assert git("rev-list", "--count", f"HEAD..{main_tip}", cwd=repo) == "0", (
            "integration lost a commit that was on the base"
        )

        # -- and the live predicate now accepts the integrated base
        state, errs = _state_and_errors(repo)
        assert state == "FINALIZED" and errs == [], "the integrated base is still illegal"


def test_the_predicate_and_the_real_guards_reject_a_merge_used_as_the_metadata_commit():
    """NEGATIVE CONTROL proving the metadata-parent rule is NOT redundant with repo_state().

    A merge whose FIRST parent is the recorded content commit and whose second parent touches only
    status-metadata files passes repo_state() cleanly: the chain binds and the first-parent diff is
    pure. Nothing except this rule rejects it. If topology_errors ever stops reading the metadata
    commit's parent count, this is the defect that walks in.
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "neyma"
        content, pair_tip, _ = _build_the_real_shape(repo)

        # a side branch off the recorded content commit, touching ONLY a status-metadata file
        git("checkout", "-q", "-b", "side", content, cwd=repo)
        _write(repo, A_STATUS_FILE, '{"commit": "side"}\n')
        side = _commit(repo, "side (status file only)")

        # forge a MERGE that occupies the metadata position: tree = the real metadata commit's
        # tree (so the recorded value still names `content`), first parent = content, second = side
        tree = git("rev-parse", f"{pair_tip}^{{tree}}", cwd=repo)
        forged = git("commit-tree", tree, "-p", content, "-p", side,
                     "-m", "Status metadata (FORGED AS A MERGE)", cwd=repo)
        git("checkout", "-q", "--detach", forged, cwd=repo)

        assert parent_count("HEAD", cwd=repo) == 2, "the forgery is not a merge"
        with _real_repo_state_against(repo):
            assert repo_state() == "FINALIZED", (
                "this scenario is only meaningful if repo_state() ACCEPTS the forgery - if it "
                "rejects it, the mutation is not exercising the metadata-parent rule"
            )
        state, errs = _state_and_errors(repo)
        assert errs, "a merge used as the status-metadata commit was accepted"
        assert any("merge" in e for e in errs), f"rejected for the wrong reason: {errs}"


def test_the_real_guards_reject_an_octopus_content_commit_carrying_a_third_lineage():
    """NEGATIVE CONTROL for the gap R-21b's relaxation would otherwise have opened.

    Dropping the content commit's parent count entirely admitted an OCTOPUS content commit whose
    parents are (metadata, origin/main, anything): the first-parent chain still binds, repo_state()
    still returns PRODUCING, and `git show` on it renders an EMPTY combined patch - so the third
    lineage rides in unreviewed while every mechanical precondition in the procedure passes. The
    two-parent bound is what rejects it, and nothing else here does: this test asserts repo_state()
    ACCEPTS the shape first, so it cannot pass for the wrong reason.
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "neyma"
        _, pair_tip, main_tip = _build_the_real_shape(repo)

        # a third lineage, off the certified pair, carrying content nobody reviewed
        git("checkout", "-q", "-b", "third", pair_tip, cwd=repo)
        _write(repo, "src/smuggled.py", "smuggled\n")
        third = _commit(repo, "a third lineage")

        # the octopus: first parent is the metadata commit, so the chain still binds
        git("checkout", "-q", "-B", "unit", pair_tip, cwd=repo)
        git("merge", "-q", "--no-ff", "-m", "Integrate (octopus content commit)",
            main_tip, third, cwd=repo)

        assert parent_count("HEAD", cwd=repo) == 3, "the scenario did not build an octopus"
        with _real_repo_state_against(repo):
            assert repo_state() == "PRODUCING", (
                "this scenario is only meaningful if repo_state() ACCEPTS the octopus - if it "
                "rejects it, the mutation is not exercising the content-parent bound"
            )
        # and the reviewer's default command really is blind on this shape
        assert "smuggled" not in git("show", "HEAD", cwd=repo), (
            "git show displayed the smuggled lineage - the premise of the bound is wrong"
        )

        state, errs = _state_and_errors(repo)
        assert state == "PRODUCING", f"expected PRODUCING, got {state}"
        assert errs, "an octopus content commit carrying a third lineage was accepted"
        assert any("content commit" in e for e in errs), f"rejected for the wrong reason: {errs}"


def test_a_finalizer_position_exists_above_a_merge_on_the_first_parent_chain():
    """THE ANCHOR-REACHABILITY REGRESSION.

    Under the superseded predicate the recorded anchor was TRAPPED BELOW any merge on the
    first-parent chain: every position where repo_state() bound was rejected on parent count, and
    every position accepted on parent count was stale. Since integration necessarily introduces
    such a merge, no finalizer position existed above it and integration was unreachable.

    This asserts the property that was missing - walking the first-parent chain and requiring that
    a position AT OR ABOVE the integrating merge satisfies BOTH guards, which is what makes
    finalize_status.py runnable there. It also requires the anchor to stay disciplined: stacking
    unfinalized content commits must still go stale.
    """
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "neyma"
        _, pair_tip, main_tip = _build_the_real_shape(repo)
        merge_pos, metadata = _integrate(repo, pair_tip, main_tip)
        assert parent_count(merge_pos, cwd=repo) == 2, "the integrating commit is not a merge"

        reachable = []
        for rev in git("rev-list", "--first-parent", metadata, cwd=repo).split("\n"):
            git("checkout", "-q", "--detach", rev, cwd=repo)
            state, errs = _state_and_errors(repo)
            if state in METADATA_COMMIT_REV and not errs:
                reachable.append(rev)

        assert reachable, "no finalizer position exists anywhere - the anchor is trapped"
        above = [
            r for r in reachable
            if subprocess.run(["git", "merge-base", "--is-ancestor", merge_pos, r],
                              cwd=repo).returncode == 0
        ]
        assert above, (
            "no finalizer position exists AT OR ABOVE the integrating merge - the recorded anchor "
            "is trapped below it and integration is unreachable (this is the procedure defect)"
        )
        assert merge_pos in above, "the integrating merge itself must be a finalizer position"

        # the anchor stays disciplined: a SECOND unfinalized content commit is still illegal
        git("checkout", "-q", "-B", "stacked", metadata, cwd=repo)
        _write(repo, "src/extra.py", "extra\n")
        _commit(repo, "a second unfinalized content commit")
        _write(repo, "src/extra2.py", "extra2\n")
        _commit(repo, "a third unfinalized content commit")
        state, errs = _state_and_errors(repo)
        assert state == "STALE" and errs, (
            "stacking unfinalized content commits must still be rejected"
        )


# --------------------------------------------------------------- 4. the obligation stays recorded

def test_the_integration_procedure_is_recorded():
    assert PROCEDURE.exists(), "the integration procedure document is missing"
    text = PROCEDURE.read_text(encoding="utf-8")
    for required in ("fast-forward", "R-21", "STATUS_METADATA_FILES", "test_status_reality"):
        assert required in text, f"the procedure no longer records: {required}"
    assert re.search(r"FAST[- ]FORWARD ONLY|fast-forward only", text, re.I), (
        "the procedure no longer states the fast-forward-only invariant"
    )


def test_the_procedure_records_the_executable_invariant():
    """The document must describe the rule the guard actually enforces, not a stricter one.

    The procedure defect was precisely a document that prescribed an unexecutable sequence. If the
    prose drifts back to "the content commit may not be a merge", or stops naming the metadata
    commit's one-parent rule, this fails.
    """
    text = PROCEDURE.read_text(encoding="utf-8")
    assert re.search(r"metadata commit[^.]*exactly one parent", text, re.I), (
        "the procedure no longer states that the METADATA commit has exactly one parent"
    )
    assert re.search(r"content commit MAY be a merge|content commit may itself be a merge", text, re.I), (
        "the procedure no longer records that the CONTENT commit may be a merge - the rule that "
        "makes integration reachable"
    )
    assert "R-21b" in text, "the procedure no longer records the procedure-repair correction"
    # A positive assertion, not an absence check: deleting the paragraph must not satisfy this.
    # GitHub's "Require linear history" would reject the integrating merge the corrected invariant
    # depends on, and `main` cannot satisfy it anyway - it already carries three merge commits.
    assert re.search(r"do NOT enable[^.]*Require linear history", text, re.I), (
        "the procedure no longer forbids GitHub's 'Require linear history', which would reject the "
        "integrating merge the corrected invariant depends on"
    )
    # The relaxation leans on independent review as the control for the class the guard cannot
    # detect - and `git show` on a merge prints an EMPTY combined diff. If the procedure stops
    # naming the first-parent diff, that control is silently removed.
    # F-2: the procedure must not restore the overstatement the register already forbids. Paired
    # with a POSITIVE assertion so deleting the scoping cannot satisfy the absence check vacuously.
    assert re.search(r"at\s+most\s+\**TWO\**\s+parents|at\s+most\s+two\s+parents", text, re.I), (
        "the procedure no longer states the bound on the content commit's parent count - without "
        "it an octopus content commit reads as permitted"
    )
    assert not re.search(r"without\W{0,4}relaxing anything", text, re.I), (
        "the procedure has restored the overstatement that the rule was corrected 'without "
        "relaxing anything it protects' - the content commit's one-parent requirement WAS "
        "dropped, and the document must scope that the way section 5 does"
    )
    assert re.search(r"git diff HEAD\^ HEAD", text), (
        "the procedure no longer tells a reviewer to read a merge content commit by its "
        "FIRST-PARENT diff - `git show` renders a merge as an empty patch, so the independent "
        "review the relaxation depends on would see nothing"
    )


def _register_row(register: str, rid: str) -> list[str]:
    row = next(
        (l for l in register.split("\n")
         if re.match(r"^\|\s*(###\s*)?\*\*" + re.escape(rid) + r"\*\*", l)), None
    )
    assert row, f"{rid} is no longer recorded in the risk register"
    return row.split("|")


def test_r21_is_recorded_with_a_mechanism_and_an_owner():
    """A mitigation that reads 'remember to use the right merge button' is not a mitigation.

    Extended for R-21b so that neither of the two claims the independent review corrected can be
    silently restored by a later edit:

      - R-21 may not present the topology guard as a COMPLETE control for the merge button. After
        R-21b a button-created merge that preserves first-parentage is topologically
        indistinguishable from a legitimate integrating merge, so the control for that class is
        the allow-only-rebase-merging repository configuration.
      - R-21b may not claim that "nothing was relaxed". Something was: the content commit is no
        longer required to have exactly ONE parent. The row must scope that precisely, name what
        is retained, and record that the count is still BOUNDED - at two - so an octopus content
        commit carrying an unreviewed third lineage is still rejected.
    """
    register = REGISTER.read_text(encoding="utf-8")

    cells = _register_row(register, "R-21")
    mitigation = cells[5]
    assert "fast-forward" in mitigation.lower(), "R-21's mitigation no longer names the mechanism"
    assert "integration-topology-procedure" in mitigation, "R-21 no longer points at the procedure"
    assert cells[7].strip(), "R-21 has no owner"
    # the guard is not a complete control for this class, and the row must say so
    assert "indistinguishable" in mitigation.lower(), (
        "R-21 no longer records that a first-parent-preserving merge-button commit is "
        "topologically indistinguishable from a legitimate integrating merge"
    )
    assert "rebase merging" in mitigation.lower(), (
        "R-21 no longer names the allow-only-rebase-merging repository configuration as the "
        "control for the class the topology guard cannot detect"
    )

    b = _register_row(register, "R-21b")
    bm = b[5]
    assert b[7].strip(), "R-21b has no owner"
    assert "nothing was relaxed" not in bm.lower(), (
        "R-21b has reverted to the overstated claim that nothing was relaxed - the content "
        "commit's one-parent requirement WAS dropped, and the row must say which relaxation "
        "was made"
    )
    assert "octopus content commit" in bm.lower(), (
        "R-21b no longer records that the content commit's parent count is BOUNDED at two - "
        "without that bound an octopus content commit smuggles an unreviewed third lineage past "
        "both `git show` and the chain-binding check"
    )
    for needle, why in (
        ("content commit", "what the relaxation applies to"),
        ("parent count", "the relaxation itself"),
        ("metadata", "that a merge used as the metadata commit is still rejected"),
        ("rejected", "the retained rejections"),
        ("producing", "the state an accepted content-commit merge must be in"),
        ("finalizer", "that a finalizer must be owed on it"),
    ):
        assert needle in bm.lower(), f"R-21b's mitigation no longer records {why}"


def test_the_progress_protocol_states_the_invariant():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "Integration topology" in text, "PROGRESS-PROTOCOL.md no longer covers integration topology"
    assert "integration-topology-procedure.md" in text, (
        "PROGRESS-PROTOCOL.md no longer points at the procedure"
    )
    assert re.search(r"fast[- ]forward only", text, re.I), (
        "PROGRESS-PROTOCOL.md no longer states the fast-forward-only invariant"
    )
