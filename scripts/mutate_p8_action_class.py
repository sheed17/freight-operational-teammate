#!/usr/bin/env python3
"""U8.5 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a SPECIFIC defect the `lane` -> `action_class` migration exists to prevent,
and names the guard that must turn RED under it:

  * reintroduce an authoritative operational `lane` into product code (the detector must catch it);
  * swap an `action_class` occurrence to `workflow_id` (the reservation loses its canonical field);
  * accept an UNKNOWN action class through a default gate (F-20 regressed);
  * cross tenants in the migrated autonomous-run counter (the tenant predicate dropped);
  * let the effect_grants legacy `lane` mirror WIN over `action_class` (old field decides the lookup);
  * alter a commit key through the rename (effect identity moved);
  * neuter the detector so a reintroduced operational `lane` is no longer flagged (a vacuous gate).

The ANTI-VACUITY CONTROL is a NO-MUTATION baseline: the acceptance guard on the untouched tree must
be GREEN, so 'every mutant caught' is a measurement, not an assertion over a broken target.

It mutates TEXT and shells out to pytest; it NEVER imports the migration, and it NEVER uses git to
undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is purged
around every run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

ROUTER = "src/freight_recon/operation_router.py"
PROD = "src/freight_recon/product_policy.py"
WF = "src/freight_recon/workflow.py"
DET = "eval/phase0/action_class_migration.py"
T = "eval/tests/test_phase8_action_class_migration.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Anchors must be UNIQUE.
CASES = [
    ("### AN AUTHORITATIVE OPERATIONAL `lane` IS REINTRODUCED into product code — the overloaded "
     "legacy identifier is back as a live dict write",
     [(ROUTER,
       '    return str(params.get("action_class") or params.get("lane") or "").lower()',
       '    _reintroduced = {"lane": params}  # MUTANT operational lane\n'
       '    return str(params.get("action_class") or params.get("lane") or "").lower()')],
     f"{T}::test_no_unresolved_operational_lane_in_product_authority"),

    ("### AN `action_class` OCCURRENCE IS SWAPPED TO `workflow_id` — the reservation stops carrying "
     "the canonical WHAT-effect field, so the router cannot look it up",
     [(ROUTER,
       '        "action_class": route.name,\n        "load_ref": _load_ref_of(intent) or "",',
       '        "workflow_id": route.name,  # MUTANT\n        "load_ref": _load_ref_of(intent) or "",')],
     f"{T}::test_router_reservation_carries_action_class_and_preserves_the_commit_key"),

    ("### AN UNKNOWN ACTION CLASS IS ACCEPTED — `product_gate_for` returns a safe-looking default "
     "instead of refusing, so forgetting to classify a class is survivable again (F-20)",
     [(PROD,
       "    entry = PRODUCT_POLICY.get(name)\n    if entry is None:\n        raise UnclassifiedActionClass(",
       "    entry = PRODUCT_POLICY.get(name)\n    if entry is None:\n        return GateDecision.HUMAN_APPROVAL_REQUIRED  # MUTANT default\n    if False and entry is None:\n        raise UnclassifiedActionClass(")],
     f"{T}::test_unregistered_action_class_still_refuses_f20"),

    ("### THE MIGRATED AUTONOMOUS-RUN COUNTER CROSSES TENANTS — the tenant predicate is inverted, so "
     "one brokerage reads another's counter",
     [(WF,
       "            SELECT runs FROM autonomous_run_counters\n            WHERE tenant = ? AND action_class = ? AND day = ?",
       "            SELECT runs FROM autonomous_run_counters\n            WHERE tenant != ? AND action_class = ? AND day = ?  -- MUTANT cross-tenant")],
     f"{T}::test_autonomous_counter_stays_tenant_scoped_after_rename"),

    ("### THE LEGACY `lane` MIRROR WINS OVER `action_class` — the compatibility lookup reverts to the "
     "deprecated field, so old-field-decides returns the wrong rows",
     [(WF,
       "WHERE tenant = ? AND action_class = ? AND load_ref = ? AND party = ? AND commit_key != ?",
       "WHERE tenant = ? AND lane = ? AND load_ref = ? AND party = ? AND commit_key != ?  -- MUTANT old field wins")],
     f"{T}::test_legacy_lookup_reads_action_class_not_the_lane_mirror"),

    ("### THE RENAME ALTERS A COMMIT KEY — the effect's action_class value is changed, so the same "
     "logical effect mints a DIFFERENT identity (double-commit risk)",
     [(ROUTER,
       "        action_class=route.name,\n        target_system=target_system,",
       '        action_class="mutant_" + route.name,  # MUTANT alters effect identity\n        target_system=target_system,')],
     f"{T}::test_router_reservation_carries_action_class_and_preserves_the_commit_key"),

    ("### THE DETECTOR IS NEUTERED — a reintroduced operational `lane` is classified resolved, so the "
     "acceptance gate becomes vacuous",
     [(DET,
       "    return UNRESOLVED_OPERATIONAL",
       "    return FREIGHT_DOMAIN  # MUTANT neutered gate")],
     f"{T}::test_the_detector_is_non_vacuous_a_reintroduced_operational_lane_is_caught"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    originals = {ROOT / rel: (ROOT / rel).read_bytes() for rel, _o, _n in edits}
    for rel, old, _new in edits:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if text.count(old) != 1:
            return "SETUP-FAIL", f"anchor appears {text.count(old)}x in {rel} (need exactly 1)"

    purge_pycache()
    if not run_guard(guard):
        return "SETUP-FAIL", "guard already RED before mutation"

    try:
        mutated = {path: blob.decode("utf-8") for path, blob in originals.items()}
        for rel, old, new in edits:
            path = ROOT / rel
            before = mutated[path]
            mutated[path] = before.replace(old, new, 1)
            if mutated[path] == before:
                raise RuntimeError(f"mutation was a no-op in {rel}")
        for path, text in mutated.items():
            path.write_text(text, encoding="utf-8")
        purge_pycache()
        caught = not run_guard(guard)
    except RuntimeError as exc:
        for path, blob in originals.items():
            path.write_bytes(blob)
        purge_pycache()
        return "SETUP-FAIL", str(exc)
    finally:
        for path, blob in originals.items():
            path.write_bytes(blob)
        purge_pycache()
    for path, blob in originals.items():
        if path.read_bytes() != blob:
            return "RESTORE-RED", f"byte-for-byte restore FAILED for {path}"
    if not run_guard(guard):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def _baseline_control() -> tuple[str, str]:
    """### THE ANTI-VACUITY CONTROL: the tree is NOT mutated, and the acceptance gate must be GREEN."""
    purge_pycache()
    green = run_guard(f"{T}::test_no_unresolved_operational_lane_in_product_authority")
    return ("GREEN" if green else "RED"), ""


