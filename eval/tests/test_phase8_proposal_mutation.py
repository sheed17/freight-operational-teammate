"""P8 / U8.6 — make the proposal MUTATION BATTERY operable by the repository's own pytest runner.

`scripts/mutate_phase8_proposal.py` reintroduces each genuinely new load-bearing seam's defect
(unregistered/missing action_class accepted, MODEL_INFERRED promoted, forged token as approval,
PROPOSED auto-advanced, reservation/owner/tamper) and proves each guard goes RED, then restores every
file from memory. It is wired into CI (the blocking `proposal` job), but a script is not collected by
pytest. This thin wrapper subprocess-invokes the battery with the SAME interpreter and asserts its
stable success line and a clean tree afterwards, so "every mutant caught, 0 escaped" becomes an
executed, observed check under the source-of-truth runner — additive coverage, not a committed
receipt (CLAUDE.md §0).

The battery restores every mutation from an in-memory copy before it exits (never via git), so it
must leave the tree byte-identical; this wrapper asserts that too, mirroring the CI job.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_BATTERY = ROOT / "scripts" / "mutate_phase8_proposal.py"
_SCOPE = ["src", "eval", "scripts"]


def _porcelain() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--", *_SCOPE],
        cwd=str(ROOT), capture_output=True, text=True).stdout


def test_the_proposal_mutation_battery_catches_every_mutant():
    before = _porcelain()
    result = subprocess.run(
        [sys.executable, str(_BATTERY)], cwd=str(ROOT), capture_output=True, text=True)
    after = _porcelain()

    assert result.returncode == 0, (
        f"the mutation battery exited {result.returncode}\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}")
    assert re.search(r"^\d+ mutants caught, 0 escaped$", result.stdout, re.MULTILINE), (
        f"a proposal mutant escaped (or the stable summary line is missing):\n{result.stdout}")
    # The battery restores from an in-memory copy, not git; a dirty delta here means a mutation was
    # NOT restored and the tree is now running mutated source.
    assert before == after, (
        f"the mutation battery left the tree dirty:\n--- before ---\n{before}\n--- after ---\n{after}")
