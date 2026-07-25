"""The deprecated-semantics inventory.

Phase 0 RECORDS these and prevents NEW ones. It renames nothing: names follow behavior, and each
rename is the last commit of the phase that made the name true (migration plan, Part 5). Renaming
`lane` across 310 sites into concepts that do not exist yet would be one guess made 310 times.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .evaluation import Evaluation
from .sources import SCRIPTS, SRC, TESTS, python_files, rel

# term -> (canonical replacement, phase that removes it, the unit that owns the rename)
DEPRECATED_TERMS = {
    "CommandIntent":      ("Proposal / Effect Request", "P8", "U8.6"),
    "MockTmsWriteLedger": ("spec-derived contract simulator", "P3", "U3.5"),
    "workflow_runs":      ("Work Item + Pipeline Instance (SPLIT)", "P6", "U6.4"),
    "commit_identity":    ("Commit Key", "P1", "U1.6"),
    "operation_action_claims": ("approval consumption", "P3", "U3.2"),
    "lane":               ("action_class | workflow_id | policy scope", "P8", "U8.5"),
}


@dataclass(frozen=True)
class Occurrence:
    term: str
    file: str
    lineno: int


def _word(term: str) -> re.Pattern:
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])")


def _is_phase0_meta(path) -> bool:
    """The Phase-0 guards NAME the terms they guard. That is metadata, not usage.

    Excluding them is stated in the counting rule rather than left implicit, because an unstated
    exclusion is how a count stops meaning what its label says.
    """
    parts = path.parts
    return "phase0" in parts or path.name.startswith("test_phase0_")


def occurrences(*, include_tests: bool = False) -> tuple[dict[str, list[Occurrence]], Evaluation]:
    ev = Evaluation(name="deprecated.occurrences")
    roots = [SRC, SCRIPTS] + ([TESTS] if include_tests else [])
    found: dict[str, list[Occurrence]] = {t: [] for t in DEPRECATED_TERMS}
    patterns = {t: _word(t) for t in DEPRECATED_TERMS}
    for path in python_files(*roots):
        if _is_phase0_meta(path):
            ev.rejected.append(rel(path))
            continue
        ev.sources_inspected.append(rel(path))
        for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
            for term, pat in patterns.items():
                if pat.search(line):
                    occ = Occurrence(term, rel(path), i)
                    found[term].append(occ)
                    ev.candidates.append(occ)
                    ev.parsed.append(occ)
                    ev.accepted.append(occ)
    return found, ev


def counts(*, include_tests: bool = False) -> dict[str, int]:
    found, _ = occurrences(include_tests=include_tests)
    return {t: len(v) for t, v in found.items()}


def production_counts() -> dict[str, int]:
    """Occurrences in PRODUCTION only (src/ + scripts/) - the surface the ratchet is actually about.

    Phase 1 exposed that a combined src+tests count measures the wrong thing. `commit_identity` fell
    to ZERO in production (U1.6 complete), yet the total read 2 - both inside a guard whose whole job
    is to assert `"def _commit_identity(" not in source`. Naming a deleted symbol in order to forbid
    it is the opposite of a regression, and a rule that scores it as one teaches people to silence
    the rule.

    Tests are counted separately and tracked, not ratcheted: a test's vocabulary is derivative of the
    API it exercises, it entrenches nothing, and P8's rename sweeps it along with the code. What must
    never grow is the PRODUCTION surface that P8 has to migrate.
    """
    found, _ = occurrences(include_tests=False)
    return {t: len(v) for t, v in found.items()}


def test_counts() -> dict[str, int]:
    """Informational: occurrences in eval/tests only (excluding the phase guards themselves)."""
    all_found, _ = occurrences(include_tests=True)
    prod, _ = occurrences(include_tests=False)
    return {t: len(all_found[t]) - len(prod[t]) for t in all_found}


def files_touching(term: str, *, include_tests: bool = False) -> set[str]:
    found, _ = occurrences(include_tests=include_tests)
    return {o.file for o in found.get(term, [])}
