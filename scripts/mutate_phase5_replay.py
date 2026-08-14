#!/usr/bin/env python3
"""Safe in-memory mutation battery for P5 U5.4+U5.5+U5.6 — corpus, replay, audit.

Doctrine (CLAUDE.md sec 9), identical to the P3/P4/U5.3 batteries:
  * original bytes are held IN MEMORY - never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation
  * a guard that does NOT fail on the mutant proves nothing and is reported as a MISS
  * restoration is verified byte-for-byte, and the guard must be GREEN again before moving on
  * every case states the REAL defect it reintroduces

### THE UNIT'S MUTATION REQUIREMENT IS NAMED IN THE REGISTRY: "required - replay must be proven
unable to call an adapter". R1 and R2 are that proof. The rest defend determinism, redelivery,
tenant isolation and the audit's beliefs-of-that-day rule - the properties that make a
reconstruction trustworthy rather than merely produced.

Three cases (R3, R4, R11) reintroduce defects THIS BUILD ACTUALLY SHIPPED and its own battery
caught: an arrival-ordered fold, a double-counted redelivery, and an audit that flattened facts
across aggregates so it silently disagreed with the rebuild.

### THIS IS NOT AN INDEPENDENT REVIEW. It was written by the session that implemented the unit.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv/bin/python"

RP = "src/freight_recon/event_replay.py"
AU = "src/freight_recon/event_audit.py"
GEN = "scripts/build_gc1_corpus.py"
CORPUS = "eval/fixtures/gc1-corpus.json"

T = "eval/tests/test_p5_replay_and_audit.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([str(PY), "-m", "pytest", nodeid, "-q", "-p", "no:randomly"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


TEXT_CASES = [
    # ---- the registry's mandated proof: replay cannot call an adapter -----------------------
    ("R1  replay gains a direct import of the effect boundary",
     RP,
     "from .event_contracts import read_against",
     "from .effect_boundary import execute_effect  # MUTANT\nfrom .event_contracts import read_against",
     f"{T}::test_replay_cannot_reach_an_effect_capable_module"),

    ("R2  audit reaches a store, so beliefs-of-that-day can become beliefs-of-today",
     AU,
     "from .event_contracts import CONTRACTS, contract_for",
     "from .workflow import WorkflowStore  # MUTANT\nfrom .event_contracts import CONTRACTS, contract_for",
     f"{T}::test_replay_cannot_reach_an_effect_capable_module"),

    # ---- determinism -------------------------------------------------------------------------
    ("R3  the fold returns to ARRIVAL order: a shuffled delivery rebuilds to a different digest",
     RP,
     "        for envelope in sorted(group, key=lambda e: (e.aggregate_version, e.event_id)):",
     "        for envelope in group:  # MUTANT",
     f"{T}::test_the_rebuild_is_deterministic_under_delivery_ORDER"),

    ("R4  a redelivered fact is folded twice: a duplicate reconstructs a history that never happened",
     RP,
     "        previous = seen_identities.get(identity)\n        if previous is not None:",
     "        previous = None  # MUTANT\n        if previous is not None:",
     f"{T}::test_a_duplicate_delivery_folds_to_the_same_state"),

    ("R5  the digest stops covering folded fields: a changed reconstruction pins identically",
     RP,
     '            "fields": dict(self.fields),',
     '            "fields": {},  # MUTANT',
     f"{T}::test_rebuilding_gc1_reproduces_the_pinned_digest"),

    ("R6  aggregates are no longer sorted into the digest: key order leaks into the pin",
     RP,
     '            "aggregates": [self.aggregates[k].as_document() for k in sorted(self.aggregates)],',
     '            "aggregates": [s.as_document() for s in self.aggregates.values()],  # MUTANT',
     f"{T}::test_the_rebuild_is_deterministic_under_delivery_ORDER"),

    # ---- tenant isolation --------------------------------------------------------------------
    ("R7  a bound rebuild FILTERS a foreign event instead of refusing it (C-1)",
     RP,
     "        if tenant is not None and envelope.tenant_id != tenant:",
     "        if False and tenant is not None and envelope.tenant_id != tenant:  # MUTANT",
     f"{T}::test_a_foreign_tenant_event_stops_a_bound_rebuild"),

    ("R8  the audit reads across a tenant boundary",
     AU,
     "    if foreign:",
     "    if False and foreign:  # MUTANT",
     f"{T}::test_explain_refuses_to_cross_a_tenant_boundary"),

    # ---- corrupted / unreadable history ------------------------------------------------------
    ("R9  a non-canonical event is folded instead of refused: corrupt history rebuilds silently",
     RP,
     "            if strict:\n                raise ReplayError(\n                    f\"corpus event {envelope.event_id} is not a canonical fact: {exc}\"\n                ) from exc",
     "            if False:  # MUTANT\n                raise ReplayError(\n                    f\"corpus event {envelope.event_id} is not a canonical fact: {exc}\"\n                ) from exc",
     f"{T}::test_a_corrupted_payload_is_refused_and_never_folded"),

    ("R10 an undeclared payload rider is folded into reconstructed truth",
     RP,
     "        if name in declared:",
     "        if True:  # MUTANT",
     f"{T}::test_a_payload_rider_is_carried_by_the_transport_but_never_folded_into_truth"),

    # ---- the audit ---------------------------------------------------------------------------
    ("R11 the audit flattens facts across aggregates: it reports the COMPENSATION's approval as "
     "the effect's, and silently disagrees with the rebuild",
     AU,
     '        known[ref] = folded',
     '        known.setdefault("_all", {}).update(folded); known[ref] = folded  # MUTANT',
     f"{T}::test_the_audit_answer_agrees_with_the_reconstructed_state"),

    ("R12 an absent fact is invented instead of reported UNRECONSTRUCTIBLE",
     AU,
     "    return values[-1] if values else UNRECONSTRUCTIBLE",
     '    return values[-1] if values else "none"  # MUTANT',
     f"{T}::test_an_absent_fact_is_reported_as_unreconstructible_never_invented"),

    ("R13 an UNKNOWN_OUTCOME stops being explainable AS an unknown (AC-AUD-006)",
     AU,
     '    fields["what_was_unknown"] = [',
     '    fields["what_was_unknown"] = [] and [  # MUTANT',
     f"{T}::test_an_unknown_outcome_is_explainable_AS_an_unknown"),

    ("R14 a chain with no closure event stops reporting the obligation as STILL OPEN",
     AU,
     '            "state": "STILL_OPEN",',
     '            "state": "CLOSED",  # MUTANT',
     f"{T}::test_an_absent_fact_is_reported_as_unreconstructible_never_invented"),

    ("R15 divergence detection stops reporting a field-level disagreement",
     RP,
     "            if live_value != rebuilt_value:",
     "            if False and live_value != rebuilt_value:  # MUTANT",
     f"{T}::test_a_divergence_between_rebuild_and_live_projection_is_reported_field_by_field"),

    # ---- the five defects an independent review found; none had a mutant that could reach it ----
    ("R19 the import-closure walk is gated on `node.level` again: an ABSOLUTE "
     "`from freight_recon.effect_boundary import ...` becomes invisible to the mandated M-27 proof",
     T,
     "            if isinstance(node, ast.ImportFrom):\n                if node.module:",
     "            if isinstance(node, ast.ImportFrom) and node.level:  # MUTANT\n                if node.module:",
     f"{T}::test_the_import_closure_walk_sees_every_import_spelling"),

    ("R20 the causal walk collects descendants only: an effect's checkpoint, approval and owner "
     "vanish from its own explanation",
     AU,
     "                parent = event.causation_id\n                if parent and parent in by_id and parent not in chain_ids:\n                    grown.add(parent)",
     "                pass  # MUTANT: ancestors no longer collected",
     f"{T}::test_the_causal_chain_collects_ANCESTORS_not_only_descendants"),

    ("R21 the pins flatten across the chain again: the COMPENSATION's SD-3 set is reported as the "
     "EFFECT's",
     AU,
     "    if subject is not None:\n        own = carried([e for e in events if e.aggregate_id == subject])\n        if own:\n            return _last(own)",
     "    if False and subject is not None:  # MUTANT\n        own = carried([e for e in events if e.aggregate_id == subject])\n        if own:\n            return _last(own)",
     f"{T}::test_the_pins_come_from_the_subjects_own_aggregate"),

    ("R22 explain() stops deduping: an audit reports one grant claimed TWICE",
     AU,
     "        if identity in _seen:\n            continue",
     "        if False and identity in _seen:  # MUTANT\n            continue",
     f"{T}::test_explain_is_invariant_to_a_redelivered_fact"),

    # ### R23 RETIRED, AND THE REASON IS WORTH KEEPING. It mutated `as_of` from
    # `max(e.occurred_at ...)` to `ordered[-1].occurred_at` — a real defect when `ordered` followed
    # corpus order. Once R25's fix sorted `ordered` BY `occurred_at`, the two expressions became
    # equal by construction and the mutant could no longer fail. A mutant that cannot fail is a
    # decoration (CLAUDE.md §9), so it is removed rather than left green: the property it defended
    # is now guaranteed structurally by the sort, and R25 is what defends the sort.

    ("R25 explain() reverts to CORPUS order: one chain, two arrival orders, two explanations",
     AU,
     "    ordered.sort(key=lambda e: (e.occurred_at, e.aggregate_version, e.event_id))",
     "    pass  # MUTANT: corpus order again",
     f"{T}::test_explain_is_invariant_to_a_redelivered_fact"),

    ("R24 a colliding event_id with a DIFFERENT body is silently swallowed instead of refused",
     RP,
     "            if current.digest() == previous:",
     "            if True:  # MUTANT",
     f"{T}::test_two_different_facts_sharing_one_event_id_are_refused"),

    # ---- the corpus itself -------------------------------------------------------------------
    ("R16 GC-1 loses its duplicate delivery",
     GEN,
     "    return [*events, events[7]]",
     "    return list(events)  # MUTANT",
     f"{T}::test_gc1_spans_every_condition_the_acceptance_spec_requires"),

    ("R17 GC-1 collapses to a single tenant",
     GEN,
     'TENANT_B = "brokerage-cascade"',
     'TENANT_B = "brokerage-northwind"  # MUTANT',
     f"{T}::test_gc1_spans_every_condition_the_acceptance_spec_requires"),

    ("R18 the committed corpus drifts from its builder",
     CORPUS,
     '"_corpus": "GC-1"',
     '"_corpus": "GC-1-TAMPERED"',
     f"{T}::test_the_committed_corpus_and_its_pins_are_exactly_what_the_builder_derives"),
]


def regenerate() -> None:
    """Re-derive GC-1 from the builder.

    ### A BUILDER MUTATION IS INERT UNTIL THE FIXTURE IS REBUILT — the same lesson the U5.3 battery
    learned about the contract parser, and the first run of this battery reported R16/R17 as MISSes
    for exactly that reason. Every guard reads the COMMITTED corpus, so mutating `build_gc1_corpus`
    changes nothing a test can see until the corpus is regenerated from it. Regenerating makes these
    genuine end-to-end proofs: the mutant produces a DEFICIENT CORPUS, and the span assertions catch
    the deficiency.
    """
    subprocess.run([str(PY), "scripts/build_gc1_corpus.py"],
                   cwd=ROOT, capture_output=True, text=True)


def _run_text_case(case) -> tuple[str, str]:
    label, rel, old, new, guard = case
    path = ROOT / rel
    if not path.exists():
        return "SETUP-FAIL", f"{rel} does not exist"
    original = path.read_bytes()
    text = original.decode("utf-8")
    if text.count(old) != 1:
        return "SETUP-FAIL", f"anchor appears {text.count(old)}x in {rel} (need exactly 1)"

    purge_pycache()
    if not run_guard(guard):
        return "SETUP-FAIL", "guard already RED before mutation"

    mutated = text.replace(old, new, 1)
    if mutated == text:
        return "SETUP-FAIL", "mutation was a no-op"

    is_builder = rel == GEN
    corpus_path, pin_path = ROOT / CORPUS, ROOT / "eval/fixtures/gc1-pinned-digests.json"
    fixtures = ((corpus_path, corpus_path.read_bytes()), (pin_path, pin_path.read_bytes())) \
        if is_builder else ()

    try:
        path.write_text(mutated, encoding="utf-8")
        purge_pycache()
        if is_builder:
            regenerate()
        caught = not run_guard(guard)
    finally:
        path.write_bytes(original)
        for fixture_path, fixture_bytes in fixtures:
            fixture_path.write_bytes(fixture_bytes)
        purge_pycache()
    if path.read_bytes() != original:
        return "RESTORE-RED", f"byte-for-byte restore FAILED for {rel}"
    for fixture_path, fixture_bytes in fixtures:
        if fixture_path.read_bytes() != fixture_bytes:
            return "RESTORE-RED", f"byte-for-byte restore FAILED for {fixture_path.name}"
    if not run_guard(guard):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def main() -> int:
    results = [(c[0], *_run_text_case(c)) for c in TEXT_CASES]
    print("\n=========== P5 U5.4+U5.5+U5.6 REPLAY/AUDIT MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
