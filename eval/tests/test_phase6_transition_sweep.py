"""### THE EXHAUSTIVE `(state × trigger)` SWEEP, OVER ALL THIRTEEN MACHINES.

`foundational-machine-acceptance.md`'s coverage requirement:

> ### **100% of the 134 legal transitions. Every omitted `(state,trigger)` pair proved ILLEGAL. No
> exceptions.**

and its per-machine mandatory assertion 2:

> ### **Every omitted transition is ILLEGAL** — an exhaustive `(state × trigger)` sweep.

### THE SWEEP EXISTED FOR TWO MACHINES OUT OF THIRTEEN. M1 and M2 each carried a bespoke sweep; M3
through M13 carried none, so eleven machines' omitted pairs were never enumerated at all. This file is
the missing eleven, and it replaces the other two's STRUCTURAL half rather than duplicating it —
`test_phase6_work_item.py` and `test_phase6_pipeline_instance.py` keep their BEHAVIOURAL sweeps, which
drive a real machine into every state and prove each refusal raises, persists nothing and records
`IllegalTransitionAttempted` on the audit AND security surfaces.

### ONE GENERIC GUARD, NOT THIRTEEN BESPOKE BLOCKS. Every machine now declares its §14 table as data
and answers `legal_transitions(state, trigger)`, so the sweep asks each machine what IT considers
legal and compares that with what ITS OWN TABLE declares. Thirteen hand-written blocks would be
thirteen chances to write the sweep to match the machine.

### AND NO MACHINE KEEPS AN EXCEPTION POPULATION. A row that cannot appear in any (state, trigger)
pair must say so on the ROW — `illegal`, a delegation, a creation row, no declared trigger, a
`kernel_path`, or `refusal_only`. `phase6_machine_population_kit._sweep_exclusion` reads those fields;
this file contains no list of transitions to skip, and `test_no_machine_carries_an_undeclared_exception`
proves it cannot acquire one.

### WHAT THIS PROVES, STATED EXACTLY. The legality DECISION of each machine agrees, pair for pair,
with the §14 table that `AC-MACH-000` has already put in bijection with the specification. It is the
structural half of the requirement. The behavioural half — that a refusal raises, writes nothing and
is recorded — is proved by each machine's own battery, and `test_phase6_anchor_traceability.py` is
what checks that every machine actually has that evidence and that it runs.
"""

from __future__ import annotations

import pathlib
import sys
from enum import Enum

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from phase6_machine_population_kit import (  # noqa: E402
    join,
    state_universe,
    trigger_universe,
)

MACHINES, _ORPHANS = join()


def _v(member) -> str:
    return member.value if isinstance(member, Enum) else str(member)


class Swept:
    """One machine's whole (state × trigger) product, classified by the machine itself."""

    def __init__(self, machine):
        self.machine = machine
        self.states = state_universe(machine)
        self.triggers = trigger_universe(machine)
        self.legal_transitions = machine.impl.module.legal_transitions
        self.legal: dict[tuple[str, str], tuple[str, ...]] = {}
        self.illegal: list[tuple[str, str]] = []
        for state in self.states:
            for trigger in self.triggers:
                rows = self.legal_transitions(state, trigger)
                pair = (_v(state), _v(trigger))
                if rows:
                    self.legal[pair] = tuple(r.id for r in rows)
                else:
                    self.illegal.append(pair)

    # The pairs §14's table declares, derived from the rows the sweep is entitled to reach.
    @property
    def declared(self) -> set[tuple[str, str]]:
        return {(s, t) for row in self.machine.impl.rows if row.excluded is None
                for s in row.from_states for t in row.triggers}

    @property
    def swept_rows(self) -> set[str]:
        return {r.id for r in self.machine.impl.rows if r.excluded is None}

    @property
    def pairs(self) -> int:
        return len(self.states) * len(self.triggers)


SWEPT = {m.label: Swept(m) for m in MACHINES}
LABELS = [m.label for m in MACHINES]


def _report() -> str:
    """### THE DENOMINATORS, PER MACHINE AND PHASE-WIDE. An exhaustive sweep whose population is not
    printed is an exhaustive sweep nobody can check the exhaustiveness of."""
    lines = ["", "  machine   states  triggers   pairs   legal   ILLEGAL   swept rows / table",
             "  -------   ------  --------   -----   -----   -------   ------------------"]
    tp = tl = ti = 0
    for label in LABELS:
        s = SWEPT[label]
        tp += s.pairs
        tl += len(s.legal)
        ti += len(s.illegal)
        lines.append(
            f"  {label:9s} {len(s.states):6d}  {len(s.triggers):8d}   {s.pairs:5d}   "
            f"{len(s.legal):5d}   {len(s.illegal):7d}   "
            f"{len(s.swept_rows):2d} / {len(s.machine.impl.rows):2d}")
    lines.append(f"  {'PHASE':9s} {'':6s}  {'':8s}   {tp:5d}   {tl:5d}   {ti:7d}")
    return "\n".join(lines)


