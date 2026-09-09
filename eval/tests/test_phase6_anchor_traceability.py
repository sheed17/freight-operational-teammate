"""`P6-AC-5` — ### EVERY REQUIRED ANCHOR IS NAMED, MAPPED, AND ACTUALLY RUNS.

The criterion's authority is `foundational-machine-acceptance.md`'s *"Per-machine mandatory assertions
(every machine, every case)"* and its *"named anchors (merge-gating)"* line. The adjudication that
failed `P6-AC-5` did not find the behaviour missing — it found the IDS untraceable: `AC-MACH-208`,
`AC-MACH-605x` and `AC-MACH-1305` appeared nowhere under `eval/` or `scripts/`, and `AC-MACH-903`
only inside a probe's prose.

### THE REQUIRED SET IS PARSED OUT OF THE AUTHORITY, NOT RETYPED HERE. The seven anchor ids and the
ten numbered assertions are read from the acceptance file itself, so an eighth anchor added tomorrow
fails this file until it is registered — which is the only version of this guard that stays true.

### AND "MAPPED" MEANS FOUR THINGS, EACH CHECKED SEPARATELY.
  1. the id the authority requires is in the register;
  2. the id is DERIVABLE from the canonical transition it names (`AC-MACH-<machine><row suffix>`), so
     it cannot be a plausible-looking string;
  3. the evidence node EXISTS in the file the register names; and
  4. pytest COLLECTS it — existence in a file pytest never runs is not verification, so the guard
     asks pytest for its own collected node ids rather than trusting the source.
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from phase6_anchor_manifest import (  # noqa: E402
    ANCHORS,
    ASSERTIONS,
    EVIDENCE,
    MACHINE_FILES,
    MUTATION_PROBES,
    UNEVIDENCED,
)
from phase6_machine_population_kit import ACCEPTANCE, ROOT, join  # noqa: E402

TESTS_DIR = pathlib.Path(__file__).resolve().parent
MACHINES, _ = join()

# The phase-wide guards that serve an assertion for EVERY machine at once.
SWEEP_FILE = "test_phase6_transition_sweep.py"
POPULATION_FILE = "test_phase6_machine_population.py"


# ------------------------------------------------------------------ the authority, parsed not typed

def _acceptance_text() -> str:
    return ACCEPTANCE.read_text(encoding="utf-8")


def required_anchor_ids() -> set[str]:
    """The anchor ids on the acceptance file's own "named anchors (merge-gating)" line."""
    text = _acceptance_text()
    start = text.index("## The named anchors")
    return set(re.findall(r"`(AC-MACH-\d+[a-z]*)`", text[start:]))


def required_assertion_numbers() -> set[int]:
    """The numbers of the acceptance file's own "Per-machine mandatory assertions" list."""
    text = _acceptance_text()
    start = text.index("## Per-machine mandatory assertions")
    end = text.index("## The named anchors", start)
    return {int(n) for n in re.findall(r"^(\d+)\.\s", text[start:end], flags=re.M)}


# --------------------------------------------------------------------- pytest's own collected nodes

