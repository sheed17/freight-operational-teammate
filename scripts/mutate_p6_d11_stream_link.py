#!/usr/bin/env python3
"""Safe in-memory mutation battery for P6-D11 — the STRICT-ORDER F2 stream link.

Doctrine (CLAUDE.md §9), identical to the P3/P4/P5/M1/M2 batteries:
  * original bytes are held IN MEMORY — never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation
  * a guard that does NOT fail on the mutant proves nothing and is reported as a MISS
  * restoration is verified byte-for-byte, and the guard must be GREEN again before moving on
  * every case states the REAL defect it reintroduces

### WHAT THIS BATTERY IS FOR. The claim is that an intentionally silent M2 transition can no longer
stall a legitimate downstream consumer, AND that a genuinely lost or reordered event still parks.
The first half is easy to make true by deleting a guard. The second half is what makes it a fix
rather than a hole, so most of these mutants attack the SAFETY side: they try to prove that the
park which must still happen is really still happening, and that the link cannot be forged.

`M1` restores the exact defect this unit closed — the pre-fix contiguity rule — and the battery is
worthless if that one does not go red.

### THIS IS NOT AN INDEPENDENT REVIEW. It was written by the session that implemented the unit.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv/bin/python"

INBOX = "src/freight_recon/event_inbox.py"
OUTBOX = "src/freight_recon/event_outbox.py"
ENVELOPE = "src/freight_recon/event_envelope.py"
PL = "src/freight_recon/pipeline_instance.py"
REGISTRY = "docs/specifications/events/registry.md"

T = "eval/tests/test_p6_d11_strict_order_stream_link.py"
TM2 = "eval/tests/test_phase6_pipeline_instance.py"
T5 = "eval/tests/test_phase5_event_transport.py"

CAPABILITY = f"{T}::test_the_checkpoint_reaches_an_m3_shaped_consumer_across_an_intentional_gap"
LOST = f"{T}::test_a_genuinely_lost_event_still_parks"
REORDER = f"{T}::test_a_reordered_delivery_parks_and_then_drains_in_order"
FORGE = f"{T}::test_the_outbox_refuses_an_envelope_whose_declared_predecessor_is_a_lie"
CHAIN = f"{T}::test_every_event_of_a_real_attempt_declares_an_unbroken_chain"
LEGACY = f"{T}::test_an_unlinked_envelope_still_uses_the_contiguity_rule"
SITES = f"{T}::test_m2_builds_every_envelope_in_exactly_one_place"
DOCS = f"{T}::test_the_canonical_registry_states_the_contract_this_code_implements"
CYCLE = f"{T}::test_a_predecessor_at_or_above_its_own_version_is_not_an_envelope"
TENANT = f"{T}::test_the_link_is_derived_per_tenant_and_per_aggregate"
ITA = f"{T}::test_an_illegal_attempt_records_evidence_that_a_consumer_can_still_read"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([str(PY), "-m", "pytest", nodeid, "-q", "-p", "no:randomly"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


CASES = [
    # ---- the defect itself ---------------------------------------------------------------------
    ("M1  ### THE EXACT P6-D11 DEFECT, RESTORED. The inbox goes back to reading a gap as an "
     "unarrived event, so M3 parks at PL-6's silent version and the invoice for load 4471 is never "
     "authorized — for that load and every load after it",
     INBOX,
     "            predecessor = event.previous_aggregate_version\n",
     "            predecessor = None  # MUTANT\n",
     CAPABILITY),

    ("M1b the same defect seen from the OTHER end: the guard's own capability case is not the only "
     "thing that must go red — M2's battery asserts the emitted chain is followable",
     PL,
     "            previous_aggregate_version=TransactionalOutbox(",
     "            previous_aggregate_version=None and TransactionalOutbox(  # MUTANT",
     f"{TM2}::test_the_f2_event_stream_has_gaps_where_a_CONSUMES_row_moved_the_attempt"),

    # ---- the SAFETY half: the park that must still happen ---------------------------------------
    ("M2  the block is removed entirely, so a genuinely LOST event no longer parks and a strict "
     "consumer applies v6 with v5 missing forever. This is the hole a careless fix leaves",
     INBOX,
     "                predecessor > applied_version if predecessor is not None",
     "                False if predecessor is not None  # MUTANT",
     LOST),

    ("M3  the comparison is loosened to `>=`... in the wrong direction: `predecessor >= "
     "applied_version` parks an event whose predecessor is exactly applied, which is EVERY "
     "well-ordered event. The stream stalls on the happy path",
     INBOX,
     "                predecessor > applied_version if predecessor is not None",
     "                predecessor >= applied_version if predecessor is not None  # MUTANT",
     CAPABILITY),

    ("M4  reordered delivery stops parking: v6 arriving before v5 is applied out of order, so a "
     "consumer folds a later fact over an earlier one it has not seen",
     INBOX,
     "            if strict and blocked:",
     "            if False and strict and blocked:  # MUTANT",
     REORDER),

    ("M5  the strict/order-tolerant distinction is dropped, so an order-tolerant family starts "
     "parking on the strict rule",
     INBOX,
     "            if strict and blocked:",
     "            if blocked:  # MUTANT",
     T5),

    # ---- the link cannot be forged ---------------------------------------------------------------
    ("M6  ### THE OUTBOX STOPS VERIFYING THE DECLARED PREDECESSOR. A producer may now state any "
     "link, which is an instruction to every consumer to skip past a real event — silently, "
     "permanently, on a fact that is otherwise perfectly canonical",
     OUTBOX,
     "        if envelope.previous_aggregate_version is not None:\n            actual = self.last_emitted_version(",
     "        if envelope.previous_aggregate_version is None:  # MUTANT\n            actual = self.last_emitted_version(",
     FORGE),

    ("M6b the verification survives but is scoped to the whole tenant instead of the aggregate, so "
     "another attempt's versions supply this one's predecessor",
     OUTBOX,
     '        sql = ("SELECT COALESCE(MAX(aggregate_version), 0) FROM event_outbox "\n'
     '               "WHERE tenant = ? AND aggregate_type = ? AND aggregate_id = ?")\n'
     "        params: tuple[Any, ...] = (self._tenant, aggregate_type, aggregate_id)",
     '        sql = ("SELECT COALESCE(MAX(aggregate_version), 0) FROM event_outbox "\n'
     '               "WHERE tenant = ? AND aggregate_type = ? AND ? IS NOT NULL")  # MUTANT\n'
     "        params: tuple[Any, ...] = (self._tenant, aggregate_type, aggregate_id)",
     TENANT),

    ("M6c the derivation ignores tenant, so tenant B's stream supplies tenant A's predecessor [C-1]",
     OUTBOX,
     "        params: tuple[Any, ...] = (self._tenant, aggregate_type, aggregate_id)",
     "        params: tuple[Any, ...] = ('%', aggregate_type, aggregate_id)  # MUTANT",
     TENANT),

    ("M6d the `below` bound is dropped, so an event riding at an ALREADY-EMITTED version — which "
     "`IllegalTransitionAttempted` does, at the attempt's unchanged version — takes ITSELF as its "
     "predecessor. The chain acquires a self-loop, and the evidence of a refused attack becomes "
     "unwritable on the one surface an operator is paged from",
     OUTBOX,
     '            sql += " AND aggregate_version < ?"',
     '            sql += " AND aggregate_version <= ?"  # MUTANT',
     ITA),

    ("M7  the envelope stops refusing a forward or self-referential link, so a cycle is "
     "constructible and a consumer parks on it forever",
     ENVELOPE,
     "            if previous >= self.aggregate_version:",
     "            if previous > 10**9:  # MUTANT",
     CYCLE),

    # ---- backward compatibility ------------------------------------------------------------------
    ("M8  ### AN ABSENT LINK IS READ AS 'THERE IS NOTHING BEFORE ME'. Every historical event and "
     "every order-tolerant producer would then be applied straight through a real gap — the fix "
     "turned into a much larger version of the bug it closed",
     INBOX,
     "                else event.aggregate_version > applied_version + 1",
     "                else False  # MUTANT",
     LEGACY),

    ("M8b the link is dropped from the canonical serialization, so it never survives the outbox and "
     "every consumer silently falls back to contiguity",
     ENVELOPE,
     '            "previous_aggregate_version": self.previous_aggregate_version,\n',
     "",
     CAPABILITY),

    # ---- the structural guards themselves ---------------------------------------------------------
    ("M9  a SECOND envelope construction site appears in M2, bypassing the factory that declares "
     "the link. The AST guard is the only thing standing between that and a stream a consumer parks "
     "on",
     PL,
     "    def _reread(self, pipeline_instance_id: str) -> PipelineInstance:",
     "    def _bypass(self):  # MUTANT\n"
     "        return EventEnvelope(event_id='x', event_name='X', event_version=1,\n"
     "                             occurred_at='', recorded_at='', tenant_id='t',\n"
     "                             aggregate_type='a', aggregate_id='b', aggregate_version=1,\n"
     "                             causation_id=None, correlation_id='c', producer_component='p',\n"
     "                             producer_transition_id='PL-1', actor_type='system',\n"
     "                             actor_id='s', trace_id='t', payload={})\n\n"
     "    def _reread(self, pipeline_instance_id: str) -> PipelineInstance:",
     SITES),

    ("M10 the canonical registry loses the §8 clarification, so the mechanism becomes a local "
     "convention the next machine's author has no way to learn",
     REGISTRY,
     "- ### **STRICT MEANS *ORDER*. IT HAS NEVER MEANT *CONTIGUOUS*, AND IT CANNOT**",
     "- ### **STRICT MEANS something the reader must guess**",   # MUTANT
     DOCS),
]


def _run_case(case) -> tuple[str, str]:
    _, rel, old, new, guard = case
    path = ROOT / rel
    if not path.exists():
        return "SETUP-FAIL", f"{rel} does not exist"
    text = path.read_bytes().decode("utf-8")
    if text.count(old) != 1:
        return "SETUP-FAIL", f"anchor appears {text.count(old)}x in {rel} (need exactly 1)"
    if text.replace(old, new, 1) == text:
        return "SETUP-FAIL", f"mutation was a no-op in {rel}"

    purge_pycache()
    if not run_guard(guard):
        return "SETUP-FAIL", "guard already RED before mutation"

    original = path.read_bytes()
    try:
        path.write_text(original.decode("utf-8").replace(old, new, 1), encoding="utf-8")
        purge_pycache()
        caught = not run_guard(guard)
    finally:
        path.write_bytes(original)
        purge_pycache()
    if path.read_bytes() != original:
        return "RESTORE-RED", f"byte-for-byte restore FAILED for {path}"
    if not run_guard(guard):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def main() -> int:
    results = [(c[0], *_run_case(c)) for c in CASES]
    print("\n=========== P6-D11 STRICT-ORDER STREAM LINK MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
