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
    """REPLACED at the R-07 CLOSURE CONTENT COMMIT (CLAUDE.md sec 5 rule 20 - the function NAME is
    kept under its original name so its node identity is stable; the body is re-pointed).

    PL-18 may not be falsely closed - and it may not be falsely left open either. The original body
    asserted `NOT CONTAINED` in the status and `NONE` in the mechanism, which was the truth from P0
    through the second P4 finalization. R-07 is now recorded CONTAINED by the separate content
    commit repository authority reserved for exactly that act, so those two literals became false
    and could only be deleted or re-pointed. Re-pointed, and made stronger in the same move: the
    record must now name a REAL structural mechanism, and this file's own subject - the
    effect-capable-BY-IMPORT entry-point set - must be exactly the recorded, mock-guarded,
    test-only quarantine. A PRODUCTION entry point reappearing there fails here even while the
    status still reads CONTAINED. The full close conditions live in test_phase0_baseline_manifest.py
    ::test_r07_containment_record_holds_only_while_its_mechanical_conditions_hold.
    """
    legacy = manifest.load()["expected_legacy_paths"]
    assert legacy["risk_id"] == "R-07"
    assert legacy["status"] == "CONTAINED"
    assert legacy["removed_by_phase"] == "P4"
    mech = legacy["containment_mechanism"]
    assert not mech.strip().startswith("NONE"), (
        "the containment mechanism still opens with NONE while the status claims CONTAINED"
    )
    assert "STRUCTURAL" in mech and "effect_boundary" in mech, (
        "R-07 is recorded CONTAINED without naming the structural mechanism that contains it"
    )
    # the exposure itself: only the recorded, mock-guarded quarantine importers may remain
    remaining = {e["script"] for e in legacy["effect_capable_by_import"]}
    assert remaining == {"scripts/enter_tms_payable.py", "scripts/run_dogfood_pilot.py"}, (
        f"the effect-capable-by-import set drifted from the recorded quarantine: {sorted(remaining)}"
    )
    for entry in legacy["effect_capable_by_import"]:
        assert "test-only" in entry["cutover"], (
            f"{entry['script']} is effect-capable by import and is NOT test-only - R-07 cannot be "
            "recorded CONTAINED while a production entry point is effect-capable by import"
        )


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


def test_the_formerly_unlisted_read_path_is_now_adjudicated_ep14():
    """P0-F4, CLOSED by U-HANDOFF-1B. This test used to assert the path was UNLISTED/CLASSIFY -
    it marked the open finding, and it correctly failed the moment the adjudication landed.
    REPLACED (not deleted) with the post-adjudication truth: EP-14, read-by-convention,
    MAKE_READ_ONLY at P4, still inside the R-07 containment scope. The exact adjudication lives
    in docs/implementation/EFFECT-PATH-INVENTORY.yaml and is exact-set guarded there."""
    paths = manifest.load()["expected_legacy_paths"]
    # P4/U4.10 CONTAINED it, so it is no longer effect-capable by import and no longer belongs in
    # that list - `entrypoint_probe` would disagree with a manifest that still claimed it was. The
    # adjudication and closure record MOVED to the contained list rather than being deleted: a
    # finding whose closure record vanishes when the finding is fixed is one nobody can audit.
    assert not any(e["script"] == "scripts/read_tms_browser_use.py"
                   for e in paths["effect_capable_by_import"]), (
        "EP-14 is contained but the manifest still lists it as effect-capable by import"
    )
    entry = next(
        e for e in paths["contained_formerly_effect_capable_by_import"]
        if e["script"] == "scripts/read_tms_browser_use.py"
    )
    assert entry["ep"] == "EP-14", "the P0-F4 adjudication was reverted without a decision"
    assert "MAKE_READ_ONLY" in entry["cutover"], "EP-14 lost its read-only containment disposition"
    assert "P0-F4 CLOSED" in entry.get("note", ""), "the closure record left the manifest"
    assert "U4.10" in entry.get("contained_at", ""), "the containment is unattributed"