def main() -> int:
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    control_verdict, _ = _baseline_control()

    print("\n=========== U8.5 LANE->ACTION_CLASS MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    control_mark = "PASS" if control_verdict == "GREEN" else "### MISS ###"
    print(f"  [{control_mark:>12}] anti-vacuity control: the un-mutated acceptance gate is GREEN "
          f"(expected GREEN, got {control_verdict})")

    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    total = len(results)
    escaped = total - caught
    control_ok = control_verdict == "GREEN"
    print(f"\n  {caught}/{total} mutants caught")
    print(f"  {caught} mutations caught, {escaped} escaped")
    print(f"  anti-vacuity control: {'GREEN as expected' if control_ok else 'FAILED — target already red'}")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if (caught == total and control_ok) else 1


def test_the_u85_action_class_mutation_battery_catches_every_mutant():
    """### THE PYTEST-COLLECTED ENTRY POINT (CLAUDE.md §6): the runner OPERATES this battery directly
    — `pytest scripts/mutate_p8_action_class.py` — and reads its exit status, so the guards are
    MEASURED, not merely hand-run. `main()` runs every mutant (each reintroduces a real defect and
    must be CAUGHT) plus the anti-vacuity control (the un-mutated acceptance gate must be GREEN),
    restoring every file byte-for-byte from memory and never with git.

    Not collected by a bare `pytest eval` (outside testpaths, not named test_*.py); it runs only when
    named explicitly — the right way to operate a slow mutation battery."""
    assert len(CASES) >= 6, (
        f"the battery carries {len(CASES)} mutants; U8.5 must exercise at least the six load-bearing "
        f"migration guards for 'every mutant caught' to mean anything (M-9).")
    assert main() == 0, (
        "the U8.5 mutation battery did NOT report every mutant CAUGHT with a GREEN anti-vacuity "
        "control; a guard that cannot be shown to fire is unverified. See the report.")


if __name__ == "__main__":
    raise SystemExit(main())
