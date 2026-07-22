#!/usr/bin/env python3
"""Safe in-memory mutation harness for the P3 batteries — GUARDS and KERNEL.

Doctrine (CLAUDE.md sec 9):
  * original bytes are held IN MEMORY - never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation, or a same-length restore within one mtime
    tick leaves poisoned bytecode and reports a false green
  * a guard that does not FAIL on the mutant proves nothing, and is reported as a MISS
  * restoration is verified byte-for-byte before moving on
  * a mutation that does not reintroduce the REAL defect proves nothing either, so every case
    below states which defect it reintroduces

TWO BATTERIES, and the difference matters when reading the result:

  GUARD battery (M1-M8, from the P3 implementation session). It mutates the things the guards
  read - manifests, control documents, the surface registry - and proves the GUARDS fire. It
  proves nothing about the kernel.

  KERNEL battery (K1-K11, added by the P3 findings remediation, closing independent-review
  findings F-D and F-A). It mutates `checkpoint.py`, `workflow.py`, the P3 migration and the
  recorded rebaseline anchor - the load-bearing runtime - and proves a TEST fails for each.
  K1 is the finding's named case: swap checkpoint steps 6 and 7.

### NEITHER BATTERY IS AN INDEPENDENT REVIEW. Both were written by sessions inside the work they
audit. The independent reviewer ran its own kernel mutations and RETURNED FINDINGS; a battery
that agrees with its author is evidence, never adjudication.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv/bin/python"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    """True when the guard PASSES."""
    r = subprocess.run([str(PY), "-m", "pytest", nodeid, "-q", "-p", "no:randomly"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# ------------------------------------------------------------------ programmatic mutators
#
# A textual find/replace cannot express "swap two blocks", and writing the swap out as a literal
# would silently stop applying the moment either block is edited. These mutators locate their
# targets by the canonical section markers instead, and assert that they actually changed
# something - a mutator that no-ops is reported as a SETUP-FAIL, never as a MISS.


def swap_steps_6_and_7(text: str) -> str:
    """K1 (finding F-D): run the brake check BEFORE policy evaluation.

    The real defect this reintroduces: a checkpoint that reports the wrong refusing step when
    several would fail. An operator told BRAKE_ENGAGED for a FORBIDDEN action class releases the
    brake and lets through something no approval could ever unlock.
    """
    start6 = text.index("    # ---- STEP 6 —")
    start7 = text.index("    # ---- STEP 7 —")
    end7 = text.index("    # ---- all seven passed")
    block6, block7 = text[start6:start7], text[start7:end7]
    return text[:start6] + block7 + block6 + text[end7:]


def widen_the_rebaseline_window_to_include_p3(text: str) -> str:
    """K11 (finding F-A): make the rebaseline's recorded change window swallow P3's src/ changes.

    History is immutable, so "the rebaseline touched src/" cannot literally be reintroduced. The
    faithful mutant moves the recorded window's head onto a commit whose range DOES contain
    production runtime changes, and regenerates the recorded membership to match - so the
    membership check passes and the ONLY thing that can fail is the src/-untouched assertion
    itself. That is the invariant under test, isolated.
    """
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    base = re.search(r"^    base_commit: ([0-9a-f]{40})", text, re.M).group(1)
    paths = subprocess.run(["git", "diff", "--name-only", base, head], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout
    listing = sorted(p for p in paths.split("\n") if p.strip())
    assert any(p.startswith("src/") for p in listing), (
        "the widened window contains no src/ change - this mutant would not reintroduce the "
        "defect, and a MISS from it would prove nothing"
    )
    text = re.sub(r"^    head_commit: [0-9a-f]{40}", f"    head_commit: {head}", text,
                  count=1, flags=re.M)
    block = "    changed_paths:\n" + "".join(f"      - {p}\n" for p in listing)
    return re.sub(r"^    changed_paths:\n(?:      - .*\n)+", block, text, count=1, flags=re.M)


# (label, file, old, new[, count], guard nodeid) - or (label, file, mutator, guard nodeid)
CASES = [
    # ============================================================ GUARD battery
    ("M1 partition: same-count member substitution",
     "src/freight_recon/migrations/phase3_checkpoint.py",
     '("checkpoint_witnesses", "brakes")', '("checkpoint_witnesses", "brakez")',
     "eval/tests/test_bootstrap_hermeticity.py::test_the_canonical_table_partition_is_exact_and_disjoint"),

    ("M2 tenant posture: drop the platform_brake exemption",
     "src/freight_recon/migrations/phase3_checkpoint.py",
     'P3_EXEMPT_TABLES: tuple[str, ...] = ("platform_brake",)',
     'P3_EXEMPT_TABLES: tuple[str, ...] = ()',
     "eval/tests/test_phase0_errata_guards.py::test_tenant_offending_tables_exact_set_not_count"),

    ("M3 gate leak: a gate decision escapes into a non-kernel module",
     "src/freight_recon/fingerprint.py",
     '"""', '"""\nLEAKED_GATE = "AUTONOMOUS_WITHIN_CAPS"\n', 1,
     "eval/tests/test_phase0_null_gate.py::test_the_typed_gate_population_is_now_non_empty_and_confined_to_the_checkpoint_kernel"),

    ("M4 policy authority: strip the ADR-010 citation from the kernel",
     "src/freight_recon/checkpoint.py", "ADR-010", "ADR-XXX",
     "eval/tests/test_phase0_errata_guards.py::test_typed_policy_runtime_exists_only_with_its_canonical_authority"),

    ("M5 surface: IMPLEMENTED concept cites a symbol that does not exist",
     "docs/implementation/IMPLEMENTATION-SURFACE.yaml",
     "symbol: run_checkpoint", "symbol: run_checkpoint_that_does_not_exist",
     "eval/tests/test_docs_control_system.py::test_a_concept_is_implemented_only_when_its_owning_unit_ran_and_its_symbols_exist"),

    ("M6 false completion: a document declares P3 COMPLETE",
     "docs/implementation/CURRENT.md",
     "## Completed phases", "## Completed phases\n\nP3 is COMPLETE.\n",
     "eval/tests/test_docs_control_system.py::test_9_no_control_document_claims_a_phase_is_complete_before_the_registry_does"),

    ("M7 status record: P3 loses its NOT COMPLETE marking",
     "docs/implementation/CURRENT.md", "IN PROGRESS — NOT COMPLETE", "IN PROGRESS",
     "eval/tests/test_status_reality.py::test_the_status_record_still_states_the_canonical_facts"),

    ("M8 build status: deny the preserved independent rebaseline report",
     "docs/implementation/BUILD-STATUS.yaml",
     "The gate-level independent reviews (U-HANDOFF-2B, U-REBASELINE-REVIEW-1) are preserved and adjudicated, but they predate P3 and say nothing about it.",
     "Nothing has been reviewed.",
     "eval/tests/test_switch_consistency.py::test_build_status_does_not_claim_an_independent_review_is_unstarted_once_it_exists"),

    # ============================================================ KERNEL battery (F-D, F-A, F-C, F-I)
    ("K1 step order: swap checkpoint steps 6 and 7  [finding F-D, the named case]",
     "src/freight_recon/checkpoint.py", swap_steps_6_and_7,
     "eval/tests/test_phase3_step_order.py::test_policy_failure_and_an_active_brake_report_step_6_not_step_7"),

    # K1 pins the ONE named case; K2 re-runs the same mutant against the WHOLE step-order module.
    # They answer different questions: K1 proves the reviewed dual-fault assertion is load-bearing,
    # K2 proves the module as a whole would not have let the swap through on some other case had
    # K1's assertion been weakened or deleted.
    ("K2 step order: the 6/7 swap is caught by the whole step-order module, not one assertion",
     "src/freight_recon/checkpoint.py", swap_steps_6_and_7,
     "eval/tests/test_phase3_step_order.py"),

    ("K3 claim CAS: drop the brake_version predicate",
     "src/freight_recon/checkpoint.py",
     "AND expires_at > ? AND brake_version = ? AND policy_version = ?",
     "AND expires_at > ? AND policy_version = ?",
     "eval/tests/test_phase3_claim_cas.py"),

    ("K4 claim CAS: drop the policy_version predicate",
     "src/freight_recon/checkpoint.py",
     "AND expires_at > ? AND brake_version = ? AND policy_version = ?",
     "AND expires_at > ? AND brake_version = ?",
     "eval/tests/test_phase3_claim_cas.py"),

    ("K5 claim CAS: drop the tenant predicate  [finding F-I, defense in depth]",
     "src/freight_recon/checkpoint.py",
     "WHERE tenant = ? AND grant_id = ? AND state = 'GRANTED'",
     "WHERE grant_id = ? AND state = 'GRANTED'",
     "eval/tests/test_phase3_claim_cas.py"),

    ("K6 claim CAS: drop the expires_at predicate  [finding F-I, defense in depth]",
     "src/freight_recon/checkpoint.py",
     "AND expires_at > ? AND brake_version = ?", "AND brake_version = ?",
     "eval/tests/test_phase3_claim_cas.py"),

    ("K7 witness: make CheckpointPassed publicly constructable",
     "src/freight_recon/checkpoint.py",
     "        if _token is not _FACTORY_TOKEN:", "        if False:",
     "eval/tests/test_phase3_witness.py"),

    ("K8 witness: drop the append-only DELETE trigger",
     "src/freight_recon/migrations/phase3_checkpoint.py",
     "BEFORE DELETE ON checkpoint_witnesses", "AFTER INSERT ON brakes",
     "eval/tests/test_phase3_witness.py"),

    ("K9 ledger: unscope operation_commit_claim  [finding F-C, wrong-row selection]",
     "src/freight_recon/workflow.py",
     'f"SELECT * FROM effect_grants WHERE tenant = ? AND commit_key = ? AND {_LIVE_HOLD_SQL}",\n'
     "            (self._tenant, commit_key, *_LIVE_HOLD_STATES),",
     '"SELECT * FROM effect_grants WHERE tenant = ? AND commit_key = ?",\n'
     "            (self._tenant, commit_key),",
     "eval/tests/test_phase3_ledger_compatibility.py"),

    ("K10 ledger: unscope release_operation_commit  [finding F-C, the foreign-key error]",
     "src/freight_recon/workflow.py",
     'f"DELETE FROM effect_grants WHERE tenant = ? AND commit_key = ? "\n'
     '            f"AND {_LEGACY_OWNED_SQL} AND {_LIVE_HOLD_SQL}",\n'
     "            (self._tenant, commit_key, *_LIVE_HOLD_STATES),",
     '"DELETE FROM effect_grants WHERE tenant = ? AND commit_key = ?",\n'
     "            (self._tenant, commit_key),",
     "eval/tests/test_phase3_ledger_compatibility.py"),

    ("K11 rebaseline anchor: widen the window over P3's src/ changes  [finding F-A]",
     "docs/implementation/U-REBASELINE-1-ACCEPTANCE.yaml", widen_the_rebaseline_window_to_include_p3,
     "eval/tests/test_rebaseline_invariants.py::test_no_src_runtime_file_was_touched_by_the_rebaseline"),
]


def _mutate(text: str, case) -> str:
    """Apply one case's mutation. Raises SetupFailure when the anchor is gone or it no-ops."""
    spec = case[2]
    if callable(spec):
        return spec(text)
    old, new = case[2], case[3]
    count = case[4] if len(case) == 6 else -1
    if old not in text:
        raise SetupFailure(f"anchor not found: {old[:60]!r}")
    return text.replace(old, new, count) if count > 0 else text.replace(old, new)


