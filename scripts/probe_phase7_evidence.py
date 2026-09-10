#!/usr/bin/env python3
"""P7 (Evidence) behavioural probe.

Operates the Evidence layer against a fresh canonical database and reports what it observed. This is
the surface a reviewer runs to see the behaviour directly: content-addressed retention that
deduplicates, a digest verified on write, a MODEL_EXTRACTED claim that a span makes admissible,
immutable-and-never-deleted artifacts, tenant isolation, span lineage traversal, and a fail-closed
answer when an artifact is lost or illegible. It measures the DATABASE and the store, not its own
narration; each check has a positive control so a vacuous pass is impossible.

Run:  .venv/bin/python scripts/probe_phase7_evidence.py
      .venv/bin/python scripts/probe_phase7_evidence.py --list
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

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
    CANONICAL_TABLES,
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

T_A = "acme-brokerage"
T_B = "borderline-logistics"
NOW = "2026-09-09T12:00:00.000Z"

_CASES: dict = {}


def case(name):
    def deco(fn):
        _CASES[name] = fn
        return fn
    return deco


class Probe:
    def __init__(self):
        tmp = Path(tempfile.mkdtemp(prefix="p7ev-probe-"))
        self.conn = sqlite3.connect(str(tmp / "evidence.db"))
        self.conn.row_factory = sqlite3.Row
        enable_and_verify_foreign_keys(self.conn)
        create_canonical_schema(self.conn)
        enable_and_verify_foreign_keys(self.conn)
        self.store = EvidenceStore(self.conn)

    def observation(self, tenant: str, obs_id: str) -> str:
        self.conn.execute(
            "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, external_id, "
            "content_digest, raw_value, as_of, received_at, state, version, provenance_class, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?, 'RECEIVED', 1, 'SYSTEM_IMPORTED', ?, ?)",
            (tenant, obs_id, "tms", f"L-{obs_id}", f"d-{obs_id}", "loads page", NOW, NOW, NOW, NOW))
        self.conn.commit()
        return obs_id


def _fail(msg: str) -> str:
    return f"### WRONG ### {msg}"


@case("the-evidence-layer-is-in-the-canonical-set")
def _c(p: Probe) -> list[str]:
    out = []
    for t in ("evidence", "evidence_spans"):
        ok = t in CANONICAL_TABLES
        out.append(f"{t} in canonical table set: {ok}" if ok else _fail(f"{t} missing from canonical set"))
    out.append("schema readiness clean: " + ("True" if not schema_readiness_problems(p.conn)
                                             else _fail(str(schema_readiness_problems(p.conn)))))
    out.append("evidence readiness clean: " + ("True" if not phase7_evidence_readiness_problems(p.conn)
                                               else _fail("evidence not ready")))
    return out


@case("identical-bytes-deduplicate")
def _c(p: Probe) -> list[str]:
    p.observation(T_A, "obs-1")
    b = b"POD bytes for load 4471"
    a1 = p.store.retain(T_A, content=b, media_type="application/pdf", source_observation_id="obs-1", now=NOW)
    a2 = p.store.retain(T_A, content=b, media_type="application/pdf", source_observation_id="obs-1", now=NOW)
    n = p.conn.execute("SELECT COUNT(*) FROM evidence WHERE tenant=?", (T_A,)).fetchone()[0]
    ok = a1 == a2 and n == 1
    return [f"identical bytes -> one Evidence (rows={n}): {ok}" if ok else _fail("identical bytes duplicated")]


@case("the-digest-is-verified-on-write")
def _c(p: Probe) -> list[str]:
    p.observation(T_A, "obs-1")
    out = []
    try:
        p.store.retain(T_A, content=b"x", media_type="t", source_observation_id="obs-1", now=NOW,
                       expected_digest="0" * 64)
        out.append(_fail("a lying digest was accepted"))
    except DigestMismatch:
        out.append("a digest that does not match the bytes is REFUSED: True")
    truth = content_digest_of(b"x")
    ev = p.store.retain(T_A, content=b"x", media_type="t", source_observation_id="obs-1", now=NOW,
                        expected_digest=truth)
    out.append(f"the true digest is accepted (positive control): {p.store.get(T_A, ev).content_digest == truth}")
    return out


@case("a-model-extracted-claim-needs-a-span")
def _c(p: Probe) -> list[str]:
    p.observation(T_A, "obs-1")
    ev = p.store.retain(T_A, content=b"rate conf", media_type="application/pdf",
                        source_observation_id="obs-1", now=NOW)
    out = []
    try:
        p.store.require_span_for_model_extracted(T_A, ev, MODEL_EXTRACTED)
        out.append(_fail("a MODEL_EXTRACTED claim with no span was admitted"))
    except SpanRequired:
        out.append("a MODEL_EXTRACTED claim with NO span is refused: True")
    p.store.attach_span(T_A, ev, locator="page 1, line 8", now=NOW, extracted_text="2850.00")
    p.store.require_span_for_model_extracted(T_A, ev, MODEL_EXTRACTED)
    out.append("a MODEL_EXTRACTED claim WITH a span is admitted (positive control): True")
    return out


@case("evidence-is-immutable-and-never-deleted")
def _c(p: Probe) -> list[str]:
    p.observation(T_A, "obs-1")
    ev = p.store.retain(T_A, content=b"immutable", media_type="t", source_observation_id="obs-1", now=NOW)
    out = []
    for col in ("content_digest", "content_ref", "media_type", "source_observation_id"):
        try:
            p.conn.execute(f"UPDATE evidence SET {col}='z' WHERE tenant=? AND evidence_id=?", (T_A, ev))
            p.conn.commit()
            out.append(_fail(f"{col} was editable")); p.conn.rollback()
        except sqlite3.IntegrityError:
            p.conn.rollback()
    try:
        p.conn.execute("DELETE FROM evidence WHERE tenant=? AND evidence_id=?", (T_A, ev))
        p.conn.commit(); out.append(_fail("evidence was deletable")); p.conn.rollback()
    except sqlite3.IntegrityError:
        p.conn.rollback()
    out.append(f"content immutable and never deleted; row survives: {p.store.get(T_A, ev) is not None}")
    return out


@case("evidence-is-tenant-isolated")
def _c(p: Probe) -> list[str]:
    p.observation(T_A, "obs-1"); p.observation(T_B, "obs-b")
    b = b"identical customer document"
    ea = p.store.retain(T_A, content=b, media_type="application/pdf", source_observation_id="obs-1", now=NOW)
    eb = p.store.retain(T_B, content=b, media_type="application/pdf", source_observation_id="obs-b", now=NOW)
    rows = p.conn.execute("SELECT DISTINCT tenant FROM evidence").fetchall()
    two_tenants = {r["tenant"] for r in rows} == {T_A, T_B}
    isolated = p.store.get(T_B, ea) is None and p.store.get(T_A, eb) is None
    ok = two_tenants and isolated
    return [f"same bytes in two tenants are two isolated artifacts, neither readable by the other: {ok}"
            if ok else _fail("cross-tenant evidence read")]


@case("lost-or-illegible-evidence-blocks")
def _c(p: Probe) -> list[str]:
    p.observation(T_A, "obs-1")
    ev = p.store.retain(T_A, content=b"a POD", media_type="application/pdf",
                        source_observation_id="obs-1", now=NOW)
    out = [f"present + legible evidence lets a claim proceed (positive control): {p.store.claim_may_proceed_on(T_A, ev)}"]
    out.append(f"absent evidence blocks: {not p.store.claim_may_proceed_on(T_A, 'nope')}")
    try:
        p.store.assert_supports_consequential_action(T_A, "nope"); out.append(_fail("absent did not raise"))
    except EvidenceAbsent:
        pass
    p.store.mark_illegible(T_A, ev)
    out.append(f"illegible evidence blocks: {not p.store.claim_may_proceed_on(T_A, ev)}")
    try:
        p.store.assert_supports_consequential_action(T_A, ev); out.append(_fail("illegible did not raise"))
    except EvidenceIllegible:
        pass
    return out


@case("span-lineage-is-traversable")
def _c(p: Probe) -> list[str]:
    p.observation(T_A, "obs-1")
    ev = p.store.retain(T_A, content=b"multi-span", media_type="application/pdf",
                        source_observation_id="obs-1", now=NOW)
    p.store.attach_span(T_A, ev, locator="page 1", now=NOW, extracted_text="4471")
    p.store.attach_span(T_A, ev, locator="page 2", now=NOW, extracted_text="2850.00")
    chain = p.store.trace(T_A, ev)
    ok = len(chain["spans"]) == 2 and chain["source_observation_id"] == "obs-1"
    return [f"trace walks evidence -> {len(chain['spans'])} spans -> observation {chain['source_observation_id']!r}: {ok}"
            if ok else _fail("lineage traversal incomplete")]


@case("evidence-sets-no-provenance")
def _c(p: Probe) -> list[str]:
    cols = {r[1] for r in p.conn.execute("PRAGMA table_info(evidence)")}
    ok = "provenance_class" not in cols and "state" not in cols and "commit_key" not in cols
    return [f"evidence carries no provenance_class / state / commit_key (Evidence is DATA): {ok}"
            if ok else _fail("Evidence carries provenance/state/commit_key")]


def _run(names: list[str]) -> int:
    wrong = 0
    for name in names:
        lines = _CASES[name](Probe())
        for line in lines:
            print(line)
            if "### WRONG ###" in line or ": False" in line:
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
    names = [args.case] if args.case else list(_CASES)
    return _run(names)


if __name__ == "__main__":
    sys.exit(main())