@pytest.fixture(scope="session")
def collected_nodes() -> set[str]:
    """### THE STRONG HALF OF "IS IT VERIFIED?". A function that exists in a file is not evidence; a
    node pytest COLLECTS is. This asks pytest, in a subprocess, for the ids it would run."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header", "-p", "no:cacheprovider",
         str(TESTS_DIR)],
        cwd=str(ROOT), capture_output=True, text=True)
    nodes = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "::" not in line:
            continue
        path, _, rest = line.partition("::")
        if not path.endswith(".py"):
            continue
        # Drop a parametrisation suffix: `test_x[M1/WI]` -> `test_x`.
        nodes.add(f"{pathlib.Path(path).name}::{rest.split('[')[0]}")
    assert len(nodes) > 500, (
        f"pytest collected {len(nodes)} nodes from {TESTS_DIR}; the traceability check would be "
        f"asking a question nothing can answer.\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return nodes


def _case_id(machine_number: int, row_suffix: str) -> str:
    """### THE ACCEPTANCE FILE'S OWN CASE-ID SHAPE: `AC-MACH-<machine><ordinal, two digits><letters>`.

    Its coverage table spells the ranges `AC-MACH-101..114`, `AC-MACH-201..225`, `AC-MACH-1001..1009`,
    `AC-MACH-1301..1305`, so the ordinal is zero-padded to two digits and the machine number is simply
    prefixed — M1's WI-1 is 101, M10's CM-1 is 1001. A lettered row keeps its letter: PL-10u is 210u,
    IB-5x is 605x. `test_the_case_id_shape_reproduces_the_acceptance_tables_ranges` checks this
    derivation against the ranges the authority prints, so the rule is verified, not assumed."""
    digits = "".join(c for c in row_suffix if c.isdigit())
    letters = row_suffix[len(digits):]
    return f"AC-MACH-{machine_number}{int(digits):02d}{letters}"


def _functions_in(filename: str) -> set[str]:
    path = TESTS_DIR / filename
    assert path.exists(), f"{filename} does not exist; a register entry points at a file that is gone."
    return {n.name for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}


# ======================================================== A. the register covers what is required

def test_the_register_covers_exactly_the_authoritys_seven_anchors():
    required = required_anchor_ids()
    registered = {a.anchor for a in ANCHORS}
    assert len(required) == 7, f"the acceptance file names {sorted(required)}; seven were expected."
    assert registered == required, (
        f"unregistered anchors the authority requires: {sorted(required - registered)}; "
        f"registered anchors the authority does not name: {sorted(registered - required)}")


def test_the_register_covers_exactly_the_authoritys_ten_assertions():
    required = required_assertion_numbers()
    registered = {a.number for a in ASSERTIONS}
    assert required == set(range(1, 11)), sorted(required)
    assert registered == required, sorted(registered ^ required)


def test_the_machine_register_is_the_discovered_population():
    """### THE REGISTER CANNOT OUTLIVE A MACHINE. Its keys are checked against the population
    `phase6_machine_population_kit` discovers, so deleting a machine breaks this file too."""
    discovered = {m.name for m in MACHINES}
    assert set(MACHINE_FILES) == discovered, sorted(set(MACHINE_FILES) ^ discovered)
    assert set(MUTATION_PROBES) == discovered, sorted(set(MUTATION_PROBES) ^ discovered)


# ============================================== B. the seven anchors — derivable, present, collected

@pytest.mark.parametrize("anchor", ANCHORS, ids=[a.anchor for a in ANCHORS])
def test_the_anchor_id_is_derived_from_the_canonical_transition_it_names(anchor):
    """### `AC-MACH-605x` IS PROVABLY "M6's IB-5x", NOT A STRING THAT LOOKS RIGHT. The id encodes the
    machine number and the row suffix; the derivation is reproduced and compared."""
    by_prefix = {m.spec.prefix: m for m in MACHINES}
    prefix, suffix = anchor.transition.split("-", 1)
    machine = by_prefix.get(prefix)
    assert machine is not None, f"{anchor.anchor} names transition {anchor.transition}, prefix unknown."
    assert anchor.transition in machine.spec.ids, (
        f"{anchor.anchor} names {anchor.transition}, which is not a canonical §14 row of "
        f"{machine.label}.")
    derived = _case_id(machine.spec.number, suffix)
    assert anchor.anchor == derived, (
        f"{anchor.anchor} does not derive from {anchor.transition} on {machine.label}; "
        f"{derived} would.")


def test_the_case_id_shape_reproduces_the_acceptance_tables_ranges():
    """### THE DERIVATION IS CHECKED AGAINST THE AUTHORITY, NOT ASSERTED.

    The coverage table prints each machine a case RANGE, and the range is POSITIONAL: `AC-MACH-201..225`
    is M2's twenty-five cases numbered 01..25, not its row suffixes — M2's last row is PL-15x, not
    PL-25. The two numberings agree at the START (every machine's first row is `-1`), and the named
    anchors use the ROW-SUFFIX form: `AC-MACH-208` is PL-8, `AC-MACH-215x` is PL-15x. Both facts are
    asserted here, for all thirteen, which is what licenses `_case_id` to judge the seven anchors."""
    text = ACCEPTANCE.read_text(encoding="utf-8")
    ranges = dict(re.findall(r"\|\s*M(\d{1,2})\b[^|]*\|[^|]*\|\s*`(AC-MACH-[\w.]+)`", text))
    assert len(ranges) == 13, sorted(ranges)
    for machine in MACHINES:
        first, last = ranges[str(machine.spec.number)].replace("AC-MACH-", "").split("..")
        n, ids = machine.spec.number, machine.spec.ids
        assert first == f"{n}{1:02d}", f"{machine.label}'s range starts at {first}, not {n}01."
        assert last == f"{n}{len(ids):02d}", (
            f"{machine.label}'s range ends at {last}, but it enumerates {len(ids)} rows — the range "
            f"is positional over the row count.")
        assert _case_id(n, ids[0].split("-", 1)[1]) == f"AC-MACH-{first}", (
            f"{machine.label}'s first row {ids[0]} does not derive to the range start {first}.")
    # And the row-suffix form is a FUNCTION of the row, so two rows never collide on one case id.
    for machine in MACHINES:
        derived = [_case_id(machine.spec.number, i.split("-", 1)[1]) for i in machine.spec.ids]
        assert len(set(derived)) == len(derived), (
            f"{machine.label} derives duplicate case ids: {sorted(derived)}")


@pytest.mark.parametrize("anchor", ANCHORS, ids=[a.anchor for a in ANCHORS])
def test_every_anchors_evidence_exists(anchor):
    assert anchor.evidence, f"{anchor.anchor} is registered with no evidence at all."
    for node in anchor.evidence:
        filename, _, func = node.partition("::")
        assert func in _functions_in(filename), (
            f"{anchor.anchor} cites {node}, which does not exist.")


@pytest.mark.parametrize("anchor", ANCHORS, ids=[a.anchor for a in ANCHORS])
def test_every_anchors_evidence_is_collected_by_pytest(anchor, collected_nodes):
    """### EXISTENCE IS NOT EXECUTION. Every cited node must be one pytest actually collects."""
    uncollected = [n for n in anchor.evidence if n not in collected_nodes]
    assert not uncollected, (
        f"{anchor.anchor} cites nodes pytest does not collect: {uncollected}. Evidence that never "
        f"runs proves nothing.")


def _source_of(filename: str, func: str) -> str:
    """The source of exactly one test function — not the file it lives in."""
    text = (TESTS_DIR / filename).read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{func} is not in {filename}")


@pytest.mark.parametrize("anchor", ANCHORS, ids=[a.anchor for a in ANCHORS])
def test_every_anchor_is_named_at_every_one_of_its_evidence_sites(anchor):
    """### THE TRACE HAS TO WORK FROM EITHER END, AT EVERY SITE. Grepping `AC-MACH-1305` must land on
    the things that prove it — that is precisely what the adjudication found missing.

    ### AND THE CHECK IS PER FUNCTION, NOT PER FILE, BECAUSE PER FILE IS TOO WEAK TO FAIL. An anchor
    with two cited tests in one file would stay traceable after the id was deleted from one of them;
    the mutation battery injects exactly that and it escaped a file-level check."""
    unnamed = [node for node in anchor.evidence
               if anchor.anchor not in _source_of(*node.split("::"))]
    assert not unnamed, (
        f"{anchor.anchor} cites {unnamed}, whose own source does not name it. Every cited site "
        f"carries its anchor id, so the trace works from the id as well as from the register.")


def test_all_seven_anchor_ids_are_greppable_under_eval():
    """The whole point, stated once: every merge-gating id resolves to a file under `eval/`."""
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in TESTS_DIR.glob("test_*.py"))
    missing = sorted(a.anchor for a in ANCHORS if a.anchor not in corpus)
    assert not missing, f"these merge-gating anchors name nothing under eval/tests: {missing}"


