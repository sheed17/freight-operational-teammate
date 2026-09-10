"""P7 — Evidence — acceptance and hostile battery (P7-AC-6, with P7-AC-7/12/15 touches).

Entity 08-evidence sec 44 names seven adversarial tests; they are here by those names. The rest of
the battery covers content addressing as idempotency, the immutability the database enforces, the
fail-closed behaviour when an artifact is lost or illegible, span lineage traversal, and the
ship-dark posture. Several node ids are the guards `scripts/mutate_phase7_evidence.py` turns RED — a
guard never seen to fail is a decoration.

The suite protects the Evidence layer's actual behaviour: a retained artifact can never be quietly
rewritten, duplicated, deleted, or made to authorize a claim it cannot support. Evidence is DATA — it
may EVIDENCE a claim; it may never MAKE one, authorize an effect, or set provenance (M-66).
"""

from __future__ import annotations

import ast
import sqlite3
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "freight_recon"

from freight_recon.evidence import (  # noqa: E402
    MODEL_EXTRACTED,
    DigestMismatch,
    EvidenceAbsent,
    EvidenceIllegible,
    EvidenceStore,
    SpanRequired,
    content_digest_of,
)
from freight_recon.migrations.phase7_evidence import (  # noqa: E402
    phase7_evidence_readiness_problems,
)
from freight_recon.schema import (  # noqa: E402
    ALL_TENANT_TABLES,
    CANONICAL_TABLES,
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

T_A = "acme-brokerage"
T_B = "borderline-logistics"
NOW = "2026-09-09T10:00:00.000Z"


def require_population(items, what: str):
    """A negative/absence assertion over an empty set passes while proving nothing. Refuse that."""
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


def _conn() -> sqlite3.Connection:
    tmp = Path(tempfile.mkdtemp(prefix="p7ev-test-"))
    conn = sqlite3.connect(str(tmp / "evidence.db"))
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _observation(conn: sqlite3.Connection, tenant: str, observation_id: str) -> str:
    """A minimal valid Observation row: Evidence enters via the Observation that retained it, so the
    `source_observation_id` FK needs a real referent."""
    conn.execute(
        "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, external_id, "
        "content_digest, raw_value, as_of, received_at, state, version, provenance_class, "
        "created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?, 'RECEIVED', 1, 'SYSTEM_IMPORTED', ?, ?)",
        (tenant, observation_id, "tms", f"L-{observation_id}", f"digest-{observation_id}",
         "the loads page as read", NOW, NOW, NOW, NOW),
    )
    conn.commit()
    return observation_id


def _store(tenant: str = T_A, observation_id: str = "obs-1"):
    conn = _conn()
    _observation(conn, tenant, observation_id)
    return EvidenceStore(conn), conn


# =============================================================== the layer landed (P7-S08 / AC-6)


def test_the_evidence_layer_landed_tenant_first_and_in_the_canonical_set():
    """P7-S08's subject: the canonical schema/table set contains `evidence` AND `evidence_spans`, and
    both are tenant-first. A fresh canonical database is READY with them present."""
    for table in ("evidence", "evidence_spans"):
        assert table in CANONICAL_TABLES, f"{table} is not in the canonical table set"
        assert table in ALL_TENANT_TABLES, f"{table} is not tenant-owned"
    conn = _conn()
    assert schema_readiness_problems(conn) == []
    assert phase7_evidence_readiness_problems(conn) == []
    present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"evidence", "evidence_spans"} <= present
    for table in ("evidence", "evidence_spans"):
        pk = [r[1] for r in conn.execute(f"PRAGMA table_info({table})") if r[5]]
        assert pk and pk[0] == "tenant", f"{table} primary key is not tenant-first: {pk}"


# =============================================================== entity sec 44 adversarial tests


