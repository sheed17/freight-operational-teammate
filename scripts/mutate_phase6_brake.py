#!/usr/bin/env python3
"""M13 (the Brake) mutation battery.

Each mutant reintroduces a defect whose prohibition is canonically established, and each must turn
its guard test RED for the intended reason. The count is DERIVED (len(CASES)), never hard-coded.
Originals are held in memory and restored unconditionally; __pycache__ is purged around every run;
git is never used to undo a mutation (CLAUDE.md §6). An anti-vacuity control — an unmutated
representative guard that must stay GREEN — makes the count a measurement, not an assertion.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

BR = "src/freight_recon/brake.py"
BL = "src/freight_recon/brake_lifecycle.py"
MIG = "src/freight_recon/migrations/phase6_brakes.py"
CP = "src/freight_recon/checkpoint.py"
T = "eval/tests/test_phase6_brake.py"

_SENTINEL = "MUTANT"

# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Each anchor must appear EXACTLY
# once. Every new_text embeds the sentinel so a stranded mutation is detectable.
CASES = [
    ("a third brake state becomes insertable",
     [(MIG, "state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED')),\n            actor TEXT NOT NULL,",
       "state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED','PENDING_RELEASE')),  -- MUTANT\n            actor TEXT NOT NULL,")],
     f"{T}::test_the_two_states_and_no_third_is_insertable"),

    ("a TTL column is added to the brakes table",
     [(MIG, "            signal_count INTEGER NOT NULL DEFAULT 1,",
       "            signal_count INTEGER NOT NULL DEFAULT 1,\n            ttl_seconds INTEGER,  -- MUTANT")],
     f"{T}::test_no_ttl_or_expiry_column_on_either_brake_table"),

    ("the released_by foreign key is dropped",
     [(MIG, "            CHECK (signal_count >= 1),\n            FOREIGN KEY (tenant, released_by) REFERENCES tenant_humans (tenant, human_id)",
       "            CHECK (signal_count >= 1)  -- MUTANT dropped released_by FK")],
     f"{T}::test_a_releaser_who_is_not_a_recorded_human_is_refused"),

    ("the platform row gains a tenant column",
     [(MIG, "            state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED')),\n            brake_version INTEGER NOT NULL,\n            actor TEXT,",
       "            state TEXT NOT NULL CHECK (state IN ('ACTIVE','RELEASED')),\n            brake_version INTEGER NOT NULL,\n            tenant TEXT,  -- MUTANT\n            actor TEXT,")],
     f"{T}::test_the_platform_brake_has_no_tenant_column"),

    ("multiple platform rows are allowed",
     [(MIG, "            id INTEGER PRIMARY KEY CHECK (id = 1),",
       "            id INTEGER PRIMARY KEY CHECK (id >= 1),  -- MUTANT")],
     f"{T}::test_the_platform_brake_is_exactly_one_row_structurally"),

    ("the brakes delete-refusing trigger is defanged",
     [(MIG, "BEFORE DELETE ON brakes\n        BEGIN SELECT RAISE(ABORT, '{BRAKE_DELETE_ABORT}'); END",
       "BEFORE DELETE ON brakes\n        BEGIN SELECT 1; END  -- MUTANT")],
     f"{T}::test_a_brake_row_is_never_deleted"),

    ("the platform delete-refusing trigger is defanged",
     [(MIG, "BEFORE DELETE ON platform_brake\n        BEGIN SELECT RAISE(ABORT, '{PLATFORM_BRAKE_DELETE_ABORT}'); END",
       "BEFORE DELETE ON platform_brake\n        BEGIN SELECT 1; END  -- MUTANT")],
     f"{T}::test_the_platform_brake_row_is_never_deleted"),

    ("the rising signal count is suppressed",
     [(BR, '"UPDATE brakes SET signal_count = signal_count + 1 "',
       '"UPDATE brakes SET signal_count = signal_count + 0 "  # MUTANT')],
     f"{T}::test_the_signal_count_rises_on_repeated_engagement_by_row"),

    ("automation may release a brake",
     [(BL, 'id="BR-4", from_state="ACTIVE", to_state="RELEASED",\n        actors=frozenset({HUMAN_CLASS}),',
       'id="BR-4", from_state="ACTIVE", to_state="RELEASED",\n        actors=frozenset({HUMAN_CLASS, AUTOMATION_CLASS}),  # MUTANT')],
     f"{T}::test_automation_can_engage_but_never_release"),

    ("a detector may narrow a brake",
     [(BL, 'id="BR-3", from_state="ACTIVE", to_state="ACTIVE",   # narrower scope (broadens authority)\n        actors=frozenset({HUMAN_CLASS}),',
       'id="BR-3", from_state="ACTIVE", to_state="ACTIVE",   # narrower scope (broadens authority)\n        actors=frozenset({HUMAN_CLASS, DETECTOR_CLASS}),  # MUTANT')],
     f"{T}::test_only_a_human_may_narrow"),

    ("a model may engage a brake",
     [(BL, 'id="BR-1", from_state=None, to_state="ACTIVE",\n        actors=frozenset({HUMAN_CLASS, DETECTOR_CLASS, AUTOMATION_CLASS}),',
       'id="BR-1", from_state=None, to_state="ACTIVE",\n        actors=frozenset({HUMAN_CLASS, DETECTOR_CLASS, AUTOMATION_CLASS, MODEL_CLASS}),  # MUTANT')],
     f"{T}::test_a_model_may_never_engage_narrow_or_release"),

    ("a loaded page is accepted as positive health",
     [(BL, '    if proof.get("kind") != "positive_control":\n        return False\n    return bool(proof.get("verified"))',
       '    return True  # MUTANT accepts any proof as positive health')],
     f"{T}::test_a_loaded_page_is_not_a_positive_health_proof"),

    ("release stops requiring in-flight effects accounted for",
     [(BL, '    if not evidence.get("in_flight_accounted"):\n        return False',
       '    if False and not evidence.get("in_flight_accounted"):  # MUTANT\n        return False')],
     f"{T}::test_an_unaccounted_in_flight_effect_blocks_release"),

    ("release lets an unresolved Sev-0 pass",
     [(BL, '    if evidence.get("unresolved_sev0"):\n        return False',
       '    if False and evidence.get("unresolved_sev0"):  # MUTANT\n        return False')],
     f"{T}::test_an_unresolved_sev0_blocks_release"),

    ("the claim CAS stops revalidating the brake version",
     [(CP, "AND expires_at > ? AND brake_version = ? AND policy_version = ?",
       "AND expires_at > ? AND policy_version = ?  -- MUTANT dropped brake_version")],
     f"{T}::test_the_claim_cas_revalidates_the_composite_brake_token"),

    ("an unreadable brake store reads as off",
     [(BR, '        except sqlite3.Error as exc:\n            raise BrakeStoreUnreachable(f"brake state could not be read: {exc}") from exc',
       '        except sqlite3.Error:  # MUTANT allow-on-error\n            return None')],
     f"{T}::test_fail_closed_on_unreadable_brake"),

    ("an active brake is hidden from the operator report",
     [(BL, "def reports_unprompted_when_active() -> bool:\n    return True",
       "def reports_unprompted_when_active() -> bool:\n    return False  # MUTANT")],
     f"{T}::test_the_report_is_produced_unprompted_when_active"),

    ("a second unauthorized-release contract synonym is introduced",
     [(BL, 'UNAUTHORIZED_RELEASE_CONTRACT = "UnauthorizedBrakeReleaseAttempted"',
       'UNAUTHORIZED_RELEASE_CONTRACT = "UnauthorizedBrakeReleaseAttempted"\nBrakeReleaseRefused = "brake-release-refused"  # MUTANT synonym')],
     f"{T}::test_an_unauthorized_release_emits_the_registered_f14_and_no_synonym"),
]

# Anti-vacuity control: NOT mutated; a representative guard must be GREEN.
CONTROL_GUARD = f"{T}::test_readiness_is_clean_on_a_fresh_canonical_database"


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
