#!/usr/bin/env python3
"""U8.2 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a SPECIFIC real defect the standing-rule admission layer (ADR-010 §8 layer
6) exists to prevent: a PERMIT-effect rule that LOOSENS a running DENY (a layer-6 rule broadening
authority), an allow-on-rule-error path that swallows a MODEL_INFERRED failure instead of failing
closed, a DENY rule that stops denying (the fence silently opens), the layer forgetting to READ the
tenant's active rules (real evidence silently dropped), and a non-gate BIND/RESOLVE effect passing
unjudged instead of failing closed. Each names the guard that must turn RED under it.

The ANTI-VACUITY CONTROL is a NO-MUTATION baseline: the same battery target run with the tree
untouched must be GREEN. If it is red before any mutation, the counts below are assertions, not
measurements.

It mutates TEXT and shells out to pytest; it NEVER imports the admission layer, and it NEVER uses
git to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is
purged around every run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

RADM = "src/freight_recon/rule_admission.py"
T = "eval/tests/test_p8_rule_admission.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider",
                        "-p", "no:randomly"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Anchors must be UNIQUE.
CASES = [
    # -------------------------------------------------- the never-loosen guard (the tier-1 one)
    ("### A LAYER-6 RULE LOOSENS A DENY — the PERMIT branch no longer refuses; a PERMIT-effect rule "
     "flips a running DENY into a PERMIT, so a standing rule BROADENS authority (ADR-010 §7/§8)",
     [(RADM,
       "            if decision == _DENY:\n                rejected.append((",
       "            if decision == _DENY:\n"
       "                decision = _PERMIT  # MUTANT — a PERMIT rule LOOSENS a running DENY\n"
       "            if False and decision == _DENY:\n                rejected.append((")],
     f"{T}::test_a_rule_that_would_LOOSEN_a_DENY_is_REFUSED_and_attributable"),

    # -------------------------------------------------- allow-on-rule-error (how the fence dies)
    ("### ALLOW ON RULE ERROR — a MODEL_INFERRED fact at evaluation is SWALLOWED and the rule is "
     "skipped instead of failing closed, so a guess is passed through the layer (ADR-010 §5.1/§11)",
     [(RADM,
       "            verdict = self._evaluate(rec, material_facts)",
       "            try:\n"
       "                verdict = self._evaluate(rec, material_facts)\n"
       "            except Exception:  # MUTANT — allow on rule error\n"
       "                continue")],
     f"{T}::test_a_MODEL_INFERRED_fact_at_evaluation_FAILS_CLOSED_no_decision"),

    # -------------------------------------------------- a DENY rule stops denying
    ("### A DENY RULE STOPS DENYING — the layer no longer tightens the decision on a DENY verdict, so "
     "'never bill without a POD' silently permits the bill",
     [(RADM,
       "            if effect == _DENY:\n                decision = _DENY\n",
       "            if effect == _DENY:\n"
       "                decision = decision  # MUTANT — a DENY rule no longer denies\n")],
     f"{T}::test_an_active_DENY_rule_with_no_POD_is_REAL_evidence_and_denies"),

    ("a DENY rule stops denying, END TO END — the effect reaches the mint instead of refusing at "
     "step 6, so a standing rule stops being a real control",
     [(RADM,
       "            if effect == _DENY:\n                decision = _DENY\n",
       "            if effect == _DENY:\n"
       "                decision = decision  # MUTANT — a DENY rule no longer denies\n")],
     f"{T}::test_e2e_an_active_DENY_rule_refuses_at_step_6_with_no_witness"),

    # -------------------------------------------------- the evidence is silently dropped
    ("### THE LAYER STOPS READING ACTIVE RULES — `active_rules` returns nothing, so a real ACTIVE "
     "rule is neither evaluated nor enforced and `rules_evaluated`/`rules_matched` go decorative again",
     [(RADM,
       "        return tuple(sorted(found.values(), key=lambda r: r.rule_id))",
       "        return ()  # MUTANT — the layer forgets the tenant's active rules\n"
       "        return tuple(sorted(found.values(), key=lambda r: r.rule_id))")],
     f"{T}::test_the_full_admission_decision_carries_real_rule_ids"),

    # -------------------------------------------------- a non-gate effect passes unjudged
    ("### A NON-GATE (BIND/RESOLVE) EFFECT PASSES UNJUDGED — the fail-closed check is disabled, so a "
     "rule whose effect is not a gate decision is silently ignored instead of refusing",
     [(RADM,
       "            if effect not in _GATE_EFFECTS:",
       "            if False and effect not in _GATE_EFFECTS:  # MUTANT")],
     f"{T}::test_a_non_gate_effect_rule_FAILS_CLOSED_at_the_checkpoint"),
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
    """### THE ANTI-VACUITY CONTROL: the tree is NOT mutated, and a representative guard must be
    GREEN. A battery whose target is already red would report every mutation 'caught' while proving
    nothing. Expected outcome: GREEN."""
    purge_pycache()
    green = run_guard(f"{T}::test_an_active_DENY_rule_with_no_POD_is_REAL_evidence_and_denies")
    return ("GREEN" if green else "RED"), ""


def main() -> int:
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    control_verdict, _ = _baseline_control()

    print("\n=========== U8.2 RULE ADMISSION MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    control_mark = "PASS" if control_verdict == "GREEN" else "### MISS ###"
    print(f"  [{control_mark:>12}] anti-vacuity control: the un-mutated tree is GREEN "
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


def test_the_p8_rule_admission_mutation_battery_catches_every_mutant():
    """### THE PYTEST-COLLECTED ENTRY POINT (CLAUDE.md §6): the standard runner OPERATES this battery
    directly — `pytest scripts/mutate_p8_rule_admission.py` — and reads its exit status, not only the
    `__main__` CLI. An unmeasured guard is not a passing guard.

    `main()` runs EVERY mutant (each reintroduces a real U8.2 defect and must be CAUGHT) and the
    anti-vacuity control (the un-mutated tree must be GREEN), restoring `rule_admission.py`
    byte-for-byte from memory and never with git. It returns 0 only if every mutant is caught AND the
    control is green, so `== 0` is the whole battery, measured — over a non-empty population, so it
    cannot pass vacuously (M-9).

    This file is deliberately NOT collected by a bare `pytest eval` (it is outside `testpaths` and is
    not named `test_*.py`); it runs only when named explicitly, which is exactly how a slow mutation
    battery should be operated — on purpose, never by accident sweeping the whole suite.
    """
    assert len(CASES) >= 5, (
        f"the battery carries {len(CASES)} mutants; it must carry all of them (>=5) for 'every mutant "
        f"caught' to mean anything (M-9).")
    assert main() == 0, (
        "the U8.2 rule admission mutation battery did NOT report every mutant CAUGHT with a GREEN "
        "anti-vacuity control; a guard that cannot be shown to fire is unverified. See the report.")


if __name__ == "__main__":
    raise SystemExit(main())
