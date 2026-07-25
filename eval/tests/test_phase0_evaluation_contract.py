"""U0.5 - the anti-false-green contract, and the regression test for the defect that motivated it.

During implementation planning a contradiction checker reported "0 contradictions" while parsing
**0 rows**: a wrong column index meant it examined nothing and pronounced the artifact clean
(planning review, finding M-9). These tests prove that the same defect now fails loudly.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0.evaluation import EmptyPopulationError, Evaluation, MalformedRecordError


def test_a_probe_that_evaluated_nothing_fails():
    ev = Evaluation(name="probe", sources_inspected=["a.md"])
    with pytest.raises(EmptyPopulationError, match="evaluated 0 records"):
        ev.require_population()


def test_a_probe_that_inspected_no_sources_fails_even_if_it_claims_rows():
    """A wrong path is the other way to examine nothing."""
    ev = Evaluation(name="probe", accepted=["x"])
    with pytest.raises(EmptyPopulationError, match="inspected NO source files"):
        ev.require_population()


def test_the_M9_defect_reproduced_then_caught():
    """THE regression: a wrong column index yields zero rows; the checker must NOT report clean.

    This mirrors M-9 exactly. A table is parsed with an out-of-range column, so every row is skipped
    and the contradiction count is legitimately zero. Under the old style that read as "no
    contradictions found". Under the contract it raises.
    """
    rows = [["G4", "P2"], ["G4", "P8"], ["G1", "P6"]]
    WRONG_COLUMN = 9

    ev = Evaluation(name="gate.contradictions", sources_inspected=["gap-matrix.md"])
    contradictions = []
    for r in rows:
        ev.candidates.append(r)
        if WRONG_COLUMN >= len(r):
            continue          # the M-9 bug: silently skip what you cannot address
        ev.accepted.append(r)
        if r[0] != r[WRONG_COLUMN]:
            contradictions.append(r)

    assert contradictions == []          # "0 contradictions" - and it means nothing
    with pytest.raises(EmptyPopulationError, match="planning review M-9"):
        ev.require_population()


def test_the_same_probe_with_the_right_column_evaluates_the_real_population():
    """The control: with the correct index the population is real and the verdict is evidence."""
    rows = [["G4", "P2"], ["G4", "P8"], ["G1", "P6"]]
    RIGHT_COLUMN = 1
    ev = Evaluation(name="gate.contradictions", sources_inspected=["gap-matrix.md"])
    for r in rows:
        ev.candidates.append(r)
        ev.accepted.append(r)
    ev.require_population()
    assert ev.evaluated == 3
    assert len(rows[0]) > RIGHT_COLUMN


def test_unmatched_rows_are_a_hard_failure_not_a_silent_skip():
    ev = Evaluation(name="probe", sources_inspected=["a.md"], accepted=["ok"],
                    unmatched=["row 12: could not parse"])
    with pytest.raises(MalformedRecordError, match="silently ignored"):
        ev.require_population()


def test_an_empty_population_passes_only_when_explicitly_declared():
    ev = Evaluation(name="probe", sources_inspected=["a.md"])
    ev.declare_empty_is_legitimate("this repository has no X by contract")
    ev.require_population()
    assert ev.evaluated == 0


def test_declaring_an_empty_set_legitimate_requires_a_reason():
    ev = Evaluation(name="probe", sources_inspected=["a.md"])
    with pytest.raises(ValueError):
        ev.declare_empty_is_legitimate("   ")


def test_every_report_states_its_evaluated_count():
    ev = Evaluation(name="probe", sources_inspected=["a.md"], accepted=[1, 2])
    report = ev.report()
    for field in ("source files inspected", "candidate rows found", "rows parsed", "rows accepted",
                  "rows rejected", "unmatched rows", "duplicates", "FINAL EVALUATED COUNT"):
        assert field in report
