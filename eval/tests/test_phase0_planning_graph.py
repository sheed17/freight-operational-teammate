"""U0.7 - planning-graph consistency.

The load-bearing case here is G4. The frozen gate requires AC-SAFE-001..028 in full, and those reach
past the checkpoint into P5 (outbox), P6 (ownership), P7 (provenance) and P8 (Exception,
Compensation). An earlier draft scoped G4 to "P2+P3+P4" (planning review M-3).

That is not a documentation error. P12 - the first live external write - is gated on G4. An engineer
could have qualified "G4" at P4, honestly believed the wall was cleared, and shipped a live money
write with no provenance rules, no accountable owner and no compensation semantics, while following
the plan exactly. These tests make that specific regression impossible.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import markdown, planning_corpus
from phase0.evaluation import Evaluation
from phase0.sources import ACCEPTANCE, IMPLEMENTATION

GATE_PLAN = IMPLEMENTATION / "release-gate-plan.md"
GAP_MATRIX = IMPLEMENTATION / "current-to-target-gap-matrix.md"


def test_the_probes_evaluate_real_populations():
    planning_corpus.ids_of("phase").require_population(minimum=10)
    planning_corpus.ids_of("gate").require_population(minimum=10)
    planning_corpus.ids_of("risk").require_population(minimum=15)


def test_g4_resolves_through_phase_8():
    """REG-6 / INV-P0-5. G4 may never be reduced to P2-P4 again."""
    text = planning_corpus.gate_plan_text()
    row = next((l for l in text.split("\n") if re.match(r"^\|\s*#*\s*\*\*G4\*\*", l)), None)
    assert row, "no G4 row in release-gate-plan.md"
    assert "P8" in row, f"G4 must resolve through Phase 8. Row: {row}"
    assert not re.search(r"P2\s*\+\s*P3\s*\+\s*P4", row), (
        "G4 has been reduced to P2+P3+P4 - the M-3 regression. The frozen gate requires "
        "AC-SAFE-001..028, which reach to P5, P6, P7 and P8."
    )


def test_the_g4_correction_is_recorded_with_its_reasoning():
    """The correction must survive as an explanation, not be quietly reworded away."""
    text = planning_corpus.gate_plan_text()
    assert "CORRECTION" in text
    assert "M-3" in text
    assert "ungated live write" in text


def test_g4_scope_covers_every_dependency_the_frozen_gate_demands():
    """Derive G4's real span from the FROZEN gate row, not from the plan's own summary."""
    gates = markdown.find_table(ACCEPTANCE / "release-gates.md", "Gate", "Required cases")
    g4 = next(r for r in gates["rows"] if "G4" in markdown.clean(r[0]))
    required = markdown.clean(g4[2])
    for token in ("AC-SAFE-001..028", "AC-CKPT", "AC-RACE", "AC-REC", "AC-SEC"):
        assert token in required, f"the frozen G4 row no longer requires {token}: {required!r}"

    plan = planning_corpus.gate_plan_text()
    # AC-SAFE-028 needs Work Item ownership (P6); AC-SAFE-015/016 need provenance (P7);
    # AC-REC-001 needs Compensation (P8). The plan must name those phases in the correction.
    for phase in ("P5", "P6", "P7", "P8"):
        assert phase in plan, f"the G4 correction does not account for {phase}"


def test_every_gap_matrix_row_has_a_defined_gate_value():
    """M-4: the Gate column once had NO defined meaning; 14 of 34 rows were unadjudicable.

    The column is now defined as 'the earliest gate that cannot pass without this component' and is
    computed from the row's cited cases. This test asserts the definition is present and every row
    carries a resolvable value.
    """
    text = GAP_MATRIX.read_text(encoding="utf-8")
    assert "DEFINITION OF THE GATE COLUMN" in text, "the Gate column's meaning is undefined again"
    assert "gate that cannot pass without this component" in text.lower()

    ev = Evaluation(name="planning.gap_matrix_gate_column", sources_inspected=[str(GAP_MATRIX)])
    for line in text.split("\n"):
        cells = line.split("|")
        if len(cells) < 10 or not cells[1].strip().isdigit():
            continue
        ev.candidates.append(cells[1].strip())
        gate_cell = cells[9]
        ev.parsed.append(gate_cell)
        if re.search(r"G\d+", gate_cell) or "n/a" in gate_cell.lower():
            ev.accepted.append(cells[1].strip())
        else:
            ev.unmatched.append(f"row {cells[1].strip()}: unresolvable Gate value {gate_cell!r}")
    ev.require_population(minimum=30)


def test_the_gate_column_matches_the_strictest_cited_case():
    """The definition is only worth having if it is mechanically enforced."""
    frozen_gate = {
        "AC-SAFE": "G4", "AC-CKPT": "G4", "AC-RACE": "G4", "AC-REC": "G4", "AC-SEC": "G4",
        "AC-MACH": "G1", "AC-DOM": "G1", "AC-EVT": "G2", "AC-ADPT": "G3",
        "AC-WF": "G5", "AC-FC": "G5", "AC-DEG": "G7", "AC-AUD": "G9", "AC-TRACE": "G0",
    }
    order = {f"G{i}": i for i in range(11)}
    ev = Evaluation(name="planning.gate_column_correctness", sources_inspected=[str(GAP_MATRIX)])
    contradictions = []
    for line in GAP_MATRIX.read_text(encoding="utf-8").split("\n"):
        c = line.split("|")
        if len(c) < 10 or not c[1].strip().isdigit():
            continue
        ev.candidates.append(c[1].strip())
        cases = re.findall(r"AC-[A-Z]+", c[6])
        stated = re.findall(r"G\d+", c[9])
        req = [frozen_gate[x] for x in cases if x in frozen_gate]
        if not req or not stated:
            continue
        ev.accepted.append(c[1].strip())
        earliest_required = min(req, key=lambda g: order[g])
        earliest_stated = min(stated, key=lambda g: order[g])
        if earliest_stated != earliest_required:
            contradictions.append(
                f"row {c[1].strip()}: cites a {earliest_required} case but states {earliest_stated}"
            )
    ev.require_population(minimum=25)   # <- the M-9 guard: this check MUST see the real population
    assert not contradictions, "Gate column contradictions:\n  " + "\n  ".join(contradictions)


def test_the_dependency_spine_is_intact_and_ordered():
    """U0.2 -> U1.2/U1.3 -> U2.1 -> U2.3 -> U3.1 -> U3.2 -> U3.3 -> U4.9 -> U4.6 -> P12."""
    text = (IMPLEMENTATION / "pr-sequence.md").read_text(encoding="utf-8")
    spine = next(l for l in text.split("\n") if "U0.2" in l and "P12" in l)
    order = ["U0.2", "U1.2", "U2.1", "U2.3", "U3.1", "U3.2", "U3.3", "U4.9", "U4.6", "P12"]
    positions = [spine.index(u) for u in order]
    assert positions == sorted(positions), f"the dependency spine is out of order: {spine}"


def test_every_phase_zero_unit_is_declared():
    units = set(planning_corpus.declared_units().accepted)
    for u in ("U0.1", "U0.2", "U0.3", "U0.4"):
        assert u in units, f"{u} is not declared in pr-sequence.md"


def test_every_risk_has_an_owner_and_a_mitigation():
    register = IMPLEMENTATION / "implementation-risk-register.md"
    ev = Evaluation(name="planning.risks", sources_inspected=[str(register)])
    for line in register.read_text(encoding="utf-8").split("\n"):
        if not re.match(r"^\|\s*(###\s*)?\*\*R-\d\d\*\*", line):
            continue
        c = line.split("|")
        rid = re.search(r"R-\d\d", c[1]).group()
        ev.candidates.append(rid)
        ev.parsed.append(rid)
        assert c[5].strip(), f"{rid}: no mitigation"
        assert c[7].strip(), f"{rid}: no owner"
        ev.accepted.append(rid)
    ev.require_population(minimum=20)


def test_r07_is_recorded_as_open_and_not_structurally_mitigated():
    """PL-18 may not be falsely closed by a document."""
    register = (IMPLEMENTATION / "implementation-risk-register.md").read_text(encoding="utf-8")
    r07 = next(l for l in register.split("\n") if re.match(r"^\|\s*(###\s*)?\*\*R-07\*\*", l))
    assert "NONE that is structural" in r07 or "NOT A MECHANISM" in r07.upper()
    review = (IMPLEMENTATION / "implementation-planning-review.md").read_text(encoding="utf-8")
    assert "PL-18" in review
    assert "NO — AND IT CANNOT BE" in review
