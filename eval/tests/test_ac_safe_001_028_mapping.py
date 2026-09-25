"""AC-SAFE-001..028 — the G4 platform-safety family, mapped to PRESENT, COLLECTED executable oracles.

Authority (not invented here):
  * `docs/specifications/acceptance/platform-safety-acceptance.md` PART A is the SOLE authority for
    the AC-SAFE population — the 28 permanent safety invariants.
  * `release-gates.md` G4 requires 100% (zero-tolerance, no waiver) of `AC-SAFE-001..028`, each mapped
    to a PRESENT executable oracle establishing a non-empty, complete population.
  * `acceptance/registry.md` — THE ORACLE RULE: a passing result rests on an oracle (a DB-state /
    event-stream / negative / external-observation assertion), never on "appears correct".

Why this file exists (the exact gap it closes):
  The frozen P8 phase-acceptance review (`p8-phase-acceptance-review-319debc.md` §4) recorded AC-SAFE
  as "28/28 have oracles", but there was NO STANDING, RE-DERIVABLE proof of the bijection — the R13
  acceptance-gate guard only checks `len(spec ids) == 28`, i.e. that the spec enumerates 28, not that
  each id maps to a real, collected behavioural oracle. The later independent adjudication could
  reproduce every other G4 family (AC-CKPT, AC-RACE, AC-SEC, AC-REC, crash-point, brake/no-autonomy,
  standing mutation) but could not INDEPENDENTLY CLOSE the AC-SAFE present-executable-oracle
  bijection. This module is that closure, and nothing broader.

What it proves MECHANICALLY, on every run (no substring/file-level grep evidence is accepted):
  1. The authoritative id set is DERIVED from the spec (PART A) — the contiguous range AC-SAFE-001..028.
  2. EXACT SET EQUALITY between the spec ids and the mapped ids: no required id is left unmapped, and
     no id is invented beyond the spec.
  3. Every mapped node's FILE and FUNCTION exist (AST), and pytest ACTUALLY COLLECTS that node (a real
     `--collect-only` subprocess) — a renamed / removed / uncollectable oracle fails.
  4. Each mapped node's body carries a distinctive behavioural symbol, checked on THAT FUNCTION'S AST
     source segment (never a file-wide substring) — a node that does not exercise the criterion fails.
A RED control drives every facet of the checker to prove it discriminates (CLAUDE.md §6).

Direction of authority is ONE-WAY: the spec is the machine authority for the population; this file
only reads it. It invents no requirement and changes no product runtime.
"""

from __future__ import annotations

import ast
import functools
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EVAL_TESTS = ROOT / "eval" / "tests"
SPEC = ROOT / "docs" / "specifications" / "acceptance" / "platform-safety-acceptance.md"


def require_population(items, what: str):
    """CLAUDE.md §6: an assertion over an empty set passes vacuously. Prove the population first."""
    assert items, f"no {what} to assert over — this guard would measure nothing"
    return items


