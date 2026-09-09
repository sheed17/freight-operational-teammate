"""`AC-MACH-000` — ### THE P6 TRANSITION POPULATION, PROVED IN BOTH DIRECTIONS OVER A DISCOVERED SET.

`foundational-machine-acceptance.md` requires this case by name:

> ### **A `STRUCTURAL` case (`AC-MACH-000`) enumerates the transition tables FROM THE
> IMPLEMENTATION's declarative data and asserts a bijection with the 134 spec rows.** A transition in
> the spec with no case, or a case with no spec row, **fails the build.**
> ### **The oracle is EXACT SET EQUALITY of transition identifiers, not a count. A count match with
> different members MUST fail.**

### THE CASE DID NOT EXIST, AND EVERY MACHINE'S OWN BATTERY ASSERTING ITS OWN COUNT IS NOT IT. Thirteen
local assertions that thirteen local tables have the length their authors expected cannot see a
machine that is missing, a module that was deleted, an id that two machines both claim, or a table
that agrees with itself and with nothing else. This file is the phase-level guard: it discovers the
specification corpus, discovers the implementation modules, joins them by transition-id prefix, and
compares the two populations as SETS.

### FOUR INDEPENDENT AXES, SO THE BIJECTION IS NOT A DOCUMENT AGREEING WITH ITSELF.

 1. SPEC ids  ==  IMPLEMENTATION ids, exact set equality, both directions.
 2. The DENOMINATORS (134, and 14/25/13/11/8/11/7/8/7/9/7/9/5) are parsed out of
    `foundational-machine-acceptance.md`'s own coverage table — the authority's number read from the
    authority, never retyped here.
 3. Every declared id is a string LITERAL the module actually uses, and every transition-id literal
    in the module is a declared row (`_source_literals`). A table that drifts from the code it claims
    to describe fails, even when it still matches the specification.
 4. Every producer id in the canonical event registry is a canonical transition id — P5's
    `event_contracts_data.json` was built from the event families, so it is a THIRD party to the
    argument and cannot be fixed by editing either table.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys
from collections import Counter

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from phase6_machine_population_kit import (  # noqa: E402
    ROOT,
    SRC_DIR,
    acceptance_denominators,
    discover_machine_modules,
    discover_specs,
    join,
    state_universe,
    trigger_universe,
)

MACHINES, ORPHANS = join()
ACCEPTANCE_PER_MACHINE, ACCEPTANCE_TOTAL = acceptance_denominators()


def _denominator_report() -> str:
    """### THE DENOMINATORS, PRINTED RATHER THAN ASSUMED. Attached to every failure below, because a
    population guard that fails without saying what it counted sends the reader back to the code."""
    lines = ["", "  machine   spec  impl   module", "  -------   ----  ----   ------"]
    spec_total = impl_total = 0
    for m in MACHINES:
        spec_total += len(m.spec.ids)
        impl_total += len(m.impl.ids)
        flag = "" if len(m.spec.ids) == len(m.impl.ids) else "   <-- MISMATCH"
        lines.append(f"  {m.label:9s} {len(m.spec.ids):4d}  {len(m.impl.ids):4d}   "
                     f"freight_recon.{m.impl.module_name}{flag}")
    lines.append(f"  {'TOTAL':9s} {spec_total:4d}  {impl_total:4d}   "
                 f"(acceptance table declares {ACCEPTANCE_TOTAL})")
    return "\n".join(lines)


REPORT = _denominator_report()


# ============================================================== A. the population exists and is whole

def test_the_specification_corpus_is_thirteen_machines():
    """### A SPECIFICATION THAT DISAPPEARS MUST BREAK SOMETHING. The corpus is globbed, so deleting a
    `*.machine.md` drops a prefix, and the join below loses a machine."""
    specs = discover_specs()
    numbers = sorted(s.number for s in specs)
    assert numbers == list(range(1, 14)), (
        f"the machine specification corpus is {numbers}, not M1..M13. A specification file that "
        f"vanished takes its rows out of the canonical denominator with it.{REPORT}")
    assert len({s.prefix for s in specs}) == 13, sorted(s.prefix for s in specs)


def test_the_implementation_corpus_is_thirteen_machine_modules():
    """### A MODULE THAT DISAPPEARS MUST BREAK SOMETHING. Discovery parses `src/freight_recon/*.py`
    for a module-level `TRANSITIONS`; it does not consult a filename list, which is the only version
    of this test that can fail when a machine is deleted."""
    impls = discover_machine_modules()
    assert len(impls) == 13, (
        f"discovered {len(impls)} machine modules, not 13: "
        f"{sorted(i.module_name for i in impls)}{REPORT}")


def test_every_specification_joins_exactly_one_module():
    assert ORPHANS == {"spec_without_module": [], "module_without_spec": []}, (
        f"the specification and implementation populations did not join: {ORPHANS}. A specification "
        f"with no module is an unimplemented machine; a module with no specification is a machine "
        f"nobody specified.{REPORT}")
    assert len(MACHINES) == 13, REPORT


def test_the_canonical_denominator_is_one_hundred_and_thirty_four():
    """### 134, DERIVED THREE WAYS AND AGREEING. The sum of the parsed §14 tables, the sum of the
    acceptance file's per-machine column, and the acceptance file's own Total cell."""
    per_machine = {m.name: len(m.spec.ids) for m in MACHINES}
    assert per_machine == ACCEPTANCE_PER_MACHINE, (
        f"the §14 tables and the acceptance file's coverage table disagree per machine.\n"
        f"  parsed from §14:        {per_machine}\n"
        f"  acceptance table says:  {ACCEPTANCE_PER_MACHINE}{REPORT}")
    assert sum(per_machine.values()) == ACCEPTANCE_TOTAL == 134, (
        f"the canonical population is {sum(per_machine.values())}; the acceptance table declares "
        f"{ACCEPTANCE_TOTAL}; the coverage requirement is 134.{REPORT}")


def test_no_transition_identifier_is_declared_twice():
    """### A DUPLICATE ID IS A COUNT THAT MATCHES WITH DIFFERENT MEMBERS. Checked on both sides and
    across the whole phase, because two machines claiming one id would still sum to 134."""
    spec_ids = [i for m in MACHINES for i in m.spec.ids]
    impl_ids = [i for m in MACHINES for i in m.impl.ids]
    for label, ids in (("specification", spec_ids), ("implementation", impl_ids)):
        dupes = sorted(i for i, n in Counter(ids).items() if n > 1)
        assert not dupes, f"duplicate {label} transition identifiers: {dupes}{REPORT}"
    assert len(spec_ids) == len(set(spec_ids)) == 134, f"{len(spec_ids)}{REPORT}"
    assert len(impl_ids) == len(set(impl_ids)) == 134, f"{len(impl_ids)}{REPORT}"


# =============================================== B. AC-MACH-000 — the bijection, in both directions

def test_ac_mach_000_specification_minus_implementation_is_empty():
    """### A TRANSITION IN THE SPECIFICATION WITH NO CASE FAILS THE BUILD."""
    missing = {m.label: sorted(set(m.spec.ids) - set(m.impl.ids))
               for m in MACHINES if set(m.spec.ids) - set(m.impl.ids)}
    assert not missing, (
        f"AC-MACH-000: spec - implementation != empty. These canonical transitions have no "
        f"implementation row:\n  {missing}{REPORT}")


