"""U0.10 - the live-effect entry-point guard.

Records every effect-capable entry point and fails when a new one appears, when a read-only module
gains an actuator, or when an effect path hides behind a wrapper.

THIS IS NOT CONTAINMENT. The six production-reachable live-write paths remain physically capable of
ungated effects until Phase 4 deletes or converts them (R-07, PL-18). Nothing in this file may be
read as making them safe. Phase 0 buys visibility, not safety.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import entrypoint_probe, manifest


def test_the_probe_evaluates_every_script():
    eps, ev = entrypoint_probe.entry_points()
    ev.require_population(minimum=40)


def test_effect_capable_entry_points_match_the_manifest():
    """REG-3. A new effect-capable entry point must be classified, deliberately, by a human."""
    found = {e.script for e in entrypoint_probe.effect_capable_entry_points()}
    known = manifest.effect_capable_scripts()
    new = found - known
    stale = known - found
    assert not new, (
        f"NEW effect-capable entry point(s) with no classification: {sorted(new)}\n"
        f"Classify them in the baseline manifest (ep, cutover) before merging."
    )
    assert not stale, (
        f"Manifest lists effect-capable entry point(s) that no longer exist: {sorted(stale)}\n"
        f"If Phase 4 removed them, remove them from the manifest too."
    )


def test_r07_exposure_is_recorded_as_open_and_uncontained():
    """PL-18 may not be falsely closed. The manifest must SAY the paths are not contained."""
    legacy = manifest.load()["expected_legacy_paths"]
    assert legacy["risk_id"] == "R-07"
    assert "NOT CONTAINED" in legacy["status"]
    assert "NONE" in legacy["containment_mechanism"]
    assert legacy["removed_by_phase"] == "P4"


def test_every_reference_to_an_effect_capable_script_is_classified():
    """The import graph cannot see a subprocess launch. EP-2 is effect-capable only by spawn."""
    refs = entrypoint_probe.references_to_effect_capable()
    classified = manifest.classified_references()
    unclassified = set(refs) - set(classified)
    assert not unclassified, (
        f"Script(s) referencing an effect-capable script with no classification: {sorted(unclassified)}\n"
        f"Adjudicate each as SPAWNS or DOCUMENTS in the manifest."
    )
    for script, kind in classified.items():
        assert kind in ("SPAWNS", "DOCUMENTS"), f"{script}: unknown classification {kind!r}"


def test_the_supervisor_is_recorded_as_effect_capable_by_spawn():
    """EP-2 imports no adapter. An import-only guard would call it harmless."""
    assert manifest.classified_references()["scripts/run_teammate.py"] == "SPAWNS"


def test_a_runbook_string_is_not_a_spawn():
    """The negative control: run_sunday_readiness PRINTS the command; it launches nothing.

    A first version of this probe guessed SPAWNS here and was wrong. A guard that cries wolf gets
    ignored, and an ignored guard is not a guard.
    """
    assert manifest.classified_references()["scripts/run_sunday_readiness.py"] == "DOCUMENTS"
    source = (Path(__file__).resolve().parents[2] / "scripts" / "run_sunday_readiness.py").read_text()
    assert "_runbook" in source


def test_the_unlisted_read_path_is_recorded():
    """P0-F4: read_tms_browser_use.py is effect-capable by import and absent from EP-1..EP-13."""
    entry = next(
        e for e in manifest.load()["expected_legacy_paths"]["effect_capable_by_import"]
        if e["script"] == "scripts/read_tms_browser_use.py"
    )
    assert entry["ep"] == "UNLISTED"
    assert entry["cutover"] == "CLASSIFY"
