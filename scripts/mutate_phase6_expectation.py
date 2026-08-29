#!/usr/bin/env python3
"""M8 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the Expectation machine exists to prevent — a blind
window collapsed into an accusation, an OVERDUE minted without healthy coverage, absent or partial
coverage read as health, a declared channel made optional, a duplicate live expectation, a cross-tenant
coalescing of one key, an unbound observation that discharges, a late arrival rejected for lateness, a
terminal-age timer that fires silently, a dropped deadline history, a dropped OCC predicate, a DST
window evaluated in UTC, an ownerless human-owned state, confidence used as a guard input, a replay that
recomputes from the live channel, a sweep beside the durable timer, an M9/M10 neighbouring table, M8
made a gate minter, and a production importer that breaks the ship-dark posture — and names the guard
that must turn RED under it. A mutant that no test catches is a hole with a passing status; a mutant
that does not reintroduce the real defect proves nothing.

It mutates TEXT and shells out to pytest; it NEVER imports the expectation machine, and it NEVER uses
git to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is
purged around every run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

M8 = "src/freight_recon/expectation.py"
MIG = "src/freight_recon/migrations/phase6_expectations.py"
SCHEMA = "src/freight_recon/schema.py"
T = "eval/tests/test_phase6_expectation.py"


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
    ("INDETERMINATE is removed from the honesty split — a blind window is routed to OVERDUE instead, "
     "collapsing 'the thing never came' and 'we were not watching' into one state (I8, M-32)",
     [(M8,
       'expectation, "EX-3i", ExState.INDETERMINATE, event_name="ExpectationIndeterminate"',
       'expectation, "EX-3i", ExState.OVERDUE, event_name="ExpectationIndeterminate"  # MUTANT')],
     f"{T}::test_ex_deadline_while_blind_is_indeterminate_not_overdue"),

    ("OVERDUE is allowed without a healthy coverage_ref — the entity §16 CHECK is widened to "
     "always-true, so a blind window can be labelled OVERDUE (M-32)",
     [(MIG,
       "CHECK (state <> 'OVERDUE' OR (coverage_ref IS NOT NULL AND coverage_health = '%(healthy)s')),",
       "CHECK (1 = 1 OR state <> 'OVERDUE' OR (coverage_ref IS NOT NULL AND coverage_health = '%(healthy)s')),  -- MUTANT")],
     f"{T}::test_overdue_requires_healthy_coverage"),

    ("absent coverage is treated as healthy — the M-32 fail-closed default is flipped, so no coverage "
     "record reads as a healthy window instead of INDETERMINATE",
     [(M8,
       '            return ("ABSENT", None)',
       '            return (HEALTHY_COVERAGE, "absent-as-healthy")  # MUTANT')],
     f"{T}::test_absent_coverage_is_not_health"),

    ("partial coverage is treated as healthy — the 'throughout the window' span check is dropped, so a "
     "HEALTHY row that covers only part of the window reads as full health (EX-3)",
     [(M8,
       '                    if r["window_start"] <= window_start and r["window_end"] >= window_end]',
       '                    if True]  # MUTANT dropped the throughout-the-window span check')],
     f"{T}::test_partial_coverage_is_not_health"),

    ("the declared expected_source requirement is dropped — the entity §21 NOT NULL is removed, so an "
     "expectation with no declared channel is insertable",
     [(MIG,
       "            expected_source TEXT NOT NULL,",
       "            expected_source TEXT,  -- MUTANT")],
     f"{T}::test_db_requires_expected_source_not_null"),

    ("the one-live-per-key index loses UNIQUE — two live RAISED expectations for one owed observation "
     "become insertable (entity §17)",
     [(MIG,
       '        "CREATE UNIQUE INDEX ix_expectations_one_live_per_key "',
       '        "CREATE INDEX ix_expectations_one_live_per_key "  # MUTANT')],
     f"{T}::test_partial_unique_index_refuses_two_live_raised"),

    ("the partial index loses its WHERE clause — every expectation (discharged/expired history "
     "included) competes for uniqueness, so a discharged key cannot be raised again (entity §17)",
     [(MIG,
       '        "ON expectations (tenant, expectation_key) WHERE state IN (%(live)s)"',
       '        "ON expectations (tenant, expectation_key)"  # MUTANT dropped WHERE')],
     f"{T}::test_a_discharged_key_can_be_raised_again"),

    ("the tenant is dropped from the uniqueness boundary — one key in two tenants coalesces, "
     "cross-tenant ([C-1])",
     [(MIG,
       '        "ON expectations (tenant, expectation_key) WHERE state IN (%(live)s)"',
       '        "ON expectations (expectation_key) WHERE state IN (%(live)s)"  # MUTANT dropped tenant')],
     f"{T}::test_the_same_key_in_two_tenants_are_two_isolated_expectations"),

    ("an unbound observation is allowed to discharge — the entity §13 BOUND guard is dropped, so a "
     "reading not yet a fact about a known subject discharges the expectation",
     [(M8,
       '        if obs["state"] != "BOUND":',
       '        if False and obs["state"] != "BOUND":  # MUTANT')],
     f"{T}::test_unbound_observation_cannot_discharge"),

    ("a late arrival is rejected because the deadline passed — a 'the deadline passed' rejection is "
     "reintroduced at EX-4, so the POD that arrives in month four is refused (entity §26)",
     [(M8,
       "        elif expectation.state in (ExState.OVERDUE, ExState.INDETERMINATE):\n"
       '            producer, late = "EX-4", True',
       "        elif expectation.state in (ExState.OVERDUE, ExState.INDETERMINATE):\n"
       '            raise GuardNotSatisfied("MUTANT: the deadline passed")\n'
       '            producer, late = "EX-4", True')],
     f"{T}::test_late_arrival_discharges"),

    ("the terminal-age timer fires silently — the EX-7 expiry is skipped when the terminal timer "
     "fires, so an aged obligation ages without ever expiring (never-silence half, entity §26)",
     [(M8,
       "            return self.expire(trigger.aggregate_id, correlation_id=trigger.correlation_id,",
       "            return None  # MUTANT silent expiry\n"
       "            return self.expire(trigger.aggregate_id, correlation_id=trigger.correlation_id,")],
     f"{T}::test_terminal_age_timer_expires_via_relay"),

    ("the deadline history is dropped — EX-5 re-versions and forgets, so the prior deadline is lost "
     "(entity §19)",
     [(M8,
       "        history = expectation.deadline_history_list + [expectation.deadline_utc]",
       "        history = []  # MUTANT dropped the deadline history")],
     f"{T}::test_deadline_history_is_retained"),

    ("the OCC predicate is weakened — the version guard accepts a stale version, so a lost update "
     "silently overwrites newer state (GR-3, C-10)",
     [(M8,
       'f"WHERE tenant = ? AND expectation_id = ? AND state = ? AND version = ?", args)',
       'f"WHERE tenant = ? AND expectation_id = ? AND state = ? AND version >= ?", args)  # MUTANT')],
     f"{T}::test_occ_refuses_a_stale_version"),

    ("a facility appointment is evaluated in UTC instead of facility-local — a 17:00 Denver window "
     "becomes 17:00 UTC across a DST boundary (F-25)",
     [(M8,
       "        zone = ZoneInfo(facility_timezone)",
       "        zone = timezone.utc  # MUTANT evaluated the window in UTC")],
     f"{T}::test_appointment_window_evaluated_in_facility_local_time_across_dst"),

    ("the owner requirement is dropped from the human-owned states — the AC-SAFE-028 CHECK is widened, "
     "so an OVERDUE/INDETERMINATE row with no accountable human is insertable",
     [(MIG,
       "            CHECK (state NOT IN (%(human_owned)s) OR owner_id IS NOT NULL),",
       "            CHECK (1 = 1 OR state NOT IN (%(human_owned)s) OR owner_id IS NOT NULL),  -- MUTANT")],
     f"{T}::test_ownerless_human_owned_state_is_impossible"),

    ("confidence becomes a guard input — a proposed_confidence of 1.0 forces the OVERDUE branch, so a "
     "confident model turns an INDETERMINATE window into an accusation (GR-8)",
     [(M8,
       "        if health == HEALTHY_COVERAGE and coverage_id is not None:",
       "        if (health == HEALTHY_COVERAGE and coverage_id is not None) or float(expectation.proposed_confidence or 0) >= 1.0:  # MUTANT")],
     f"{T}::test_confidence_never_turns_indeterminate_into_overdue"),

    ("replay recomputes from the current channel state — the rebuild is made to call the live coverage "
     "read, so a rebuild's verdict depends on the channel now rather than the recorded coverage "
     "(entity §34)",
     [(M8,
       "        stream = events if events is not None else self._event_stream(expectation_id)",
       "        stream = events if events is not None else self._event_stream(expectation_id)\n"
       '        _ = self._coverage_verdict("x", "a", "z")  # MUTANT replay reads the live channel')],
     f"{T}::test_rebuild_does_not_read_the_coverage_table"),

    ("a sweep/reaper is introduced beside the durable timer — a scan for expectations past their "
     "deadline, the exact 'things that look old' M-36 forbids",
     [(M8,
       "    def __init__(\n        self,\n        conn: sqlite3.Connection,",
       "    def sweep_overdue(self):  # MUTANT reaper\n"
       "        return self._conn.execute(\"SELECT * FROM expectations WHERE deadline_utc < 'now'\").fetchall()\n\n"
       "    def __init__(\n        self,\n        conn: sqlite3.Connection,")],
     f"{T}::test_the_machine_defines_no_sweep_or_reaper_method"),

    ("an M9 exceptions table is created — an unauthorized neighbouring machine's storage is built with "
     "M8 (task §3.9)",
     [(MIG,
       'P6EX_TENANT_TABLES: tuple[str, ...] = ("expectations", "observation_coverage")',
       'P6EX_TENANT_TABLES: tuple[str, ...] = ("expectations", "observation_coverage", "exceptions")  # MUTANT'),
      (MIG,
       '    "observation_coverage": """',
       '    "exceptions": "CREATE TABLE exceptions (tenant TEXT NOT NULL, exception_id TEXT NOT NULL, '
       'PRIMARY KEY (tenant, exception_id))",  # MUTANT\n    "observation_coverage": """')],
     f"{T}::test_the_neighbouring_machines_are_not_built"),

    ("M8 is made a gate-decision minter — it imports the checkpoint, crossing the CLAUDE.md rule 17 "
     "boundary that P3 is the sole gate authority",
     [(M8,
       "from .event_contracts import CONTRACTS",
       "from .checkpoint import GateDecision  # MUTANT\nfrom .event_contracts import CONTRACTS")],
     f"{T}::test_m8_mints_no_gate_decision"),

    ("the ship-dark posture is weakened — a production module imports the expectation machine, so M8's "
     "'live tracking / SLA' product form arrives with it",
     [(SCHEMA,
       "def create_canonical_schema(conn: sqlite3.Connection) -> None:",
       "from . import expectation as _mutant_expectation  # MUTANT production importer\n\n\n"
       "def create_canonical_schema(conn: sqlite3.Connection) -> None:")],
     f"{T}::test_m8_ships_dark_no_production_importer"),
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
    print("\n=========== P6 M8 EXPECTATION MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
