#!/usr/bin/env python3
"""`AC-MACH-000` / P6 machine-population mutation battery.

### A STRUCTURAL GUARD THAT CANNOT FAIL IS A GUARD THAT PROVES NOTHING, and a population guard is the
kind most likely to be quietly vacuous: it compares two sets, and two sets that are both derived from
the same mistake agree perfectly. So every failure mode the guard claims to catch is INJECTED here and
must turn a NAMED guard RED.

The nine mutants are the nine ways the phase-level argument can be broken:

  1. a canonical transition row leaves the specification;
  2. a declarative transition row leaves the implementation;
  3. an implementation-only transition appears with no canonical row;
  4. two rows claim one transition identifier;
  5. a whole machine module drops out of the discovered population;
  6. an illegal (state, trigger) pair is made legal by the legality function alone;
  7. an anchor's evidence mapping is emptied;
  8. an anchor's evidence TARGET stops naming its anchor;
  9. an anchor is mapped to the wrong canonical transition.

Originals are held in memory and restored unconditionally and byte-for-byte; `__pycache__` is purged
around every run; git is never used to undo a mutation (CLAUDE.md §6). An anti-vacuity control — an
unmutated guard that must stay GREEN — makes the count a measurement rather than an assertion.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

SPEC_EC = "docs/specifications/state-machines/09-exception.machine.md"
CONFLICT = "src/freight_recon/conflict.py"
EXPECTATION = "src/freight_recon/expectation.py"
EXCEPTION = "src/freight_recon/exception.py"
MANIFEST = "eval/tests/phase6_anchor_manifest.py"
BRAKE_T = "eval/tests/test_phase6_brake.py"

POP = "eval/tests/test_phase6_machine_population.py"
SWEEP = "eval/tests/test_phase6_transition_sweep.py"
TRACE = "eval/tests/test_phase6_anchor_traceability.py"

_SENTINEL = "MUTANT"

# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Each anchor must appear EXACTLY
# once. Every new_text embeds the sentinel so a stranded mutation is detectable.
CASES = [
    # ---- 1. a canonical transition row leaves the specification.
    # Unbolding the id is the minimal removal: §14's parser reads bolded ids, so EC-5 stops being one
    # of the 134 while the prose stays put. M9's implementation still declares it.
    ("a canonical §14 row leaves the specification (EC-5)",
     [(SPEC_EC, "| **EC-5** |", "| EC-5 (MUTANT unbolded) |")],
     f"{POP}::test_ac_mach_000_implementation_minus_specification_is_empty"),

    # ---- 2. a declarative transition row leaves the implementation.
    ("a declared transition row leaves the implementation (CF-5)",
     [(CONFLICT,
       '        id="CF-5", from_states=(CfState.OPEN,), to_state=CfState.ESCALATED,',
       '        id="CF-5-MUTANT", from_states=(CfState.OPEN,), to_state=CfState.ESCALATED,')],
     f"{POP}::test_ac_mach_000_specification_minus_implementation_is_empty"),

    # ---- 3. an implementation-only transition with no canonical row.
    ("an implementation-only transition appears (CF-9)",
     [(CONFLICT,
       '    TransitionRow(\n        id="CF-2", from_states=(CfState.RAISED,), to_state=CfState.OPEN,',
       '    TransitionRow(  # MUTANT\n        id="CF-9", from_states=(CfState.RAISED,),'
       ' to_state=CfState.OPEN,\n        triggers=(Trigger.ACKNOWLEDGED,), trigger_types=("H",),'
       ' event="ConflictOpened"),\n    TransitionRow(\n'
       '        id="CF-2", from_states=(CfState.RAISED,), to_state=CfState.OPEN,')],
     f"{POP}::test_ac_mach_000_implementation_minus_specification_is_empty"),

    # ---- 4. two rows claim one identifier. The count still sums to 134, which is exactly the
    # "count match with different members" the acceptance oracle says MUST fail.
    ("two rows claim one transition identifier (CF-5 becomes a second CF-4)",
     [(CONFLICT,
       '        id="CF-5", from_states=(CfState.OPEN,), to_state=CfState.ESCALATED,',
       '        id="CF-4", from_states=(CfState.OPEN,), to_state=CfState.ESCALATED,  # MUTANT')],
     f"{POP}::test_no_transition_identifier_is_declared_twice"),

    # ---- 5. a machine module drops out of the discovered population.
    ("a machine module drops out of the discovered population (M8)",
     [(EXPECTATION,
       "TRANSITIONS: tuple[TransitionRow, ...] = (\n    # ### EX-1 CARRIES NO TRIGGER",
       "TRANSITIONS: tuple[TransitionRow, ...] = ()  # MUTANT\n"
       "_WAS_TRANSITIONS = (\n    # ### EX-1 CARRIES NO TRIGGER")],
     f"{POP}::test_the_implementation_corpus_is_thirteen_machine_modules"),

    # ---- 6. an illegal pair is made legal by the LEGALITY FUNCTION alone, so the table still says
    # AGEING cannot resolve and the machine says it can. This is the disagreement the sweep exists to
    # find; a change made in both places at once would not be a defect, it would be a decision.
    ("an illegal (state, trigger) pair is made legal (M9 AGEING + Resolved)",
     [(EXCEPTION,
       "        if not row.creates and trigger in row.triggers and state in row.from_states)",
       "        if not row.creates and trigger in row.triggers and (\n"
       "            state in row.from_states\n"
       '            or (row.id == "EC-3" and state is EcState.AGEING)))  # MUTANT')],
     f"{SWEEP}::test_the_illegal_population_is_the_exact_complement"),

    # ---- 7. an anchor's evidence mapping is emptied.
    ("an anchor's evidence mapping is removed (AC-MACH-903)",
     [(MANIFEST,
       '        evidence=(\n            "test_phase6_exception.py::test_ec_close_requires_valid_decision_ref",\n        )),',
       '        evidence=()),  # MUTANT')],
     f"{TRACE}::test_every_anchors_evidence_exists"),

    # ---- 8. an anchor's evidence TARGET stops naming its anchor — the exact defect the adjudication
    # found: the behaviour is there and the id is not.
    ("an anchor stops being named at its evidence (AC-MACH-1305)",
     [(BRAKE_T,
       '"""`AC-MACH-1305` — no timer releases a brake."""',
       '"""no timer releases a brake."""  # MUTANT: the anchor id removed')],
     f"{TRACE}::test_every_anchor_is_named_at_every_one_of_its_evidence_sites"),

    # ---- 9. an anchor is mapped to the wrong canonical transition. AC-MACH-605x derives from IB-5x;
    # pointed at IB-5 it derives to AC-MACH-605, and the register no longer means what it says.
    ("an anchor is mapped to the wrong canonical transition (AC-MACH-605x -> IB-5)",
     [(MANIFEST,
       '        anchor="AC-MACH-605x", transition="IB-5x",',
       '        anchor="AC-MACH-605x", transition="IB-5",  # MUTANT')],
     f"{TRACE}::test_the_anchor_id_is_derived_from_the_canonical_transition_it_names"),
]

# Anti-vacuity control: NOT mutated; a representative guard must be GREEN.
CONTROL_GUARD = f"{POP}::test_the_canonical_denominator_is_one_hundred_and_thirty_four"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def assert_pristine() -> None:
    targets = sorted({rel for _, edits, _ in CASES for rel, _o, _n in edits})
    poisoned = [rel for rel in targets if _SENTINEL in (ROOT / rel).read_text(encoding="utf-8")]
    if poisoned:
        print(f"### REFUSING TO MEASURE: mutation residue in {poisoned} — restore first",
              file=sys.stderr)
        raise SystemExit(2)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, _old, _new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        originals.setdefault(path, path.read_bytes())
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
        return "RESTORE-RED", "guard red after restore — investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def _baseline_control() -> str:
    purge_pycache()
    return "GREEN" if run_guard(CONTROL_GUARD) else "RED"


def main() -> int:
    assert_pristine()
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    control = _baseline_control()

    for label, verdict, detail in results:
        mark = "PASS" if verdict == "CAUGHT" else "### MISS ###"
        line = f"{mark}  {label}"
        if detail:
            line += f"  [{verdict}: {detail}]"
        print(line)
    print(f"anti-vacuity control (unmutated guard stays GREEN): {control}")

    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    total = len(results)
    escaped = total - caught
    control_ok = control == "GREEN"
    print(f"{caught} mutations caught, {escaped} escaped")
    if caught == total and control_ok:
        return 0
    if not control_ok:
        print("### MISS ### the anti-vacuity control did not stay GREEN — the battery is vacuous",
              file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
