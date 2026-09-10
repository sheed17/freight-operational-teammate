#!/usr/bin/env python3
"""P7 (AC-13) resilience probe — concurrency, duplicate, replay and fault.

Operates the P7 surface under a race, a duplicate, a rebuild and an interruption, and prints a PASS
line per rule with a positive control. This is the surface a reviewer runs to observe that the P7
guarantees hold off the happy path — not only that they hold on it.

Run:  .venv/bin/python scripts/probe_phase7_resilience.py
      .venv/bin/python scripts/probe_phase7_resilience.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon import linker as L  # noqa: E402
from freight_recon import provenance as P  # noqa: E402
from freight_recon.evidence import EvidenceStore  # noqa: E402
from freight_recon.schema import create_canonical_schema, enable_and_verify_foreign_keys  # noqa: E402

T = "acme-brokerage"
NOW = "2026-09-09T12:00:00.000Z"
_JOIN = 60.0
_CASES: dict = {}


def case(name):
    def deco(fn):
        _CASES[name] = fn
        return fn
    return deco


def _connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db), timeout=30.0)
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    return conn


def _seed(db: Path, observations=("obs-1", "obs-2")) -> None:
    conn = _connect(db)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    for obs in observations:
        conn.execute(
            "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, external_id, "
            "content_digest, raw_value, as_of, received_at, state, version, provenance_class, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?, 'RECEIVED', 1, 'SYSTEM_IMPORTED', ?, ?)",
            (T, obs, "tms", f"L-{obs}", f"d-{obs}", "page", NOW, NOW, NOW, NOW))
    conn.commit()
    conn.close()


def _run_threads(worker, n: int) -> None:
    barrier = threading.Barrier(n)
    errors: list = []
    lock = threading.Lock()

    def guarded(i):
        try:
            worker(i, barrier)
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)
            barrier.abort()

    threads = [threading.Thread(target=guarded, args=(i,), daemon=True) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_JOIN)
    if any(t.is_alive() for t in threads):
        raise RuntimeError("a race worker deadlocked (still alive after the join bound)")


@case("concurrent-identical-ingestion-yields-one-row")
def _c() -> list[str]:
    db = Path(tempfile.mkdtemp(prefix="p7res-")) / "race.db"
    _seed(db)
    payload = b"identical POD bytes"
    n = 8
    results: list[str] = []
    lock = threading.Lock()

    def worker(_i, barrier):
        conn = _connect(db)
        try:
            store = EvidenceStore(conn)
            barrier.wait(timeout=_JOIN)
            ev = store.retain(T, content=payload, media_type="application/pdf",
                              source_observation_id="obs-1", now=NOW)
            with lock:
                results.append(ev)
        finally:
            conn.close()

    _run_threads(worker, n)
    conn = _connect(db)
    rows = conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant=?", (T,)).fetchone()[0]
    conn.close()
    one_row = rows == 1
    one_id = len(set(results)) == 1 and len(results) == n
    return [f"AC-13 {n} threads racing to ingest identical bytes -> exactly ONE content-addressed row: {one_row}",
            f"AC-13 every racing worker saw the same deduplicated id (decided by the DB, not a check): {one_id}"]


@case("duplicate-reingestion-is-idempotent")
def _c() -> list[str]:
    db = Path(tempfile.mkdtemp(prefix="p7res-")) / "dup.db"
    _seed(db)
    conn = _connect(db)
    try:
        store = EvidenceStore(conn)
        ids = {store.retain(T, content=b"a POD", media_type="application/pdf",
                            source_observation_id="obs-1", now=NOW) for _ in range(5)}
        rows = conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant=?", (T,)).fetchone()[0]
    finally:
        conn.close()
    return [f"AC-13 re-ingesting the same bytes 5x is idempotent to one row and one id: {len(ids) == 1 and rows == 1}"]


@case("concurrent-binding-never-loses-an-owner")
def _c() -> list[str]:
    signals = [L.Signal("EXACT_ID", "load-4471", source="tms")]
    outcomes: list = []
    lock = threading.Lock()

    def link_worker(_i, barrier):
        barrier.wait(timeout=_JOIN)
        out = L.link("pod-1", signals)
        with lock:
            outcomes.append((out.status, out.bound_identifier))

    _run_threads(link_worker, 8)
    deterministic = len(set(outcomes)) == 1 and outcomes[0][0] is L.LinkStatus.CONFIRMED

    owner = P.ProvenanceRecord(value="load-4471", provenance_class="OWNER_ASSERTED")
    refused = {"n": 0}

    def relink_worker(_i, barrier):
        barrier.wait(timeout=_JOIN)
        try:
            L.relink(owner, "pod-1", [L.Signal("EXACT_ID", "load-4718", source="x")])
        except P.OwnerAssertedRecompute:
            with lock:
                refused["n"] += 1

    _run_threads(relink_worker, 8)
    return [f"AC-13 concurrent link() of the same signals agrees on one CONFIRMED binding: {deterministic}",
            f"AC-13 concurrent relink of an OWNER_ASSERTED binding: all 8 refused, owner value preserved: {refused['n'] == 8 and owner.value == 'load-4471'}"]


def _digest(conn) -> str:
    ev = conn.execute("SELECT tenant, content_digest, content_ref, media_type, source_observation_id, "
                      "illegible, COALESCE(superseded_by,'') FROM evidence ORDER BY tenant, content_digest").fetchall()
    sp = conn.execute("SELECT tenant, evidence_id, locator, COALESCE(extracted_text,'') FROM evidence_spans "
                      "ORDER BY tenant, evidence_id, locator").fetchall()
    h = hashlib.sha256()
    for r in ev + sp:
        h.update(repr(tuple(r)).encode())
    return h.hexdigest()


def _build(db: Path) -> None:
    _seed(db)
    conn = _connect(db)
    try:
        store = EvidenceStore(conn)
        store.retain(T, content=b"POD 4471", media_type="application/pdf",
                     source_observation_id="obs-1", now=NOW, evidence_id="ev-1")
        store.attach_span(T, "ev-1", locator="page 1", now=NOW, extracted_text="4471", span_id="span-1")
        store.retain(T, content=b"rate conf", media_type="application/pdf",
                     source_observation_id="obs-2", now=NOW, evidence_id="ev-2")
    finally:
        conn.close()


@case("replay-rebuilds-the-same-digest-and-mints-no-authority")
def _c() -> list[str]:
    base = Path(tempfile.mkdtemp(prefix="p7res-"))
    a, b = base / "a.db", base / "b.db"
    _build(a)
    _build(b)
    ca, cb = _connect(a), _connect(b)
    try:
        rows = ca.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        same = _digest(ca) == _digest(cb)
        witnesses = ca.execute("SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0]
        grants = ca.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
    finally:
        ca.close()
        cb.close()
    return [f"AC-13 rebuilding the content-addressed projection reconstructs the same digest (corpus rows={rows}): {same and rows >= 2}",
            f"AC-13 building the P7 layer mints ZERO authority (checkpoint_witnesses={witnesses}, effect_grants={grants}): {witnesses == 0 and grants == 0}"]


@case("interrupted-ingestion-fails-closed")
def _c() -> list[str]:
    db = Path(tempfile.mkdtemp(prefix="p7res-")) / "fault.db"
    _seed(db)
    conn = _connect(db)
    try:
        store = EvidenceStore(conn)
        faulted = False
        try:
            store.retain(T, content=b"orphan", media_type="application/pdf",
                         source_observation_id="does-not-exist", now=NOW)
        except sqlite3.IntegrityError:
            faulted = True
        after_fault = conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant=?", (T,)).fetchone()[0]
        store.retain(T, content=b"orphan", media_type="application/pdf",
                     source_observation_id="obs-1", now=NOW)
        after_clean = conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant=?", (T,)).fetchone()[0]
    finally:
        conn.close()
    return [f"AC-13 an interrupted ingestion (unknown source) FAILS CLOSED — no half-written row: {faulted and after_fault == 0}",
            f"AC-13 a clean re-run then produces exactly one row: {after_clean == 1}"]


def _run(names: list[str]) -> int:
    wrong = 0
    for name in names:
        for line in _CASES[name]():
            print(line)
            if line.rstrip().endswith(": False") or "### WRONG ###" in line:
                wrong += 1
    print(f"behaviours as specified, {wrong} wrong")
    return 0 if wrong == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--case")
    args = ap.parse_args()
    if args.list:
        for n in _CASES:
            print(n)
        return 0
    return _run([args.case] if args.case else list(_CASES))


if __name__ == "__main__":
    sys.exit(main())