class SetupFailure(RuntimeError):
    pass


def main() -> int:
    results = []
    for case in CASES:
        label, rel, guard = case[0], case[1], case[-1]
        path = ROOT / rel
        original = path.read_bytes()
        text = original.decode("utf-8")

        purge_pycache()
        if not run_guard(guard):
            results.append((label, "SETUP-FAIL", "guard already RED before mutation"))
            continue

        try:
            mutated = _mutate(text, case)
        except SetupFailure as exc:
            results.append((label, "SETUP-FAIL", str(exc)))
            continue
        except Exception as exc:  # noqa: BLE001 - a mutator that cannot locate its target
            results.append((label, "SETUP-FAIL", f"{type(exc).__name__}: {exc}"))
            continue
        if mutated == text:
            results.append((label, "SETUP-FAIL", "mutation was a no-op - it proves nothing"))
            continue

        try:
            path.write_text(mutated, encoding="utf-8")
            purge_pycache()
            caught = not run_guard(guard)
        finally:
            path.write_bytes(original)
            purge_pycache()

        assert path.read_bytes() == original, f"RESTORE FAILED for {rel}"
        if not run_guard(guard):
            results.append((label, "RESTORE-RED", "guard red after restore - investigate"))
            continue
        results.append((label, "CAUGHT" if caught else "MISS", ""))

    print("\n=========== P3 MUTATION BATTERY (guards + kernel) ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by sessions inside the work it audits - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
