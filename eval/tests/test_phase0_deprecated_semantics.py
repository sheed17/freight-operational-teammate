"""U0.11 - the deprecated-semantics baseline.

Phase 0 RECORDS these and prevents NEW ones. It renames nothing: names follow behaviour, and each
rename is the last commit of the phase that made the name true (migration plan, Part 5). Renaming
`lane` across 310 sites into concepts that do not exist yet would be one guess made 310 times, and
would produce the worst artifact available - code that reads canonical and behaves legacy.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import deprecated_probe, manifest


def test_the_probe_evaluates_a_real_population():
    _, ev = deprecated_probe.occurrences(include_tests=True)
    ev.require_population(minimum=100)


def test_deprecated_usage_never_grows():
    """REG-4. Counts may only DECREASE. This is the whole guard."""
    recomputed = deprecated_probe.counts(include_tests=True)
    baseline = manifest.deprecated_counts()
    grown = {t: (recomputed[t], baseline[t]) for t in baseline if recomputed.get(t, 0) > baseline[t]}
    assert not grown, (
        "Deprecated terminology GREW:\n  " +
        "\n  ".join(f"{t}: {now} now vs {was} at baseline" for t, (now, was) in grown.items()) +
        "\n\nNew uses of a deprecated term are prohibited (REG-4). The canonical replacement and its "
        "phase are in the baseline manifest."
    )


def test_a_decrease_requires_the_manifest_to_be_updated():
    """A count that fell means a rename landed. The manifest must record it, so the list shrinks."""
    recomputed = deprecated_probe.counts(include_tests=True)
    baseline = manifest.deprecated_counts()
    shrunk = {t: (recomputed[t], baseline[t]) for t in baseline if recomputed.get(t, 0) < baseline[t]}
    assert not shrunk, (
        "Deprecated usage DROPPED below the baseline:\n  " +
        "\n  ".join(f"{t}: {now} now vs {was} at baseline" for t, (now, was) in shrunk.items()) +
        "\n\nThis is good news - update the baseline manifest to the new count so the ratchet holds."
    )


def test_every_deprecated_term_has_a_replacement_a_phase_and_an_owner():
    """No allowance justified only as 'legacy'."""
    for term in manifest.load()["expected_deprecated_terms"]["terms"]:
        assert term.get("canonical"), f"{term['term']}: no canonical replacement named"
        assert term.get("removed_by_phase"), f"{term['term']}: no removal phase"
        assert term.get("accountable_unit"), f"{term['term']}: no accountable unit"


def test_lane_is_recorded_as_the_largest_and_last_rename():
    """`lane` means action class AND workflow AND policy scope. It is deliberately migrated last."""
    lane = next(t for t in manifest.load()["expected_deprecated_terms"]["terms"] if t["term"] == "lane")
    assert lane["removed_by_phase"] == "P8"
    assert lane["accountable_unit"] == "U8.5"
    assert lane["count"] == deprecated_probe.counts(include_tests=True)["lane"]
