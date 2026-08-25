#!/usr/bin/env python3
"""M6 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the Identity Binding Claim machine exists to prevent —
a model guess that gets confirmed, a confidence threshold that authorizes, an OWNER_ASSERTED binding
the relinker overwrites (the B3 regression), a single weak candidate that auto-binds, a provenance a
caller can choose or edit, a MODEL_EXTRACTED claim with no evidence span, two CONFIRMED bindings for
one subject, a human ordinal that falls back to position, an inferrer that picks itself the winner, a
cross-tenant read, a correction that names no effect for compensation, a replay that re-derives an
owner's provenance — and names the guard that must turn RED under it. A mutant that no test catches is
a hole with a passing status; a mutant that does not reintroduce the real defect proves nothing.

It mutates TEXT and shells out to pytest; it NEVER imports the claim machine, and it NEVER uses git to
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

M6 = "src/freight_recon/identity_binding_claim.py"
MIG = "src/freight_recon/migrations/phase6_identity_binding_claims.py"
T = "eval/tests/test_phase6_identity_binding_claim.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider",
                        "-p", "no:randomly"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Each anchor must appear EXACTLY ONCE.
CASES = [
    ("a MODEL_INFERRED guess is allowed to CONFIRM — the IB-4 routing guard is inverted and the "
     "CONFIRMED-provenance CHECK is widened, so a guess becomes a canonical binding (entity §37, GR-8)",
     [(M6,
       '    if method is MatchMethod.MODEL_INFER:\n        return "AMBIGUOUS", "model_inferred"',
       '    if method is MatchMethod.MODEL_INFER:\n        return "CONFIRMED", None  # MUTANT'),
      (MIG,
       'CONFIRMED_ALLOWED_PROVENANCE: tuple[str, ...] = ("LINKER_INFERRED", "RECONCILED", "OWNER_ASSERTED")',
       'CONFIRMED_ALLOWED_PROVENANCE: tuple[str, ...] = ("LINKER_INFERRED", "RECONCILED", "OWNER_ASSERTED", "MODEL_INFERRED")  # MUTANT')],
     f"{T}::test_guess_never_confirms_at_confidence_1_0"),

    ("a confidence THRESHOLD is used as a confirmation guard — the `if confidence > 0.98` defeat "
     "ADR-007 §8 names by hand, so a high-confidence guess confirms",
     [(M6,
       "    method = attempt.match_method\n    if method is MatchMethod.MODEL_INFER:",
       "    method = attempt.match_method\n    if attempt.confidence is not None and attempt.confidence > 0.98:\n        return \"CONFIRMED\", None  # MUTANT confidence gate\n    if method is MatchMethod.MODEL_INFER:"),
      (MIG,
       'CONFIRMED_ALLOWED_PROVENANCE: tuple[str, ...] = ("LINKER_INFERRED", "RECONCILED", "OWNER_ASSERTED")',
       'CONFIRMED_ALLOWED_PROVENANCE: tuple[str, ...] = ("LINKER_INFERRED", "RECONCILED", "OWNER_ASSERTED", "MODEL_INFERRED")  # MUTANT')],
     f"{T}::test_guess_never_confirms_at_confidence_1_0"),

    ("the IB-5x provenance guard is dropped — the relinker OVERWRITES an OWNER_ASSERTED binding "
     "(the B3 regression, GR-9, R-P3)",
     [(M6,
       "        if claim.is_owner_asserted:",
       "        if False and claim.is_owner_asserted:  # MUTANT")],
     f"{T}::test_owner_binding_survives_relinker"),

    ("the IB-4 weak-candidate guard is removed — a single WEAK candidate AUTO-CONFIRMS instead of "
     "failing to a human (M-17)",
     [(M6,
       '    if attempt.weak:\n        return "AMBIGUOUS", "single_weak"',
       '    if False and attempt.weak:  # MUTANT\n        return "AMBIGUOUS", "single_weak"')],
     f"{T}::test_single_weak_candidate_is_still_ambiguous"),

    ("the SD-6 mapping CHECK is widened to always-true — a caller can choose a provenance off the "
     "function (entity §13, ADR-002 R-P2)",
     [(MIG,
       "            CHECK (%(sd6)s),",
       "            CHECK (1 = 1 OR %(sd6)s),")],
     f"{T}::test_sd6_mismatched_insert_is_refused"),

    ("the provenance_class immutability trigger is defanged — provenance can be EDITED in place "
     "instead of a new claim being made (entity §13 SD-6, R-P2)",
     [(MIG,
       "        BEGIN SELECT RAISE(ABORT, '{PROVENANCE_CLASS_ABORT}'); END",
       "        BEGIN SELECT 1; END")],
     f"{T}::test_provenance_class_cannot_be_edited"),

    ("the MODEL_EXTRACTED evidence-span CHECK is widened to always-true — a MODEL_EXTRACTED claim "
     "with no span becomes writable (entity §16/§37)",
     [(MIG,
       "            CHECK (provenance_class <> 'MODEL_EXTRACTED' OR (evidence_id IS NOT NULL AND span IS NOT NULL)),",
       "            CHECK (1 = 1 OR provenance_class <> 'MODEL_EXTRACTED' OR (evidence_id IS NOT NULL AND span IS NOT NULL)),  -- MUTANT")],
     f"{T}::test_model_extracted_requires_evidence_span"),

    ("the one-CONFIRMED-per-subject index loses UNIQUE — two CONFIRMED bindings for one subject "
     "become insertable (entity §17)",
     [(MIG,
       '        "CREATE UNIQUE INDEX ix_ibc_one_confirmed_per_subject "',
       '        "CREATE INDEX ix_ibc_one_confirmed_per_subject "')],
     f"{T}::test_a_direct_second_confirmed_insert_is_refused_by_the_partial_index"),

    ("the ordinal slot-change guard is removed and the bind falls back to POSITION — a human action "
     "whose slot moved binds the new occupant instead of failing closed (L-B)",
     [(M6,
       "            if idx < 0 or idx >= len(current) or current[idx] != resolved:",
       "            if False and (idx < 0 or idx >= len(current) or current[idx] != resolved):  # MUTANT"),
      (M6,
       "            return resolved\n        subject = str(subject_ref or \"\").strip()",
       "            return current[idx] if 0 <= idx < len(current) else resolved  # MUTANT\n        subject = str(subject_ref or \"\").strip()")],
     f"{T}::test_ordinal_binding_resolves_to_immutable_id_or_fails_closed"),

    ("IB-6 is turned into an OVERWRITE — the inferrer disagreeing with the owner supersedes the owner "
     "binding instead of raising a conflict (ADR-007 §4.3; Neyma does not pick a winner)",
     [(M6,
       "\"UPDATE identity_binding_claims SET state = 'CONFLICTING', version = version + 1, \"",
       "\"UPDATE identity_binding_claims SET state = 'SUPERSEDED', version = version + 1, \"  # MUTANT")],
     f"{T}::test_inferrer_vs_owner_raises_conflict_not_a_winner"),

    ("the tenant predicate is dropped from the claim read — one tenant reads another's binding "
     "([C-1])",
     [(M6,
       '            "SELECT * FROM identity_binding_claims WHERE tenant = ? AND binding_claim_id = ?",',
       '            "SELECT * FROM identity_binding_claims WHERE (tenant = ? OR 1=1) AND binding_claim_id = ?",  # MUTANT')],
     f"{T}::test_cross_tenant_read_is_isolated"),

    ("the correction fails to name the completed effects — the propagation obligation is written but "
     "carries NO effects for compensation (ADR-007 §6, M-20)",
     [(M6,
       '            "completed_effects_needing_compensation": list(completed_effects),',
       '            "completed_effects_needing_compensation": [],  # MUTANT')],
     f"{T}::test_correction_propagates_a_compensation"),

    ("the replay RE-DERIVES provenance instead of reading it from the event — an OWNER_ASSERTED "
     "binding is rebuilt as LINKER_INFERRED (ADR-007 §7: a rebuild rebuilds projections, not the "
     "owner's mind)",
     [(M6,
       "                provenance = carried",
       "                provenance = \"LINKER_INFERRED\"  # MUTANT: re-derived, not from the event")],
     f"{T}::test_replay_preserves_owner_asserted_byte_identical"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, old, new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        if path not in originals:
            originals[path] = path.read_bytes()
        text = originals[path].decode("utf-8")
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


def main() -> int:
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    print("\n=========== P6 M6 IDENTITY BINDING CLAIM MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
