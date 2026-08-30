#!/usr/bin/env python3
"""M9 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the Exception machine exists to prevent — an ownerless
obligation, a cross-tenant owner, a sixth lifecycle state, a sub_status promoted to a state, a RESOLVED
row with no decision, a decision_ref resolver weakened to a non-null check, a model resolving, an
AutoClose, a resolved exception deleted, a timer that resolves, a background sweep, a dropped
previous_severity, a replay that reads the live row, a dropped tenant, a freeze with nothing to block, an
M10 table, M9 made a gate minter, M9 made a brake engager, a PERMANENT failure retried, permanence
inferred from a message, and a production importer that breaks the ship-dark posture — and names the
guard that must turn RED under it. A mutant that no test catches is a hole with a passing status; a
mutant that does not reintroduce the real defect proves nothing.

It mutates TEXT and shells out to pytest; it NEVER imports the exception machine, and it NEVER uses git
to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is purged
around every run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

M9 = "src/freight_recon/exception.py"
MIG = "src/freight_recon/migrations/phase6_exceptions.py"
SCHEMA = "src/freight_recon/schema.py"
T = "eval/tests/test_phase6_exception.py"


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
    ("the owner NOT NULL is dropped from creation — an ownerless Exception becomes insertable (entity "
     "§16/§37, I1, AC-SAFE-028)",
     [(MIG, "            owner_id TEXT NOT NULL,", "            owner_id TEXT,  -- MUTANT")],
     f"{T}::test_ownerless_exception_impossible"),

    ("an owner from another tenant is permitted — the tenant predicate on the named-human guard is "
     "widened to always-true ([C-1])",
     [(M9,
       '"SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?"',
       '"SELECT state FROM tenant_humans WHERE (tenant = ? OR 1=1) AND human_id = ?"  # MUTANT')],
     f"{T}::test_cross_tenant_owner_fails_closed"),

    ("a sixth lifecycle state is added — the frozen five gain a CLOSED, and entity §26/machine §14 say "
     "none exists (registry §4)",
     [(MIG,
       '    "OPEN", "ACKNOWLEDGED", "AGEING", "ESCALATED", "RESOLVED",',
       '    "OPEN", "ACKNOWLEDGED", "AGEING", "ESCALATED", "RESOLVED", "CLOSED",  # MUTANT')],
     f"{T}::test_the_five_canonical_states_and_no_sixth"),

    ("a sub_status is promoted to a lifecycle state — the sub_status vocabulary gains a state name, so "
     "the two are no longer DISJOINT (machine header)",
     [(MIG, '    "resolution_proposed",', '    "resolution_proposed", "OPEN",  # MUTANT')],
     f"{T}::test_sub_status_is_a_field_never_a_lifecycle_state"),

    ("RESOLVED is allowed with no decision_ref — the entity §16 structural CHECK is widened to "
     "always-true, so an exception closed without a decision is insertable (GR-14, F-30)",
     [(MIG,
       "CHECK (state <> 'RESOLVED' OR decision_ref IS NOT NULL),",
       "CHECK (1 = 1 OR state <> 'RESOLVED' OR decision_ref IS NOT NULL),  -- MUTANT")],
     f"{T}::test_db_resolved_requires_decision_ref"),

    ("the decision_ref resolver is weakened to a non-null check — M1's resolver call is bypassed, so a "
     "bare string that references nothing closes the exception (K-1, AC-SAFE-024)",
     [(M9,
       "            resolved: Any = resolve_decision_ref(\n"
       "                self._conn, tenant=self._tenant, ref=ref, kind=decision_ref_kind)",
       "            resolved: Any = ref  # MUTANT non-null only")],
     f"{T}::test_decision_ref_must_resolve_to_a_human_decision_event_or_active_rule"),

    ("a model is permitted to resolve — the EC-3/EC-6 human guard is disabled, so a model clears an "
     "exception at any confidence ([C-6], GR-7, ER-9)",
     [(M9,
       "        if str(actor_kind).upper() != HUMAN:\n"
       "            self._refuse_illegal(exception.exception_id, Trigger.RESOLVED, actor_id=actor_id)",
       "        if False and str(actor_kind).upper() != HUMAN:  # MUTANT\n"
       "            self._refuse_illegal(exception.exception_id, Trigger.RESOLVED, actor_id=actor_id)")],
     f"{T}::test_model_cannot_resolve_an_exception"),

    ("an AutoClose is added — both closure guards (the empty-ref guard AND the resolver) are removed, so "
     "resolve(decision_ref=None) closes by silence (target spec §12.9 illegal row, F-30)",
     [(M9,
       '        ref = str(decision_ref or "").strip()\n        if not ref:',
       '        ref = str(decision_ref or "").strip()\n        if not ref and False:  # MUTANT'),
      (M9,
       "            resolved: Any = resolve_decision_ref(\n"
       "                self._conn, tenant=self._tenant, ref=ref, kind=decision_ref_kind)",
       "            resolved: Any = ref or 'auto-closed'  # MUTANT")],
     f"{T}::test_exception_closure_requires_decision_ref"),

    ("the no-delete trigger is disabled — a resolved exception can be deleted (swept/reaped/expired), the "
     "exact forgetting this entity exists to prevent (entity §26/§28, C-9)",
     [(MIG, "BEGIN SELECT RAISE(ABORT, '{DELETE_ABORT}'); END",
       "BEGIN SELECT 1; END  -- MUTANT")],
     f"{T}::test_an_exception_never_expires_and_no_sweep_deletes_it"),

    ("the escalation timer is made to RESOLVE instead of escalate — a timer resolves an exception "
     "(machine §37: never a resolution timer)",
     [(M9,
       '            exception, "EC-5", EcState.ESCALATED, event_name="ExceptionEscalated"',
       '            exception, "EC-5", EcState.RESOLVED, event_name="ExceptionEscalated"  # MUTANT')],
     f"{T}::test_ec_escalates"),

    ("a background sweep is introduced beside the durable timer — a scan for exceptions that look old, "
     "the exact 'things that look old' M-36 forbids",
     [(M9,
       "    def __init__(\n        self,\n        conn: sqlite3.Connection,\n        *,\n"
       "        tenant: str,\n        clock:",
       "    def sweep_stale(self):  # MUTANT reaper\n"
       "        return self._conn.execute(\"SELECT * FROM exceptions\").fetchall()\n\n"
       "    def __init__(\n        self,\n        conn: sqlite3.Connection,\n        *,\n"
       "        tenant: str,\n        clock:")],
     f"{T}::test_the_machine_defines_no_sweep_or_reaper_method"),

    ("previous_severity is dropped from the severity-change event — a rebuild reproduces the ORIGINAL "
     "severity and can UNDER-STATE a live Sev-0 (F9)",
     [(M9,
       'payload={"severity": new_sev, "previous_severity": previous, "changed_by": who,',
       'payload={"severity": new_sev, "changed_by": who,  # MUTANT dropped previous_severity')],
     f"{T}::test_severity_change_records_previous_and_new_and_who"),

    ("replay recomputes severity from the current row — the fold is made to read the live row, so a "
     "rebuild's severity depends on the row now rather than the recorded events (entity §34)",
     [(M9,
       "        row = self.get(exception_id)\n"
       "        freezes = bool(row.freezes_entity) if row is not None else False",
       "        row = self.get(exception_id)\n"
       "        severity = row.severity if row is not None else severity  # MUTANT reads the live row\n"
       "        freezes = bool(row.freezes_entity) if row is not None else False")],
     f"{T}::test_replay_rebuilds_severity_from_the_recorded_events_not_the_row"),

    ("the tenant is dropped from the open-exception dedup index — one cause in two tenants coalesces, "
     "cross-tenant ([C-1])",
     [(MIG,
       '"ON exceptions (tenant, source_ref, type) WHERE state != \'RESOLVED\'"',
       '"ON exceptions (source_ref, type) WHERE state != \'RESOLVED\'"  # MUTANT dropped tenant')],
     f"{T}::test_the_same_source_in_two_tenants_are_two_isolated_exceptions"),

    ("the freeze CHECK is widened to always-true — a freezing exception with no entity_ref/frozen_field "
     "is insertable, a freeze that blocks nothing (### M9-AQ-5, entity §38)",
     [(MIG,
       "CHECK (freezes_entity = 0 OR (entity_ref IS NOT NULL AND frozen_field IS NOT NULL)),",
       "CHECK (1 = 1 OR freezes_entity = 0 OR (entity_ref IS NOT NULL AND frozen_field IS NOT NULL)),  -- MUTANT")],
     f"{T}::test_db_freeze_requires_entity_and_field"),

    ("an M10 compensations table is created — an unauthorized neighbouring machine's storage is built "
     "with M9 (task §3.9)",
     [(MIG,
       'P6XC_TENANT_TABLES: tuple[str, ...] = ("exceptions",)',
       'P6XC_TENANT_TABLES: tuple[str, ...] = ("exceptions", "compensations")  # MUTANT'),
      (MIG,
       '    "exceptions": """',
       '    "compensations": "CREATE TABLE compensations (tenant TEXT NOT NULL, compensation_id TEXT '
       'NOT NULL, PRIMARY KEY (tenant, compensation_id))",  # MUTANT\n    "exceptions": """')],
     f"{T}::test_the_neighbouring_machines_are_not_built"),

    ("M9 is made a gate-decision minter — it imports the checkpoint, crossing the CLAUDE.md rule 17 "
     "boundary that P3 is the sole gate authority",
     [(M9,
       "from .event_contracts import CONTRACTS",
       "from .checkpoint import EvidenceCondition  # MUTANT\nfrom .event_contracts import CONTRACTS")],
     f"{T}::test_m9_mints_no_gate_decision"),

    ("M9 is made a brake engager — it imports the brake, crossing the F9 boundary that the brake is the "
     "source detector's act (F9 cross-cutting)",
     [(M9,
       "from .event_inbox import ConsumeResult, DedupInbox",
       "from .brake import BrakeStore  # MUTANT\nfrom .event_inbox import ConsumeResult, DedupInbox")],
     f"{T}::test_m9_engages_no_brake"),

    ("a PERMANENT failure is retried before raising — the L-D zero-retries guard is disabled, so an "
     "auth/config failure that spun is accepted (M-74, entity §43(d))",
     [(M9,
       "        if classification is FailureDisposition.PERMANENT and int(attempts_before_raise) != 0:",
       "        if False and classification is FailureDisposition.PERMANENT and int(attempts_before_raise) != 0:  # MUTANT")],
     f"{T}::test_auth_failure_raises_exception_immediately_zero_retries"),

    ("permanence is inferred from an error message — a classifier is introduced that maps a message to "
     "PERMANENT, the classifier that must not exist (M-74)",
     [(M9,
       "    text = str(classification)\n    if text in FAILURE_CLASSIFICATIONS:\n"
       "        return FailureDisposition(text)\n    raise MalformedException(",
       "    text = str(classification)\n    if text in FAILURE_CLASSIFICATIONS:\n"
       "        return FailureDisposition(text)\n"
       '    if "auth" in text.lower() or "config" in text.lower():  # MUTANT infer\n'
       "        return FailureDisposition.PERMANENT  # MUTANT\n    raise MalformedException(")],
     f"{T}::test_failure_classification_is_supplied_never_inferred"),

    ("the ship-dark posture is weakened — a production module imports the exception machine, so M9's "
     "'exception queue / MTTR dashboard' product form arrives with it",
     [(SCHEMA,
       "def create_canonical_schema(conn: sqlite3.Connection) -> None:",
       "from . import exception as _mutant_exception  # MUTANT production importer\n\n\n"
       "def create_canonical_schema(conn: sqlite3.Connection) -> None:")],
     f"{T}::test_m9_ships_dark_no_production_importer"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, old, new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        if path not in originals:
            originals[path] = path.read_bytes()

    # Validate every anchor against the ORIGINAL text (before any edit in this case is applied).
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
    print("\n=========== P6 M9 EXCEPTION MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
