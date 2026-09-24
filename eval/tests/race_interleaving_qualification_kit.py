"""A deterministic interleaving scheduler for the G4 race qualification (AC-RACE-001..017).

release-gates.md G4 declares "10,000 interleavings per race". recovery-and-compensation-
acceptance.md is emphatic that "Every schedule is an EXACT interleaving driven by a controllable
scheduler (barriers/injected pauses), not luck. 'No reproducible race occurred' is NOT an acceptable
result — a non-deterministic run FAILS." So this qualification is NOT threads-and-luck and it is NOT
`--repeat 10000` of one schedule (the exact vacuity the frozen P8 review flagged: a single-threaded
alternation whose headline is tautological). It is a deterministic enumeration of DISTINCT
interleavings.

### WHAT A "SCHEDULE" IS.
A race is modelled as a set of concurrent THREADS, each a fixed ordered list of ATOMIC operations
(atomic because the product's real writes — the claim CAS, a brake bump, an inbox commit — are each
a single serialised statement). A schedule is one EXACT interleaving of those atomic operations
(which thread advances at each position), crossed with a controllable PRE-STATE vector (the
revalidation base a version pins, a duplicate count, a fault position). Every distinct
(interleaving, pre-state) pair is one qualified schedule; the race-specific invariant is checked on
EVERY one, and any single failure fails the race.

### WHY THIS IS FAITHFUL, NOT A TOY.
The apply function encodes the REAL decision predicate of the mechanism under test — e.g. a claim
writes CLAIMED iff the grant is still GRANTED and the version it pinned at checkpoint still equals
the current version (the claim CAS's WHERE clause, checkpoint.py `_claim_locked`). The flagship
races additionally CROSS-VALIDATE the model against the live product (run_checkpoint /
claim_grant_cas / BrakeStore) on the bounded set of semantically-distinct orderings, so the model is
tied to the product, not asserted in a vacuum. And each race carries an anti-vacuity control: a
broken apply (the revalidation dropped) MUST make the invariant fail on some schedule, proving the
10,000 checks discriminate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


def distinct_interleavings(counts: list[int]):
    """Yield every DISTINCT interleaving of threads whose step counts are `counts`, as a tuple of
    thread ids (the thread that advances at each position). Distinct multiset permutations: each
    interleaving is emitted exactly once, deterministically, and it preserves each thread's own
    internal order by construction (a thread's k-th appearance consumes its k-th step)."""
    n = sum(counts)
    remaining = list(counts)
    cur: list[int] = []

    def rec():
        if len(cur) == n:
            yield tuple(cur)
            return
        for t in range(len(remaining)):
            if remaining[t] > 0:
                remaining[t] -= 1
                cur.append(t)
                yield from rec()
                cur.pop()
                remaining[t] += 1

    yield from rec()


@dataclass(frozen=True)
class Race:
    """One race's faithful model. `build_threads(pre)` returns the per-thread ordered op lists;
    `initial_state(pre)` the shared mutable state; `apply_op(state, op)` the REAL decision predicate;
    `invariant(state, trace)` raises on a violation of the canonical outcome."""

    id: str
    canonical: str
    build_threads: Callable[[Any], list[list[Any]]]
    initial_state: Callable[[Any], dict]
    apply_op: Callable[[dict, Any], None]
    invariant: Callable[[dict, list], None]
    prestates: Callable[[], list]


@dataclass(frozen=True)
class QualResult:
    race_id: str
    denominator: int          # distinct qualified schedules checked
    interleavings: int
    prestates: int
    checked: int
    failures: list
    canonical: str


def qualify_race(race: Race, *, repeat: int = 10000, apply_override: Callable | None = None):
    """Enumerate ≥ `repeat` DISTINCT schedules for `race`, checking its invariant on every one.

    The population is `distinct interleavings × pre-states`; it must be ≥ repeat (a race whose
    controllable space is smaller is a modelling error, surfaced here, not padded with repeats).
    `apply_override` swaps in a broken predicate for the anti-vacuity control."""
    prestates = race.prestates()
    assert prestates, f"{race.id}: no pre-state family"
    shape = [len(t) for t in race.build_threads(prestates[0])]
    perms = list(distinct_interleavings(shape))
    denominator = len(perms) * len(prestates)
    assert denominator >= repeat or apply_override is not None, (
        f"{race.id}: only {denominator} distinct schedules (< {repeat}); the controllable space is "
        f"under-modelled — widen the interleaving/pre-state space, never repeat a schedule")
    apply_op = apply_override or race.apply_op

    failures: list = []
    checked = 0
    for pre in prestates:
        threads = race.build_threads(pre)
        for perm in perms:
            state = race.initial_state(pre)
            trace: list = []
            cursors = [0] * len(threads)
            for t in perm:
                op = threads[t][cursors[t]]
                cursors[t] += 1
                apply_op(state, op)
                trace.append(op)
            try:
                race.invariant(state, trace)
            except AssertionError as exc:
                if len(failures) < 20:
                    failures.append((pre, perm, str(exc)))
            checked += 1
    return QualResult(race.id, denominator, len(perms), len(prestates), checked, failures,
                      race.canonical)
