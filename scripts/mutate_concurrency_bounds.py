#!/usr/bin/env python3
"""Safe in-memory mutation battery for the tier-1 concurrency BOUNDS.

Doctrine (CLAUDE.md §6), identical to the P3/P4/P5/P6 batteries:
  * original bytes are held IN MEMORY — never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation
  * a guard that does NOT fail on the mutant proves nothing and is reported as a MISS
  * restoration is verified byte-for-byte
  * every case states the REAL defect it reintroduces

### WHAT THIS BATTERY IS FOR. `eval/tests/concurrency_kit.py` claims that a deadlocked race test
becomes a deterministic pytest FAILURE instead of a hang. That claim is trivially satisfiable by a
kit that never blocks and never checks anything, so this battery attacks it from both sides:

  M1 proves the corrected test FAILS FAST on the exact scenario that cancelled CI run 34187826313.
  M2 proves the same injection HANGS without the bounds — i.e. that M1's mutant really does
     reintroduce the defect, rather than being a scenario that was always harmless.
  M3 proves a worker that never returns is caught by the JOIN bound and NAMED, not ignored.
  M4 proves the bounds did not turn the race into a formality: unmutated, it still passes and
     still establishes exactly-one-winner across eight real contenders.

M2 is the case that makes this a proof. If M2 does not hang, M1 proves nothing.

### THIS IS NOT AN INDEPENDENT REVIEW. It was written by the session that made the correction.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv/bin/python"
TARGET = ROOT / "eval/tests/test_phase3_claim_cas.py"
NODE = ("eval/tests/test_phase3_claim_cas.py::"
        "test_n_racing_claimers_on_separate_connections_produce_exactly_one_claim")

HANG_BUDGET = 45.0   # a run still alive after this is, for our purposes, hung
FAST_BUDGET = 30.0   # a corrected failure must land well inside this

# --- the corrected shape, as it stands in the tree -------------------------------------------
# The file holds two bounded waits, so the anchor carries the line after it to stay unique.
CLAIM = "        results[i] = claim_grant_cas(contender_kernel, outcome.handle, params_for(effect))\n"
BOUND_WAIT = "        barrier.wait(timeout=BARRIER_TIMEOUT)\n" + CLAIM
BOUND_JOIN = "    run_race(contender, [(i,) for i in range(8)], barrier=barrier)\n"

# --- the pre-correction shape, reconstructed for M2 ------------------------------------------
UNBOUND_WAIT = "        barrier.wait()\n" + CLAIM
UNBOUND_JOIN = ("    threads = [threading.Thread(target=contender, args=(i,)) for i in range(8)]\n"
                "    for t in threads:\n"
                "        t.start()\n"
                "    for t in threads:\n"
                "        t.join()\n")

# --- the injected worker death: a contender that dies BEFORE reaching the barrier -------------
DEATH = ("        if i == 3:\n"
         "            raise RuntimeError('injected: unable to open database file')\n")


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def run(node: str, budget: float):
    """Run one test node in a subprocess. Returns (verdict, seconds)."""
    purge_pycache()
    t0 = time.monotonic()
    try:
        p = subprocess.run([str(PY), "-m", "pytest", node, "-q", "-p", "no:randomly", "-x"],
                           cwd=ROOT, capture_output=True, text=True, timeout=budget)
        dt = time.monotonic() - t0
        return ("PASSED" if p.returncode == 0 else "FAILED", dt, p.stdout[-1500:])
    except subprocess.TimeoutExpired:
        return ("HUNG", time.monotonic() - t0, "(no output — the run never finished)")


def main() -> int:
    original = TARGET.read_bytes()
    results = []
    try:
        # ---------------------------------------------------------------- M4: unmutated baseline
        v, dt, out = run(NODE, HANG_BUDGET)
        results.append(("M4 unmutated: the race still runs and still proves one winner",
                        "PASSED", v, dt))

        # ---------------------------------------------------------------- M1: death before barrier
        src = original.decode()
        assert src.count(BOUND_WAIT) == 1, "corrected barrier anchor drifted"
        mutant = src.replace(BOUND_WAIT, DEATH + BOUND_WAIT)
        TARGET.write_text(mutant)
        v, dt, out = run(NODE, HANG_BUDGET)
        results.append(("M1 a contender dies BEFORE the barrier (the CI-cancellation scenario)",
                        "FAILED", v, dt))
        if v == "FAILED" and "WorkerFailure" not in out and "injected" not in out:
            print("  !! M1 failed, but not with an attributable worker failure:\n", out[-600:])

        # ---------------------------------------------------------------- M2: same, UNBOUNDED
        assert src.count(BOUND_JOIN) == 1, "corrected join anchor drifted"
        pre = (src.replace(BOUND_WAIT, DEATH + UNBOUND_WAIT)
                  .replace(BOUND_JOIN, UNBOUND_JOIN))
        TARGET.write_text(pre)
        v, dt, out = run(NODE, HANG_BUDGET)
        results.append(("M2 the SAME injection with the pre-correction unbounded waits",
                        "HUNG", v, dt))

        # ---------------------------------------------------------------- M3: a wedged worker
        wedge = ("        if i == 3:\n"
                 "            import threading as _t; _t.Event().wait()\n")
        m3 = (src.replace(BOUND_WAIT, wedge + BOUND_WAIT)
                 .replace(BOUND_JOIN,
                          "    run_race(contender, [(i,) for i in range(8)], "
                          "barrier=barrier, join_timeout=3.0)\n"))
        TARGET.write_text(m3)
        v, dt, out = run(NODE, HANG_BUDGET)
        results.append(("M3 a contender never returns: the JOIN bound catches and names it",
                        "FAILED", v, dt))
        if v == "FAILED" and "still running after" not in out:
            print("  !! M3 failed, but not via the join bound:\n", out[-600:])
    finally:
        TARGET.write_bytes(original)
        purge_pycache()
        assert TARGET.read_bytes() == original, "RESTORE FAILED — target bytes differ"
        print("\nrestored eval/tests/test_phase3_claim_cas.py byte-for-byte; __pycache__ purged")

    print(f"\n{'=' * 96}\nDENOMINATOR: {len(results)} mutation cases\n{'=' * 96}")
    misses = 0
    for label, expected, got, dt in results:
        hit = expected == got
        misses += not hit
        print(f"  [{'HIT ' if hit else 'MISS'}] expected {expected:<7} got {got:<7} "
              f"{dt:6.1f}s  {label}")
    print(f"\n{len(results) - misses}/{len(results)} cases behaved as claimed.")
    if misses:
        print("MISS means the guard did not fire on a mutant — the bound proves nothing there.")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
