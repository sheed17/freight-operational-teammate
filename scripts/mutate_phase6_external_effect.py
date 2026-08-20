#!/usr/bin/env python3
"""M3 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the External Effect / Effect Grant machine exists to
prevent — FAILED without proof, VERIFIED without a matching positive control, an UNKNOWN_OUTCOME with
no named human, a timer that moves an UNKNOWN_OUTCOME, a forged handle laundered into an ordinary
refusal, a ledger whose witness FK is gone — and names the guard that must turn RED under it. A
mutant that no test catches is a hole with a passing status.

It mutates TEXT and shells out to pytest; it NEVER imports the module under test, and it NEVER uses
git to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is
purged around every run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv/bin/python")

M3 = "src/freight_recon/external_effect.py"
MIG = "src/freight_recon/migrations/phase6_external_effects.py"
T = "eval/tests/test_phase6_external_effect.py"
TS = "eval/tests/test_u26bc_schema_readiness.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:randomly"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, rel_path, old_anchor, new_text, guard_nodeid). Each anchor must appear EXACTLY ONCE.
TEXT_CASES = [
    ("EF-3f accepts FAILED with NO proof of non-occurrence — a timeout wearing a resolution, and a "
     "retry that pays load 4471's invoice twice",
     M3,
     '            if not proof:\n                # ### GR-5 AT THE ROW: FAILED REQUIRES AFFIRMATIVE',
     '            if not proof and False:  # MUTANT\n                # ### GR-5 AT THE ROW: FAILED REQUIRES AFFIRMATIVE',
     f"{T}::test_FAILED_without_proof_is_refused_not_persisted"),

    ("EF-4 stops requiring the readback to MATCH the approved fingerprint — VERIFIED without a "
     "positive control, so a mis-sent invoice is recorded as success",
     M3,
     '            if not approved or matched != approved:',
     '            if not approved or (matched != approved and False):  # MUTANT',
     f"{T}::test_a_verified_requires_a_matching_fingerprint"),

    ("EF-3u/EF-4c/EF-4u create an UNKNOWN_OUTCOME with NO named human — the one obligation nobody "
     "owes (rule 13)",
     M3,
     '        if to_state in HUMAN_OWNED_STATES:\n            self._require_active_human(facts.accountable_owner_id, row.id)',
     '        if to_state in HUMAN_OWNED_STATES and False:  # MUTANT\n            self._require_active_human(facts.accountable_owner_id, row.id)',
     f"{T}::test_UNKNOWN_OUTCOME_cannot_be_created_without_a_named_active_human"),

    ("EF-5x stops being ILLEGAL — a timer is allowed to move an UNKNOWN_OUTCOME (GR-6), quietly "
     "turning we-do-not-know into a resolution",
     M3,
     '        id="EF-5x", from_states=(EffectGrantState.UNKNOWN_OUTCOME,), to_state=None,\n        triggers=(Trigger.TIMER_FIRED,), trigger_types=("T",),\n        kind=RowKind.NON_PRODUCING, illegal=True,',
     '        id="EF-5x", from_states=(EffectGrantState.UNKNOWN_OUTCOME,), to_state=None,\n        triggers=(Trigger.TIMER_FIRED,), trigger_types=("T",),\n        kind=RowKind.NON_PRODUCING, illegal=False,  # MUTANT',
     f"{T}::test_no_timer_moves_an_UNKNOWN_OUTCOME"),

    ("a CONFUSED_DEPUTY (wrong-target) claim is laundered into an ordinary ClaimRefused instead of a "
     "Sev-0 — an attack recorded as routine",
     M3,
     '    "POLICY_CHANGED": "policy",\n}',
     '    "POLICY_CHANGED": "policy",\n    "CONFUSED_DEPUTY": "already_claimed",  # MUTANT\n}',
     f"{T}::test_a_wrong_target_claim_is_a_confused_deputy_sev0"),

    ("the claim stops emitting EffectAttempted before the call — a claimed effect whose attempt was "
     "never recorded, so a lost response is undetectable",
     M3,
     '        self._outbox().emit(attempted_env)',
     '        _ = attempted_env  # MUTANT: not emitted',
     f"{T}::test_the_claim_is_atomic_never_both_never_neither"),

    ("EF-3 emits a SECOND EffectAttempted — a double effect on the audit stream",
     M3,
     '        kind=RowKind.PRODUCER, events=("EffectExecuted",), consequential=True,',
     '        kind=RowKind.PRODUCER, events=("EffectExecuted", "EffectAttempted"), consequential=True,  # MUTANT',
     f"{T}::test_EffectAttempted_is_emitted_exactly_once_across_the_whole_lifecycle"),

    ("the strict-order consumer stops advancing over an SD-3 pin — a legitimately drained "
     "verification re-parks forever (P6-D24)",
     M3,
     '        if aggregate_type != AGGREGATE_TYPE:\n            return True',
     '        if aggregate_type != AGGREGATE_TYPE:\n            return False  # MUTANT',
     f"{T}::test_a_verification_parks_on_its_unapplied_predecessor_and_drains_when_it_lands"),

    ("the ledger loses its foreign key into checkpoint_witnesses — 'mint requires a real witness' "
     "becomes decoration a string satisfies",
     MIG,
     'REFERENCES checkpoint_witnesses ',
     'REFERENCES pipeline_instances ',
     f"{TS}::test_1_fresh_canonical_database_is_ready"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, old, new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        text = path.read_bytes().decode("utf-8")
        if text.count(old) != 1:
            return "SETUP-FAIL", f"anchor appears {text.count(old)}x in {rel} (need exactly 1)"
        if text.replace(old, new, 1) == text:
            return "SETUP-FAIL", f"mutation was a no-op in {rel}"

    purge_pycache()
    if not run_guard(guard):
        return "SETUP-FAIL", "guard already RED before mutation"

    try:
        for rel, old, new in edits:
            path = ROOT / rel
            originals[path] = path.read_bytes()
            path.write_text(originals[path].decode("utf-8").replace(old, new, 1), encoding="utf-8")
        purge_pycache()
        caught = not run_guard(guard)
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


def _run_text_case(case) -> tuple[str, str]:
    _, rel, old, new, guard = case
    return _run_edits(((rel, old, new),), guard)


def main() -> int:
    results = [(c[0], *_run_text_case(c)) for c in TEXT_CASES]
    print("\n=========== P6 M3 EXTERNAL EFFECT / EFFECT GRANT MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
