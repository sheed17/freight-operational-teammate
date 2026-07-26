"""Mutual exclusion for the finalizer. One finalizer per repository, ever.

`finalize_status.py` had no lock. A second finalizer started while the first was
mid-run — the monitoring process concluded the first had died because an
expected log file was not on disk. It had not: `nohup` outlives its parent and
buffers output, so an absent log proves nothing whatsoever about liveness.

Both finalizers then did what finalizers do. They deleted receipts, re-ran the
canonical suite, and wrote derived status — against a tree the other one was
concurrently changing. The status record that survived described a state neither
run had actually certified, which is precisely the false green the whole receipt
convention exists to prevent.

The lock is `flock`, and it is authoritative:

  * acquisition is NON-BLOCKING, so a second finalizer fails immediately — before
    it can delete a receipt, run a suite or write a status file;
  * it cannot go stale while its owner lives, because the owner holds the file
    descriptor open;
  * the kernel releases it the moment the owner exits, however it exits, so a
    crashed finalizer never wedges the repository and no timeout heuristic is
    needed to clean up after one.

Critically, a lock is NEVER reclaimed because a log file is missing, a process
listing was unreadable, or a run "looks" stale. Those are the inferences that
produced the second finalizer. If the lock is held, the answer is to attach to
or wait on the existing owner, or to stop.

The JSON record written beside the lock identifies the owner for humans. It is
descriptive only and never decides whether the lock may be taken.

Deliberately dependency-free: standard library only, so the finalizer can
acquire it before importing or installing anything else.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

LOCK_NAME = "neyma-finalizer.lock"


class FinalizerLockHeld(Exception):
    """Another live finalizer owns this repository. Do not proceed."""


def _git_dir(repo: Path) -> Path:
    """The real .git directory, so a worktree locks with its parent repository."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(repo), capture_output=True, text=True, timeout=30, check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            candidate = Path(proc.stdout.strip())
            return candidate if candidate.is_absolute() else repo / candidate
    except (OSError, subprocess.SubprocessError):
        pass
    return repo / ".git"


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return exc.errno != errno.ESRCH
    return True


def describe(record: dict) -> str:
    pid = int(record.get("pid", 0) or 0)
    started = float(record.get("started_at", 0) or 0)
    age = f", started {int(max(0, time.time() - started))}s ago" if started else ""
    return (
        f"pid {pid} ({'alive' if _process_alive(pid) else 'not running'}{age}) "
        f"on {record.get('host') or 'this host'}, "
        f"repository {record.get('repository') or '(unknown)'}, "
        f"target {str(record.get('target_commit') or '')[:12] or '(unknown)'}, "
        f"run {record.get('run_id') or '(none)'}, session {record.get('session_id') or '(none)'}"
    )


def lock_path(repo: Path) -> Path:
    return _git_dir(Path(repo)) / LOCK_NAME


def current_owner(repo: Path) -> dict | None:
    """The record of a live owner, or None. Probes with flock, not with the file."""
    path = lock_path(repo)
    if not path.exists():
        return None
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return None
    except OSError:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"pid": 0}
    finally:
        os.close(fd)


@contextmanager
def finalizer_lock(repo: Path, *, target_commit: str = "", run_id: str = "",
                   session_id: str = ""):
    """Hold exclusive finalization rights for ``repo``, or raise.

    Acquire this BEFORE any suite run, receipt deletion or status write.
    """
    repo = Path(repo)
    path = lock_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        owner = current_owner(repo) or {}
        os.close(fd)
        raise FinalizerLockHeld(
            f"another finalizer already owns {repo}: {describe(owner)}.\n"
            "Two finalizers delete each other's receipts and certify a moving tree.\n"
            "The lock is authoritative: do NOT start a second finalizer, and do NOT "
            "reclaim this lock because a log file is missing — nohup survives its parent "
            "and buffers output.\n"
            "Attach to or wait on the existing owner, or stop."
        ) from exc

    now = time.time()
    record = {
        "pid": os.getpid(),
        "started_at": now,
        "started_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "repository": str(repo),
        "target_commit": target_commit,
        "run_id": run_id or os.environ.get("NEYMA_RUN_ID", ""),
        "session_id": session_id or os.environ.get("NEYMA_SESSION_ID", ""),
        "host": socket.gethostname(),
    }
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, json.dumps(record, indent=2).encode("utf-8"))
        os.fsync(fd)
    except OSError:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        raise

    try:
        yield record
    finally:
        # Released on EVERY exit path: success, failure, or an exception thrown
        # by a suite deep inside the run.
        try:
            os.ftruncate(fd, 0)
        except OSError:
            pass
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass
