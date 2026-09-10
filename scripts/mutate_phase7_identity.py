#!/usr/bin/env python3
"""P7 (identity / lineage / conflict / correction / F14) mutation battery.

Each mutant reintroduces a defect whose prohibition is canonically established (ADR-007, ADR-002),
and each must turn its guard test RED for the intended reason. Covers AC-7, AC-8, AC-9, AC-10, AC-11
and the F14 R-P2 emission. In-memory save/restore; __pycache__ purged; git never used to undo a
mutation (CLAUDE.md sec 6); an anti-vacuity control keeps the count a measurement.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

LK = "src/freight_recon/linker.py"
LG = "src/freight_recon/lineage.py"
PROV = "src/freight_recon/provenance.py"
T = "eval/tests/test_phase7_identity.py"

_SENTINEL = "MUTANT"

CASES = [
    ("AC-8: an unauthenticated human signal is trusted as OWNER_ASSERTED",
     [(LK, "        if not authenticated_human:", "        if False and not authenticated_human:  # MUTANT")],
     f"{T}::test_ambiguous_or_weak_candidates_fail_closed"),

    ("AC-8: model-extraction stops re-entering the deterministic linker",
     [(LK, '    effective = {**by_method, "EXACT_ID": reentered}',
       "    effective = {**by_method}  # MUTANT model-extract no longer re-enters")],
     f"{T}::test_model_extraction_re_enters_the_deterministic_linker"),

    ("AC-9: a relink overwrites an OWNER_ASSERTED binding (bypasses R-P3)",
     [(LK, "    return machine_recompute(existing, new_value=proposed_value, new_class=proposed_class.value)",
       "    return ProvenanceRecord(value=proposed_value, provenance_class=proposed_class)  # MUTANT")],
     f"{T}::test_owner_asserted_binding_survives_relink_and_replay"),

    ("AC-10: a Conflict can be closed by a third way",
     [(LK,
       '    raise ConflictClosureRefused(\n        "a Conflict closes ONLY via a registered rule (rule_id)',
       '    return "RESOLVED_BY_RULE"  # MUTANT third way\n    raise ConflictClosureRefused(\n        "a Conflict closes ONLY via a registered rule (rule_id)')],
     f"{T}::test_a_conflict_closes_only_via_a_registered_rule_or_a_human_decision"),

    ("AC-10: an open Conflict stops blocking",
     [(LK, "    if state in OPEN_CONFLICT_STATES:\n        return True",
       "    if state in OPEN_CONFLICT_STATES:\n        return False  # MUTANT")],
     f"{T}::test_conflict_is_first_class_and_blocks_while_open"),

    ("AC-11: a correction stops raising a downstream obligation (conflated with supersession)",
     [(LK, "                        corrected_event=corrected_event, downstream_obligation=True)",
       "                        corrected_event=corrected_event, downstream_obligation=False)  # MUTANT")],
     f"{T}::test_correction_and_supersession_are_distinct_with_retained_attributable_history"),

    ("AC-7: a MODEL_EXTRACTED claim with no span stops failing closed",
     [(LG, "        if pc is ProvenanceClass.MODEL_EXTRACTED and not spans:",
       "        if False and pc is ProvenanceClass.MODEL_EXTRACTED and not spans:  # MUTANT")],
     f"{T}::test_lineage_fails_closed_on_a_missing_or_inferred_link"),

    ("F14: a refused strengthening no longer emits the audit event",
     [(PROV, "    if on_strengthening_attempt is not None:",
       "    if False and on_strengthening_attempt is not None:  # MUTANT")],
     f"{T}::test_a_refused_strengthening_emits_the_registered_f14_event"),
]

# Anti-vacuity control: NOT mutated; a representative guard must be GREEN.
CONTROL_GUARD = f"{T}::test_the_binding_order_vocabulary_is_the_one_m6_authority"


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