# --------------------------------------------------------------------------- the mapping
# id -> [(test_file, test_function, a distinctive symbol that must appear IN THAT FUNCTION'S BODY)].
# Each node is a REAL behavioural oracle whose body exercises the invariant (a DB-state, event-stream,
# or negative assertion). The symbol is characteristic of the criterion, so the mapping cannot point
# at a function that does not exercise it. Every entry was verified present at authoring time AGAINST
# THE COLLECTED TREE; the guard below re-verifies existence, collection, and the symbol on every run.
MAPPING: dict[str, list[tuple[str, str, str]]] = {
    "AC-SAFE-001": [  # no external effect without a CLAIMED grant; ZERO calls; ClaimRefused
        ("test_phase6_external_effect.py",
         "test_two_claims_on_one_grant_leave_exactly_one_CLAIMED", "ClaimRefused"),
        ("test_adapter_boundary_acceptance.py",
         "test_direct_adapter_invocation_without_capability_is_orphan", "OrphanEffectDetected"),
    ],
    "AC-SAFE-002": [  # no external effect without a FRESH witness; StaleWitnessUsed; zero calls
        ("test_phase3_witness.py",
         "test_a_stale_witness_is_refused_at_the_claim_and_recorded", "StaleWitnessUsed"),
    ],
    "AC-SAFE-003": [  # witness+grant bind the same fields; a mismatch is a Sev-0, no call
        ("test_phase6_pipeline_instance.py",
         "test_pl_8_co_commits_the_witness_the_grant_and_this_row", "entity_versions_json"),
        ("test_phase3_claim_cas.py",
         "test_the_confused_deputy_is_refused_with_a_sev0_naming_the_mismatch", "ConfusedDeputyRefused"),
    ],
    "AC-SAFE-004": [  # all seven steps in ONE atomic transaction (txn-boundary probe)
        ("test_phase3_schema.py",
         "test_exactly_one_commit_contains_the_seven_reads_the_witness_and_the_mint", "set_trace_callback"),
    ],
    "AC-SAFE-005": [  # no async work between checkpoint success and the claim
        ("test_phase3_witness.py", "test_the_kernel_contains_no_asynchronous_work", "AsyncFunctionDef"),
    ],
    "AC-SAFE-006": [  # brake before claim => the claim affects ZERO rows; adapter never invoked
        ("test_phase3_claim_cas.py",
         "test_brake_between_mint_and_claim_makes_the_cas_match_zero_rows", "BRAKE_CHANGED"),
        ("test_phase6_external_effect.py",
         "test_a_brake_between_mint_and_claim_makes_the_cas_match_zero_rows", "EffectAttempted"),
    ],
    "AC-SAFE-007": [  # brake after claim does NOT kill the in-flight worker; no manufactured UNKNOWN
        ("test_phase6_brake.py",
         "test_engaging_the_brake_during_an_adapter_call_does_not_create_an_unknown_outcome",
         "UNKNOWN_OUTCOME"),
    ],
    "AC-SAFE-008": [  # material-fact drift voids a stale approval; the £3,100 invoice never issues
        ("test_phase6_approval.py",
         "test_F01_approve_2850_then_tms_moves_to_3100_no_effect_occurs", "VOID_ON_DRIFT"),
    ],
    "AC-SAFE-009": [  # entity-version drift blocks the claim: CheckpointFailed{step:5}
        ("test_phase3_observability.py",
         "test_a_refused_checkpoint_emits_every_step_up_to_and_including_the_failure", "CheckpointFailed"),
    ],
    "AC-SAFE-010": [  # policy-version drift blocks the claim; ApprovalVoided{policy}; CAS zero rows
        ("test_phase3_claim_cas.py",
         "test_policy_version_change_between_mint_and_claim_refuses", "POLICY_CHANGED"),
        ("test_phase6_approval.py", "test_policy_change_voids_inflight_approval", "void_on_policy"),
    ],
    "AC-SAFE-011": [  # an approval authorizes one committed effect; a frozen approval is NOT reusable
        ("test_phase6_approval.py",
         "test_approval_after_unknown_attempt_is_not_reusable", "unknown_outcome_ref"),
    ],
    "AC-SAFE-012": [  # commit key EXCLUDES the amount => two amounts, one identical key, one invoice
        ("test_phase1_commit_key.py",
         "test_01_approved_amount_does_not_affect_the_commit_key", "commit_key"),
        ("test_phase1_commit_key.py",
         "test_06_same_logical_effect_claimed_twice_converges_on_one_reservation", "claim_operation_commit"),
    ],
    "AC-SAFE-013": [  # commit key EXISTS for non-money effects => filing the same POD twice, one attach
        ("test_phase1_commit_key.py",
         "test_04_every_consequential_non_money_effect_has_a_commit_key", "commit_key"),
        ("test_phase1_commit_key.py",
         "test_race_same_non_money_effect_from_two_entry_points", "document_path"),
    ],
    "AC-SAFE-014": [  # two racing attempts at one logical effect => at most one claim
        ("test_phase3_claim_cas.py",
         "test_n_racing_claimers_on_separate_connections_produce_exactly_one_claim", "ALREADY_CLAIMED"),
        ("test_phase6_external_effect.py",
         "test_two_claims_on_one_grant_leave_exactly_one_CLAIMED", "ClaimRefused"),
    ],
    "AC-SAFE-015": [  # MODEL_INFERRED cannot be read by a consequential gate; confidence 1.0 refuses
        ("test_phase7_provenance.py",
         "test_a_model_inferred_fact_cannot_be_read_by_a_consequential_gate", "GateReadOfInferredFact"),
    ],
    "AC-SAFE-016": [  # OWNER_ASSERTED cannot be overwritten by recomputation; byte-identical after
        ("test_phase6_identity_binding_claim.py",
         "test_owner_binding_survives_relinker", "OwnerAssertedOverwrite"),
    ],
    "AC-SAFE-017": [  # an open Conflict blocks dependent consequential actions (checkpoint step 4)
        ("test_phase6_conflict.py", "test_open_conflict_blocks_all_consequential_actions", "run_checkpoint"),
    ],
    "AC-SAFE-018": [  # a counterparty assertion cannot self-authorize; never OWNER_ASSERTED
        ("test_phase6_identity_binding_claim.py",
         "test_counterparty_cannot_become_owner_asserted", "CounterpartySelfAuthorizationDetected"),
    ],
    "AC-SAFE-019": [  # replay creates no witness/grant/adapter call/effect
        ("test_p5_replay_and_audit.py", "test_replaying_the_whole_corpus_mints_nothing", "witnesses_minted"),
    ],
    "AC-SAFE-020": [  # compensation uses the ORDINARY pipeline (its own witness+grant+key)
        ("test_phase6_compensation.py",
         "test_ac_rec_002_compensation_uses_the_ordinary_pipeline", "pipeline_instances"),
    ],
    "AC-SAFE-021": [  # a timeout alone NEVER produces FAILED => UNKNOWN_OUTCOME, no failure_proof
        ("test_phase6_external_effect.py",
         "test_a_timeout_crash_or_lost_response_is_UNKNOWN_never_FAILED", "unknown_reason"),
    ],
    "AC-SAFE-022": [  # UNKNOWN_OUTCOME carries an owner+reason; no timer moves it (illegal)
        ("test_phase6_external_effect.py",
         "test_no_timer_moves_an_UNKNOWN_OUTCOME", "IllegalTransitionAttempted"),
        ("test_phase6_external_effect.py",
         "test_an_ambiguous_outcome_is_UNKNOWN_named_human_and_one_EffectAttempted", "OutcomeUnknown"),
    ],
    "AC-SAFE-023": [  # local persistence cannot verify an external effect; a blind readback stays UNKNOWN
        ("test_phase6_external_effect.py",
         "test_a_blind_readback_is_OBSERVATION_UNAVAILABLE_never_FAILED", "OBSERVATION_UNAVAILABLE"),
        ("test_adapter_boundary_acceptance.py",
         "test_ef4u_blind_readback_is_unavailable_never_verified_failure", "OBSERVATION_UNAVAILABLE"),
    ],
    "AC-SAFE-024": [  # an Exception cannot close without a resolving decision_ref; a bare string fails
        ("test_phase6_exception.py",
         "test_decision_ref_must_resolve_to_a_human_decision_event_or_active_rule", "rule-compiled"),
        ("test_phase6_exception.py", "test_exception_closure_requires_decision_ref", "IllegalTransition"),
    ],
    "AC-SAFE-025": [  # cross-tenant processing rejected before business handling; GLOBAL brake
        ("test_adapter_boundary_acceptance.py",
         "test_ac_adpt_016_cross_tenant_is_contained_and_globally_braked", "platform_status"),
        ("test_phase5_event_transport.py",
         "test_an_event_for_another_tenant_is_rejected_before_the_handler_and_before_any_write",
         "REJECTED_CROSS_TENANT"),
    ],
    "AC-SAFE-026": [  # unauthorized adapter invocation engages the brake (orphan => Sev-0 => auto-brake)
        ("test_adapter_boundary_acceptance.py",
         "test_orphan_detector_is_not_vacuous_and_auto_engages_the_brake", "OrphanAdapterInvocation"),
    ],
    "AC-SAFE-027": [  # automation cannot broaden policy or release a brake (F14 recorded)
        ("test_phase6_policy.py", "test_a_model_cannot_activate_a_policy",
         "UnauthorizedPolicyActivationAttempted"),
        ("test_phase6_brake.py", "test_detector_cannot_release_its_own_brake",
         "UnauthorizedBrakeReleaseAttempted"),
    ],
    "AC-SAFE-028": [  # every open Work Item has exactly ONE accountable human owner
        ("test_phase6_work_item.py", "test_no_transition_leaves_a_work_item_ownerless", "human_authority"),
        ("test_phase6_work_item.py",
         "test_creation_without_a_recorded_owner_fails_and_writes_nothing", "OwnershipRefused"),
    ],
}

