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
    # Added by P5 U5.3: it reads the specification corpus and the event_contracts source, so the
    # central inventory discovers it as a control guard.
    "test_p5_event_contracts.py": (RETAIN, "U5.3's contract layer held to the RUNTIME rather than to the registries: the 118 canonical contracts - 105 machine-emitted (F1-F13) plus 13 audit/security (F14) - DERIVED from events/registry.md sec 3/5/8 and the F1-F14 family files rather than transcribed, with the derivation re-run every build so a specification edit without a regeneration fails rather than silently serving stale contracts. Identity, producer-transition attribution, aggregate binding, version support, payload contract, sec-5 decision-context pins and actor authority (ER-9/10/11/12) are each refused before a fact can be committed or consumed, and sec 6's asymmetry is preserved exactly - a PRODUCER refuses an undeclared payload field, a CONSUMER ignores one. The seven-step transport round trip runs EXHAUSTIVELY over all 118 contracts, and the contract gate sits inside the emitting transaction so a non-canonical fact takes its state change down with it. Section 1b is an INDEPENDENTLY WRITTEN oracle - fixed values, enums, list fields, one-of groups with their required flags, aggregate types and value shapes, hand-transcribed from the markdown - because every other fixture in the battery derives from the generated data and the anti-drift node compares the generator's output to its own, so neither can see a PARSER bug. Five of this unit's nine blocking defects were the validator inventing a rule STRICTER than the specification and refusing events the corpus declares legal; that class is what this file exists to keep closed"),
    # Added by P5 U5.4+U5.5+U5.6: it reads the replay/audit module sources to prove their import
    # CLOSURE reaches nothing effect-capable, so the central inventory discovers it as a control guard.
    "test_p5_replay_and_audit.py": (RETAIN, "reconstruction held to the property that makes it "
     "safe: M-27 requires replay to be side-effect free STRUCTURALLY, so the load-bearing node "
     "asserts the IMPORT CLOSURE of event_replay + event_audit reaches no adapter, no effect "
     "boundary, no checkpoint kernel, no brake store, no WorkflowStore and no network client - "
     "across EVERY import spelling Python offers, because an earlier version tested node.level and "
     "so saw only relative from-imports while this package carries 26 absolute ones, leaving the "
     "registry's mandated 'replay must be proven unable to call an adapter' proven against one "
     "spelling in four. The rebuild is a pure function of the SET of events (ordered by sec 8's "
     "key, tie-broken by event_id, shuffled five ways in the suite); a redelivered fact folds once "
     "and two DIFFERENT bodies under one event_id are refused rather than silently first-won; "
     "GC-1's pinned rebuild digest is the AC-EVT-008 oracle and re-pinning is an explicit human "
     "act; replay writes to no durable surface, asserted by row counts across six canonical tables; "
     "and explain() reads events ONLY - no store, no connection - which is the mechanism behind "
     "AC-AUD-002's beliefs-of-that-day rather than a promise about it, with the causal chain "
     "walking ancestors as well as descendants so an effect's checkpoint, approval and accountable "
     "owner are reconstructed rather than reported absent"),
    # Added by P5's timer/PostgreSQL unit: it cites CLAUDE.md's sweep prohibition and reads every
    # module's SQL to enforce it, so the central inventory discovers it as a control guard.
    "test_p5_durable_timers.py": (RETAIN, "M-36 held STRUCTURALLY rather than by convention: a "
     "timeout must be a durable timer emitting TimerFired, never a background sweep, and "
     "test_no_component_scans_for_staleness parses every module's SQL literals to prove no "
     "component infers age by scanning. That node exists in its current form because an earlier "
     "version was shaped until it went GREEN rather than until it DETECTED - it passed nine of ten "
     "genuine sweeps injected as positive controls, and carved its exemption around a real one, so "
     "it now normalises whitespace, inspects UPDATE and DELETE rather than SELECT alone, "
     "distinguishes a SCHEDULE the component owns from a DEADLINE column another mechanism wrote "
     "(pending_references.expires_at is M-26's prescribed park, not a sweep), and holds "
     "checkpoint.py:expire_unclaimed in an EXACT-SET exemption so a second sweep or this one moving "
     "file is a failure rather than a silent inheritance. The battery also fixes the boundary that "
     "makes GR-6 enforceable - TimerFired is a TRIGGER and not one of the 105, asserted by PARSING "
     "the module's imports rather than substring-matching them, because the substring form missed "
     "'from .x import y', the spelling every module here uses - and holds the lease to the only "
     "arrangement that tests it, a second relay running from inside the first one's handler while "
     "the lease is held and the row is still SCHEDULED, since running them SEQUENTIALLY passed with "
     "the leasing mechanism deleted entirely. A cancelled timer reports SUPERSEDED and never fired, "
     "because history saying CANCELLED while the relay said fired answers 'did this ever go "
     "overdue?' with NO for a machine already told it did"),
    # Added by P5 U5.7+U5.8: it reads the transport module sources to prove they import no adapter or
    # network client, so the central inventory discovers it as a control guard.
    "test_phase5_event_transport.py": (RETAIN, "P5's first runtime capability held to its durability contract: a state change and the events it emits commit atomically or not at all - emit REFUSES to run outside an open transaction and no autocommit escape parameter exists - a relay publishes at-least-once under lease exclusivity, and consumption is idempotent on (tenant, consumer_id, event_id) so a redelivery is a no-op rather than a second effect. Strict per-aggregate ordering is enforced by a trigger asserting that no two DIFFERENT producer transitions own one version, which admits EF-2's legitimate GrantClaimed + EffectAttempted co-emission that a UNIQUE index would have made uninsertable; cross-tenant events are refused before the handler and before any write; and production stays dark - no default sink, no adapter or network import, zero witnesses and zero grants"),
    # Added by P6-U1: it reads the machine and registry SPECIFICATIONS to prove the implementation's
    # transition table is a bijection with sec 14, and it reads the package and scripts/ sources to
    # prove M1 has no production caller - so the central inventory discovers it as a control guard.
    #
    # ### THIS ENTRY IS THE FIX FOR A FALSE GREEN THIS UNIT ACTUALLY PRODUCED, and it is the SAME
    # false green P5's independent review rejected a candidate for. `guard_files()` discovers control
    # guards through the central inventory, which reads `git ls-files` - so while this module was
    # untracked the whole suite ran GREEN and the classification guard could not see it. It went red
    # the moment the file was committed, and the finalizer refused before writing any status. The
    # lesson is recorded here rather than only in a report: a suite run against an untracked new
    # guard module is not evidence about the commit that tracks it.
    "test_phase6_work_item.py": (RETAIN, "P6's first entity capability held to the claim it makes: that accountable human ownership is STRUCTURAL rather than documented. It asserts AC-MACH-000's bijection between the implementation's declarative transition table and the fourteen rows of state-machines/01-work-item.machine.md sec 14 by EXACT SET EQUALITY of transition identifiers, with a positive control performing a same-count substitution so the oracle is demonstrated to be a set comparison and not a count; it drives the exhaustive (state x trigger) sweep over a PROVEN population of 91 pairs, 27 legal and 64 illegal, and requires every illegal pair to persist nothing while recording IllegalTransitionAttempted to the audit backbone AND security_events; it refuses every shape of ownerless or unrecorded owner at the API and again at the database, refuses a model actor on every transition, refuses closure on a decision_ref that does not RESOLVE to an authenticated human decision, and proves reopening leaves the prior closure event byte-identical; and it proves the capability ships dark by import closure over every import spelling, by an AST scan requiring zero production importers, and by measured zero witnesses and zero grants across all seven reachable states"),
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
