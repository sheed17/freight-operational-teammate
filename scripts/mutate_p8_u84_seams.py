#!/usr/bin/env python3
"""P8 / U8.4 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect in one of U8.4's NEW load-bearing seams — the RULE
decision_ref resolver accepting a non-ACTIVE rule, the resolver leaking across tenants, the OVERDUE/
INDETERMINATE honesty split converting blindness into counterparty fault, the escalation owner no longer
re-checked ACTIVE, a CompensationFailed escalation gone quiet or losing its exposure, a CompensationRefused
escalated in violation of M-33, and the (source_ref, type) coalesce dropped so one cause makes two open
Exceptions — and names the guard that must turn RED under it. A mutant no test catches is a hole with a
passing status; a mutant that does not reintroduce the real defect proves nothing.

It mutates TEXT and shells out to pytest; it NEVER imports the machines, and it NEVER uses git to undo a
mutation. Originals are held in memory and restored unconditionally; `__pycache__` is purged around every
run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

M1 = "src/freight_recon/work_item.py"
M9 = "src/freight_recon/exception.py"
WORK = "eval/tests/test_phase6_work_item.py"
U84 = "eval/tests/test_p8_u84_seams.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Each anchor must appear EXACTLY ONCE.
CASES = [
    ("the RULE resolver accepts a NON-ACTIVE rule — the ACTIVE gate is short-circuited, so a COMPILED "
     "rule would 'close by an active rule' that is not in force (K-1, AC-SAFE-024)",
     [(M1, 'if rule_state != "ACTIVE":', "if False:  # MUTANT")],
     f"{WORK}::test_a_rule_kind_decision_ref_resolves_only_against_an_active_m12_rule"),

    ("the RULE resolver leaks across tenants — the tenant predicate is widened to always-true, so an "
     "ACTIVE rule of another brokerage resolves here ([C-1])",
     [(M1, "SELECT state FROM rules WHERE tenant = ? AND rule_id = ?",
       "SELECT state FROM rules WHERE (tenant = ? OR 1=1) AND rule_id = ?")],
     f"{WORK}::test_a_rule_ref_active_in_another_tenant_refuses_here"),

    ("the honesty split is broken — the INDETERMINATE question drops 'NOT the counterparty's fault', "
     "converting OUR blindness into a counterparty accusation (I8, M-32)",
     [(M9, "blindness, NOT the counterparty's fault", "blindness, and the counterparty's fault")],
     f"{U84}::test_indeterminate_never_converts_blindness_into_counterparty_fault"),

    ("the escalation owner is no longer re-checked ACTIVE — a deactivated source owner would own the "
     "escalation Exception instead of failing closed (AC-RACE-016)",
     [(M9,
       'owner = self._require_named_human(\n'
       '                event.accountable_owner_id, "the escalation owner", actor_kind="system")',
       "owner = event.accountable_owner_id  # MUTANT: skip the ACTIVE re-check")],
     f"{U84}::test_owner_deactivation_during_escalation_fails_closed_then_recovers"),

    ("a CompensationFailed escalation goes QUIET — SEV0 is lowered to SEV2, so the loudest state in the "
     "system stops being loud (entity §42)",
     [(M9, 'type="compensation_failed", source_kind="compensation", severity="SEV0"',
       'type="compensation_failed", source_kind="compensation", severity="SEV2"')],
     f"{U84}::test_compensation_failed_escalates_once_with_owner_and_exposure"),

    ("a compensation escalation LOSES its exposure — the money at stake is dropped from the Exception, "
     "so the human is asked about a divergence with no amount (entity §42, K-4)",
     [(M9, "exposure=spec.exposure,", "exposure=None,  # MUTANT")],
     f"{U84}::test_compensation_failed_escalates_once_with_owner_and_exposure"),

    ("M-33 is violated — CompensationRefused (UNKNOWN_OUTCOME) now escalates to M9, inventing a second "
     "resolution path for an owner that already lives upstream on the effect grant",
     [(M9,
       '"how to make reality right — no timer, retry or model resolves this."),\n'
       "            exposure=payload.get(\"exposure\"))\n"
       "    return None",
       '"how to make reality right — no timer, retry or model resolves this."),\n'
       "            exposure=payload.get(\"exposure\"))\n"
       '    return _EscalationSpec(type="leak", source_kind="compensation", severity="SEV0", '
       'summary="leaked", question="leaked", exposure=None)  # MUTANT')],
     f"{U84}::test_unknown_outcome_refusal_is_not_escalated_by_m9_m33"),

    ("the (source_ref, type) coalesce is dropped — a second escalation for one cause is no longer "
     "recognised, so an EXPIRED after an open OVERDUE makes two rows for one expectation (entity §14/§17)",
     [(M9, "existing = self.open_exception_for(source, etype)", "existing = None  # MUTANT")],
     f"{U84}::test_same_source_different_event_coalesces_to_one_open_exception"),

    ("the escalation consumer's dedup identity is made non-stable — a per-call consumer_id re-arms "
     "every duplicate, so a REDELIVERED source event is consumed afresh instead of a DUPLICATE_NOOP "
     "(M-24; the inbox dedup key is (tenant, consumer_id, event_id))",
     [(M9, "consumer_id=SOURCE_ESCALATION_CONSUMER_ID,",
       "consumer_id=SOURCE_ESCALATION_CONSUMER_ID + uuid.uuid4().hex,  # MUTANT")],
     f"{U84}::test_redelivered_expectation_event_raises_no_second_exception"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, old, new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        if path not in originals:
            originals[path] = path.read_bytes()

    for rel, old, new in edits:
        path = ROOT / rel
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
    print("\n=========== P8 U8.4 SEAM MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