# The authoritative population the spec enumerates today (a contiguous 001..028). This is a legibility
# anchor, NOT a second authority: the guard derives the set from the spec and equates it to this range,
# so any spec amendment to the population fails here and must flow through a real remap.
CANONICAL_IDS = {f"AC-SAFE-{n:03d}" for n in range(1, 29)}


# --------------------------------------------------------------------------- spec derivation
def _spec_ac_safe_ids(text: str) -> set[str]:
    """Derive the AC-SAFE id set from the spec text. PART A is the population; every id is written as
    `AC-SAFE-0NN`. Taken as a set (pure), so the control below can feed synthetic text."""
    return set(re.findall(r"AC-SAFE-0\d\d", text))


# --------------------------------------------------------------------------- AST + collection
def _function_body_src(path: Path, func: str) -> str | None:
    """The AST source segment of `func` in `path`, or None if the function is not defined there.
    Scoped to the function, so a symbol match is IN THE BODY — never a file-wide substring."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func:
            return ast.get_source_segment(text, node)
    return None


@functools.lru_cache(maxsize=1)
def _collected_nodes() -> frozenset[tuple[str, str]]:
    """Run pytest `--collect-only` over the union of mapped files and return the set of collected
    (relpath, function) pairs — parametrization suffixes and class prefixes stripped. This is the
    "pytest actually collects the node" proof: nothing here trusts a name or a grep hit."""
    rel = sorted({f"eval/tests/{f}" for nodes in MAPPING.values() for (f, *_rest) in nodes})
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *rel],
        cwd=ROOT, capture_output=True, text=True)
    nodes: set[tuple[str, str]] = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("eval/tests/") and "::" in line:
            path = line.split("::", 1)[0]
            func = line.split("::")[-1].split("[")[0]  # strip [param]; class prefix dropped by [-1]
            nodes.add((path, func))
    _collected_nodes.last_proc = proc  # type: ignore[attr-defined]  # for diagnostics on failure
    return frozenset(nodes)


def _node_defect(fname: str, func: str, symbol: str,
                 collected: frozenset[tuple[str, str]]) -> str | None:
    """None iff the node EXISTS (AST) AND is COLLECTED by pytest AND its body contains `symbol`.
    Otherwise the reason it is not valid evidence. This is the whole force of the mapping."""
    body = _function_body_src(EVAL_TESTS / fname, func)
    if body is None:
        return f"{fname}::{func} does not exist (no such function)"
    if (f"eval/tests/{fname}", func) not in collected:
        return f"{fname}::{func} is not collected by pytest (not a runnable node)"
    if symbol not in body:
        return f"{fname}::{func} does not exercise the criterion (missing {symbol!r} in its body)"
    return None


def _bijection_violations(spec_ids: set[str], mapped_ids: set[str]) -> list[str]:
    """Pure set comparison. Any id in the spec without a mapping, or any mapped id not in the spec,
    is a violation — i.e. exact set equality is required (no unmapped requirement, none invented)."""
    violations: list[str] = []
    for missing in sorted(spec_ids - mapped_ids):
        violations.append(f"spec requires {missing} but it maps to NO executable oracle")
    for invented in sorted(mapped_ids - spec_ids):
        violations.append(f"{invented} is mapped but is NOT in the spec (invented requirement)")
    return violations


# --------------------------------------------------------------------------- the bijection guard
def test_the_ac_safe_population_is_derived_from_the_spec_and_equals_the_mapping_exactly():
    """(1) + (2): derive AC-SAFE-001..028 from the spec, and prove EXACT set equality with the mapped
    ids — no required id unmapped, none invented. The spec is the authority; the mapping must match."""
    spec_ids = require_population(_spec_ac_safe_ids(SPEC.read_text(encoding="utf-8")), "AC-SAFE ids in the spec")
    assert spec_ids == CANONICAL_IDS, (
        "the spec's AC-SAFE population is no longer the contiguous 001..028 this mapping is built "
        f"against — a spec amendment must flow through a remap here. spec-only={sorted(spec_ids - CANONICAL_IDS)} "
        f"expected-only={sorted(CANONICAL_IDS - spec_ids)}")
    mapped_ids = require_population(set(MAPPING), "mapped AC-SAFE ids")
    violations = _bijection_violations(spec_ids, mapped_ids)
    assert not violations, "AC-SAFE bijection is not exact:\n  - " + "\n  - ".join(violations)


def test_every_ac_safe_criterion_maps_to_a_present_collected_oracle_that_exercises_it():
    """(3) + (4): every mapped node exists, is collected by pytest, and its body carries the
    criterion's distinctive symbol. No substring/file-level grep evidence counts — existence is AST,
    runnability is a real `--collect-only`, and the symbol is scoped to the function body."""
    collected = _collected_nodes()
    require_population(collected, "pytest-collected nodes across the mapped files")
    defects: list[str] = []
    checked = 0
    for ac_id, nodes in sorted(MAPPING.items()):
        require_population(nodes, f"{ac_id} oracle nodes")
        for fname, func, symbol in nodes:
            checked += 1
            defect = _node_defect(fname, func, symbol, collected)
            if defect:
                defects.append(f"{ac_id}: {defect}")
    print(f"AC-SAFE mapping: {len(MAPPING)} criteria, {checked} oracle nodes present+collected+exercised")
    assert checked >= len(MAPPING), "fewer oracle nodes than criteria — a hole in the mapping"
    if defects:
        proc = getattr(_collected_nodes, "last_proc", None)
        tail = "\n".join(proc.stderr.splitlines()[-15:]) if proc is not None else ""
        raise AssertionError(
            "AC-SAFE nodes that are absent, uncollectable, or do not exercise the criterion:\n  - "
            + "\n  - ".join(defects) + (f"\n--- collect stderr tail ---\n{tail}" if tail else ""))


def test_the_collection_denominator_is_real_and_nonempty():
    """Anti-vacuity for the collection oracle itself: the subprocess actually collected nodes from the
    mapped files, and a known real node is among them — so `_node_defect`'s collection check is a
    measurement, not a structure that passes when nothing ran."""
    collected = _collected_nodes()
    require_population(collected, "collected nodes")
    assert ("eval/tests/test_phase3_witness.py",
            "test_the_kernel_contains_no_asynchronous_work") in collected, (
        "the collection subprocess did not collect a known real node — the collection check would be vacuous")


# --------------------------------------------------------------------------- ships-dark self-proof
# Product review correction 1 (ships_dark_no_enablement): the generated p8-r3-m11/m12 scenarios
# hypothesised that THIS verifier might wire the M11 policy or M12 rule machine into a production or
# out-of-package reach edge and quietly enable the dark layer. It does not, and these two functions
# make that a STANDING fact. `_own_freight_recon_reach` reproduces the exact reachability notion the
# product-driver scan uses (`from freight_recon.X import ...` / `import freight_recon.X` / a relative
# `from . import X`), applied to THIS module's own AST. The AC-SAFE mapping reads oracles purely by
# AST and by a `--collect-only` subprocess; it imports no product module and binds no gate, so it can
# never appear in "files outside the package that reach policy/rule".
def _own_freight_recon_reach(source: str) -> set[str]:
    """The freight_recon submodules a source statically imports — the product-driver scan's own()."""
    reach: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.module and (node.level or node.module.startswith("freight_recon")):
                reach.add(node.module.split(".")[-1])
            if node.level and not node.module:
                reach.update(a.name for a in node.names)
        if isinstance(node, ast.Import):
            reach.update(a.name.split(".")[-1] for a in node.names if a.name.startswith("freight_recon"))
    return reach


