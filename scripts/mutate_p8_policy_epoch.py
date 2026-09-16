#!/usr/bin/env python3
"""### MUTATION BATTERY FOR THE TENANT POLICY EPOCH (U8.1/P8, review finding S3).

Each mutant REINTRODUCES A REAL DEFECT — not a cosmetic edit that happens to redden a test. The one
that matters most is the first: the epoch rule this unit replaced was GREEN under all 60 M11 tests,
because nothing asserted it. A guard never seen to fail is a decoration, so every guard added with
the epoch is driven RED here by the exact behaviour it exists to forbid.

### THE HARNESS IS IN-MEMORY SAVE/RESTORE WITH A `__pycache__` PURGE, AND USES NO GIT.
CLAUDE.md sec 6: `git checkout` / `restore` / `stash` / `clean` destroyed unrecoverable uncommitted
work in this repository once already. Original bytes are held in memory, restored in a `finally`,
and verified byte-for-byte before the run is allowed to report anything.

Run: .venv/bin/python scripts/mutate_p8_policy_epoch.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
POLICY = REPO / "src" / "freight_recon" / "policy.py"
MIGRATION = REPO / "src" / "freight_recon" / "migrations" / "phase8_policy_epochs.py"
PY = REPO / ".venv" / "bin" / "python"
T = "eval/tests/test_phase6_policy.py"

# The pre-epoch read, verbatim: MAX over `policies` in ANY state, which is what made inserting a
# DRAFT advance the tenant scalar the claim CAS revalidates.
_EPOCH_READ = """        row = self._conn.execute(
            "SELECT COALESCE(MAX(epoch), 0) FROM policy_epochs WHERE tenant = ?",
            (self._tenant,)).fetchone()
        return int(row[0])"""
_OLD_READ = """        row = self._conn.execute(
            "SELECT COALESCE(MAX(policy_version), 0) FROM policies WHERE tenant = ?",
            (self._tenant,)).fetchone()
        return int(row[0])"""

_PO4_ADVANCE = """            new_tenant_version = str(self._advance_epoch(
                reason="ACTIVATED", policy=after, transition_id="PO-4",
                advanced_by=activator, now=now))"""
_PO4_OLD = """            new_tenant_version = str(after.policy_version)"""

_ALLOC = """        nxt = int(self._conn.execute(
            "SELECT COALESCE(MAX(epoch), 0) FROM policy_epochs WHERE tenant = ?",
            (self._tenant,)).fetchone()[0]) + 1"""
_ALLOC_ROW = """        nxt = int(policy.policy_version)"""

CASES: list[tuple[str, list[tuple[Path, str, str]], str]] = [
    ("### THE PRE-EPOCH READ RETURNS — `MAX(policy_version)` over `policies` in ANY state, so "
     "inserting a DRAFT advances the tenant scalar again and a dispatcher opening a draft at 4pm "
     "voids every in-flight grant and every outstanding approval in the brokerage (S3)",
     [(POLICY, _EPOCH_READ, _OLD_READ)],
     f"{T}::test_drafting_a_policy_does_NOT_advance_the_tenant_epoch"),

    ("### REVOCATION STOPS ADVANCING THE EPOCH — the UNDER-VOIDING direction M11's own docstring "
     "says is not available: a grant minted under the revoked policy stays claimable, so the "
     "effect executes under a policy that no longer exists",
     [(POLICY, 'epoch_reason="REVOKED")', "epoch_reason=None)")],
     f"{T}::test_revocation_advances_the_epoch_the_under_voiding_direction"),

    ("### EXPIRY STOPS ADVANCING THE EPOCH — the policy that decided no longer governs, so its "
     "decision is not REPRODUCIBLE (ADR-010 sec 9.1), yet grants judged under it stay claimable",
     [(POLICY, 'epoch_reason="EXPIRED")', "epoch_reason=None)")],
     f"{T}::test_expiry_advances_the_epoch_because_expiry_is_withdrawal"),

    ("### ACTIVATION STOPS ADVANCING THE EPOCH and binds the row's own number again — the number "
     "was spent when the DRAFT was inserted, so the policy takes effect while the scalar the claim "
     "CAS compares against does not move at all",
     [(POLICY, _PO4_ADVANCE, _PO4_OLD)],
     f"{T}::test_submission_and_approval_advance_nothing_only_activation_does"),

    ("### THE EPOCH IS ALLOCATED FROM THE ROW'S OWN VERSION instead of the tenant MAX+1, so it can "
     "REPEAT and can FALL — and a falling epoch resurrects a stale Effect Grant, which is the exact "
     "failure the CAS predicate exists to prevent",
     [(POLICY, _ALLOC, _ALLOC_ROW)],
     f"{T}::test_the_epoch_never_decreases_across_a_full_lifecycle"),

    ("### THE EPOCH READ LOSES ITS TENANT PREDICATE — one brokerage's policy activity voids "
     "another brokerage's in-flight authority [C-1]",
     [(POLICY, '"SELECT COALESCE(MAX(epoch), 0) FROM policy_epochs WHERE tenant = ?",\n'
               '            (self._tenant,)).fetchone()\n        return int(row[0])',
       '"SELECT COALESCE(MAX(epoch), 0) FROM policy_epochs WHERE ? IS NOT NULL",\n'
       '            (self._tenant,)).fetchone()\n        return int(row[0])')],
     f"{T}::test_the_epoch_is_tenant_scoped_one_brokerage_never_moves_another"),

    ("### THE APPEND-ONLY TRIGGERS ARE DROPPED — an epoch becomes editable and DELETABLE, and a "
     "DELETE lowers the tenant MAX, making a stale Effect Grant claimable again",
     # ### THE FIRST ATTEMPT AT THIS MUTANT WAS VACUOUS AND IS RECORDED RATHER THAN QUIETLY FIXED
     # (CLAUDE.md sec 6: "a mutation that does not reintroduce the real defect proves nothing").
     # It renamed the dict KEYS (`trg_policy_epochs_immutable` -> `_disabled_immutable`). The keys
     # are only the existence check; the CREATE TRIGGER name lives inside the DDL f-string, so both
     # triggers were still created and the guard stayed GREEN — correctly. Emptying the dict is the
     # real defect: no trigger is created AND `phase8_policy_epochs_readiness_problems` iterates the
     # same constant, so it reports READY while asserting nothing.
     [(MIGRATION, "P8PE_TRIGGERS: dict[str, str] = {\n",
       "P8PE_TRIGGERS: dict[str, str] = {}\n_P8PE_TRIGGERS_DISABLED: dict[str, str] = {\n")],
     f"{T}::test_a_policy_epoch_row_is_append_only_in_the_database"),

    ("### THE `reason` CHECK ADMITS ANY TEXT — 'DRAFTED' becomes an insertable cause, so the "
     "database stops being the thing that forbids drafting from moving authority",
     [(MIGRATION, "reason TEXT NOT NULL CHECK (reason IN ('ACTIVATED','REVOKED','EXPIRED'))",
       "reason TEXT NOT NULL")],
     f"{T}::test_a_policy_epoch_row_is_append_only_in_the_database"),

    ("### EVERY EPOCH ROW STOPS NAMING ITS CAUSE — the transition id is not recorded, so an epoch "
     "that voided a broker's effect cannot be explained afterwards",
     [(POLICY, "transition_id, advanced_by, now))", 'transition_id, None, now))')],
     f"{T}::test_every_epoch_row_names_the_policy_and_the_transition_that_caused_it"),
]


def purge_pycache() -> None:
    for d in REPO.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def run_guard(node: str) -> tuple[bool, str]:
    """True == GREEN. A pytest exit of 4 (node not found) is NOT green — it is a broken guard id."""
    purge_pycache()
    r = subprocess.run([str(PY), "-m", "pytest", node, "-q", "--no-header", "-x"],
                       capture_output=True, text=True, cwd=REPO)
    if r.returncode == 4:
        return False, "NODE-NOT-FOUND (exit 4) — the guard id is stale, not the code"
    return r.returncode == 0, (r.stdout or "")[-200:]


def main() -> int:
    originals = {p: p.read_bytes() for p in (POLICY, MIGRATION)}
    results: list[tuple[str, bool, str]] = []
    try:
        # Anti-vacuity control FIRST: every guard must be GREEN on the un-mutated tree, or a RED
        # below proves nothing about the mutant.
        for node in sorted({c[2] for c in CASES}):
            ok, detail = run_guard(node)
            if not ok:
                print(f"SETUP-FAIL: guard already RED before any mutation: {node}\n  {detail}")
                return 1
        results.append(("anti-vacuity control: every guard GREEN on the un-mutated tree", True,
                        f"{len({c[2] for c in CASES})} distinct guards"))

        for label, edits, node in CASES:
            applied = True
            for path, old, new in edits:
                src = path.read_text()
                if src.count(old) != 1:
                    results.append((label, False,
                                    f"MUTATION DID NOT APPLY: {src.count(old)} occurrences of the "
                                    f"target in {path.name} — the mutant is vacuous"))
                    applied = False
                    break
                path.write_text(src.replace(old, new, 1))
            if applied:
                green, detail = run_guard(node)
                results.append((label, not green,
                                "guard went RED (caught)" if not green else
                                f"### GUARD STAYED GREEN — the defect is undetected. {detail}"))
            for path, b in originals.items():
                path.write_bytes(b)

        for p, b in originals.items():
            if p.read_bytes() != b:
                print(f"RESTORE FAILED for {p}")
                return 1
    finally:
        for p, b in originals.items():
            p.write_bytes(b)
        purge_pycache()

    print("========== U8.1/P8 POLICY EPOCH MUTATION BATTERY (S3) ==========")
    for label, ok, detail in results:
        print(f"  [{'  PASS' if ok else '**FAIL':>6}] {label}")
        print(f"           {detail}")
    caught = sum(1 for _, ok, _ in results if ok) - 1  # the control is not a mutant
    total = len(CASES)
    print(f"\n  {caught}/{total} mutants caught")
    print("  NOTE: written by the session that implemented the change - evidence, not adjudication.")
    return 0 if caught == total else 1


if __name__ == "__main__":
    sys.exit(main())
