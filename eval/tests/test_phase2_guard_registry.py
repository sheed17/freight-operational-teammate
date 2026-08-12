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
# FIXED-SPECIFICATION: this dict is a CLASSIFICATION RECORD (like the authority map), not a
# discovery population - guard_files() below DISCOVERS the population dynamically and the
# two-way tests force this record to track it: an unclassified discovered file fails, and a
# classified phantom fails.
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
    "test_bootstrap_hermeticity.py": (RETAIN, "clean-clone reproducibility: bootstrap fail-fast, hermetic fixtures, result-backed status, the M-4 exact inventories"),
    "test_false_green_defenses.py": (RETAIN, "the U-HANDOFF-1C defenses: execution-not-attestation, exact node identity, whole-suite skip enforcement, transitive safety ancestry, the anti-enumeration meta-guard"),
    "test_rebaseline_invariants.py": (RETAIN, "the U-REBASELINE-1 invariants: rejected product absolutes cannot return as current authority, the ADR-012..017 commitments survive, no src/ change, R-07 stays open"),
    "test_progress_protocol.py": (RETAIN, "the founder progress protocol: percentages are mechanically derived, BUILD-STATUS cannot be inflated, the finalizer-rejection battery, required references"),
    "test_switch_consistency.py": (RETAIN, "switch consistency: live guidance surfaces (CLAUDE, CURRENT, BUILD-STATUS snapshot, authority map, index, agent files) must agree with the registry after a control transition - a completed unit may never remain the live next-work claim"),
    "test_build_status_receipt_consistency.py": (RETAIN, "N-1: the authored BUILD-STATUS snapshot may not narrate finalizer/clean-clone failure the authoritative receipts contradict, nor claim PASS they do not support - checked both directions"),
    "test_roadmap_completeness_control.py": (RETAIN, "roadmap completeness: the three-field status model (selection/execution/checkpoint) and its consistency, the drift guard forbidding a navigation document from restating a phase state the registry does not hold, the P13 decomposition covering W1-W11 plus H1/O1/M1 with P13 unable to complete while any required sub-unit is incomplete, capability traceability from promise to unit to evidence, and the mechanical full-roadmap completeness equivalence"),
    "test_integration_topology.py": (RETAIN, "R-21 integration topology: no merge commit may sit above a certified content commit, the fast-forward-only procedure rehearsed hermetically every suite, and the obligation kept recorded in the procedure document, the risk register and the progress protocol"),
    # ---- Phase 3: the checkpoint kernel. The two-key rule becomes real. ----
    "test_phase3_fingerprint.py": (RETAIN, "fp_v1 canonical serialization - determinism is the mechanism; false no-drift is a wrong payment"),
    "test_phase3_witness.py": (RETAIN, "the unconstructable, immutable, single-use Checkpoint Witness - every forgery route must mint nothing"),
    "test_phase3_checkpoint_matrix.py": (RETAIN, "THE 105-case merge-gating matrix - 7 steps x 15 conditions on the universal oracle, zero failure tolerance"),
    "test_phase3_claim_cas.py": (RETAIN, "the claim CAS - single-use, race-proven, brake/policy revalidated inside the UPDATE"),
    "test_phase3_brake.py": (RETAIN, "brake admission - the one-way ratchet, no TTL, fail-closed reads"),
    "test_phase3_schema.py": (RETAIN, "checkpoint schema readiness, live-hold index semantics, and the one-transaction atomicity probe"),
    # Added by the P3 findings remediation, closing independent-review findings F-C, F-D and F-F.
    "test_phase3_ledger_compatibility.py": (RETAIN, "F-C: the live-hold index broke the P2 ledger consumers - both reviewer failures reproduced, wrong-row selection and the witness foreign-key error"),
    "test_phase3_step_order.py": (RETAIN, "F-D: the canonical seven-step order under MULTI-FAULT inputs - the 105-case matrix cannot observe order, because one fault means one failing step"),
    "test_phase3_observability.py": (RETAIN, "F-F: the unit's observability contract proven with a REAL observer, including that an observer which fails cannot corrupt checkpoint state"),
    # Added by the P4 F-01 remediation: it reads the deployed entry point, so the central inventory
    # discovers it as a control guard.
    "test_p4_deployed_governed_route.py": (RETAIN, "the deployed entry point's governed-write wiring: the lookup boundary is wired, the callback cannot construct an operation, and the execution kernel seam stays blocked pending adjudication of AC-CKPT-6-missing"),
    # Added by P5 U5.2: it reads TRANSITION-EVENT-AUDIT.yaml and IMPLEMENTATION-REGISTRY.yaml, so
    # the central inventory discovers it as a control guard.
    "test_p5_canonical_event_mint.py": (RETAIN, "the seven MINTED canonical events proven rather than announced: exactly one producer each with no duplicate, zero-owner or overclaimed ownership; payload coverage of every persisted field; AP-9's frozen state reconstructed from POSITIVE emitted evidence and never from an absence; PO-1's PolicyProposed semantics, producer and consumers unchanged by PO-2's mint; no pre-existing contract re-attributed; no new EVENT_REQUIRED obligation introduced; and the recorded program invariants - P4 COMPLETE, R-07 CONTAINED, all fourteen P5 criteria PENDING - untouched"),
    # Added by the R-07 closure REPLACEMENT candidate, closing F-03.
    "test_evidence_binding.py": (RETAIN, "the R-07 evidence chain bound at CONTENT level rather than citation level: every load-bearing report is enumerated FROM the containment record and bound to the IMMUTABLE preserved blob at its refs/preserve ref - recorded digest, sidecar, preservation parent and recorded verdict - with banner-aware body isolation, so the required disarm banner is respected rather than circumvented and a mutable worktree report can never substitute for accepted evidence. Its hostile battery reproduces the ACCEPT-to-REJECT verdict flip that previously left 1957 tests green"),
}

GUARD_PREFIXES = ("test_phase0_", "test_phase1_", "test_u26a_", "test_u26bc_", "test_phase2_",
                  "test_phase3_")
def guard_files() -> list[str]:
    """DISCOVERED, never listed (H-6 closed the last hand-typed remnant, EXTRA_GUARDS): the
    population is phase-prefixed modules UNION every control-guard module the central inventory
    discovers by what it references. A new control guard enters automatically."""
    import sys as _s
    _s.path.insert(0, str(TESTS.parents[1]))
    from control import inventory as _inv
    names = {p.name for p in TESTS.glob("test_*.py") if p.name.startswith(GUARD_PREFIXES)}
    names |= {f.rsplit("/", 1)[-1] for f in _inv.control_guard_modules()}
    assert len(names) >= 20, "guard-file discovery collapsed"
    return sorted(names)


def test_every_guard_file_is_classified():
    found = guard_files()
    assert found, "no guard files discovered - this test would pass over an empty set"
    unclassified = [f for f in found if f not in GUARD_REGISTRY]
    assert not unclassified, f"guard files with no Phase-2 classification: {unclassified}"


def test_the_registry_names_no_file_that_does_not_exist():
    """A registry entry for a deleted file is how a classification outlives its subject.
    Existence is checked on DISK - the registry may classify more files than the dynamic
    discovery floor requires (classification beyond the floor is extra coverage, not a phantom)."""
    phantom = [f for f in GUARD_REGISTRY if not (TESTS / f).exists()]
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
