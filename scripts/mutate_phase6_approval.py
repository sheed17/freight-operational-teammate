#!/usr/bin/env python3
"""M4 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the Approval machine exists to prevent — a drifted
fact that executes, the swap-the-evidence-keep-the-number laundering route, an unreadable source read
as no-drift, a GRANTED approval with no human, two live approvals for one effect, a double tap that
raises or double-consumes, a state written without its event, a replayed token accepted, a
cross-tenant read — and names the guard that must turn RED under it. A mutant that no test catches is
a hole with a passing status; a mutant that does not reintroduce the real defect proves nothing.

It mutates TEXT and shells out to pytest; it NEVER imports the approval machine, and it NEVER uses
git to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is
purged around every run so a same-length restore cannot leave poisoned bytecode and a false green.

### TWO MUTANTS TOUCH `checkpoint.py`, AND THAT IS DELIBERATE. Provenance and evidence-condition live
INSIDE the fp_v1 canonical payload M4 CONSUMES (`checkpoint._fingerprint_facts`), not in a copy M4
owns. Dropping them there and running M4's provenance/evidence drift guards proves M4's drift
detection genuinely rests on those fields being in the fingerprint — the real laundering defect
ADR-005 §3.3/§7 names. The originals are restored byte-for-byte and the guard is re-run green after.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The interpreter running THIS script — `.venv/bin/python` locally, the runner's Python under CI —
# so the battery is runnable on a fresh checkout with no local venv (the M3 correction, kept).
PY = sys.executable

M4 = "src/freight_recon/approval.py"
MIG = "src/freight_recon/migrations/phase6_approvals.py"
CHK = "src/freight_recon/checkpoint.py"
T = "eval/tests/test_phase6_approval.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider",
                        "-p", "no:randomly"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, rel_path, old_anchor, new_text, guard_nodeid). Each anchor must appear EXACTLY ONCE.
TEXT_CASES = [
    ("check_drift stops comparing the live fingerprint to the approved one — a drifted £3,100 "
     "executes against a £2,850 approval (ADR-005 F-01)",
     M4,
     "if current_fp != approval.material_facts_fingerprint:",
     "if False and current_fp != approval.material_facts_fingerprint:  # MUTANT",
     f"{T}::test_F01_approve_2850_then_tms_moves_to_3100_no_effect_occurs"),

    ("provenance_class leaves the canonical payload — the same number believed for a different "
     "reason no longer voids (the swap-the-evidence-keep-the-number laundering route, ADR-005 §3.3)",
     CHK,
     '"provenance": fact.provenance,',
     '"provenance": "system_imported",  # MUTANT',
     f"{T}::test_same_amount_changed_provenance_voids"),

    ("evidence_condition leaves the canonical payload — a degradation from consistent to stale no "
     "longer voids (ADR-005 §3.14)",
     CHK,
     '"evidence": fact.evidence_condition,',
     '"evidence": "consistent",  # MUTANT',
     f"{T}::test_evidence_condition_degradation_voids"),

    ("check_drift reads an unreadable source as no-drift — money executes against a source we could "
     "not read (ADR-005 §3.12)",
     M4,
     '        except SourceUnreadable as exc:\n'
     '            raise SourceUnreadable(\n'
     '                f"AP-4 re-read of {approval_id!r}\'s material facts failed ({exc}); an unreadable "\n'
     '                f"source is not \'no drift\'. The approval stays GRANTED and does not execute.") from exc',
     '        except SourceUnreadable:\n'
     '            return DriftOutcome(drifted=False, approval_id=approval_id)  # MUTANT: read as no-drift',
     f"{T}::test_unreadable_source_fails_closed"),

    ("the granted_by CHECK is relaxed — a GRANTED approval with no human becomes writable (entity "
     "§37: the one structurally impossible state)",
     MIG,
     "CHECK (state <> 'GRANTED' OR granted_by IS NOT NULL),",
     "CHECK (1 = 1 OR granted_by IS NOT NULL),  -- MUTANT",
     f"{T}::test_granted_by_check_is_enforced"),

    ("the live-approval index loses UNIQUE — two live approvals for one commit key both insert "
     "(entity §17)",
     MIG,
     "CREATE UNIQUE INDEX ix_approvals_live_per_commit_key ",
     "CREATE INDEX ix_approvals_live_per_commit_key ",
     f"{T}::test_at_most_one_live_approval_per_commit_key"),

    ("the double-tap short-circuit is removed — the second tap reaches the CAS and RAISES instead "
     "of replying 'already done' (ADR-005 §3.15)",
     M4,
     "if approval.state is ApprovalState.CONSUMED:",
     "if False and approval.state is ApprovalState.CONSUMED:  # MUTANT",
     f"{T}::test_double_tap_is_idempotent_not_an_error"),

    ("the consume commits the state without emitting ApprovalConsumed — a consumed approval with no "
     "event (GR-2 co-commit broken)",
     M4,
     "            self._outbox().emit(envelope)\n"
     "            conn.commit()\n"
     "            flush_claim_records(kern, pending)",
     "            conn.commit()  # MUTANT: state committed without its ApprovalConsumed event\n"
     "            flush_claim_records(kern, pending)",
     f"{T}::test_consume_co_commits_its_event"),

    ("the transport token single-use check is removed — a replayed callback passes at the transport "
     "(ADR-005 §3.15 layer 1)",
     M4,
     "if token.mac in self._spent_tokens:",
     "if False and token.mac in self._spent_tokens:  # MUTANT",
     f"{T}::test_replayed_transport_token_is_refused"),

    ("the tenant predicate is dropped from the approval read — one tenant reads another's approval "
     "([C-1])",
     M4,
     '"SELECT * FROM approvals WHERE tenant = ? AND approval_id = ?",',
     '"SELECT * FROM approvals WHERE (tenant = ? OR 1=1) AND approval_id = ?",  # MUTANT',
     f"{T}::test_tenant_isolation_no_cross_tenant_read"),
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
    print("\n=========== P6 M4 APPROVAL MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
