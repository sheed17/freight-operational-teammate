"""P7 — AC-13: concurrency, duplicate delivery, replay and fault coverage over the P7 surface.

The happy-path behaviour of Evidence, provenance and the linker is proven elsewhere; this battery
proves it holds UNDER a race, a duplicate, a rebuild and an interruption:

  * concurrent ingestion of identical Evidence bytes resolves to EXACTLY ONE content-addressed row,
    decided by the database's UNIQUE index rather than a check (real threads, real connections);
  * concurrent binding is deterministic and never loses an OWNER_ASSERTED value;
  * replaying/rebuilding the content-addressed projection reconstructs the SAME digest and mints
    ZERO authority (no checkpoint witness, no effect grant) and no external effect;
  * an interrupted ingestion FAILS CLOSED — no half-written row — and a re-run reaches the same
    single row; a conflict-close fault leaves no partial state.

Every negative/absence assertion runs over a PROVEN NON-EMPTY population (CLAUDE.md sec 6). Races are
bounded by concurrency_kit.run_race so a deadlock is a deterministic FAILURE, never a hang.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path

import pytest
from concurrency_kit import BARRIER_TIMEOUT, run_race

ROOT = Path(__file__).resolve().parents[2]

from freight_recon import linker as L  # noqa: E402
from freight_recon import provenance as P  # noqa: E402
from freight_recon.checkpoint import ProvenanceClass  # noqa: E402
from freight_recon.evidence import EvidenceStore  # noqa: E402
from freight_recon.schema import create_canonical_schema, enable_and_verify_foreign_keys  # noqa: E402

T = "acme-brokerage"
NOW = "2026-09-09T12:00:00.000Z"


def require_population(items, what: str):
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


def _connect(db: Path) -> sqlite3.Connection:
    # timeout=30.0 sets SQLite's busy handler, so a contended writer queues rather than raising
    # 'database is locked' — the same 30s bound WorkflowStore uses (concurrency_kit docstring).
    conn = sqlite3.connect(str(db), timeout=30.0)
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    return conn


def _seed(db: Path, *, observations=("obs-1",)) -> None:
    conn = _connect(db)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    for obs in observations:
        conn.execute(
            "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, external_id, "
            "content_digest, raw_value, as_of, received_at, state, version, provenance_class, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?, 'RECEIVED', 1, 'SYSTEM_IMPORTED', ?, ?)",
            (T, obs, "tms", f"L-{obs}", f"d-{obs}", "loads page", NOW, NOW, NOW, NOW))
    conn.commit()
    conn.close()


# =============================================================== concurrency / duplicate


def test_concurrent_ingestion_of_identical_bytes_yields_exactly_one_evidence(tmp_path):
    """AC-13: real threads race to retain the SAME bytes; the UNIQUE (tenant, content_digest) index
    decides, so exactly ONE Evidence row exists and every thread sees the same id. Decided by the
    database, not a check."""
    db = tmp_path / "race.db"
    _seed(db)
    payload = b"identical POD bytes for load 4471"
    n = 8
    barrier = threading.Barrier(n)
    results: dict[int, str] = {}
    lock = threading.Lock()

    def worker(i: int) -> None:
        conn = _connect(db)
        try:
            store = EvidenceStore(conn)
            barrier.wait(timeout=BARRIER_TIMEOUT)  # collide on the same instant
            ev = store.retain(T, content=payload, media_type="application/pdf",
                              source_observation_id="obs-1", now=NOW)
            with lock:
                results[i] = ev
        finally:
            conn.close()

    run_race(worker, [(i,) for i in range(n)], barrier=barrier, label="evidence-dedup")

    final = _connect(db)
    try:
        count = final.execute("SELECT COUNT(*) FROM evidence WHERE tenant = ?", (T,)).fetchone()[0]
    finally:
        final.close()
    assert count == 1, f"concurrent ingestion of identical bytes produced {count} rows, not one"
    ids = require_population(list(results.values()), "per-thread evidence ids")
    assert len(ids) == n, f"only {len(ids)} of {n} workers returned an id"
    assert len(set(ids)) == 1, f"the workers disagreed on the deduplicated id: {sorted(set(ids))}"


def test_duplicate_reingestion_is_idempotent_to_one_content_addressed_row(tmp_path):
    """AC-13: duplicate delivery is a no-op — retaining the same bytes any number of times yields one
    row and the same id (content addressing IS the idempotency)."""
    db = tmp_path / "dup.db"
    _seed(db)
    conn = _connect(db)
    try:
        store = EvidenceStore(conn)
        ids = {store.retain(T, content=b"a POD", media_type="application/pdf",
                            source_observation_id="obs-1", now=NOW) for _ in range(5)}
        count = conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant = ?", (T,)).fetchone()[0]
    finally:
        conn.close()
    assert len(ids) == 1 and count == 1, f"duplicate re-ingestion was not idempotent: ids={ids} count={count}"


def test_concurrent_binding_is_deterministic_and_never_loses_an_owner_binding(tmp_path):
    """AC-13: the linker is a pure decision and an OWNER_ASSERTED record is immutable, so a race
    cannot tear them. Concurrent link() of the same signals agree on one outcome; concurrent relink()
    over an OWNER_ASSERTED binding are ALL refused and the owner's value is preserved."""
    signals = [L.Signal("EXACT_ID", "load-4471", source="tms")]
    n = 8
    barrier = threading.Barrier(n)
    outcomes: list = []
    lock = threading.Lock()

    def link_worker(_i: int) -> None:
        barrier.wait(timeout=BARRIER_TIMEOUT)
        out = L.link("pod-1", signals)
        with lock:
            outcomes.append((out.status, out.bound_identifier, out.provenance_class))

    run_race(link_worker, [(i,) for i in range(n)], barrier=barrier, label="link")
    require_population(outcomes, "link outcomes")
    assert len(set(outcomes)) == 1, f"concurrent link() disagreed: {set(outcomes)}"
    assert outcomes[0][0] is L.LinkStatus.CONFIRMED

    owner = P.ProvenanceRecord(value="load-4471", provenance_class="OWNER_ASSERTED")
    barrier2 = threading.Barrier(n)
    refusals = {"count": 0}

    def relink_worker(_i: int) -> None:
        barrier2.wait(timeout=BARRIER_TIMEOUT)
        try:
            L.relink(owner, "pod-1", [L.Signal("EXACT_ID", "load-4718", source="tms")])
        except P.OwnerAssertedRecompute:
            with lock:
                refusals["count"] += 1

    run_race(relink_worker, [(i,) for i in range(n)], barrier=barrier2, label="relink")
    assert refusals["count"] == n, f"only {refusals['count']} of {n} relinks were refused"
    assert owner.value == "load-4471", "a concurrent relink lost the owner's value"