def test_identical_bytes_deduplicate():
    """entity sec 43(a)/44: storing identical bytes twice yields ONE Evidence. Content addressing is
    the idempotency (entity sec 33)."""
    store, conn = _store()
    payload = b"POD PDF bytes for load 4471"
    first = store.retain(T_A, content=payload, media_type="application/pdf",
                         source_observation_id="obs-1", now=NOW)
    second = store.retain(T_A, content=payload, media_type="application/pdf",
                          source_observation_id="obs-1", now=NOW)
    assert first == second, "identical bytes produced two different Evidence ids"
    count = conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant = ?", (T_A,)).fetchone()[0]
    assert count == 1, f"identical bytes deduplicated to {count} rows, not one"


def test_digest_mismatch_rejected_on_write():
    """entity sec 43(b)/44: a caller-asserted digest that does not match the RUNTIME hash of the bytes
    is refused. A content-addressed row whose bytes do not match its digest is impossible."""
    store, _ = _store()
    payload = b"the real bytes"
    with pytest.raises(DigestMismatch):
        store.retain(T_A, content=payload, media_type="text/plain", source_observation_id="obs-1",
                     now=NOW, expected_digest="0" * 64)
    # positive control: the TRUE digest is accepted, so the guard is not simply always-raising.
    truth = content_digest_of(payload)
    ev = store.retain(T_A, content=payload, media_type="text/plain", source_observation_id="obs-1",
                      now=NOW, expected_digest=truth)
    assert store.get(T_A, ev).content_digest == truth


def test_model_extracted_claim_requires_evidence_span():
    """entity sec 43(c)/44, ADR-002 sec 2.3: a MODEL_EXTRACTED claim MUST reference an Evidence span —
    the region that makes the reading checkable. Without a span it is indistinguishable from a guess."""
    store, _ = _store()
    ev = store.retain(T_A, content=b"rate confirmation", media_type="application/pdf",
                      source_observation_id="obs-1", now=NOW)
    with pytest.raises(SpanRequired):
        store.require_span_for_model_extracted(T_A, ev, MODEL_EXTRACTED)
    # positive control: once a span exists, the MODEL_EXTRACTED claim is admissible.
    store.attach_span(T_A, ev, locator="page 1, line 8", now=NOW, extracted_text="2850.00")
    store.require_span_for_model_extracted(T_A, ev, MODEL_EXTRACTED)  # does not raise


def test_lost_evidence_blocks_consequential_action():
    """entity sec 36/44, ADR-007 sec 10: a claim whose evidence is absent or illegible BLOCKS — it
    fails closed rather than degrading to best-available."""
    store, _ = _store()
    ev = store.retain(T_A, content=b"a POD", media_type="application/pdf",
                      source_observation_id="obs-1", now=NOW)
    # present + legible: the positive control that proves the block is not unconditional.
    assert store.claim_may_proceed_on(T_A, ev) is True
    store.assert_supports_consequential_action(T_A, ev)  # does not raise

    # absent: a claim on evidence that was never retained blocks.
    assert store.claim_may_proceed_on(T_A, "no-such-evidence") is False
    with pytest.raises(EvidenceAbsent):
        store.assert_supports_consequential_action(T_A, "no-such-evidence")

    # illegible: retained but unreadable blocks, and the distinction is preserved in the exception.
    store.mark_illegible(T_A, ev)
    assert store.claim_may_proceed_on(T_A, ev) is False
    with pytest.raises(EvidenceIllegible):
        store.assert_supports_consequential_action(T_A, ev)


def test_evidence_content_is_immutable():
    """entity sec 6/16/22/44, C-8: the content and identity of an Evidence never mutate, and the row
    is never deleted. The database refuses it — a trigger, not a comment."""
    store, conn = _store()
    ev = store.retain(T_A, content=b"immutable bytes", media_type="text/plain",
                      source_observation_id="obs-1", now=NOW)
    for column, value in (("content_digest", "x"), ("content_ref", "x"),
                          ("media_type", "x"), ("source_observation_id", "obs-1"),
                          ("evidence_id", "x")):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"UPDATE evidence SET {column} = ? WHERE tenant = ? AND evidence_id = ?",
                         (value, T_A, ev))
        conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM evidence WHERE tenant = ? AND evidence_id = ?", (T_A, ev))
    conn.rollback()
    # the row survived every attempt.
    assert store.get(T_A, ev) is not None


