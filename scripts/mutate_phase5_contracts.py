#!/usr/bin/env python3
"""Safe in-memory mutation battery for the P5 U5.3 canonical event contracts.

Doctrine (CLAUDE.md sec 9), identical to the P3 and P4 batteries:
  * original bytes are held IN MEMORY - never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation, or a same-length restore within one mtime tick
    leaves poisoned bytecode and reports a false green
  * a guard that does NOT fail on the mutant proves nothing and is reported as a MISS
  * restoration is verified byte-for-byte, and the guard must be GREEN again before moving on
  * every case states the REAL defect it reintroduces

WHAT THIS AUDITS, and why each target is load-bearing:

  `event_contracts.py`      the validator. Each mutation removes ONE refusal, and the defect it
                            reintroduces is a class of non-canonical fact becoming committable.
  `event_outbox.py`         the contract GATE's position - inside the transaction, before the
                            INSERT. Moving or removing it is what makes a bad fact durable.
  `event_inbox.py`          the read path. Removing the check hands a handler an unvalidated fact.
  `events/registry.md`      ### THE SPECIFICATION ITSELF. Two cases edit the canonical corpus to
                            prove the anti-drift guard is real: a runtime that kept serving the old
                            contracts after a spec edit would be a second authority, silently.
  `generate_event_contracts.py` THE PARSER. Four real defects lived here and no original case
                            could reach them, because every fixture in the suite is derived from this
                            file's own output. These are checked by the INDEPENDENTLY-WRITTEN oracle.

### THIS IS NOT AN INDEPENDENT REVIEW. It was written by the session that implemented U5.3. A
battery that agrees with its author is evidence, never adjudication - the independent reviewer runs
its own.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv/bin/python"

EC = "src/freight_recon/event_contracts.py"
ECD = "src/freight_recon/event_contracts_data.json"
GEN = "scripts/generate_event_contracts.py"
OUT = "src/freight_recon/event_outbox.py"
INB = "src/freight_recon/event_inbox.py"
REG = "docs/specifications/events/registry.md"
FAM4 = "docs/specifications/events/04-approval-events.md"

CON = "eval/tests/test_p5_event_contracts.py"
TRANS = "eval/tests/test_phase5_event_transport.py"
NULLGATE = "eval/tests/test_phase0_null_gate.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    """True when the guard PASSES."""
    r = subprocess.run([str(PY), "-m", "pytest", nodeid, "-q", "-p", "no:randomly"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# ---------------------------------------------------------------------------------------------
# (label, rel_file, old, new, guard_nodeid). `old` must appear exactly once; a no-op or an
# ambiguous anchor is a SETUP-FAIL, never a MISS.
# ---------------------------------------------------------------------------------------------
TEXT_CASES = [
    ("C1  unknown event names accepted by the VALIDATION gate: any string becomes a canonical fact",
     EC,
     '    contract = contracts.get(envelope.event_name)\n    if contract is None:\n        raise UnknownEventName(f"{envelope.event_name!r} is not a canonical event contract")',
     '    contract = contracts.get(envelope.event_name)\n    if contract is None:\n        contract = next(iter(contracts.values()))  # MUTANT',
     f"{CON}::test_an_unknown_event_name_is_refused_by_the_validator"),

    ("C37 `contract_for` stops refusing an unknown name — the SECOND refusal path, which C1 alone "
     "no longer isolates now that the validation gate has its own",
     EC,
     "    contract = CONTRACTS.get(event_name)\n    if contract is None:",
     "    contract = CONTRACTS.get(event_name)\n    if contract is None and False:  # MUTANT",
     f"{CON}::test_contract_for_itself_refuses_an_unknown_name"),

    ("C2  producer attribution unchecked: BrakeReleased can be attributed to WI-1",
     EC,
     "    if contract.producers and envelope.producer_transition_id not in contract.producers:",
     "    if False and contract.producers and envelope.producer_transition_id not in contract.producers:  # MUTANT",
     f"{CON}::test_a_canonical_name_attributed_to_the_wrong_transition_is_refused"),

    ("C3  aggregate binding unchecked: an event orders against a foreign history",
     EC,
     "    if contract.aggregate_type is not None and envelope.aggregate_type != contract.aggregate_type:",
     "    if False and contract.aggregate_type is not None and envelope.aggregate_type != contract.aggregate_type:  # MUTANT",
     f"{CON}::test_a_canonical_event_on_the_wrong_aggregate_type_is_refused"),

    ("C4  required payload fields optional: an event omits the fact it exists to record",
     EC,
     "            if spec.required:\n                raise PayloadContractViolation(",
     "            if spec.required and False:  # MUTANT\n                raise PayloadContractViolation(",
     f"{CON}::test_dropping_any_single_required_field_is_refused"),

    ("C5  null accepted for a required field: a fact asserts its own absence",
     EC,
     "        if spec.required and value is None:",
     "        if False and spec.required and value is None:  # MUTANT",
     f"{CON}::test_a_required_field_present_as_null_is_refused"),

    ("C6  enum constraint dropped: a declared vocabulary accepts anything",
     EC,
     "        if spec.enum is not None and value is not None:",
     "        if False and spec.enum is not None and value is not None:  # MUTANT",
     f"{CON}::test_a_value_outside_a_declared_enum_is_refused"),

    ("C7  fixed values mutable: ApprovalFrozen can say frozen=false",
     EC,
     "        if spec.fixed is not None and value is not None:",
     "        if False and spec.fixed is not None and value is not None:  # MUTANT",
     f"{CON}::test_a_fixed_value_cannot_be_changed"),

    ("C8  one-of collapses: both members accepted, an unresolvable fact",
     EC,
     "        if len(answered) > 1:",
     "        if False and len(answered) > 1:  # MUTANT",
     f"{CON}::test_a_one_of_group_takes_exactly_one_member"),

    ("C9  PRODUCER accepts an invented field: a typo becomes durable history",
     EC,
     "    if mode is ValidationMode.PRODUCER:",
     "    if False and mode is ValidationMode.PRODUCER:  # MUTANT",
     f"{CON}::test_a_producer_may_not_invent_a_payload_field_but_a_consumer_ignores_one"),

    ("C10 CONSUMER refuses an additive field: sec 6's mixed-version rule broken the other way",
     EC,
     "    if mode is ValidationMode.PRODUCER:",
     "    if mode in (ValidationMode.PRODUCER, ValidationMode.CONSUMER):  # MUTANT",
     f"{CON}::test_a_producer_may_not_invent_a_payload_field_but_a_consumer_ignores_one"),

    ("C11 consequential pins unenforced: a decision becomes unreproducible (ER-13)",
     EC,
     "    if not contract.consequential:\n        return",
     "    if True:  # MUTANT\n        return",
     f"{CON}::test_a_consequential_event_without_its_pins_is_refused"),

    ("C12 automation may broaden authority: a machine releases a brake (ER-11/ER-12)",
     EC,
     "    if contract.name in HUMAN_ONLY_EVENTS and actor != \"human\":",
     "    if False and contract.name in HUMAN_ONLY_EVENTS and actor != \"human\":  # MUTANT",
     f"{CON}::test_an_automated_actor_may_never_broaden_authority"),

    ("C13 a model states a fact: ER-9's claim/proposal confinement removed",
     EC,
     "    if actor == \"model\" and contract.name not in MODEL_PERMITTED_EVENTS:",
     "    if False and actor == \"model\" and contract.name not in MODEL_PERMITTED_EVENTS:  # MUTANT",
     f"{CON}::test_a_model_actor_may_only_claim_or_propose_never_state_a_fact"),

    ("C14 a machine asserts OWNER_ASSERTED: an inference laundered into an owner's word (ER-10)",
     EC,
     "    if actor in _AUTOMATED_ACTORS and _asserts_owner_provenance(envelope):",
     "    if False and actor in _AUTOMATED_ACTORS:  # MUTANT",
     f"{CON}::test_a_machine_actor_cannot_assert_owner_asserted_provenance"),

    ("C15 a future version is read anyway: an unknown schema silently reinterpreted (sec 6)",
     EC,
     "    if envelope.event_version > contract.current_version:\n        raise UnsupportedFutureVersion(",
     "    if envelope.event_version > contract.current_version and False:  # MUTANT\n        raise UnsupportedFutureVersion(",
     f"{CON}::test_an_event_from_an_unsupported_future_version_is_refused"),

    ("C16 a missing upcaster link passes through: a v1 body read under v3 assumptions (M-25)",
     EC,
     "            if upcaster is None:\n                raise MissingUpcaster(",
     "            if upcaster is None and False:  # MUTANT\n                raise MissingUpcaster(",
     f"{CON}::test_a_missing_upcaster_link_is_refused_never_passed_through"),

    ("C17 the outbox contract gate removed: a non-canonical fact becomes durable",
     OUT,
     "        validate(envelope, mode=ValidationMode.PRODUCER)",
     "        pass  # MUTANT: contract gate removed",
     f"{CON}::test_an_unknown_event_name_cannot_be_committed_to_the_outbox"),

    ("C18 the inbox contract gate removed: a handler is handed an unvalidated fact",
     INB,
     "            event = read_canonical(event, upcasters=self._upcasters)",
     "            event = event  # MUTANT: contract gate removed",
     f"{CON}::test_an_unknown_event_name_is_refused_by_the_inbox_as_malformed"),

    ("C19 tenant precedence lost: the contract check runs BEFORE [C-1]",
     INB,
     "        if event.tenant_id != self._tenant:",
     "        if False and event.tenant_id != self._tenant:  # MUTANT",
     f"{TRANS}::test_an_event_for_another_tenant_is_rejected_before_the_handler_and_before_any_write"),

    # ---- the specification itself: the anti-drift guard must be real -------------------------
    ("C20 SPEC DRIFT - a canonical name changes and the runtime keeps the old contract",
     FAM4,
     "**`ApprovalFrozen`** AP-9",
     "**`ApprovalQuarantined`** AP-9",
     f"{CON}::test_the_generated_contract_data_is_exactly_what_the_specification_derives"),

    ("C21 SPEC DRIFT - the CONSEQUENTIAL set loses a member and the runtime never notices",
     REG,
     "`ApprovalRequested`, `ApprovalGranted`, `ApprovalConsumed`, `CheckpointPassed`",
     "`ApprovalRequested`, `ApprovalGranted`, `CheckpointPassed`",
     f"{CON}::test_the_consequential_set_is_exactly_registry_section_5"),

    # ---- THE PARSER ITSELF ---------------------------------------------------------------------
    #
    # ### THE COVERAGE HOLE AN INDEPENDENT REVIEW NAMED, NOW CLOSED. The battery mutated the
    # validator, the gates and the specification — but never `generate_event_contracts.py`. Four
    # real defects lived in the parser, and not one of the original 21 cases could have caught them,
    # because every fixture in the suite is derived from the parser's own output (self-consistent by
    # construction). These cases mutate the parser and are checked by the INDEPENDENTLY-WRITTEN
    # oracle in section 1b of the battery, which is the only thing that can see them.

    ("C22 fixed values read from free prose: a derivation formula becomes a literal, and "
     "ClaimProposed/ObservationReceived become unemittable",
     GEN,
     '    m_fixed = re.search(r"`\\s*=\\s*([A-Za-z][A-Za-z0-9_]*)\\s*`", annotation)',
     '    m_fixed = re.search(r"=\\s*`?([A-Za-z][A-Za-z0-9_]*)`?", annotation)  # MUTANT',
     f"{CON}::test_the_fixed_values_are_exactly_the_ones_a_human_read_off_the_family_files"),

    ("C23 strict-order harvests the ORDER-TOLERANT half of section 8's line too",
     GEN,
     "    strict_half, _, tolerant_half = line.partition(\"Order-tolerant\")",
     "    strict_half, _, tolerant_half = line, '', line  # MUTANT",
     f"{CON}::test_the_strict_order_families_are_exactly_the_ones_the_registry_requires"),

    ("C24 a global RULE is accepted as a producer transition (GR-1)",
     GEN,
     '        if tid.startswith("GR-"):\n            continue',
     '        if tid.startswith("GR-") and False:  # MUTANT\n            continue',
     f"{CON}::test_no_contract_is_attributed_to_a_global_rule_instead_of_a_transition"),

    ("C25 the human-only constraint is not read from the family files: ApprovalGranted and "
     "RuleActivated accept a machine actor",
     GEN,
     "def parse_human_only(notes: str) -> bool:\n    return bool(_HUMAN_ONLY.search(notes))",
     "def parse_human_only(notes: str) -> bool:\n    return False  # MUTANT",
     f"{CON}::test_the_human_only_contracts_are_the_ones_the_family_files_declare_unconditionally"),

    # ---- the authority holes the review found --------------------------------------------------
    ("C26 ER-10 evadable again: provenance_refs and Enum members stop being inspected",
     EC,
     "    return walk(envelope.payload, 0) or walk(envelope.provenance_refs or {}, 0)",
     "    return envelope.payload.get('provenance_class') == OWNER_ASSERTED  # MUTANT",
     f"{CON}::test_owner_asserted_provenance_cannot_be_smuggled_past_er_10"),

    ("C27 a model confirms a consequential identity binding (GR-8)",
     EC,
     '_MODEL_FORBIDDEN_CLAIMS: frozenset[str] = frozenset({"ClaimConfirmed"})',
     "_MODEL_FORBIDDEN_CLAIMS: frozenset[str] = frozenset()  # MUTANT",
     f"{CON}::test_a_model_actor_may_only_claim_or_propose_never_state_a_fact"),

    ("C28 a constrained field accepts a list: ClaimRefused records two causes at once",
     EC,
     "        if ((spec.enum is not None or spec.fixed is not None)",
     "        if (False and (spec.enum is not None or spec.fixed is not None)  # MUTANT",
     f"{CON}::test_a_constrained_field_refuses_a_collection"),

    ("C32 the collection refusal is BROADENED back to every scalar: 14 canonical contracts, "
     "including CheckpointPassed's SD-3 set, become unsatisfiable",
     EC,
     "        if ((spec.enum is not None or spec.fixed is not None)\n"
     "                and not spec.listed and isinstance(value, (list, tuple, Mapping))):",
     "        if not spec.listed and isinstance(value, (list, tuple, Mapping)):  # MUTANT",
     f"{CON}::test_a_spec_declared_structured_field_is_accepted"),

    ("C33 section 5's qualifier is discarded: a deterministic ClaimConfirmed is forced to pin a "
     "decision context it has none of",
     GEN,
     '    return tuple(re.findall(r"`([A-Za-z][A-Za-z0-9]*)`\\s*\\(", listing[0]))',
     "    return ()  # MUTANT",
     f"{CON}::test_the_conditionally_consequential_member_is_not_pinned_unconditionally"),

    ("C29 a consequential pin may be blank: an empty string reproduces no decision context",
     EC,
     "        if isinstance(value, str):\n            return not value.strip()",
     "        if isinstance(value, str):\n            return False  # MUTANT",
     f"{CON}::test_a_blank_consequential_pin_is_no_pin_at_all"),

    ("C30 a producer may emit a stale version: body and stamped version disagree",
     EC,
     "    if mode is ValidationMode.PRODUCER and envelope.event_version != contract.current_version:",
     "    if False and mode is ValidationMode.PRODUCER:  # MUTANT",
     f"{CON}::test_a_producer_must_emit_the_current_version"),

    ("C31 the contract data stops agreeing with the transport that enforces ordering",
     GEN,
     '            "strict_order": entry["family"] in strict_families,',
     '            "strict_order": True,  # MUTANT',
     f"{CON}::test_the_contract_strict_order_agrees_with_the_transport_that_enforces_it"),

    ("C34 a required one-of is satisfied by a null: ConflictResolved carries no resolution ref",
     EC,
     "        present = [m for m in answered if payload[m] is not None]",
     "        present = answered  # MUTANT",
     f"{CON}::test_a_required_one_of_is_not_answered_by_a_null"),

    ("C35 the fixed check stops resolving an Enum: a value the enum path accepts is refused",
     EC,
     'else _token(value))',
     'else str(value))  # MUTANT',
     f"{CON}::test_an_enum_member_reads_the_same_way_for_an_enum_field_and_a_fixed_field"),

    ("C36 a required one-of becomes optional: ConflictResolved{} is admitted, and the behavioural "
     "guard SKIPS its own assertion because it is gated by the flag it guards",
     GEN,
     '                one_of.append({"members": tuple(members), "required": "?" not in declaration})',
     '                one_of.append({"members": tuple(members), "required": False})  # MUTANT',
     f"{CON}::test_the_one_of_groups_are_exactly_the_ones_a_human_read_off_the_family_files"),
]


def regenerate() -> None:
    """Re-derive the contract data from the specification.

    ### WHY THE PARSER CASES NEED THIS, AND WHY DISCOVERING IT MATTERED. The first run of the
    generator mutations reported four MISSes, and the battery was right to: mutating
    `generate_event_contracts.py` changes nothing a guard can see, because every guard reads the
    COMMITTED `event_contracts_data.json` and the mutant never rewrote it. A parser defect only
    becomes real when the data is regenerated.

    So a `GEN` case regenerates after mutating and again after restoring. That makes it a genuine
    end-to-end proof: the mutant produces bad DATA, and the independently-written oracle catches
    the bad data. Pointing these cases at the anti-drift node instead would have been the weaker
    test - it would only have proved the file was stale, not that anything noticed it was wrong.
    """
    subprocess.run([str(PY), "scripts/generate_event_contracts.py"],
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

    # A parser mutation is inert until the data is re-derived from it (see `regenerate`). The
    # generated file is held in memory too, so the restore is byte-exact for BOTH files.
    is_parser_case = rel == GEN
    data_path = ROOT / ECD
    data_original = data_path.read_bytes() if is_parser_case else None

    try:
        path.write_text(mutated, encoding="utf-8")
        purge_pycache()
        if is_parser_case:
            regenerate()
        caught = not run_guard(guard)
    finally:
        path.write_bytes(original)
        if data_original is not None:
            data_path.write_bytes(data_original)
        purge_pycache()
    if path.read_bytes() != original:
        return "RESTORE-RED", f"byte-for-byte restore FAILED for {rel}"
    if data_original is not None and data_path.read_bytes() != data_original:
        return "RESTORE-RED", f"byte-for-byte restore FAILED for {ECD}"
    if not run_guard(guard):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def main() -> int:
    results = []
    for case in TEXT_CASES:
        verdict, note = _run_text_case(case)
        results.append((case[0], verdict, note))

    print("\n=========== P5 U5.3 CONTRACT MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented U5.3 - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
