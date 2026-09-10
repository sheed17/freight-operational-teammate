#!/usr/bin/env python3
"""P7 (Evidence) mutation battery.

Each mutant reintroduces a defect whose prohibition is canonically established (entity 08-evidence,
ADR-002 sec 2.3, ADR-007), and each must turn its guard test RED for the intended reason. The count
is DERIVED (len(CASES)), never hard-coded. Originals are held in memory and restored unconditionally;
__pycache__ is purged around every run; git is never used to undo a mutation (CLAUDE.md sec 6). An
anti-vacuity control — an unmutated representative guard that must stay GREEN — makes the count a
measurement, not an assertion.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

EV = "src/freight_recon/evidence.py"
MIG = "src/freight_recon/migrations/phase7_evidence.py"
T = "eval/tests/test_phase7_evidence.py"

_SENTINEL = "MUTANT"

# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Each anchor must appear EXACTLY
# once. Every new_text embeds the sentinel so a stranded mutation is detectable.
CASES = [
    ("the content-addressing index drops UNIQUE (dedup off)",
     [(MIG,
       '        "CREATE UNIQUE INDEX ix_evidence_content_addressing "\n'
       '        "ON evidence (tenant, content_digest)",',
       '        "CREATE INDEX ix_evidence_content_addressing "  # MUTANT dropped UNIQUE\n'
       '        "ON evidence (tenant, content_digest)",')],
     f"{T}::test_the_content_addressing_index_is_unique_and_covers_tenant_and_digest"),

    ("content_digest becomes editable (dropped from the immutability trigger)",
     [(MIG,
       "BEFORE UPDATE OF tenant, evidence_id, content_digest, content_ref, media_type,",
       "BEFORE UPDATE OF tenant, evidence_id, content_ref, media_type,  -- MUTANT dropped content_digest")],
     f"{T}::test_evidence_content_is_immutable"),

    ("the evidence no-delete trigger is defanged",
     [(MIG,
       "BEFORE DELETE ON evidence\n        BEGIN SELECT RAISE(ABORT, '{EVIDENCE_DELETE_ABORT}'); END",
       "BEFORE DELETE ON evidence\n        BEGIN SELECT 1; END  -- MUTANT")],
     f"{T}::test_evidence_content_is_immutable"),

    ("the digest-mismatch check is disabled (a lying digest is accepted)",
     [(EV,
       "        if expected_digest is not None and expected_digest != digest:",
       "        if False and expected_digest is not None and expected_digest != digest:  # MUTANT")],
     f"{T}::test_digest_mismatch_rejected_on_write"),

    ("the MODEL_EXTRACTED span requirement is disabled",
     [(EV,
       "        if not self.spans_for(tenant, evidence_id):",
       "        if False and not self.spans_for(tenant, evidence_id):  # MUTANT")],
     f"{T}::test_model_extracted_claim_requires_evidence_span"),

    ("absent evidence reads as consistent (fail-open on lost)",
     [(EV,
       "        if record is None:\n            return CONDITION_ABSENT",
       "        if record is None:\n            return CONDITION_CONSISTENT  # MUTANT fail-open on absent")],
     f"{T}::test_lost_evidence_blocks_consequential_action"),

    ("illegible evidence reads as consistent (fail-open on illegible)",
     [(EV,
       "        if record.illegible:\n            return CONDITION_ILLEGIBLE",
       "        if False and record.illegible:  # MUTANT fail-open on illegible\n            return CONDITION_ILLEGIBLE")],
     f"{T}::test_lost_evidence_blocks_consequential_action"),

    ("the tenant predicate is dropped from an Evidence read (cross-tenant leak)",
     [(EV,
       '            "FROM evidence WHERE tenant = ? AND evidence_id = ?",\n'
       "            (tenant, evidence_id),",
       '            "FROM evidence WHERE evidence_id = ?",  # MUTANT dropped tenant predicate\n'
       "            (evidence_id,),")],
     f"{T}::test_cross_tenant_evidence_isolation"),

    ("evidence gains a provenance_class column (Evidence sets provenance)",
     [(MIG,
       "            created_at TEXT NOT NULL,\n\n            PRIMARY KEY (tenant, evidence_id),",
       "            created_at TEXT NOT NULL,\n            provenance_class TEXT,  -- MUTANT Evidence sets no provenance\n\n            PRIMARY KEY (tenant, evidence_id),")],
     f"{T}::test_evidence_is_data_it_carries_no_provenance_and_no_lifecycle"),
]

# Anti-vacuity control: NOT mutated; a representative guard must be GREEN.
CONTROL_GUARD = f"{T}::test_the_evidence_layer_landed_tenant_first_and_in_the_canonical_set"


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