def test_ac_mach_000_implementation_minus_specification_is_empty():
    """### A CASE WITH NO SPECIFICATION ROW FAILS THE BUILD."""
    extra = {m.label: sorted(set(m.impl.ids) - set(m.spec.ids))
             for m in MACHINES if set(m.impl.ids) - set(m.spec.ids)}
    assert not extra, (
        f"AC-MACH-000: implementation - spec != empty. These implementation transitions have no "
        f"canonical row:\n  {extra}{REPORT}")


@pytest.mark.parametrize("machine", MACHINES, ids=[m.label for m in MACHINES])
def test_ac_mach_000_exact_set_equality_per_machine(machine):
    """### THE ORACLE IS SET EQUALITY, NOT A COUNT — asserted per machine so a failure names one."""
    spec, impl = set(machine.spec.ids), set(machine.impl.ids)
    assert spec == impl, (
        f"{machine.label}: spec-only={sorted(spec - impl)} implementation-only={sorted(impl - spec)}. "
        f"A count match with different members MUST fail, and this is where it does.{REPORT}")
    assert len(machine.spec.ids) == ACCEPTANCE_PER_MACHINE[machine.name], (
        f"{machine.label} enumerates {len(machine.spec.ids)} rows; the acceptance table declares "
        f"{ACCEPTANCE_PER_MACHINE[machine.name]}.{REPORT}")


# ================================================ C. the table describes the code, not just the spec

_LITERAL_CACHE: dict[str, set[str]] = {}


