#!/usr/bin/env python3
"""P7 (identity / lineage / conflict / correction) behavioural probe.

Operates each rule directly and prints a PASS line with BOTH a refusal and a positive control, so a
reviewer observes P7 behaviour without schema introspection.

Run:  .venv/bin/python scripts/probe_phase7_identity.py
      .venv/bin/python scripts/probe_phase7_identity.py --list
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon import lineage as LG  # noqa: E402
from freight_recon import linker as L  # noqa: E402
from freight_recon import provenance as P  # noqa: E402
from freight_recon.checkpoint import ProvenanceClass  # noqa: E402
from freight_recon.evidence import EvidenceStore  # noqa: E402
from freight_recon.schema import create_canonical_schema, enable_and_verify_foreign_keys  # noqa: E402

T = "acme-brokerage"
NOW = "2026-09-09T12:00:00.000Z"
_CASES: dict = {}


def case(name):
    def deco(fn):
        _CASES[name] = fn
        return fn
    return deco


def _refused(exc_type, fn) -> bool:
    try:
        fn()
        return False
    except exc_type:
        return True


def _evidence_store():
    tmp = Path(tempfile.mkdtemp(prefix="p7id-probe-"))
    conn = sqlite3.connect(str(tmp / "e.db"))
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    conn.execute(
        "INSERT INTO observations (tenant, observation_id, source_system, external_id, content_digest, "
        "raw_value, as_of, received_at, state, version, provenance_class, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?, 'RECEIVED', 1, 'SYSTEM_IMPORTED', ?, ?)",
        (T, "obs-1", "tms", "L-1", "d1", "loads page", NOW, NOW, NOW, NOW))
    conn.commit()
    store = EvidenceStore(conn)
    ev = store.retain(T, content=b"POD 4471", media_type="application/pdf",
                      source_observation_id="obs-1", now=NOW)
    store.attach_span(T, ev, locator="page 1", now=NOW, extracted_text="4471")
    return store, ev


@case("ac8-model-reads-linker-decides")
def _c() -> list[str]:
    guess = L.link("pod-1", [L.Signal("MODEL_INFER", "load-4471", confidence=1.0)])
    reentered = L.link("pod-1", [L.Signal("MODEL_EXTRACT", "load-4471", source="ocr")])
    exact = L.link("pod-1", [L.Signal("EXACT_ID", "load-4471", source="tms")])
    return [f"AC-8 a MODEL_INFER guess is never committed (AMBIGUOUS at confidence 1.0): {guess.status is L.LinkStatus.AMBIGUOUS and guess.bound_identifier is None}",
            f"AC-8 MODEL_EXTRACT re-enters and the LINKER decides (-> LINKER_INFERRED, not MODEL_EXTRACTED): {reentered.is_binding and reentered.provenance_class is ProvenanceClass.LINKER_INFERRED}",
            f"AC-8 a deterministic EXACT_ID match confirms (positive control): {exact.is_binding}"]


@case("ac9-owner-binding-persists")
def _c() -> list[str]:
    owner = P.ProvenanceRecord(value="load-4471", provenance_class="OWNER_ASSERTED")
    refused = _refused(P.OwnerAssertedRecompute,
                       lambda: L.relink(owner, "pod-1", [L.Signal("EXACT_ID", "load-4718", source="tms")]))
    survives = L.owner_binding_survives_replay([owner])
    weak = L.link("pod-1", [L.Signal("HUMAN", "load-4471")]).status is L.LinkStatus.AMBIGUOUS
    return [f"AC-9 a relink of an OWNER_ASSERTED binding is REFUSED and the owner value is preserved: {refused and owner.value == 'load-4471'}",
            f"AC-9 an OWNER_ASSERTED binding survives replay/rebuild byte-identical: {survives}",
            f"AC-9 weak/unauthenticated identity fails closed rather than guessing: {weak}"]


@case("ac10-conflict-blocks-and-closes-two-ways")
def _c() -> list[str]:
    conflict = L.link("pod-1", [L.Signal("EXACT_ID", "load-4471", source="a"),
                                L.Signal("EXACT_ID", "load-4718", source="b")])
    blocks = L.conflict_blocks("OPEN") and not L.conflict_blocks("RESOLVED_BY_RULE")
    rule = L.close_conflict(rule_id="R-12") == "RESOLVED_BY_RULE"
    human = L.close_conflict(decision_ref="dec-9") == "RESOLVED_BY_HUMAN"
    no_third = _refused(L.ConflictClosureRefused, lambda: L.close_conflict())
    return [f"AC-10 mutually exclusive candidates become a first-class Conflict that blocks while open: {conflict.status is L.LinkStatus.CONFLICT and blocks}",
            f"AC-10 a Conflict closes via a registered rule or a human decision (positive controls): {rule and human}",
            f"AC-10 a Conflict cannot be closed by a model/recency/timeout — no third way: {no_third}"]


@case("ac11-correction-vs-supersession")
def _c() -> list[str]:
    prior = L.Claim("c1", "pod-1", "load-4471", "OWNER_ASSERTED")
    s = L.supersede(prior, "load-4471-v2", "SYSTEM_IMPORTED")
    cr = L.correct(prior, "load-4718", decision_ref="dec-1", new_provenance="OWNER_ASSERTED")
    return [f"AC-11 supersession retains the prior claim and raises no downstream obligation: {s.retained == (prior,) and not s.downstream_obligation}",
            f"AC-11 correction retains the prior (attributable), emits ClaimCorrected and propagates: {cr.retained == (prior,) and cr.corrected_event['event'] == 'ClaimCorrected' and cr.downstream_obligation}"]


@case("ac7-lineage-traversable-and-fails-closed")
def _c() -> list[str]:
    store, ev = _evidence_store()
    chain = LG.trace(store, T, LG.CanonicalClaim("pod_load", "MODEL_EXTRACTED", evidence_id=ev))
    traced = chain["terminates_in"] == "evidence" and chain["source_observation_id"] == "obs-1" and len(chain["spans"]) == 1
    inferred_blocks = not LG.is_defensible(store, T, LG.CanonicalClaim("g", "MODEL_INFERRED"))
    absent_blocks = not LG.is_defensible(store, T, LG.CanonicalClaim("a", "MODEL_EXTRACTED", evidence_id="nope"))
    return [f"AC-7 a claim traces to its Evidence, spans and source Observation in one walk: {traced}",
            f"AC-7 a MODEL_INFERRED claim (no artifact) and an absent-evidence claim both fail closed: {inferred_blocks and absent_blocks}"]


@case("f14-refused-strengthening-emits-the-registered-event")
def _c() -> list[str]:
    events: list[dict] = []
    emitted = _refused(P.ProvenanceLaundering,
                       lambda: P.reassign("MODEL_INFERRED", "LINKER_INFERRED",
                                          on_strengthening_attempt=events.append))
    ok = emitted and len(events) == 1 and events[0]["event"] == "ProvenanceStrengtheningAttempted"
    quiet: list[dict] = []
    P.reassign("OWNER_ASSERTED", "MODEL_INFERRED", on_strengthening_attempt=quiet.append)
    return [f"F14 a refused laundering emits the registered ProvenanceStrengtheningAttempted: {ok}",
            f"F14 a legal weakening emits no security event (positive control): {quiet == []}"]


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
