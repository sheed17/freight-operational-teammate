"""P8 / U8.6 — make the proposal PROBE operable by the repository's own pytest runner.

`scripts/probe_phase8_proposal.py` is the deterministic behaviour probe for the inert Proposal
boundary. It is wired into CI (the blocking `proposal` job), but a script is not collected by pytest,
so an evaluator that operates only pytest-collected tests never sees it run. This thin wrapper
subprocess-invokes the probe with the SAME interpreter and asserts its stable success line, so the
probe's "0 wrong" becomes an executed, observed check under the source-of-truth runner — additive
test coverage, not a committed receipt (CLAUDE.md §0).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_PROBE = ROOT / "scripts" / "probe_phase8_proposal.py"


def test_the_proposal_probe_reports_zero_wrong():
    result = subprocess.run(
        [sys.executable, str(_PROBE)], cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, (
        f"the proposal probe exited {result.returncode}\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}")
    assert "behaviours as specified, 0 wrong" in result.stdout, (
        f"the proposal probe did not report '0 wrong':\n{result.stdout}")
