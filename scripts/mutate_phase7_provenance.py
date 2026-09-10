#!/usr/bin/env python3
"""P7 (provenance-safety core) mutation battery.

Each mutant reintroduces a defect whose prohibition is canonically established (ADR-002 sec 2.3,
AC-SAFE-015/016), and each must turn its guard test RED for the intended reason. All four rules are
covered: R-P1 (runtime assignment), AC-4 (MODEL_INFERRED cannot gate), R-P2 (no laundering), R-P3
(OWNER_ASSERTED never machine-recomputed). The count is DERIVED (len(CASES)); originals are held in
memory and restored unconditionally; __pycache__ is purged around every run; git is never used to
undo a mutation (CLAUDE.md sec 6). An anti-vacuity control keeps the count a measurement.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

PROV = "src/freight_recon/provenance.py"
T = "eval/tests/test_phase7_provenance.py"

_SENTINEL = "MUTANT"

CASES = [
    ("R-P1: a model guess is assigned OWNER_ASSERTED",
     [(PROV,
       "    Acquisition.MODEL_GUESS: ProvenanceClass.MODEL_INFERRED,",
       "    Acquisition.MODEL_GUESS: ProvenanceClass.OWNER_ASSERTED,  # MUTANT")],
     f"{T}::test_provenance_is_assigned_by_the_runtime_from_how_the_value_was_obtained"),

    ("R-P1: inbound content is no longer screened for a provenance key",
     [(PROV,
       "    if isinstance(inbound, Mapping):",
       "    if False and isinstance(inbound, Mapping):  # MUTANT")],
     f"{T}::test_inbound_content_cannot_choose_its_own_provenance"),

    ("AC-4: MODEL_INFERRED is removed from the gate-forbidden set",
     [(PROV,
       "_GATE_FORBIDDEN: frozenset[ProvenanceClass] = frozenset({ProvenanceClass.MODEL_INFERRED})",
       "_GATE_FORBIDDEN: frozenset[ProvenanceClass] = frozenset()  # MUTANT")],
     f"{T}::test_a_model_inferred_fact_cannot_be_read_by_a_consequential_gate"),

    ("AC-4: the consequential gate-read stops refusing",
     [(PROV,
       "    if not may_gate_consequential_action(provenance_class):",
       "    if False and not may_gate_consequential_action(provenance_class):  # MUTANT")],
     f"{T}::test_confidence_cannot_rescue_a_model_inferred_gate_read"),

    ("R-P2: reassign allows a mechanical strengthen (returns instead of refusing)",
     [(PROV,
       "    raise ProvenanceLaundering(",
       "    return new_c  # MUTANT allows laundering\n    raise ProvenanceLaundering(")],
     f"{T}::test_provenance_may_weaken_but_never_mechanically_strengthen"),

    ("R-P2: is_stronger reports nothing is ever stronger",
     [(PROV,
       "    return _TRUST_RANK[as_class(new)] > _TRUST_RANK[as_class(old)]",
       "    return False  # MUTANT nothing is ever stronger")],
     f"{T}::test_provenance_may_weaken_but_never_mechanically_strengthen"),

    ("R-P2: mechanical derivation strengthens instead of carrying",
     [(PROV,
       '    laundering defect."""\n    return as_class(source)',
       '    laundering defect."""\n    return ProvenanceClass.OWNER_ASSERTED  # MUTANT carry strengthens')],
     f"{T}::test_a_model_inferred_fact_stays_model_inferred_through_every_derivation_path"),

    ("R-P3: a machine recompute may overwrite an OWNER_ASSERTED value",
     [(PROV,
       "    if record.provenance_class is ProvenanceClass.OWNER_ASSERTED:\n        raise OwnerAssertedRecompute(",
       "    if False and record.provenance_class is ProvenanceClass.OWNER_ASSERTED:  # MUTANT\n        raise OwnerAssertedRecompute(")],
     f"{T}::test_owner_asserted_is_never_machine_recomputed_and_the_value_is_preserved"),
]

# Anti-vacuity control: NOT mutated; a representative guard must be GREEN.
CONTROL_GUARD = f"{T}::test_exactly_the_six_provenance_classes_and_no_seventh"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def assert_pristine() -> None:
    targets = sorted({rel for _, edits, _ in CASES for rel, _o, _n in edits})
    poisoned = [rel for rel in targets if _SENTINEL in (ROOT / rel).read_text(encoding="utf-8")]
    if poisoned:
        print(f"### REFUSING TO MEASURE: mutation residue in {poisoned} — restore first", file=sys.stderr)
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