def test_this_verifier_ships_dark_it_reaches_no_production_policy_rule_or_effect():
    """ships_dark_no_enablement for THIS file: the AC-SAFE bijection verifier statically imports no
    product module, so it introduces NO production importer and NO out-of-package reach edge into the
    M11 policy or M12 rule machine (or any freight_recon module). It reads oracles by AST and a
    `--collect-only` subprocess only — it binds no gate, enables no route, and grants no autonomy."""
    reach = _own_freight_recon_reach(Path(__file__).read_text(encoding="utf-8"))
    assert reach == set(), (
        f"the AC-SAFE verifier statically reaches freight_recon module(s) {sorted(reach)} — it must "
        "stay inert (AST + --collect-only only), or it could become a production/out-of-package edge "
        "into a dark machine (ships_dark_no_enablement)")


def test_the_ships_dark_reach_detector_discriminates():
    """RED control: the reach detector actually fires on a real freight_recon import (policy, rule,
    checkpoint) and stays silent on stdlib — so the inertness assertion above is a measurement, not a
    vacuous pass."""
    assert _own_freight_recon_reach("from freight_recon.policy import M11Machine") == {"policy"}
    assert _own_freight_recon_reach("from freight_recon.rule import M12Machine") == {"rule"}
    assert _own_freight_recon_reach("import freight_recon.checkpoint as c") == {"checkpoint"}
    assert _own_freight_recon_reach("from . import rule") == {"rule"}
    assert _own_freight_recon_reach("import ast, subprocess, re") == set()


