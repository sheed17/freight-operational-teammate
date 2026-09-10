#!/usr/bin/env python3
"""P7 (AC-14) — the consolidated mutation + anti-vacuity sweep across the WHOLE P7 surface.

AC-14 requires that every guard protecting a P7 tier-1 invariant has been SEEN TO FAIL against a
mutant that reintroduces the REAL defect, and that the tally is a MEASUREMENT (an anti-vacuity
control stays GREEN), never an assertion. This runner aggregates the per-surface batteries so the
whole surface is measured in one command:

  * provenance-safety core (R-P1/R-P2/R-P3, AC-4) ............ scripts/mutate_phase7_provenance.py
  * content-addressed Evidence (dedup, immutability, span) ... scripts/mutate_phase7_evidence.py
  * linker / identity persistence / conflict / correction ... scripts/mutate_phase7_identity.py
  * knowledge-base tenant closure (AC-12) ................... the guard's in-test anti-vacuity control

The KB closure's anti-vacuity is an IN-TEST control (the file-mutation form was refused by the
harness as deploy tooling because it edits action_callback.py); it is exercised here via pytest so
the whole surface — including AC-12 — is covered in one run. Each child battery restores its own
mutations in memory and purges __pycache__; this runner writes nothing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

BATTERIES = [
    ("provenance-safety core (R-P1/R-P2/R-P3, AC-4)", "scripts/mutate_phase7_provenance.py"),
    ("content-addressed Evidence (AC-6)", "scripts/mutate_phase7_evidence.py"),
    ("linker / persistence / conflict / correction (AC-7..AC-11, F14)", "scripts/mutate_phase7_identity.py"),
]

KB_ANTIVACUITY = (
    "eval/tests/test_bootstrap_hermeticity.py::"
    "test_the_knowledge_write_guard_is_not_vacuous_and_catches_a_reintroduced_default"
)

_TALLY = re.compile(r"(\d+)\s+mutations caught,\s+(\d+)\s+escaped")
_CONTROL = re.compile(r"anti-vacuity control.*:\s*(GREEN|RED)")


def _run_battery(path: str) -> tuple[int, int, str, str]:
    r = subprocess.run([PY, path], cwd=ROOT, capture_output=True, text=True)
    out = r.stdout + r.stderr
    tally = _TALLY.search(out)
    control = _CONTROL.search(out)
    caught, escaped = (int(tally.group(1)), int(tally.group(2))) if tally else (0, -1)
    control_state = control.group(1) if control else "MISSING"
    return caught, escaped, control_state, out


def _run_kb_antivacuity() -> bool:
    r = subprocess.run([PY, "-m", "pytest", KB_ANTIVACUITY, "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    total_caught = total_planted = 0
    all_controls_green = True
    ok = True

    for label, path in BATTERIES:
        caught, escaped, control, out = _run_battery(path)
        planted = caught + escaped if escaped >= 0 else -1
        green = control == "GREEN"
        all_controls_green &= green
        if planted < 0 or escaped != 0 or not green:
            ok = False
            print(f"### MISS ###  {label}: caught={caught} escaped={escaped} control={control}")
            print(out.strip()[-800:])
        else:
            total_caught += caught
            total_planted += planted
            print(f"PASS  {label}: {caught}/{planted} caught, anti-vacuity control GREEN")

    kb_ok = _run_kb_antivacuity()
    ok &= kb_ok
    print(f"PASS  knowledge-base tenant closure (AC-12): guard SEEN TO FAIL on a reintroduced default "
          f"(in-test anti-vacuity control): {kb_ok}" if kb_ok else
          "### MISS ###  knowledge-base tenant closure (AC-12): anti-vacuity control did not pass")

    print(f"\nCONSOLIDATED P7 MUTATION SWEEP: {total_caught}/{total_planted} planted defects caught "
          f"across the P7 surface; all anti-vacuity controls GREEN: {all_controls_green and kb_ok}")
    if ok and total_planted > 0:
        print("every P7 guard was seen to fail against the real defect it protects")
        return 0
    print("### MISS ### the consolidated P7 mutation sweep did not fully close", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
