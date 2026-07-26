#!/usr/bin/env python3
"""Safe in-memory mutation battery for the P4 adapter-containment boundary.

Doctrine (CLAUDE.md sec 9), identical to the P3 batteries:
  * original bytes are held IN MEMORY - never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation, or a same-length restore within one mtime tick
    leaves poisoned bytecode and reports a false green
  * a guard that does NOT fail on the mutant proves nothing and is reported as a MISS
  * restoration is verified byte-for-byte, and the guard must be GREEN again before moving on
  * every case states the REAL defect it reintroduces; a mutation that reintroduces nothing proves
    nothing, so the cases target load-bearing invariants of the boundary, not decoration

WHAT THIS AUDITS: `src/freight_recon/effect_boundary.py` (the containment boundary) and
`eval/phase0/import_probe.py` (the boundary-aware import gate), plus one CREATE mutation that
resurrects a deleted effect path to prove the deletion is guarded, not merely done.

### THIS IS NOT AN INDEPENDENT REVIEW. It was written by the session that implemented P4. A battery
that agrees with its author is evidence, never adjudication - the independent reviewer runs its own.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv/bin/python"
EB = "src/freight_recon/effect_boundary.py"
PROBE = "eval/phase0/import_probe.py"
EP12 = "scripts/enter_tms_payable.py"
BRAIN = "src/freight_recon/brain_runtime.py"
EP8 = "scripts/orient_tms.py"

AC = "eval/tests/test_adapter_boundary_acceptance.py"
GATE = "eval/tests/test_import_gate.py"
HERM = "eval/tests/test_bootstrap_hermeticity.py"
IMPORTS = "eval/tests/test_phase0_adapter_imports.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    """True when the guard PASSES."""
    r = subprocess.run([str(PY), "-m", "pytest", nodeid, "-q", "-p", "no:randomly"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


class SetupFailure(RuntimeError):
    pass


# ---------------------------------------------------------------------------------------------
# TEXT cases: (label, rel_file, old, new, guard_nodeid). The old string must be present exactly
# once (a no-op or an ambiguous anchor is a SETUP-FAIL, never a MISS).
# ---------------------------------------------------------------------------------------------
TEXT_CASES = [
    ("B1  grant validation removed: a refused claim proceeds to touch the world",
     EB,
     "    if not claim.claimed:",
     "    if not claim.claimed and False:  # MUTANT",
     f"{AC}::test_missing_grant_refuses_and_touches_nothing"),

    ("B2  single-use defeated: a consumed capability is accepted a second time",
     EB,
     "    if cap._consumed:",
     "    if cap._consumed and False:  # MUTANT",
     f"{AC}::test_capability_is_single_use"),

    ("B3  tenant guard bypassed: a cross-tenant call is not refused before the claim",
     EB,
     "    if params.tenant.strip().lower() != kernel.store.tenant.strip().lower():",
     "    if False and params.tenant.strip().lower() != kernel.store.tenant.strip().lower():  # MUTANT",
     f"{AC}::test_wrong_tenant_params_are_refused_before_any_claim"),

    ("B4  attempt not recorded before the call: an orphan becomes undetectable",
     EB,
     "    record_effect_attempted(kernel, grant_id=grant_id, params=params)",
     "    pass  # MUTANT: skip the EffectAttempted record",
     f"{AC}::test_valid_claimed_grant_reaches_exactly_one_adapter_call_and_verifies"),

    ("B5  health-signal gate bypassed: a blind readback is no longer OBSERVATION_UNAVAILABLE",
     EB,
     "    if not observation.health_signal:",
     "    if False and not observation.health_signal:  # MUTANT",
     f"{AC}::test_ef4u_blind_readback_is_unavailable_never_verified_failure"),

    ("B6  UNKNOWN downgraded to FAILED (EF-3u): an ambiguous attempt is marked FAILED",
     EB,
     "            kernel, grant_id, to=UNKNOWN_OUTCOME,\n"
     "            unknown_reason=UnknownReason.UNKNOWN_OUTCOME,",
     "            kernel, grant_id, to=FAILED,  # MUTANT\n"
     "            unknown_reason=UnknownReason.UNKNOWN_OUTCOME,",
     f"{AC}::test_ef3u_ambiguous_attempt_is_unknown_never_failed"),

    ("B7  CONFLICTING downgraded to FAILED (EF-4c / AC-ADPT-015)",
     EB,
     "            kernel, grant_id, to=UNKNOWN_OUTCOME,\n"
     "            verification_outcome=VerificationOutcome.OBSERVATION_CONFLICTING,",
     "            kernel, grant_id, to=FAILED,  # MUTANT\n"
     "            verification_outcome=VerificationOutcome.OBSERVATION_CONFLICTING,",
     f"{AC}::test_ef4c_conflicting_readback_is_unknown_not_failed"),

    ("B8  UNKNOWN auto-resolves: the WHO/decision-ref requirement is dropped (EF-5x)",
     EB,
     '    if not str(decision_ref or "").strip() or not str(established_by or "").strip():',
     '    if False and (not str(decision_ref or "").strip() or not str(established_by or "").strip()):  # MUTANT',
     f"{AC}::test_ef5_unknown_resolves_only_by_human_or_proof"),

    ("B9  import gate weakened: a non-boundary effect-adapter import is no longer a violation",
     PROBE,
     "    return _importer_stem(site.module) not in allowed",
     "    return False  # MUTANT: nothing is a violation",
     f"{GATE}::test_a_new_non_boundary_effect_import_is_caught"),

    ("B11 orphan detection disabled: every EffectAttempted is treated as healthy",
     EB,
     '        if grant is not None and grant["state"] in CLAIMED_OR_LATER:',
     '        if True:  # MUTANT: never an orphan',
     f"{AC}::test_orphan_detector_is_not_vacuous_and_auto_engages_the_brake"),

    ("B12 orphan brake disabled: a Sev-0 orphan no longer auto-engages the brake",
     EB,
     "        kernel.brakes.engage(\n"
     "            tenant=kernel.store.tenant, action_class=params.action_class,\n"
     '            actor="orphan-effect-detector"',
     "        kernel.brakes.DISABLED_engage(  # MUTANT\n"
     "            tenant=kernel.store.tenant, action_class=params.action_class,\n"
     '            actor="orphan-effect-detector"',
     f"{AC}::test_orphan_detector_is_not_vacuous_and_auto_engages_the_brake"),

    ("B13 cross-tenant GLOBAL brake disabled: a cross-tenant breach no longer trips the platform brake",
     EB,
     "        kernel.brakes.engage(\n"
     '            tenant=None, actor="cross-tenant-detector"',
     "        kernel.brakes.DISABLED_engage(  # MUTANT\n"
     '            tenant=None, actor="cross-tenant-detector"',
     f"{AC}::test_ac_adpt_016_cross_tenant_is_contained_and_globally_braked"),

    ("B14 adapter constructs authority: a forged capability passes the genuine-registry check",
     EB,
     "    if cap not in _GENUINE_CAPABILITIES:",
     "    if cap not in _GENUINE_CAPABILITIES and False:  # MUTANT",
     f"{AC}::test_forged_capability_is_refused"),

    ("B15 F4: a generic post-attempt exception is laundered into FAILED (no proof of non-occurrence)",
     EB,
     "                kernel, grant_id, to=UNKNOWN_OUTCOME,\n"
     "                unknown_reason=UnknownReason.UNKNOWN_OUTCOME,\n"
     '                payload={"unknown_detail": f"post-attempt adapter exception: "',
     "                kernel, grant_id, to=FAILED,  # MUTANT\n"
     "                unknown_reason=UnknownReason.UNKNOWN_OUTCOME,\n"
     '                payload={"unknown_detail": f"post-attempt adapter exception: "',
     f"{AC}::test_f4_generic_exception_is_never_laundered_into_failed"),

    ("B16 F4: a generic post-attempt exception leaves the grant stuck in CLAIMED (invisible to the sweep)",
     EB,
     "                kernel, grant_id, to=UNKNOWN_OUTCOME,\n"
     "                unknown_reason=UnknownReason.UNKNOWN_OUTCOME,\n"
     '                payload={"unknown_detail": f"post-attempt adapter exception: "',
     '                kernel, grant_id, to="CLAIMED",  # MUTANT: grant never leaves CLAIMED\n'
     "                unknown_reason=UnknownReason.UNKNOWN_OUTCOME,\n"
     '                payload={"unknown_detail": f"post-attempt adapter exception: "',
     f"{AC}::test_f4_generic_post_attempt_exception_leaves_unknown_never_claimed"),

    # B17/B18 anchor on lines WITHOUT a ratcheted deprecated term, so this harness never spreads the
    # frozen mock-ledger vocabulary into scripts/ (the deprecated-vocabulary ratchet counts scripts/*.py).
    ("B17 F1: a quarantine importer regains a live-reaching effect-adapter import (a live bypass mislabelled quarantine)",
     EP12,
     "from freight_recon.cli_tenant import resolve_cli_tenant",
     "from freight_recon.cli_tenant import resolve_cli_tenant\n"
     "from freight_recon.cdp_actuator import CdpActuator  # noqa: E402,F401  # MUTANT: live import",
     f"{GATE}::test_every_quarantine_importer_is_structurally_production_unreachable"),

    ("B18 F1: a quarantine importer constructs a live write driver while still building the mock (substring check would pass)",
     EP12,
     "    charges = []",
     "    charges = []; _live = CdpActuator(None)  # MUTANT: constructs a live write driver",
     f"{GATE}::test_every_quarantine_importer_constructs_the_mock_and_no_live_driver"),

    ("B19 P4: brain_runtime re-imports the effect path (the injection containment is undone)",
     BRAIN,
     "from freight_recon.operator_brain import FlowStep, StepAction, StepResult",
     "from freight_recon.operator_brain import FlowStep, StepAction, StepResult\n"
     "from freight_recon.tms_write import enter_approved_payable  # noqa: F401  # MUTANT: re-import the effect path",
     f"{GATE}::test_brain_runtime_holds_no_effect_capable_import"),

    ("B20 P4: the detective sweep stops running the orphan detector (an orphan goes unbraked)",
     EB,
     "    orphans = detect_orphan_effect_attempts(kernel)\n"
     "    unknowns = pending_unknown_outcomes(kernel)",
     "    orphans = []  # MUTANT: the loop no longer reconciles EffectAttempted records\n"
     "    unknowns = pending_unknown_outcomes(kernel)",
     f"{AC}::test_detective_sweep_finds_orphans_brakes_and_surfaces_unknowns"),

    ("B21 P4: the detective sweep drops the unknown-outcome queue (an UNKNOWN grant goes invisible)",
     EB,
     "    orphans = detect_orphan_effect_attempts(kernel)\n"
     "    unknowns = pending_unknown_outcomes(kernel)",
     "    orphans = detect_orphan_effect_attempts(kernel)\n"
     "    unknowns = []  # MUTANT: unknown outcomes never surface for human resolution",
     f"{AC}::test_detective_sweep_finds_orphans_brakes_and_surfaces_unknowns"),

    # ---- U4.7 / EP-8: the read-only cut must be a mechanism, not a convention ----------------
    # EP-8's original defect was precisely that nothing failed when a "read-only" script held an
    # actuator. These three prove the cut is now load-bearing: re-import the actuator, re-import
    # the mutation-capable session, or smuggle either in dynamically, and a guard fires.

    ("B22 U4.7/EP-8: the read-only orientation tool re-imports the actuator (the exact regression)",
     EP8,
     "from freight_recon.cdp_readonly import ReadOnlyCdpObserver  # noqa: E402",
     "from freight_recon.cdp_actuator import CdpActuator  # noqa: E402,F401  # MUTANT: actuator back\n"
     "from freight_recon.cdp_readonly import ReadOnlyCdpObserver  # noqa: E402",
     f"{IMPORTS}::test_orient_tms_is_structurally_read_only_not_read_only_by_convention"),

    ("B23 U4.7/EP-8: it re-imports the mutation-capable session (F2's evaluate/command primitive)",
     EP8,
     "from freight_recon.cdp_readonly import ReadOnlyCdpObserver  # noqa: E402",
     "from freight_recon.cdp_readonly import ReadOnlyCdpObserver  # noqa: E402\n"
     "from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402,F401  # MUTANT: session back",
     f"{IMPORTS}::test_orient_tms_is_structurally_read_only_not_read_only_by_convention"),

    ("B24 U4.7/EP-8: the actuator is smuggled in dynamically rather than by a static import",
     EP8,
     "    kb = KnowledgeBase(",
     "    __import__('freight_recon.cdp_actuator')  # MUTANT: dynamic actuator acquisition\n"
     "    kb = KnowledgeBase(",
     f"{IMPORTS}::test_orient_tms_is_structurally_read_only_not_read_only_by_convention"),
]

# ---------------------------------------------------------------------------------------------
# CREATE case: resurrect a physically-deleted effect path. The clean state is the file ABSENT;
# the mutant is the file PRESENT with an effect-capable import. This proves the deletion is
# GUARDED (the effect-path inventory's on-disk-absence proof fires), not merely performed.
# ---------------------------------------------------------------------------------------------
RESURRECT_PATH = "scripts/run_operate_request.py"
RESURRECT_BODY = (
    '"""MUTANT: a deleted effect path resurrected to prove the deletion is guarded."""\n'
    "from freight_recon import cdp_actuator  # noqa: F401\n"
)
RESURRECT_GUARD = f"{HERM}::test_the_effect_path_inventory_is_exact_and_fully_classified"
RESURRECT_LABEL = "B10 deleted path resurrected: EP-9 comes back and the on-disk-absence proof must fire"


def _run_text_case(case) -> tuple[str, str]:
    _label, rel, old, new, guard = case
    path = ROOT / rel
    original = path.read_bytes()
    text = original.decode("utf-8")

    purge_pycache()
    if not run_guard(guard):
        return "SETUP-FAIL", "guard already RED before mutation"
    n = text.count(old)
    if n == 0:
        return "SETUP-FAIL", f"anchor not found: {old[:50]!r}"
    if n > 1:
        return "SETUP-FAIL", f"anchor is ambiguous ({n} matches): {old[:50]!r}"
    mutated = text.replace(old, new, 1)
    if mutated == text:
        return "SETUP-FAIL", "mutation was a no-op"

    try:
        path.write_text(mutated, encoding="utf-8")
        purge_pycache()
        caught = not run_guard(guard)
    finally:
        path.write_bytes(original)
        purge_pycache()
    if path.read_bytes() != original:
        return "RESTORE-RED", f"byte-for-byte restore FAILED for {rel}"
    if not run_guard(guard):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def _run_resurrect_case() -> tuple[str, str]:
    path = ROOT / RESURRECT_PATH
    if path.exists():
        return "SETUP-FAIL", f"{RESURRECT_PATH} already exists - the deletion never happened"
    purge_pycache()
    if not run_guard(RESURRECT_GUARD):
        return "SETUP-FAIL", "guard already RED before mutation"
    try:
        path.write_text(RESURRECT_BODY, encoding="utf-8")
        purge_pycache()
        caught = not run_guard(RESURRECT_GUARD)
    finally:
        if path.exists():
            path.unlink()
        purge_pycache()
    if path.exists():
        return "RESTORE-RED", f"{RESURRECT_PATH} was not removed after the mutation"
    if not run_guard(RESURRECT_GUARD):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def main() -> int:
    results = []
    for case in TEXT_CASES:
        verdict, note = _run_text_case(case)
        results.append((case[0], verdict, note))
    v, n = _run_resurrect_case()
    results.append((RESURRECT_LABEL, v, n))

    print("\n=========== P4 BOUNDARY MUTATION BATTERY ===========")
    for label, verdict, note in sorted(results, key=lambda r: r[0]):
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented P4 - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