# --------------------------------------------------------------------------- the RED controls
def test_the_bijection_checker_discriminates():
    """RED control for facets (1)+(2): a missing id and an invented id are each caught, and the exact
    match is accepted (no false positive)."""
    full = set(CANONICAL_IDS)
    # a required id with no mapping
    assert _bijection_violations(full, full - {"AC-SAFE-014"}), "an unmapped required id was not caught"
    # an invented id beyond the spec
    assert _bijection_violations(full, full | {"AC-SAFE-999"}), "an invented id was not caught"
    # exact equality is accepted
    assert _bijection_violations(full, full) == [], "the checker fired on an exact bijection (false positive)"
    # the spec deriver is real: it finds the ids in the spec text and none in unrelated text
    assert "AC-SAFE-001" in _spec_ac_safe_ids(SPEC.read_text(encoding="utf-8"))
    assert _spec_ac_safe_ids("no acceptance ids here") == set()


def test_the_node_checker_discriminates():
    """RED control for facets (3)+(4): a non-existent function, an uncollected (real) function, and a
    real+collected function whose body lacks the symbol are each rejected; a real+collected+exercising
    node is accepted."""
    collected = _collected_nodes()
    real_file = "test_phase3_witness.py"
    real_func = "test_the_kernel_contains_no_asynchronous_work"
    # (a) a function that does not exist
    assert _node_defect(real_file, "test_this_function_does_not_exist_at_all", "x", collected)
    # (b) a real function that is NOT in the collected set (drop it) -> "not collected"
    without = frozenset(collected - {(f"eval/tests/{real_file}", real_func)})
    d = _node_defect(real_file, real_func, "AsyncFunctionDef", without)
    assert d and "not collected" in d, f"an uncollected node was not caught: {d!r}"
    # (c) a real, collected function whose body lacks a foreign symbol
    assert _node_defect(real_file, real_func, "OrphanAdapterInvocation", collected)
    # (d) a real, collected function WITH its symbol is accepted (no false positive)
    assert _node_defect(real_file, real_func, "AsyncFunctionDef", collected) is None


def test_the_guard_itself_goes_red_on_a_broken_mapping(monkeypatch):
    """The 'seen RED' proof (CLAUDE.md §6): reintroduce the forbidden state — a required id mapped to a
    non-existent oracle — SYNTHETICALLY and require THE GUARD ITSELF to raise. Stays valid after the
    real mapping is correct, because it injects the defect rather than relying on one being present."""
    g = sys.modules[__name__]
    broken = {**MAPPING, "AC-SAFE-014": [("test_phase3_claim_cas.py",
                                          "test_a_function_that_is_not_defined_anywhere", "x")]}
    monkeypatch.setattr(g, "MAPPING", broken)
    with pytest.raises(AssertionError, match="do not exercise the criterion|absent|uncollectable"):
        g.test_every_ac_safe_criterion_maps_to_a_present_collected_oracle_that_exercises_it()

    # and the bijection guard raises when a required id is dropped from the mapping entirely
    dropped = {k: v for k, v in MAPPING.items() if k != "AC-SAFE-014"}
    monkeypatch.setattr(g, "MAPPING", dropped)
    with pytest.raises(AssertionError, match="bijection is not exact"):
        g.test_the_ac_safe_population_is_derived_from_the_spec_and_equals_the_mapping_exactly()