REPORT = _report()


# ================================================================= A. the population is not vacuous

def test_the_sweep_population_is_proven_and_phase_wide():
    """### AN EMPTY OR TRUNCATED SWEEP PASSES VACUOUSLY, WHICH `P6-AC-3`'s ORACLE NAMES AS THE FAILURE
    MODE. So the denominators are asserted, not merely computed: thirteen machines, every one with
    states and triggers, and a phase-wide product in four figures."""
    assert len(SWEPT) == 13, f"the sweep covers {len(SWEPT)} machines, not 13.{REPORT}"
    total_pairs = sum(s.pairs for s in SWEPT.values())
    total_legal = sum(len(s.legal) for s in SWEPT.values())
    total_illegal = sum(len(s.illegal) for s in SWEPT.values())
    assert total_pairs == total_legal + total_illegal
    assert total_pairs > 1000, f"the phase-wide product is {total_pairs}.{REPORT}"
    assert total_legal > 100 and total_illegal > 900, REPORT


@pytest.mark.parametrize("label", LABELS)
def test_every_machine_has_both_a_legal_and_an_illegal_population(label):
    """A machine that classified everything legal, or everything illegal, would make both halves of
    the sweep prove nothing. Each half is asserted non-empty per machine."""
    s = SWEPT[label]
    assert s.states and s.triggers, f"{label} has an empty universe.{REPORT}"
    assert s.legal, f"{label} classified NO (state, trigger) pair as legal.{REPORT}"
    assert s.illegal, f"{label} classified NO (state, trigger) pair as illegal.{REPORT}"


# ======================================================= B. every canonical legal pair is ACCEPTED

@pytest.mark.parametrize("label", LABELS)
def test_every_pair_the_table_declares_is_accepted(label):
    """### `100% OF THE 134 LEGAL TRANSITIONS`. Every (from-state, trigger) a swept §14 row declares
    is classified LEGAL by the machine, and the machine names that very row."""
    s = SWEPT[label]
    refused = sorted(s.declared - set(s.legal))
    assert not refused, (
        f"{label} refuses (state, trigger) pairs its own §14 table declares: {refused}{REPORT}")
    for row in s.machine.impl.rows:
        if row.excluded is not None:
            continue
        for state in row.from_states:
            for trigger in row.triggers:
                named = s.legal[(state, trigger)]
                assert row.id in named, (
                    f"{label}: ({state}, {trigger}) is legal but resolves to {named}, not to "
                    f"{row.id}, which declares it.{REPORT}")


@pytest.mark.parametrize("label", LABELS)
def test_every_swept_row_is_reachable_by_at_least_one_pair(label):
    """### A ROW NO PAIR REACHES IS A ROW THE SWEEP DOES NOT TEST. Asserted per machine, so the
    134-row population and the swept population cannot drift apart silently."""
    s = SWEPT[label]
    reached = {rid for ids in s.legal.values() for rid in ids}
    unreachable = sorted(s.swept_rows - reached)
    assert not unreachable, (
        f"{label} declares rows no (state, trigger) pair reaches: {unreachable}{REPORT}")
    invented = sorted(reached - {r.id for r in s.machine.impl.rows})
    assert not invented, (
        f"{label} returned transition ids that are not in its table at all: {invented}{REPORT}")


# ==================================================== C. every non-canonical pair is REJECTED

@pytest.mark.parametrize(
    "label,state",
    [(m.label, _v(st)) for m in MACHINES for st in state_universe(m)],
    ids=[f"{m.label}:{_v(st)}" for m in MACHINES for st in state_universe(m)],
)
def test_every_omitted_pair_at_this_state_is_illegal(label, state):
    """### THE EXHAUSTIVE HALF, ONE STATE AT A TIME SO A FAILURE NAMES ONE. Every trigger in the
    machine's vocabulary is offered at this state; every pair no §14 row declares must be refused."""
    s = SWEPT[label]
    offered = [(state, _v(t)) for t in s.triggers]
    assert offered, f"{label} offered no trigger at {state}.{REPORT}"
    declared = s.declared
    wrongly_legal = sorted(p for p in offered if p in s.legal and p not in declared)
    assert not wrongly_legal, (
        f"{label} accepts (state, trigger) pairs no §14 row declares: {wrongly_legal} -> "
        f"{[s.legal[p] for p in wrongly_legal]}{REPORT}")
    wrongly_illegal = sorted(p for p in offered if p in declared and p not in s.legal)
    assert not wrongly_illegal, (
        f"{label} refuses declared pairs: {wrongly_illegal}{REPORT}")


