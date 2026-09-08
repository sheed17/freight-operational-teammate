"""Bounded synchronization for the tier-1 concurrency guards.

Every safety test here that proves a race — exactly-one-winner, an atomic claim, tenant
isolation, idempotency — proves it by starting real threads on real SQLite connections and
letting them collide. That shape is correct and this module does not change it.

What it changes is how those tests WAIT. `threading.Barrier.wait()` and `Thread.join()` with no
timeout are unbounded. If one worker raises before it reaches the barrier — a SQLite file lock at
connection time is enough — its partners wait for a party that will never arrive, the joins never
return, and pytest reports nothing at all. The job runs to its ceiling and GitHub CANCELS it. A
cancelled job is not a red test: it names no test, prints no assertion, and reads like
infrastructure flake. That is how a tier-1 guard goes dark while still looking healthy.

The rule enforced here:

    a deadlock must become a deterministic pytest FAILURE — never a hang, and never a pass.

Three pieces, deliberately no more:

  * `BARRIER_TIMEOUT` / `JOIN_TIMEOUT` — liveness bounds, passed EXPLICITLY at every call site so
    a reader (and a grep) can see the bound without knowing this module's defaults.
  * `run_race(...)` — starts the workers, joins them under a bound, asserts no worker is still
    alive, and re-raises whatever a worker raised.
  * `WorkerFailure` — the loud failure that a silent hang used to be.

These bounds are LIVENESS bounds, not performance budgets. `WorkflowStore` opens SQLite with
`timeout=30.0` and `PRAGMA busy_timeout=30000` (src/freight_recon/workflow.py), so a worker may
legitimately block up to 30s inside a single contended statement. The bounds below sit far above
that, so reaching one is evidence of a real defect and never of a slow machine:

    BARRIER_TIMEOUT = 60s   2x the 30s SQLite busy timeout
    JOIN_TIMEOUT   = 120s   4x the busy timeout, and 2x BARRIER_TIMEOUT so that a worker which
                            gives up AT the barrier still has a full 60s to unwind and exit
                            before its join is allowed to call it stuck.

Nothing here reduces contention, lowers a contender count, serializes a race, or relaxes an
assertion. The races stay adversarial; only the waiting is bounded.
"""

import threading

# Liveness bounds. See the module docstring for why these clear legitimate SQLite contention.
BARRIER_TIMEOUT = 60.0
JOIN_TIMEOUT = 120.0


class WorkerFailure(AssertionError):
    """A race worker died, or would not finish, instead of the whole suite hanging."""


def run_race(worker, args_list, *, barrier=None, join_timeout=JOIN_TIMEOUT, label=""):
    """Run `worker(*args)` on one thread per entry in `args_list`, and refuse to hang.

    `args_list` fixes the contender count: it is the caller's, and this function never trims it.

    Guarantees, in order:

    1. A worker that raises does not disappear. Its exception is captured and re-raised here, in
       the main thread, where pytest can attribute it to the test.
    2. A worker that raises ABORTS the barrier (when one is supplied). `Barrier.abort()` releases
       every partner immediately with `BrokenBarrierError` instead of leaving them to burn
       `BARRIER_TIMEOUT` waiting for a party that is already dead — so the common deadlock turns
       into an immediate, attributable failure rather than a slow one.
    3. Every join is bounded. A thread still alive afterwards is named and the test FAILS; it is
       never quietly ignored, and it is never allowed to look like a pass.
    4. Threads are daemons. A worker genuinely wedged inside a C-level SQLite call cannot keep the
       interpreter alive at exit — otherwise the bounded join would fail the test and the process
       would then hang at teardown, reproducing the very cancellation this module exists to stop.

    Root causes are reported before consequences: a `BrokenBarrierError` in a partner is the echo
    of another thread's death, so real exceptions are listed first.
    """
    failures: list[tuple[int, BaseException]] = []
    lock = threading.Lock()

    def guarded(index, args):
        try:
            worker(*args)
        except BaseException as exc:  # noqa: BLE001 - captured, re-raised in the main thread
            with lock:
                failures.append((index, exc))
            # Release any partner still standing at the barrier, rather than making it wait out
            # the full timeout for a party that can no longer arrive.
            if barrier is not None:
                barrier.abort()

    threads = [
        threading.Thread(target=guarded, args=(i, tuple(args)), daemon=True,
                         name=f"race-{label or worker.__name__}-{i}")
        for i, args in enumerate(args_list)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=join_timeout)

    # Liveness first: a live thread means the bound was actually reached, which is a deadlock.
    still_alive = [t.name for t in threads if t.is_alive()]
    if still_alive:
        raise WorkerFailure(
            f"{len(still_alive)} of {len(threads)} race workers were still running after "
            f"{join_timeout}s and did not finish: {', '.join(still_alive)}. That is a deadlock or "
            f"a lost wakeup, not slowness — the SQLite busy timeout is 30s. "
            f"{_summarize(failures)}")

    if failures:
        # Order by cause, not by thread index: a broken barrier is downstream of a real death.
        ordered = sorted(failures, key=lambda f: isinstance(f[1], threading.BrokenBarrierError))
        raise WorkerFailure(
            f"{len(failures)} of {len(threads)} race workers raised. {_summarize(ordered)}"
        ) from ordered[0][1]


def _summarize(failures):
    if not failures:
        return "No worker raised."
    return "Worker exceptions: " + " | ".join(
        f"thread {i}: {type(exc).__name__}: {exc}" for i, exc in failures)