# =============================================================== replay / rebuild


def _projection_digest(conn: sqlite3.Connection) -> str:
    """A deterministic digest of the P7 content-addressed projection: every evidence row and every
    span, sorted. Content addressing makes this reproducible across a rebuild."""
    ev = conn.execute(
        "SELECT tenant, content_digest, content_ref, media_type, source_observation_id, illegible, "
        "COALESCE(superseded_by,'') FROM evidence ORDER BY tenant, content_digest").fetchall()
    spans = conn.execute(
        "SELECT tenant, evidence_id, locator, COALESCE(region,''), COALESCE(extracted_text,'') "
        "FROM evidence_spans ORDER BY tenant, evidence_id, locator").fetchall()
    h = hashlib.sha256()
    for row in ev:
        h.update(repr(tuple(row)).encode())
    for row in spans:
        h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def _build_corpus(db: Path) -> None:
    """Retain the same content-addressed corpus. Deterministic: identical bytes -> identical digests,
    so two builds of this corpus are the same projection. Spans are keyed by their locator, so a
    rebuild does not depend on a generated span_id."""
    _seed(db, observations=("obs-1", "obs-2"))
    conn = _connect(db)
    try:
        store = EvidenceStore(conn)
        # Deterministic evidence and span ids so the rebuilt projection is comparable row-for-row
        # (the content digest is already deterministic; the surrogate ids would otherwise be random
        # uuids and defeat a byte-for-byte projection comparison).
        e1 = store.retain(T, content=b"POD 4471", media_type="application/pdf",
                          source_observation_id="obs-1", now=NOW, evidence_id="ev-1")
        store.attach_span(T, e1, locator="page 1", now=NOW, extracted_text="4471", span_id="span-1")
        store.retain(T, content=b"rate confirmation", media_type="application/pdf",
                     source_observation_id="obs-2", now=NOW, evidence_id="ev-2")
    finally:
        conn.close()