@pytest.mark.parametrize("label", LABELS)
def test_the_illegal_population_is_the_exact_complement(label):
    """Legal ∪ illegal is the whole product, they are disjoint, and legal is EXACTLY what the table
    declares — so the illegal set is derived, never listed."""
    s = SWEPT[label]
    legal, illegal = set(s.legal), set(s.illegal)
    product = {(_v(st), _v(tr)) for st in s.states for tr in s.triggers}
    assert legal | illegal == product and not (legal & illegal), REPORT
    assert legal == s.declared, (
        f"{label}: accepted-but-undeclared={sorted(legal - s.declared)} "
        f"declared-but-refused={sorted(s.declared - legal)}{REPORT}")


# ================================================== D. no machine keeps a hand-maintained exception

@pytest.mark.parametrize("label", LABELS)
def test_no_machine_carries_an_undeclared_exception(label):
    """### THE ANTI-EXCEPTION-POPULATION GUARD. Every row the sweep does not reach must carry a REASON
    ON THE ROW. If a future row is excluded for a reason the tables do not declare, the kit returns
    `None` for it, the row lands in the swept population, and section B fails — there is no third
    outcome in which a transition is quietly skipped."""
    s = SWEPT[label]
    for row in s.machine.impl.rows:
        if row.excluded is None:
            assert row.from_states and row.triggers, (
                f"{label}/{row.id} is in the swept population but declares "
                f"from_states={row.from_states} triggers={row.triggers}; a row with neither cannot "
                f"be reached and must declare why.{REPORT}")
    excluded = {r.id: r.excluded for r in s.machine.impl.rows if r.excluded is not None}
    swept = s.swept_rows
    assert set(excluded) | swept == {r.id for r in s.machine.impl.rows}
    assert not (set(excluded) & swept)


def test_the_exclusion_reasons_are_declared_row_fields_and_are_a_small_closed_set():
    """### THE EXCLUSIONS ARE DATA, AND THERE ARE FEW OF THEM. If this set grows, a machine has
    acquired a new way to keep a transition out of the sweep, and that is a decision that must be read
    rather than inherited."""
    reasons = {r.excluded.split("=")[0] for m in MACHINES for r in m.impl.rows
               if r.excluded is not None}
    assert reasons <= {"illegal", "delegation", "creation", "no declared trigger", "kernel_path",
                       "refusal_only"}, sorted(reasons)
    excluded_total = sum(1 for m in MACHINES for r in m.impl.rows if r.excluded is not None)
    swept_total = sum(len(s.swept_rows) for s in SWEPT.values())
    assert excluded_total + swept_total == 134, (
        f"{swept_total} swept + {excluded_total} excluded != 134 canonical rows.{REPORT}")
    assert swept_total > excluded_total, (
        f"only {swept_total} of 134 rows are swept; the sweep would prove less than it skips.{REPORT}")


# ============================================================ E. the named structural anchors

def test_ac_mach_215x_no_timer_moves_needs_verification():
    """`AC-MACH-215x` — read off the sweep rather than off one hand-written case."""
    s = SWEPT["M2/PL"]
    timers = [p for p in s.legal if p[1] == "TimerFired"]
    assert not timers, f"a timer is legal somewhere in M2: {timers}"
    assert ("NEEDS_VERIFICATION", "TimerFired") in set(s.illegal)


def test_ac_mach_1305_no_timer_releases_a_brake():
    """`AC-MACH-1305` — the same property for M13, and for the same structural reason: `TimerFired`
    is in the vocabulary and has no legal row at either state."""
    s = SWEPT["M13/BR"]
    assert "TimerFired" in {_v(t) for t in s.triggers}
    timers = [p for p in s.legal if p[1] == "TimerFired"]
    assert not timers, f"a timer is legal somewhere in M13: {timers}"
    assert ("ACTIVE", "TimerFired") in set(s.illegal)


def test_no_timer_resolves_a_conflict_or_an_exception():
    """M7 and M9 both carry `TimerFiredToResolved` in their vocabularies precisely so GR-1 answers it
    uniformly; it must be legal at no state of either."""
    for label in ("M7/CF", "M9/EC"):
        s = SWEPT[label]
        assert "TimerFiredToResolved" in {_v(t) for t in s.triggers}, label
        assert not [p for p in s.legal if p[1] == "TimerFiredToResolved"], label