# ================================ C. the ten mandatory assertions, per machine, over 13 machines

def _cells() -> list[tuple[str, int]]:
    out = []
    for machine in MACHINE_FILES:
        for assertion in ASSERTIONS:
            if assertion.applies_to is not None and machine not in assertion.applies_to:
                continue
            out.append((machine, assertion.number))
    return out


CELLS = _cells()


def test_the_cell_population_is_proven():
    """### THE DENOMINATOR, PRINTED. Ten assertions over thirteen machines, less the two the
    authority's own wording restricts (6 to M1, 9 to M1/M9) — the restrictions are read off
    `Assertion.applies_to` and each carries its reason."""
    restricted = [a for a in ASSERTIONS if a.applies_to is not None]
    assert all(a.restriction for a in restricted), (
        "an assertion was narrowed without recording why; a narrowing nobody can read is a weakening.")
    expected = 13 * (len(ASSERTIONS) - len(restricted)) + sum(len(a.applies_to) for a in restricted)
    assert len(CELLS) == expected == 107, (
        f"{len(CELLS)} cells; {expected} expected from 13 machines x 10 assertions less the "
        f"restrictions.")
    evidenced = [c for c in CELLS if c not in UNEVIDENCED]
    assert len(evidenced) == len(CELLS) == 107, (
        f"{len(evidenced)} of {len(CELLS)} cells are evidenced; every required cell must be.")