def test_cross_tenant_evidence_isolation():
    """entity sec 7/35/44, C-1: the same bytes in two tenants are two isolated artifacts, and one
    tenant can never read the other's Evidence. There is no honest cross-tenant reading of a document."""
    store_a, conn_a = _store(T_A, "obs-1")
    payload = b"identical customer document bytes"
    ev_a = store_a.retain(T_A, content=payload, media_type="application/pdf",
                          source_observation_id="obs-1", now=NOW)
    # T_B, on the SAME connection's database, retains the identical bytes: a distinct Evidence.
    _observation(conn_a, T_B, "obs-b")
    ev_b = store_a.retain(T_B, content=payload, media_type="application/pdf",
                          source_observation_id="obs-b", now=NOW)
    rows = require_population(
        conn_a.execute("SELECT tenant, content_digest FROM evidence").fetchall(), "evidence rows")
    same_digest = {r["content_digest"] for r in rows}
    assert len(same_digest) == 1, "the two tenants' identical bytes hashed differently — test is wrong"
    assert {r["tenant"] for r in rows} == {T_A, T_B}, "the two tenants are not both present"
    # ### THE ISOLATION: T_B's store view cannot see T_A's Evidence id, and vice versa.
    assert store_a.get(T_B, ev_a) is None, "T_B read T_A's Evidence by id — tenant isolation breached"
    assert store_a.get(T_A, ev_b) is None, "T_A read T_B's Evidence by id — tenant isolation breached"
    assert store_a.get(T_A, ev_a) is not None and store_a.get(T_B, ev_b) is not None


# =============================================================== Evidence is DATA, not a claim


def test_evidence_is_data_it_carries_no_provenance_and_no_lifecycle():
    """entity sec 35, ADR-002 sec 2.3, M-66: Evidence sets no provenance and has no lifecycle. A
    provenance_class column would make the artifact look like it could set the trust of the claim that
    points at it; a state column would make a revised artifact a state change instead of a new
    Evidence. Both are structurally absent."""
    conn = _conn()
    columns = {r[1] for r in conn.execute("PRAGMA table_info(evidence)")}
    assert "provenance_class" not in columns, "evidence carries a provenance_class — Evidence is DATA"
    assert "state" not in columns, "evidence carries a state column — Evidence has no lifecycle"
    assert "commit_key" not in columns, "evidence carries a commit_key — Evidence makes no effect"


def test_content_addressing_is_idempotent_under_replay():
    """entity sec 33/34, C-3/C-5: retaining the same bytes any number of times reconstructs the same
    single Evidence and the same digest — content addressing is the idempotency."""
    store, conn = _store()
    payload = b"replayable artifact"
    ids = {store.retain(T_A, content=payload, media_type="text/plain",
                        source_observation_id="obs-1", now=NOW) for _ in range(5)}
    assert len(ids) == 1, f"content addressing was not idempotent: {ids}"
    count = conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant = ?", (T_A,)).fetchone()[0]
    assert count == 1
    assert store.get(T_A, next(iter(ids))).content_digest == content_digest_of(payload)