def _source_literals(machine) -> set[str]:
    """Every string literal in the module that has this machine's transition-id shape.

    ### THIS IS THE AXIS A HAND-WRITTEN TABLE CANNOT SATISFY BY ITSELF. The declarative rows are only
    a faithful description of the machine if the ids they name are the ids the code actually writes to
    `transition_id` / `event_producer` / `row_id`. Both directions are asserted below."""
    key = machine.impl.module_name
    if key not in _LITERAL_CACHE:
        tree = ast.parse((SRC_DIR / f"{key}.py").read_text(encoding="utf-8"))
        rx = re.compile(rf"^{machine.spec.prefix}-[0-9A-Za-z]+$")
        _LITERAL_CACHE[key] = {
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and rx.match(n.value)}
    return _LITERAL_CACHE[key]


@pytest.mark.parametrize("machine", MACHINES, ids=[m.label for m in MACHINES])
def test_every_declared_row_is_an_identifier_the_module_actually_uses(machine):
    declared, literals = set(machine.impl.ids), _source_literals(machine)
    assert declared - literals == set(), (
        f"{machine.label} declares {sorted(declared - literals)} in its TRANSITIONS table, but no "
        f"code in freight_recon.{machine.impl.module_name} names them. A row describing a transition "
        f"the module does not have is a row that makes the bijection look whole while it is not.")


@pytest.mark.parametrize("machine", MACHINES, ids=[m.label for m in MACHINES])
def test_every_transition_identifier_in_the_module_is_a_declared_row(machine):
    declared, literals = set(machine.impl.ids), _source_literals(machine)
    assert literals - declared == set(), (
        f"freight_recon.{machine.impl.module_name} names transition ids {sorted(literals - declared)} "
        f"that its TRANSITIONS table does not declare. An implementation transition with no canonical "
        f"row is exactly what AC-MACH-000 exists to refuse.")


# ================================== D. the third party — P5's canonical event registry (AC-EVT-003)

def _registry_producers() -> set[str]:
    data = json.loads((SRC_DIR / "event_contracts_data.json").read_text(encoding="utf-8"))
    return {p for c in data["contracts"] for p in (c.get("producers") or [])}


def test_every_registered_event_producer_is_a_canonical_transition():
    """### THE 134-TO-105 MAP, READ FROM THE OTHER END. `event_contracts_data.json` is generated from
    the EVENT families, so its `producers` are an independent projection of the transition population.
    A producer naming a transition that no §14 row declares is a canonical event attributed to a
    transition that does not exist — and it cannot be repaired by editing a machine's table."""
    canonical = {i for m in MACHINES for i in m.spec.ids}
    orphaned = sorted(_registry_producers() - canonical)
    assert not orphaned, (
        f"the canonical event registry attributes events to transitions that are not in the 134: "
        f"{orphaned}{REPORT}")


def test_a_row_declares_an_event_exactly_when_the_registry_names_it_a_producer():
    """### THE 134-TO-105 MAP, ASSERTED AS A BICONDITIONAL OVER ALL 134 ROWS.

    A row that declares an event but is not a registered producer is a machine minting a contract the
    registry does not know about. A registered producer whose row declares no event is a canonical
    event with nothing to emit it. Both are failures, and neither can be repaired by editing only one
    of the two files — `event_contracts_data.json` is generated from the EVENT families."""
    producers = _registry_producers()
    canonical = {i for m in MACHINES for i in m.spec.ids}
    assert 100 < len(producers) < len(canonical), (
        f"{len(producers)} registered producers against {len(canonical)} canonical transitions; at "
        f"this population the biconditional below would prove nothing.")
    disagreements = {
        f"{m.label}/{row.id}": {"declares": row.events, "registered_producer": row.id in producers}
        for m in MACHINES for row in m.impl.rows
        if bool(row.events) != (row.id in producers)
    }
    assert not disagreements, (
        f"a transition row and the canonical event registry disagree about whether it produces:\n"
        f"  {disagreements}{REPORT}")


def test_every_non_producing_row_says_why_it_produces_nothing():
    """### SILENCE IS DECLARED, NEVER INFERRED. The seventeen canonical rows that emit no registered
    event must each be an illegal row, a delegation, or a row the registry attributes elsewhere — and
    the count is asserted so a row losing its event cannot slip into this set unnoticed."""
    producers = _registry_producers()
    silent = [(f"{m.label}/{row.id}", row) for m in MACHINES for row in m.impl.rows
              if row.id not in producers]
    assert len(silent) == 134 - len(producers) == 17, (
        f"{len(silent)} canonical rows emit no registered event; the corpus has {len(producers)} "
        f"producers against 134 rows.{REPORT}")
    undeclared = [label for label, row in silent if row.events]
    assert not undeclared, (
        f"these rows emit no registered event yet declare one: {undeclared}")
