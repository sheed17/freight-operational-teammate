"""The evaluation contract: a checker that evaluated nothing may never report green.

This exists because of a real defect. During implementation planning, a contradiction checker
reported "0 contradictions" while parsing **0 rows** — a wrong column index meant it examined
nothing and pronounced the artifact clean (planning review, finding M-9). A green result from an
empty population is worse than no check at all: it is a false negative wearing a passing badge.

So every Phase-0 probe returns an ``Evaluation`` and must call ``require_population()``. A probe
whose population is empty FAILS unless its contract explicitly declares an empty set legitimate,
and that declaration must be made at the call site where a reviewer can see it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class EmptyPopulationError(AssertionError):
    """A checker evaluated zero records without declaring that an empty set is its contract."""


class MalformedRecordError(AssertionError):
    """A parser met a record it could not parse. Silently skipping it is forbidden."""


@dataclass
class Evaluation:
    """What a probe looked at, and what it made of it. Every field is reportable."""

    name: str
    sources_inspected: list[Path] = field(default_factory=list)
    candidates: list = field(default_factory=list)
    parsed: list = field(default_factory=list)
    accepted: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    unmatched: list = field(default_factory=list)
    duplicates: list = field(default_factory=list)
    allow_empty: bool = False
    empty_contract_reason: str = ""

    @property
    def evaluated(self) -> int:
        return len(self.accepted)

    def declare_empty_is_legitimate(self, reason: str) -> None:
        """The ONLY way a zero-row result may pass. The reason is required and is reported."""
        if not reason.strip():
            raise ValueError("declaring an empty population legitimate requires a stated reason")
        self.allow_empty = True
        self.empty_contract_reason = reason

    def require_population(self, minimum: int = 1) -> None:
        """Hard-fail when nothing was evaluated. This is the anti-false-green rule."""
        if not self.sources_inspected:
            raise EmptyPopulationError(
                f"{self.name}: inspected NO source files. The probe cannot have found anything.\n"
                f"{self.report()}"
            )
        if self.evaluated == 0 and not self.allow_empty:
            raise EmptyPopulationError(
                f"{self.name}: evaluated 0 records and did not declare an empty set legitimate.\n"
                f"A checker that parsed nothing has proven nothing (planning review M-9).\n"
                f"{self.report()}"
            )
        if self.evaluated < minimum and not self.allow_empty:
            raise EmptyPopulationError(
                f"{self.name}: evaluated {self.evaluated} records, expected at least {minimum}.\n"
                f"{self.report()}"
            )
        if self.unmatched:
            raise MalformedRecordError(
                f"{self.name}: {len(self.unmatched)} record(s) were not matched by the parser and "
                f"would have been silently ignored:\n  "
                + "\n  ".join(str(u) for u in self.unmatched[:10])
                + f"\n{self.report()}"
            )

    def report(self) -> str:
        """The receipt. A probe's verdict is not evidence without it."""
        lines = [
            f"--- evaluation: {self.name} ---",
            f"  source files inspected : {len(self.sources_inspected)}",
        ]
        lines += [f"      {p}" for p in self.sources_inspected[:20]]
        lines += [
            f"  candidate rows found   : {len(self.candidates)}",
            f"  rows parsed            : {len(self.parsed)}",
            f"  rows accepted          : {len(self.accepted)}",
            f"  rows rejected          : {len(self.rejected)}",
            f"  unmatched rows         : {len(self.unmatched)}",
            f"  duplicates             : {len(self.duplicates)}",
            f"  FINAL EVALUATED COUNT  : {self.evaluated}",
        ]
        if self.allow_empty:
            lines.append(f"  empty-set contract     : {self.empty_contract_reason}")
        return "\n".join(lines)
