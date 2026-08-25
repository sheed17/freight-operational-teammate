#!/usr/bin/env python3
"""M5 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the Observation machine exists to prevent — the same
email twice becoming two rows, a rewritten fact, a re-keyed fact, a duplicate that is no longer
recognized, a model guess that gets filed as truth, an ambiguous binding that auto-binds, an
inferrer re-run that supersedes, inbound content that sets its own provenance, one tenant reading
another's, a state written without its event, a lost update that silently wins — and names the guard
that must turn RED under it. A mutant that no test catches is a hole with a passing status; a mutant
that does not reintroduce the real defect proves nothing.

It mutates TEXT and shells out to pytest; it NEVER imports the observation machine, and it NEVER uses
git to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is
purged around every run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The interpreter running THIS script — `.venv/bin/python` locally, the runner's Python under CI —
# so the battery is runnable on a fresh checkout with no local venv.
PY = sys.executable

M5 = "src/freight_recon/observation.py"
MIG = "src/freight_recon/migrations/phase6_observations.py"
T = "eval/tests/test_phase6_observation.py"


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
    ("the natural-key index loses UNIQUE — the same email twice inserts as two rows, a duplicate "
     "Work Item and eventually a duplicate invoice (entity §17)",
     [(MIG,
       "CREATE UNIQUE INDEX ix_observations_natural_key ",
       "CREATE INDEX ix_observations_natural_key ")],
     f"{T}::test_natural_key_unique_index_refuses_a_duplicate_row"),

    ("the raw_value immutability trigger is defanged — a wrong reading is EDITED in place instead of "
     "superseded (entity §16/§22)",
     [(MIG,
       "BEGIN SELECT RAISE(ABORT, '{RAW_VALUE_ABORT}'); END",
       "BEGIN SELECT 1; END")],
     f"{T}::test_raw_value_is_immutable"),

    ("the content_digest immutability trigger is defanged — the fact can be re-keyed, so the same "
     "email twice stops being one fact (entity §10/§19)",
     [(MIG,
       "BEGIN SELECT RAISE(ABORT, '{DIGEST_ABORT}'); END",
       "BEGIN SELECT 1; END")],
     f"{T}::test_content_digest_is_immutable"),

    ("the duplicate short-circuit is disabled — an identical re-ingest is no longer recognized as a "
     "confirmation (the natural-key idempotency M-24 rests on)",
     [(M5,
       '"SELECT * FROM observations WHERE tenant = ? AND source_system = ? AND external_id = ? "\n'
       '            "AND content_digest = ?",',
       '"SELECT * FROM observations WHERE tenant = ? AND source_system = ? AND external_id = ? "\n'
       '            "AND content_digest = ? AND 1 = 2",  # MUTANT: duplicate detection disabled')],
     f"{T}::test_duplicate_observation_is_one_row_one_confirmation_zero_work"),

    ("the MODEL_INFERRED refusal is removed from BOTH the machine and the database — a guess gets "
     "filed as an observed fact (entity §37)",
     [(M5,
       "        if value == OBSERVATION_FORBIDDEN_PROVENANCE:",
       "        if False and value == OBSERVATION_FORBIDDEN_PROVENANCE:  # MUTANT"),
      (MIG,
       "CHECK (provenance_class <> '%(forbidden_prov)s'),",
       "CHECK (1 = 1 OR provenance_class <> '%(forbidden_prov)s'),  -- MUTANT")],
     f"{T}::test_model_inferred_observation_cannot_exist"),

    ("the guess/ambiguity guard is removed — a MODEL_INFERRED binding offered as 'confirmed' "
     "auto-binds instead of failing closed to UNBOUND (GR-8)",
     [(M5,
       "            and self.provenance_class != OBSERVATION_FORBIDDEN_PROVENANCE\n",
       "            and True  # MUTANT: guess guard removed\n")],
     f"{T}::test_a_model_guess_never_auto_binds"),

    ("the supersession guard is removed — a re-run of the inferrer supersedes an observation "
     "(entity §24, GR-9)",
     [(M5,
       "        if is_model or (not is_human and not is_rule):",
       "        if False and (is_model or (not is_human and not is_rule)):  # MUTANT")],
     f"{T}::test_supersession_requires_rule_or_human"),

    ("the provenance-from-content refusal is removed — inbound content sets its own provenance "
     "(M-13, R-P1)",
     [(M5,
       '        if isinstance(raw_value, Mapping) and "provenance_class" in {str(k) for k in raw_value}:',
       '        if False and isinstance(raw_value, Mapping) and "provenance_class" in {str(k) for k in raw_value}:  # MUTANT')],
     f"{T}::test_inbound_content_cannot_set_provenance"),

    ("the tenant predicate is dropped from the observation read — one tenant reads another's "
     "observation ([C-1])",
     [(M5,
       '"SELECT * FROM observations WHERE tenant = ? AND observation_id = ?",',
       '"SELECT * FROM observations WHERE (tenant = ? OR 1=1) AND observation_id = ?",  # MUTANT')],
     f"{T}::test_cross_tenant_same_external_id_no_collision"),

    ("the transition commits the state without emitting its event — a processing status with no "
     "event (GR-2 co-commit broken)",
     [(M5,
       "            self._outbox().emit(envelope)\n"
       "            conn.commit()\n"
       "        except BaseException:\n"
       "            conn.rollback()\n"
       "            raise\n"
       "        return TransitionResult(\n"
       "            transition_id=row.id, observation=after,",
       "            conn.commit()  # MUTANT: state committed without its event\n"
       "        except BaseException:\n"
       "            conn.rollback()\n"
       "            raise\n"
       "        return TransitionResult(\n"
       "            transition_id=row.id, observation=after,")],
     f"{T}::test_state_and_event_co_commit"),

    ("the OCC predicate is dropped from the processing-status transition — a lost update silently "
     "wins instead of raising (GR-3)",
     [(M5,
       'f"WHERE tenant = ? AND observation_id = ? AND state = ? AND version = ?",',
       'f"WHERE tenant = ? AND observation_id = ? AND state = ?",  # MUTANT'),
      (M5,
       "obs.state.value, obs.version]",
       "obs.state.value]  # MUTANT")],
     f"{T}::test_occ_on_processing_status_refuses_lost_update"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    # Snapshot each UNIQUE file's original bytes ONCE, up front — a mutation may edit the same file
    # twice (the OCC pair edits observation.py in two places), and reading the "original" per-edit
    # would capture the already-mutated bytes and leave the first edit in place on restore.
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
        # Apply every edit to the in-memory text per file, then write each file ONCE.
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
    print("\n=========== P6 M5 OBSERVATION MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
