"""U0.1 / U0.8 - the acceptance coverage probes (AC-TRACE-000's Phase-0 skeleton).

These parse the CANONICAL registries. They do not restate the specification inside the checker: a
checker that carries its own copy of the numbers agrees with itself forever.

ERRATA 2026-07-16. Phase 0 found that the corpus declared 141 transitions and 92 emitted events
while enumerating 134 and 98. The corpus has now been amended to its own enumeration - no
transitions were invented, and no bijection was weakened to an inequality.

THE ORACLE IS EXACT SET EQUALITY, NOT A COUNT:

    enumerated canonical ids == registered expected ids == acceptance-mapped ids

A count match with different members MUST fail. That is not pedantry - it is the precise defect
being corrected. A number drifted away from the members it claimed to count, and every count-based
check agreed with it for as long as it existed. Counts below are diagnostics only.
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


def test_transitions_exact_set_equality_enumerated_vs_registered():
    """ERRATA 1 ORACLE. The primary check: SET equality, not 134 == 134."""
    ev = spec_corpus.transitions()
    ev.require_population(minimum=100)
    enumerated = {k.split(":")[1] for k in ev.accepted}
    registered = manifest.expected_transition_ids()
    assert registered, "the registered expectation set is empty - the oracle would be vacuous"
    assert enumerated == registered, (
        f"transition set drift.\n"
        f"  enumerated but not registered: {sorted(enumerated - registered)}\n"
        f"  registered but not enumerated: {sorted(registered - enumerated)}"
    )
    assert len(enumerated) == 134, "diagnostic only - the set equality above is the real oracle"


def test_declared_transition_total_now_matches_the_enumeration():
    """ERRATA 1: the corpus was amended to its own enumeration. DEF-4 is CLOSED."""
    summed, stated, _ = spec_corpus.declared_transition_total()
    assert summed == 134
    assert stated == 134, (
        f"the acceptance spec's Total row says {stated}; its own per-machine rows sum to {summed}. "
        f"The errata correction has regressed."
    )


def test_g1_requires_the_134_transition_coverage_set():
    """REGRESSION 12: G1 must never require 141 again."""
    from phase0.markdown import clean, find_table
    from phase0.sources import ACCEPTANCE
    gates = find_table(ACCEPTANCE / "release-gates.md", "Gate", "Required cases")
    g1 = next(r for r in gates["rows"] if clean(r[0]) == "G1")
    required = clean(g1[2])
    assert "134/134" in required, f"G1 no longer requires 134/134 transitions: {required!r}"
    assert "141" not in required, f"G1 still requires 141 transitions: {required!r}"


def test_events_exact_set_equality_enumerated_vs_registered():
    """ERRATA 2 ORACLE. SET equality over event names."""
    ev = spec_corpus.events()
    ev.require_population(minimum=100)
    enumerated = {k.split(":")[1] for k in spec_corpus.emitted_events()}
    registered = manifest.expected_event_names()
    assert registered, "the registered expectation set is empty - the oracle would be vacuous"
    assert enumerated == registered, (
        f"emitted-event set drift.\n"
        f"  enumerated but not registered: {sorted(enumerated - registered)}\n"
        f"  registered but not enumerated: {sorted(registered - enumerated)}"
    )
    assert len(enumerated) == 98, "diagnostic only"


def test_g2_requires_the_98_event_coverage_set():
    """REGRESSION 13: G2 must never require 92 again."""
    from phase0.markdown import clean, find_table
    from phase0.sources import ACCEPTANCE
    gates = find_table(ACCEPTANCE / "release-gates.md", "Gate", "Required cases")
    g2 = next(r for r in gates["rows"] if clean(r[0]) == "G2")
    required = clean(g2[2])
    assert "98/98" in required, f"G2 no longer requires 98/98 events: {required!r}"
    assert "(92/92)" not in required, f"G2 still requires 92 events: {required!r}"


def test_timerfired_is_a_trigger_and_is_never_counted_as_an_emitted_event():
    """REGRESSION 5: an emitted event mistaken for a trigger, or vice versa.

    NOTE the require_population() call. This test is a NEGATIVE assertion - "TimerFired is not in
    the set" - and a negative assertion is VACUOUSLY TRUE over an empty set. Without the population
    check it reports "TimerFired is correctly excluded" while excluding everything, which is M-9
    wearing a different hat. It was caught exactly that way: a mutation harness left stale bytecode,
    the parser silently returned zero events, and this test went green.
    """
    ev = spec_corpus.events()
    ev.require_population(minimum=100)          # <- without this, an empty parse passes
    names = {k.split(":")[1] for k in ev.accepted}
    assert "TimerFired" not in names, (
        "TimerFired is a TRIGGER TYPE (state-machines/registry.md), not an emitted event contract. "
        "Counting it would inflate the canonical emitted set."
    )
    sm = (Path(__file__).resolve().parents[2] / "docs" / "specifications" / "state-machines"
          / "registry.md").read_text(encoding="utf-8")
    assert "TimerFired" in sm, "TimerFired vanished from the trigger registry"


def test_no_event_cites_a_producer_transition_outside_the_canonical_set():
    """ERRATA 2 step 8: the registry vs producer-transition mappings."""
    import re
    canonical = manifest.expected_transition_ids()
    registry = (Path(__file__).resolve().parents[2] / "docs" / "specifications" / "events"
                / "registry.md").read_text(encoding="utf-8")

    def expand(producers: str) -> set[str]:
        out, prefix = set(), None
        for tok in re.split(r"[/,\s]+", producers.strip()):
            tok = tok.strip("()")
            m = re.fullmatch(r"([A-Z]{2})-(\d+[a-z]?)", tok)
            if m:
                prefix = m.group(1); out.add(tok); continue
            m2 = re.fullmatch(r"(\d+[a-z]?)", tok)
            if m2 and prefix:
                out.add(f"{prefix}-{m2.group(1)}")
        return out

    cited, checked = set(), 0
    for line in registry.split("\n"):
        m = re.match(r"^\*\*(F\d+)[^:]*:?\*\*(.*)$", line.strip())
        if not m or m.group(1) in ("F14", "F15"):
            continue
        for em in re.finditer(r"`([A-Za-z]+)`\s*‡?\(([^)]*)\)", m.group(2)):
            checked += 1
            cited |= expand(em.group(2))
    assert checked >= 90, f"only {checked} event->producer citations parsed - the probe saw too little"
    orphans = cited - canonical
    assert not orphans, (
        f"event(s) cite producer transition(s) outside the canonical 134: {sorted(orphans)}"
    )


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
    ev = spec_corpus.events()
    ev.require_population(minimum=100)          # a negative assertion needs a proven population
    assert not [k for k in ev.accepted if k.startswith("F15:")]


def test_the_corpus_defects_are_recorded_as_corrected_not_quietly_deleted():
    """DEF-4/DEF-5 are CLOSED by the errata pass - but the record of them must survive.

    A defect that is fixed and then erased teaches nobody. The manifest keeps the finding, states
    how it was closed, and states explicitly that the two corrupting repairs were NOT used.
    """
    defects = {d["id"]: d for d in manifest.load()["expected_current_defects"]}
    for did in ("DEF-4", "DEF-5"):
        d = defects[did]
        assert d["accountable_unit"]
        assert "CORRECTED" in d["status"], f"{did} lost its correction record"
        assert "CLOSED" in d["removed_by_phase"]
        assert "NOT invented" in d["deletion_condition"] or "No events were invented" in d["deletion_condition"]


def test_the_corrected_totals_are_recorded_with_exact_set_digests():
    """Counts are diagnostics; the digest pins the MEMBERS."""
    counts = manifest.spec_counts()
    assert counts["transitions_declared"] == counts["transitions_enumerated"] == 134
    assert counts["emitted_events_declared"] == counts["emitted_events_enumerated"] == 98
    assert counts["transitions_exact_set_digest"]
    assert counts["emitted_events_exact_set_digest"]