def test_replay_reconstructs_the_same_projection_digest_and_mints_no_authority(tmp_path):
    """AC-13: rebuilding the content-addressed projection from the same history reconstructs the SAME
    digest, and building the P7 layer mints ZERO authority — no checkpoint witness, no effect grant,
    no external effect. The corpus is proven non-empty first, so 'zero authority' is not vacuous."""
    db_a, db_b = tmp_path / "a.db", tmp_path / "b.db"
    _build_corpus(db_a)
    _build_corpus(db_b)
    conn_a, conn_b = _connect(db_a), _connect(db_b)
    try:
        rows = conn_a.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        spans = conn_a.execute("SELECT COUNT(*) FROM evidence_spans").fetchone()[0]
        assert rows >= 2 and spans >= 1, "the replay corpus is empty — a zero-authority proof would be vacuous"
        assert _projection_digest(conn_a) == _projection_digest(conn_b), (
            "rebuilding the content-addressed projection produced a different digest — replay is not "
            "deterministic")
        # ### MINTS NO AUTHORITY: building the P7 layer creates no witness and no grant.
        witnesses = conn_a.execute("SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0]
        grants = conn_a.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
        assert witnesses == 0, f"the P7 layer minted {witnesses} checkpoint witnesses — replay/build creates authority"
        assert grants == 0, f"the P7 layer minted {grants} effect grants — replay/build creates authority"
    finally:
        conn_a.close()
        conn_b.close()


# =============================================================== fault / fail-closed


def test_an_interrupted_ingestion_fails_closed_and_a_rerun_is_clean(tmp_path):
    """AC-13: a retention that faults part-way (an unknown source Observation -> FK violation) writes
    NO half Evidence row; a clean re-run then produces exactly one. A digest mismatch is refused
    before any write. Fail closed, never a torn claim."""
    db = tmp_path / "fault.db"
    _seed(db)
    conn = _connect(db)
    try:
        store = EvidenceStore(conn)
        # fault 1: an unknown source observation -> FK IntegrityError, and NO row is left behind.
        with pytest.raises(sqlite3.IntegrityError):
            store.retain(T, content=b"orphan bytes", media_type="application/pdf",
                         source_observation_id="does-not-exist", now=NOW)
        assert conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant = ?", (T,)).fetchone()[0] == 0, (
            "an interrupted ingestion left a half-written Evidence row")
        # fault 2: a digest mismatch is refused before any write.
        with pytest.raises(Exception):
            store.retain(T, content=b"real bytes", media_type="text/plain",
                         source_observation_id="obs-1", now=NOW, expected_digest="0" * 64)
        assert conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant = ?", (T,)).fetchone()[0] == 0
        # clean re-run: exactly one row.
        store.retain(T, content=b"orphan bytes", media_type="application/pdf",
                     source_observation_id="obs-1", now=NOW)
        assert conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant = ?", (T,)).fetchone()[0] == 1
    finally:
        conn.close()


def test_a_conflict_close_fault_leaves_no_partial_state():
    """AC-13: closing a Conflict by neither a registered rule nor a human decision is refused and
    produces no terminal state (a pure decision — nothing half-written); a relink fault preserves the
    owner's value. Fault is a refusal, not a torn transition."""
    with pytest.raises(L.ConflictClosureRefused):
        L.close_conflict()  # neither rule_id nor decision_ref -> refused, no state produced
    # a legitimate close still works afterward (the refusal left nothing broken).
    assert L.close_conflict(rule_id="R-1") == "RESOLVED_BY_RULE"
    owner = P.ProvenanceRecord(value="load-4471", provenance_class="OWNER_ASSERTED")
    with pytest.raises(P.OwnerAssertedRecompute):
        P.machine_recompute(owner, new_value="load-4718", new_class="LINKER_INFERRED")
    assert owner.value == "load-4471" and owner.provenance_class is ProvenanceClass.OWNER_ASSERTED