@pytest.mark.parametrize("cell", CELLS, ids=[f"{m}:A{n}" for m, n in CELLS])
def test_every_required_cell_is_evidenced_or_a_recorded_gap(cell):
    machine, number = cell
    if number == 1:
        probe = ROOT / MUTATION_PROBES[machine]
        assert probe.exists(), (
            f"{machine} assertion 1 needs a guard-mutation probe; {probe} does not exist.")
        return
    if number == 2:
        # Served for every machine at once by the phase-wide sweep, plus the machine's own case.
        assert (TESTS_DIR / SWEEP_FILE).exists()
    # ### THERE IS NO SKIP PATH HERE ANY MORE, AND ITS ABSENCE IS THE POINT. While eleven cells were
    # recorded gaps this branch skipped them, and a skip is silence — `test_false_green_defenses`
    # rightly refuses an unapproved one. Every required cell now has evidence, so a cell with none is
    # a FAILURE rather than a note.
    nodes = EVIDENCE.get(cell)
    assert nodes, (
        f"{machine} assertion {number} has no evidence. Every required cell must name a test that "
        f"proves it — silence is what P6-AC-5 failed on.")
    functions = _functions_in(MACHINE_FILES[machine])
    for func in nodes:
        assert func in functions, (
            f"{machine} assertion {number} cites {func}, which is not in "
            f"{MACHINE_FILES[machine]}.")


@pytest.mark.parametrize("machine", sorted(MACHINE_FILES))
def test_every_registered_cell_for_this_machine_is_collected(machine, collected_nodes):
    filename = MACHINE_FILES[machine]
    cited = {f"{filename}::{func}"
             for (m, _n), funcs in EVIDENCE.items() if m == machine for func in funcs}
    uncollected = sorted(n for n in cited if n not in collected_nodes)
    assert not uncollected, (
        f"{machine} cites evidence pytest does not collect: {uncollected}")


def test_the_phase_wide_sweep_covers_assertion_two_for_every_machine(collected_nodes):
    """Assertion 2 is discharged for all thirteen at once, so its coverage is asserted at the
    population rather than machine by machine."""
    swept = {n for n in collected_nodes if n.startswith(SWEEP_FILE)}
    assert len(swept) >= 8, sorted(swept)
    assert f"{POPULATION_FILE}::test_ac_mach_000_exact_set_equality_per_machine" in collected_nodes


def test_the_unevidenced_set_is_empty_and_may_never_refill():
    """### THE RATCHET, NOW BINDING AT ZERO. Eleven cells were once recorded as gaps; all eleven are
    discharged by real behaviour tests. The set is asserted EMPTY rather than merely small, so a
    future gap cannot be recorded away — it has to be closed."""
    assert UNEVIDENCED == frozenset(), (
        f"{sorted(UNEVIDENCED)} are recorded as unevidenced. Every required cell now has behavioural "
        f"evidence; a new gap must be discharged, not registered.")
    assert not (UNEVIDENCED & set(EVIDENCE))


def test_every_required_cell_is_reachable_from_the_register():
    """### THE GUARD MUST FAIL IF ONE OF THE NEW EVIDENCE TARGETS DISAPPEARS. Each of the 107 cells
    resolves to something concrete: assertion 1 to its machine's guard-mutation probe, everything else
    to named test functions in that machine's own acceptance file."""
    unreachable = [
        (machine, number) for machine, number in CELLS
        if number != 1 and not EVIDENCE.get((machine, number))
    ]
    assert not unreachable, (
        f"these required cells resolve to no evidence at all: {unreachable}")


def test_no_registered_evidence_points_at_a_machine_that_is_not_its_own():
    """A register entry citing another machine's file would make a cell look discharged by somebody
    else's test."""
    for (machine, number), funcs in EVIDENCE.items():
        functions = _functions_in(MACHINE_FILES[machine])
        missing = [f for f in funcs if f not in functions]
        assert not missing, f"{machine} assertion {number}: {missing} not in {MACHINE_FILES[machine]}"
