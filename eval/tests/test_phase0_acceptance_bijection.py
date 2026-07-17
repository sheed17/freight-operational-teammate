"""U0.1 / U0.8 - the acceptance coverage probes (AC-TRACE-000's Phase-0 skeleton).

These parse the CANONICAL registries. They do not restate the specification inside the checker: a
checker that carries its own copy of the numbers agrees with itself forever.

Two of these tests FAIL against the frozen corpus, and that is the finding. Every coverage target
enumerated in a single table is exactly right (40 entities, 18 adapters, 11 loops, 28 invariants,
16 false-closure rules, 10 handoffs, 20 cross-domain invariants). Both targets that required summing
across 13 files are wrong: transitions (134 enumerated vs 141 declared) and emitted events (98 vs
92). See DEF-4 and DEF-5. They are recorded as EXPECTED_CURRENT_DEFECT and block G1/G2, not P1.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import manifest, spec_corpus


def test_every_probe_evaluates_a_real_population():
    for fn, minimum in (
        (spec_corpus.transitions, 100),
        (spec_corpus.events, 90),
        (spec_corpus.domain_entities, 40),
        (spec_corpus.adapters, 18),
        (spec_corpus.loops, 11),
    ):
        ev = fn()
        ev.require_population(minimum=minimum)


def test_the_enumerated_counts_are_stable_against_the_manifest():
    counts = manifest.spec_counts()
    assert spec_corpus.transitions().evaluated == counts["transitions_enumerated"]
    assert len(spec_corpus.emitted_events()) == counts["emitted_events_enumerated"]
    assert len(spec_corpus.security_events()) == counts["security_events_enumerated"]
    assert spec_corpus.domain_entities().evaluated == counts["domain_entities"]
    assert spec_corpus.adapters().evaluated == counts["adapters"]
    assert spec_corpus.loops().evaluated == counts["loops"]


def test_the_corpus_per_machine_table_agrees_with_the_machine_files():
    """Each of the 13 per-machine counts matches its file exactly. That is what makes DEF-4 clean."""
    summed, stated, per_machine = spec_corpus.declared_transition_total()
    assert len(per_machine) == 13
    actual = spec_corpus.transitions().evaluated
    assert summed == actual, (
        f"the acceptance spec's per-machine numbers sum to {summed} but the machine files enumerate "
        f"{actual} - the disagreement is now inside the per-machine rows, which is a different and "
        f"worse defect than DEF-4"
    )


@pytest.mark.xfail(strict=True, reason="DEF-4: the corpus declares 141 transitions; 134 are enumerated")
def test_declared_transition_total_matches_the_enumeration():
    """EXPECTED FAILURE - DEF-4, adjudicated in the baseline manifest.

    G1's exit criterion is "AC-MACH-* (141/141)" and AC-MACH-000 asserts "a bijection with the 141
    spec rows". A correct implementation of all 134 spec transitions would fail that bijection
    forever. Both tempting repairs are bad: invent 7 transitions, or weaken the bijection to an
    inequality. This must be adjudicated by the owner before G1.
    """
    summed, stated, _ = spec_corpus.declared_transition_total()
    assert stated == summed


@pytest.mark.xfail(strict=True, reason="DEF-5: the corpus declares 92 emitted events; 98 are enumerated")
def test_declared_emitted_event_total_matches_the_enumeration():
    """EXPECTED FAILURE - DEF-5, adjudicated in the baseline manifest. Blocks G2."""
    counts = manifest.spec_counts()
    assert len(spec_corpus.emitted_events()) == counts["emitted_events_declared"]


def test_the_security_event_count_is_correct():
    """The control: F14 is declared as 13 and enumerates 13. The corpus is not uniformly wrong."""
    assert len(spec_corpus.security_events()) == 13


def test_f15_declares_no_new_event_contracts():
    """F15 is a lens over cross-machine consumption. Counting it would double-count every event."""
    registry = (
        Path(__file__).resolve().parents[2]
        / "docs" / "specifications" / "events" / "registry.md"
    ).read_text(encoding="utf-8")
    assert "no new contracts" in registry
    assert not [k for k in spec_corpus.events().accepted if k.startswith("F15:")]


def test_the_defects_are_adjudicated_with_a_phase_and_an_owner():
    defects = {d["id"]: d for d in manifest.load()["expected_current_defects"]}
    for did in ("DEF-4", "DEF-5"):
        d = defects[did]
        assert d["accountable_unit"]
        assert d["deletion_condition"]
        assert "adjudication" in d["removed_by_phase"]