def test_span_lineage_is_traversable_from_evidence_to_observation():
    """ADR-002 sec 2.1 concern 5, ADR-007 sec 13: from an Evidence, walk to its spans and the source
    observation. The chain terminates in a source observation id, never a dangling pointer (P7-AC-7's
    generic mechanism, exercised over the Evidence layer)."""
    store, _ = _store()
    ev = store.retain(T_A, content=b"multi-span doc", media_type="application/pdf",
                      source_observation_id="obs-1", now=NOW)
    store.attach_span(T_A, ev, locator="page 1", now=NOW, extracted_text="4471")
    store.attach_span(T_A, ev, locator="page 2", now=NOW, extracted_text="2850.00")
    chain = store.trace(T_A, ev)
    spans = require_population(chain["spans"], "spans on the traced evidence")
    assert len(spans) == 2, f"traversal lost a span: {spans}"
    assert chain["source_observation_id"] == "obs-1", "the chain did not terminate in its observation"
    assert chain["evidence"].evidence_id == ev


def test_the_content_addressing_index_is_unique_and_covers_tenant_and_digest():
    """entity sec 17: 'identical bytes are one Evidence' is a UNIQUE index on (tenant, content_digest),
    read out of the live database rather than assumed from its name — the dedup defence, not a comment."""
    conn = _conn()
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name = 'ix_evidence_content_addressing'"
    ).fetchone()
    assert row is not None, "the content-addressing index is missing"
    sql = " ".join(row[0].split()).upper()
    assert "UNIQUE" in sql, "the content-addressing index is not UNIQUE — dedup is off"
    for column in ("TENANT", "CONTENT_DIGEST"):
        assert column in sql, f"the content-addressing index dropped {column}"


def test_superseded_evidence_is_retained_not_deleted():
    """entity sec 24/28: a newer artifact supersedes an older one; the OLD is RETAINED because a claim
    may have rested on it. Supersession sets a link, never deletes."""
    store, _ = _store()
    old = store.retain(T_A, content=b"POD v1", media_type="application/pdf",
                       source_observation_id="obs-1", now=NOW)
    new = store.retain(T_A, content=b"POD v2 corrected", media_type="application/pdf",
                       source_observation_id="obs-1", now=NOW)
    store.supersede(T_A, old, new)
    old_row = store.get(T_A, old)
    assert old_row is not None, "the superseded Evidence was deleted — history was lost"
    assert old_row.superseded_by == new
    assert store.get(T_A, new).superseded_by is None


# =============================================================== ships dark (P7-AC-15 touch)


def _src_modules() -> list[Path]:
    return require_population(sorted(SRC.rglob("*.py")), "src/freight_recon modules")


def test_the_evidence_store_ships_dark_with_no_production_importer():
    """P7 ships dark: nothing in production imports the Evidence STORE (`evidence.py`). Discovered by
    AST over the whole src tree with the denominator printed — never a hand-enumerated filename list
    (CLAUDE.md sec 6). Importing the phase7_evidence MIGRATION is expected (schema.py builds tables);
    importing the store would join a dark surface to a live path."""
    importers = []
    inspected = 0
    for path in _src_modules():
        if path.name == "evidence.py":
            continue
        inspected += 1
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in ("freight_recon.evidence", ".evidence"):
                importers.append(f"{path.name}: from {node.module}")
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith(".evidence"):
                importers.append(f"{path.name}: from {node.module}")
    print(f"P7-AC-15 (evidence store): inspected {inspected} src modules for a production importer")
    assert inspected > 0, "the ship-dark sweep inspected nothing"
    assert not importers, f"the Evidence store has production importer(s): {importers}"


def test_the_evidence_store_mints_no_canonical_event_and_no_gate():
    """P7-AC-15: the Evidence layer mints no canonical event (the frozen 105-event registry is
    untouched) and no gate decision — Evidence is DATA. Structural: `evidence.py` imports neither the
    event transport nor the checkpoint/gate kernel."""
    tree = ast.parse((SRC / "evidence.py").read_text(encoding="utf-8"))
    forbidden = {"event_outbox", "event_contracts", "checkpoint", "governed_write_registry"}
    reached = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            tail = node.module.rsplit(".", 1)[-1]
            if tail in forbidden:
                reached.append(node.module)
    assert not reached, f"the Evidence store reaches an event/gate module: {reached}"
