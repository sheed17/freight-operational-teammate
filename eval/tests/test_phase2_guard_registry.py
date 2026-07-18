"""The Phase-2 guard registry: every guard file classified, and the classification kept honest.

Blocker 6 requires every Phase-0, Phase-1, U2.6A and U2.6BC guard to be classified RETAIN, UPDATE,
REPLACE or REMOVE_AS_SUPERSEDED. A classification written into a document decays the moment someone
adds a file; this registry is executable, so a guard file that nobody classified fails the suite.

REMOVE_AS_SUPERSEDED is used with deliberate reluctance. A guard that is merely *also* covered
elsewhere is still evidence, and deleting it trades a proven assertion for a claim that some other
test would have caught it. Nothing in Phase 2 is classified REMOVE_AS_SUPERSEDED: the two guards
that marked intermediate states were REPLACED in place - the assertion changed, the file and its
history stayed - because deleting the test that recorded "the boundary is bound but not scoped"
would erase the record that it ever was.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent

RETAIN = "RETAIN"
UPDATE = "UPDATE"
REPLACE = "REPLACE"
REMOVE_AS_SUPERSEDED = "REMOVE_AS_SUPERSEDED"
VALID = {RETAIN, UPDATE, REPLACE, REMOVE_AS_SUPERSEDED}

# file -> (classification, why)
GUARD_REGISTRY: dict[str, tuple[str, str]] = {
    # ---- Phase 0: the baseline. Still the only record of what was true before the reset. ----
    "test_phase0_acceptance_bijection.py": (RETAIN, "the acceptance-criterion bijection is phase-independent"),
    "test_phase0_adapter_imports.py": (RETAIN, "31 direct adapter import edges - Phase-4 containment, still open"),
    "test_phase0_baseline_manifest.py": (UPDATE, "DEF-6 closed and the tenant-first table list emptied; R-07 untouched"),
    "test_phase0_deprecated_semantics.py": (UPDATE, "deprecated counts re-adjudicated for the Phase-2 modules that legitimately name the tables they guard"),
    "test_phase0_entry_points.py": (RETAIN, "the entry-point inventory is unchanged: Phase 2 added no new process entry point"),
    "test_phase0_errata_guards.py": (UPDATE, "intermediate tenant assertions replaced with post-migration truth"),
    "test_phase0_evaluation_contract.py": (RETAIN, "the evaluation contract is orthogonal to tenancy and Phase 2 touched none of it"),
    "test_phase0_guard_integrity.py": (RETAIN, "the guard that stops guards being skipped - load-bearing for every phase"),
    "test_phase0_identifiers.py": (RETAIN, "the identifier inventory is unchanged: no deprecated symbol was renamed in Phase 2"),
    "test_phase0_migration_guards.py": (RETAIN, "AC-SAFE-012/013 merge gating - GREEN and still the merge oracle"),
    "test_phase0_null_gate.py": (RETAIN, "the null gate is a permanent anti-false-green guard"),
    "test_phase0_planning_graph.py": (RETAIN, "the planning graph describes the spec corpus, which Phase 2 implemented rather than altered"),
    "test_phase0_tenant_posture.py": (REPLACE, "asserted the PRE-migration posture; now asserts the migrated posture on the same probes"),
    # ---- Phase 1: the Commit Key. Forward-only; these may never be weakened. ----
    "test_phase1_commit_key.py": (RETAIN, "the amount-out-of-the-key correction - forward-only, never relaxed"),
    "test_phase1_occurrence_identity.py": (RETAIN, "canonical occurrence identity; closes the free-form escape hatch"),
    "test_phase1_structural_guards.py": (RETAIN, "structural guards over the Commit Key surface"),
    # ---- U2.6A: the construction boundary. ----
    "test_u26a_tenant_construction.py": (REPLACE, "two markers of the 'bound but not scoped' intermediate state now assert the completed boundary"),
    # ---- U2.6BC: the six blockers. ----
    "test_u26bc_migration_tenant_validation.py": (RETAIN, "Blocker 1 - canonical tenant validation at the migration boundary"),
    "test_u26bc_owner_assertion.py": (RETAIN, "Blocker 2 - auditable ownership; append-only, never inferred"),
    "test_u26bc_schema_readiness.py": (RETAIN, "Blocker 3 - the one readiness oracle"),
    "test_u26bc_tenant_scope.py": (RETAIN, "Blocker 4 - exact tenant-scoped application qualification"),
    "test_u26bc_migration_matrix.py": (RETAIN, "Blocker 5 - the outcome matrix and cutover"),
    # ---- Phase-2 final: added by Blocker 6. ----
    "test_ac_sec_001_registry.py": (RETAIN, "AC-SEC-001 reconstructed from the frozen acceptance spec, not from the implementation"),
    "test_phase2_integrated_acceptance.py": (RETAIN, "the one integrated entry point: real SQLite, real threads, 20 schedules"),
    "test_phase2_guard_registry.py": (RETAIN, "this registry, which fails when a guard file is added and left unclassified"),
    "test_docs_control_system.py": (RETAIN, "the documentation control system guards - product identity, status, registries, findings"),
    "test_status_reality.py": (RETAIN, "the status-reality guard - CURRENT.md must match the checked-out commit, tree and live test population"),
    "test_tool_access_policy.py": (RETAIN, "the tool-access policy guards - breadth cannot be restricted, authority cannot be widened"),
}

GUARD_PREFIXES = ("test_phase0_", "test_phase1_", "test_u26a_", "test_u26bc_", "test_phase2_")
EXTRA_GUARDS = ("test_ac_sec_001_registry.py", "test_docs_control_system.py",
                "test_status_reality.py", "test_tool_access_policy.py")


def guard_files() -> list[str]:
    """DISCOVERED, never listed. Three times in this program a guard enumerated the filenames it
    knew about and silently stopped covering the files added after it was written."""
    return sorted(
        p.name
        for p in TESTS.glob("test_*.py")
        if p.name.startswith(GUARD_PREFIXES) or p.name in EXTRA_GUARDS
    )


def test_every_guard_file_is_classified():
    found = guard_files()
    assert found, "no guard files discovered - this test would pass over an empty set"
    unclassified = [f for f in found if f not in GUARD_REGISTRY]
    assert not unclassified, f"guard files with no Phase-2 classification: {unclassified}"


def test_the_registry_names_no_file_that_does_not_exist():
    """A registry entry for a deleted file is how a classification outlives its subject."""
    found = set(guard_files())
    phantom = [f for f in GUARD_REGISTRY if f not in found]
    assert not phantom, f"registry entries with no file: {phantom}"


def test_every_classification_is_valid_and_justified():
    for name, (cls, why) in GUARD_REGISTRY.items():
        assert cls in VALID, f"{name}: {cls!r} is not a classification"
        assert len(why.split()) >= 5, f"{name}: {why!r} does not say WHY"


def test_nothing_was_removed_as_superseded_without_a_replacement_named():
    """If anything is ever classified REMOVE_AS_SUPERSEDED, the guard that supersedes it must be
    named in the justification and must itself exist. Coverage asserted rather than demonstrated is
    how a deleted test becomes a hole nobody notices."""
    removed = {n: w for n, (c, w) in GUARD_REGISTRY.items() if c == REMOVE_AS_SUPERSEDED}
    for name, why in removed.items():
        named = [f for f in guard_files() if f in why]
        assert named, f"{name} was removed as superseded but names no surviving guard: {why!r}"


def test_the_forward_only_phase_1_guards_are_never_downgraded():
    """Phase 1 is forward-only: once the amount left the Commit Key, no later phase may reclassify
    those guards as superseded and drop them. This is the defect that raised two invoices."""
    for name, (cls, _) in GUARD_REGISTRY.items():
        if name.startswith("test_phase1_"):
            assert cls == RETAIN, f"{name} is {cls} - Phase-1 guards are forward-only"


def test_r07_is_never_reclassified_away():
    """R-07 must remain OPEN - NOT CONTAINED. The guard that records it may not be dropped."""
    cls, _ = GUARD_REGISTRY["test_phase0_baseline_manifest.py"]
    assert cls in {RETAIN, UPDATE}, f"the R-07 record is classified {cls}"


def test_no_guard_in_the_registry_is_skipped_or_xfailed():
    """Structural, by AST over each guard file.

    This originally only failed when EVERY test in a file was disabled - so skipping one
    load-bearing guard (the R-07 check, say) passed. Mutation caught it. Any disabled guard now
    fails: silence is not a pass.
    """
    offenders = []
    for name in guard_files():
        tree = ast.parse((TESTS / name).read_text(encoding="utf-8"))
        tests = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        if not tests:
            continue
        skipped = [
            n for n in tests
            if any("mark.skip" in ast.unparse(d) or "mark.xfail" in ast.unparse(d) for d in n.decorator_list)
        ]
        offenders.extend(f"{name}::{n.name}" for n in skipped)
    assert not offenders, f"disabled guard(s) - silence is not a pass: {offenders}"
