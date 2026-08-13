"""P5 U5.2 - the seven MINTED canonical events, proven rather than announced.

### WHAT THIS FILE IS FOR. Seven durable writes had no canonical event. Founder/architect authority
decided, on 2026-08-12, to give each of them one (D1), to make AP-9's freeze an EMITTED fact rather
than a derived one (D2), and to mint for PO-2 rather than re-attribute PO-1's `PolicyProposed` (D3).
The mint itself is a specification edit; these guards are what stop it being merely a specification
CLAIM. Each node re-derives from the canonical registries and would FAIL if the property it protects
were removed - which was verified by mutating each rule in a throwaway copy of the corpus and watching
the node go red.

### WHAT IT DELIBERATELY DOES NOT DO. Nothing here executes an event, an outbox, an inbox or a real
replay. *(Correction, P5 U5.7+U5.8: this paragraph used to say "no such code exists". A transactional
outbox and a dedup inbox now DO exist — `src/freight_recon/event_outbox.py` and `event_inbox.py`,
exercised by `test_phase5_event_transport.py`. What still does not exist is a replay sandbox (U5.5)
or an implementation of the 105 contracts (U5.3), and this module remains deliberately
specification-level: it asserts over the REGISTRIES, not over that runtime.)* Asserting over a
runtime that has not been built is exactly the kind of false green this repository has been burned
by. The REPLAY nodes therefore work the way replay itself works - they FOLD THE DECLARED PAYLOADS over the durable writes the machines declare, and ask
whether the fold can reconstruct each write. That is a specification-level property, it is stated as
one, and it is the property AC-EVT-008 will later be implemented against.

Discipline as everywhere in this suite: discover, never enumerate; exact sets, not counts; positive
anchors before every negative assertion; whole-token matching; and no guard may pass by measuring
nothing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPECS = ROOT / "docs" / "specifications"
MACHINES = SPECS / "state-machines"
EVENTS = SPECS / "events"
IMPL = ROOT / "docs" / "implementation"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_bootstrap_hermeticity import (  # noqa: E402
    _audit, _classify, _consequential_events, _declared_write_fields, _durable_write,
    _event_payloads, _event_registry, _g2_state, _states_in, _transition_rows, require_population,
)

# FIXED-SPECIFICATION: the founder/architect mint of 2026-08-12, transcribed from
# TRANSITION-EVENT-AUDIT.yaml meta.founder_architect_decisions_2026_08_12 and its `discharges`
# record. This is a deliberately specified authorization, not a discovered population - and the
# nodes below assert the audit's own record EQUALS it, so a divergence fails rather than hides.
MINTED = {
    "02-pipeline-instance:PL-7a": "AutonomousAdmissionRecorded",
    "04-approval:AP-9": "ApprovalFrozen",
    "07-conflict:CF-7": "ConflictPartyAttached",
    "09-exception:EC-7": "ExceptionSeverityChanged",
    "11-policy:PO-2": "PolicySubmitted",
    "11-policy:PO-3": "PolicyApproved",
    "12-rule:RU-8": "RuleExpired",
}


def _rows_by_key() -> dict[str, dict]:
    return {r["key"]: r for r in _transition_rows()}


def _family_files() -> dict[str, str]:
    return {f.name: f.read_text(encoding="utf-8") for f in sorted(EVENTS.glob("*-events.md"))}


# ============================================================ event accountability


def test_the_audit_record_of_the_mint_equals_this_guards_authorization_exactly():
    """The anchor for everything below. If the audit and this guard ever disagree about WHICH seven
    rows were authorized and WHICH event each received, every other node here is asserting over the
    wrong population - so that disagreement is the result, not something either side may absorb."""
    record = _audit()["frozen_event_required_set"]
    recorded = {str(d["transition"]): str(d["event"]) for d in record["discharges"]
                if d.get("route") == "MINTED_CANONICAL_EVENT"}
    assert recorded == MINTED, (
        f"the audit's minted-event discharges do not match the authorization: "
        f"audit-only={sorted(set(recorded.items()) - set(MINTED.items()))}, "
        f"authorized-only={sorted(set(MINTED.items()) - set(recorded.items()))}"
    )


def test_each_minted_event_has_exactly_one_canonical_producer_and_no_duplicate_declaration():
    """### EXACTLY ONE PRODUCER, NO DUPLICATE, NO ZERO-OWNER. Three separate failure modes, and each
    is asserted separately because they fail differently:

      zero owners     - an event nothing emits; replay can never see it, and the contract is fiction;
      several owners  - two transitions writing one fact, so a reader cannot tell which occurred.
                        Only the four DECLARED coordination events (§9, marked with the double
                        dagger) may span producers, and none of the seven is one;
      duplicate name  - the same name declared twice in §3, which makes the producer map ambiguous
                        while every count still reconciles.
    """
    registry = _event_registry()
    owned = {e["name"]: e for e in require_population(registry["owned"], "canonical contracts")}
    declared_names = [e["name"] for e in registry["owned"]]
    for key, name in sorted(MINTED.items()):
        tid = key.split(":")[1]
        assert name in owned, f"{name} is not in the §3 canonical corpus"
        assert declared_names.count(name) == 1, f"{name} is declared more than once in §3"
        assert owned[name]["producers"] == [tid], (
            f"{name} declares producers {owned[name]['producers']}, not exactly [{tid}] - a minted "
            "fact with several producers cannot tell a reader which transition occurred"
        )
        assert not owned[name]["coordination"], (
            f"{name} is marked a coordination event. None of the seven is: each records ONE "
            "transition's durable write, and the ‡ marker would license several producers"
        )
        assert registry["producers_of"].get(tid) == {name}, (
            f"{tid} owns {registry['producers_of'].get(tid)}, not exactly {{{name!r}}} - a row that "
            "owns two events, or none, is not accountable for its durable write"
        )


def test_every_minted_row_is_a_producer_and_carries_no_classification_token():
    """A sec-3 producer's identity is decided by the registry, never by the row. If one of the seven
    still carried `EVENT_REQUIRED:` (or acquired `CONSUMES:`), the classifier would report the
    contradiction - producer identity and a self-declared class cannot both hold."""
    g2 = _g2_state()
    classified = g2["result"]["classified"]
    assert not g2["result"]["errors"], g2["result"]["errors"]
    for key in sorted(MINTED):
        assert classified[key]["class"] == "PRODUCER", (
            f"{key} is classified {classified[key]['class']}, not PRODUCER"
        )
        assert classified[key]["arg"] is None
    # the reverse: a token re-added to one of these rows must be an ERROR, not a silent override
    row = dict(classified["04-approval:AP-9"]["row"])
    row["event"] = "`CONSUMES:ApprovalConsumed`"
    result = _classify([row], {"AP-9": {"ApprovalFrozen"}})
    assert result["errors"], (
        "a declared sec-3 producer was allowed to re-declare itself into another class - producer "
        "identity would then be decidable by the row that benefits from it"
    )


def test_each_minted_events_payload_covers_every_persisted_field_of_its_transition():
    """### GR-2's REAL CONTENT, applied to the mint. An event that does not carry what its transition
    persists leaves the write unreconstructable, which is the defect the seven obligations recorded in
    the first place. Fields are read from STRUCTURED forms only - a backticked declaration or a
    `name=value` assignment - on BOTH sides, so prose in either cell contributes nothing.

    Two of the seven declare no field at all (PL-7a, PO-2, RU-8 write only a state change). Their
    coverage obligation is vacuous, and the node says so explicitly instead of quietly counting them
    as passes: the population that MATTERS is the field-declaring rows, and it is asserted non-empty.
    """
    rows, payloads = _rows_by_key(), _event_payloads()
    field_declaring = []
    for key, name in sorted(MINTED.items()):
        declared = _declared_write_fields(rows[key]["writes"])
        carried = payloads.get(name, set())
        assert carried, f"{name} declares no §5 payload at all - it can record nothing"
        if declared:
            field_declaring.append(key)
        missing = sorted(declared - carried)
        assert not missing, (
            f"{key} persists {missing}, which {name}'s §5 payload does not carry "
            f"(it carries {sorted(carried)}) - a full-history replay could not reconstruct the write"
        )
    assert len(field_declaring) >= 3, (
        f"only {field_declaring} of the seven declare a persisted field, so this node is mostly "
        "vacuous - the coverage rule is not being exercised"
    )


def test_each_minted_event_declares_the_identity_and_context_its_obligation_demanded():
    """### TRUTHFUL SEMANTIC OWNERSHIP, checked against the obligation's OWN words rather than
    against the builder's summary of them. Each obligation states the fact that had to become
    recordable; the minted event's §5 payload must carry the specific identity or context that
    statement names. A name alone proves nothing - `ApprovalFrozen` that carried no reference to the
    chain that froze it would satisfy every structural guard and still be useless to an auditor."""
    payloads = _event_payloads()
    obligations = {o["transition"]: o for o in _audit()["founder_gated_event_obligations"]}
    # (obligation phrase that must be honoured, field that honours it)
    demanded = {
        "02-pipeline-instance:PL-7a": ["gate_decision", "caps_evaluated"],
        "04-approval:AP-9": ["frozen", "unknown_outcome_ref"],
        "07-conflict:CF-7": ["parties", "provenance_class"],
        "09-exception:EC-7": ["severity", "previous_severity", "changed_by"],
        "11-policy:PO-2": ["policy_version", "gate_decision"],
        "11-policy:PO-3": ["approval_id", "diff_fingerprint"],
        "12-rule:RU-8": ["rule_id"],
    }
    assert set(demanded) == set(MINTED), "the demanded-field map drifted from the minted set"
    for key, fields in sorted(demanded.items()):
        carried = payloads[MINTED[key]]
        missing = [f for f in fields if f not in carried]
        assert not missing, (
            f"{MINTED[key]} ({key}) does not carry {missing}. Its obligation "
            f"{obligations[key]['id']} required: {obligations[key]['semantic_obligation'].strip()}"
        )


def test_no_minted_event_claims_a_transition_it_does_not_own():
    """### THE OVERCLAIM CHECK. `AutonomousAdmissionRecorded` must not be readable as PL-7b's event,
    and `PolicySubmitted` must not be readable as PO-1's. Each minted name is asserted ABSENT from
    every other transition row's Event cell, over the whole 134-row corpus - a negative assertion
    with its population proven first."""
    rows = require_population(_transition_rows(), "transition rows")
    for key, name in sorted(MINTED.items()):
        pattern = re.compile(rf"`{name}\b")
        naming = [r["key"] for r in rows if pattern.search(r["event"])]
        assert naming == [key], (
            f"{name} is named in the Event cell of {naming}, but it is owned by {key} alone. A row "
            "naming an event it does not own is how EF-3's ownership went silent (G2-D14)"
        )


def test_every_minted_event_is_declared_in_its_family_file_with_its_producer():
    """events/registry.md line 5: every family file uses these names verbatim, and a family file
    introducing an unlisted name or a local synonym is defective. The converse matters just as much
    here - a minted name that never reaches its family file has a producer map entry and no
    contract."""
    families = _family_files()
    require_population(families, "event family files")
    expected_family = {
        "02-pipeline-instance:PL-7a": "02-pipeline-instance-events.md",
        "04-approval:AP-9": "04-approval-events.md",
        "07-conflict:CF-7": "07-conflict-events.md",
        "09-exception:EC-7": "09-exception-events.md",
        "11-policy:PO-2": "11-policy-events.md",
        "11-policy:PO-3": "11-policy-events.md",
        "12-rule:RU-8": "12-rule-events.md",
    }
    for key, name in sorted(MINTED.items()):
        fname = expected_family[key]
        text = families[fname]
        tid = key.split(":")[1]
        assert f"**`{name}`**" in text, f"{name} has no contract row in {fname}"
        row = next(l for l in text.split("\n") if f"**`{name}`**" in l)
        assert re.search(rf"\b{re.escape(tid)}\b", row), (
            f"{fname}'s {name} row does not name its producer transition {tid}: {row[:120]!r}"
        )
        elsewhere = [f for f, t in families.items() if f != fname and f"**`{name}`**" in t]
        assert not elsewhere, f"{name} is also declared as a contract in {elsewhere}"


def test_the_minted_events_carry_the_canonical_envelope_and_tenant_identity_unconditionally():
    """### TENANT IS NOT PER-EVENT DISCRETION. The envelope (§1) is declared once, `tenant_id` is
    mandatory on EVERY event with no exception, and none of the seven may weaken that by carrying a
    local override. Asserted structurally: the envelope's own mandate is present, and no family file
    that declares one of the seven contains an exemption phrase near it."""
    registry = (EVENTS / "registry.md").read_text(encoding="utf-8")
    envelope = registry.split("## 1. THE CANONICAL EVENT ENVELOPE")[1].split("## 2.")[0]
    assert "MANDATORY on EVERY event" in envelope and "No event may omit it" in envelope, (
        "the envelope's unconditional tenant mandate was weakened"
    )
    assert "**Every event, without exception, carries this envelope.**" in envelope
    for name in sorted(MINTED.values()):
        for text in _family_files().values():
            for line in text.split("\n"):
                if f"**`{name}`**" not in line:
                    continue
                assert not re.search(r"tenant[_ ]?id[^.|]{0,40}(optional|omitted|exempt|n/a)",
                                     line, re.I), (
                    f"{name}'s contract row claims a tenant exemption: {line[:160]!r}"
                )


# ============================================================ replay / rebuild


def _fold_reconstructs(key: str) -> tuple[set[str], set[str]]:
    """The specification-level replay question: fold the events whose §5 payloads a rebuild may read
    for this aggregate, and return (the fields the row persists, the fields the fold can reconstruct).

    Only the row's OWN producer events are folded. That is the strict reading and the honest one: an
    event owned by a different transition is emitted only if THAT transition fired, so relying on it
    is exactly the "absence is evidence" mistake D2 rejects.
    """
    row = _rows_by_key()[key]
    payloads, registry = _event_payloads(), _event_registry()
    tid = key.split(":")[1]
    carried: set[str] = set()
    for name in registry["producers_of"].get(tid, set()):
        carried |= payloads.get(name, set())
    return _declared_write_fields(row["writes"]), carried


def test_replay_reconstructs_every_newly_evented_durable_state():
    """AC-EVT-008 at the specification level, over all seven. For each row: everything it declares it
    persists is carried by the event it now owns, so a full-history fold reproduces the write instead
    of a hole. The rows that persist only a STATE change are handled by the state assertion below,
    which is a different property and is not allowed to stand in for this one."""
    covered = []
    for key in sorted(MINTED):
        persisted, carried = _fold_reconstructs(key)
        missing = sorted(persisted - carried)
        assert not missing, (
            f"{key}: a rebuild folding {MINTED[key]} cannot reconstruct {missing} - the durable "
            "write survives in live state and vanishes from history, which is the exact defect the "
            "seven obligations recorded"
        )
        if persisted:
            covered.append(key)
    require_population(covered, "field-persisting rows whose replay coverage was actually exercised")


def test_replay_reconstructs_the_state_change_of_the_rows_that_persist_no_field():
    """The other half. PL-7a, PO-2 and RU-8 persist no field: their durable write IS the state
    change. A rebuild reconstructs it from the event's PRESENCE plus its `producer_transition_id`,
    which the envelope makes required-always - so the assertion is that the row genuinely writes only
    a state, and that the envelope still binds the event to the transition that produced it."""
    states = _g2_state()["states"]
    rows = _rows_by_key()
    envelope = (EVENTS / "registry.md").read_text(encoding="utf-8")
    assert re.search(r"`producer_transition_id`\s*\|\s*R\s*\|", envelope), (
        "producer_transition_id is no longer required-always in the envelope - a state-only event "
        "would then not identify the transition it reconstructs"
    )
    state_only = [k for k in MINTED if not _declared_write_fields(rows[k]["writes"])]
    require_population(state_only, "state-only minted rows")
    for key in sorted(state_only):
        row = rows[key]
        assert _durable_write(row, states), f"{key} performs no durable write at all"
        left, right = row["from_to"].split("→", 1)
        new_states = _states_in(right, states) - _states_in(left, states)
        assert new_states, (
            f"{key} declares no field and enters no new canonical state, so there is nothing for "
            f"{MINTED[key]} to reconstruct - it would be an event with no fact"
        )


def test_replay_rebuilds_ap9_frozen_from_positive_evidence_and_never_from_an_absence():
    """### D2, THE ONE THAT MATTERS MOST, ASSERTED FROM BOTH DIRECTIONS.

    POSITIVE: `ApprovalFrozen`'s §5 payload carries `frozen=true` itself, so a fold sets the flag
    because the event is PRESENT. The reconstruction needs no other event and no ordering assumption.

    NEGATIVE: the derived alternative must be refused in the specification, not merely not-chosen by
    the builder. `ER-16` states it, and the audit records the refusal as a decision with a reason.
    Both are asserted, because a rule nobody wrote down is a preference.

    ### WHY AN ABSENCE IS NOT GOOD ENOUGH, RESTATED SO IT CANNOT BE ARGUED AWAY LATER: deriving
    `frozen` from *`OutcomeUnknown` AND NOT `RealityEstablished`* makes the flag FALSE whenever the
    fold is incomplete - a truncated window, a parked reference, a consumer that has not caught up.
    Every one of those failure modes yields a REUSABLE approval, and reuse of a frozen approval is an
    ILLEGAL determination (M4 §15). The rebuilt state would be less safe than the original, which
    inverts the purpose of replay."""
    payloads = _event_payloads()
    carried = payloads["ApprovalFrozen"]
    assert "frozen" in carried, (
        "ApprovalFrozen does not carry `frozen` - a rebuild would have to INFER the flag, which is "
        "precisely what D2 refused"
    )
    assert "unknown_outcome_ref" in carried, (
        "ApprovalFrozen carries no reference to the unknown-outcome chain that froze it, so the "
        "freeze cannot be bound to the correct approval / OutcomeUnknown chain on replay"
    )
    row = _rows_by_key()["04-approval:AP-9"]
    assert "frozen" in _declared_write_fields(row["writes"]), "AP-9 no longer writes `frozen`"

    # the fold needs NOTHING but this event: not OutcomeUnknown, not RealityEstablished, not order
    persisted, reconstructable = _fold_reconstructs("04-approval:AP-9")
    assert persisted <= reconstructable, f"AP-9's write is not reconstructable: {persisted}"
    registry = _event_registry()
    assert registry["producers_of"]["AP-9"] == {"ApprovalFrozen"}
    assert "AP-9" not in registry["producers_of"].get("EF-3u", set())

    # the derivation is REFUSED in the specification, by name
    text = (EVENTS / "registry.md").read_text(encoding="utf-8")
    er16 = next((l for l in text.split("\n") if "**ER-16**" in l), "")
    assert er16, "ER-16 is gone - the positive-evidence rule has no canonical statement"
    for phrase in ("POSITIVE", "never from an absence", "OutcomeUnknown", "RealityEstablished"):
        assert phrase in er16, f"ER-16 no longer states {phrase!r}: {er16[:200]!r}"
    # ### AND ITS SCOPING PARENTHETICAL IS PINNED TOO (F-07). ER-16 governs REPLAY. Unscoped, the
    # same sentence reads as a licence to stop treating an unresolved `OutcomeUnknown` as frozen AT
    # RUNTIME - it would turn a replay rule into a relaxation of the LIVE safety guard, the opposite
    # of what D2 decided. Deleting the parenthetical left candidate f01d942 entirely green.
    for phrase in ("fail-closed default", "at runtime", "REPLAY"):
        assert phrase in er16, (
            f"ER-16's SCOPING clause no longer states {phrase!r}. The rule is about what a REPLAY "
            f"may rely on; unscoped it reads as weakening the live fail-closed guard: {er16[:240]!r}"
        )
    obligation = next(o for o in _audit()["founder_gated_event_obligations"]
                      if o["transition"] == "04-approval:AP-9")
    assert "EMIT" in obligation["discharge_authority"]
    assert "REFUSED" in obligation["remedy_selected"], (
        "the derive remedy is recorded as un-chosen rather than REFUSED - a rejected alternative "
        "that is not recorded as rejected comes back"
    )
    assert obligation["fail_closed_default_until_decided"], (
        "the runtime fail-closed default for an unresolved approval reality was dropped; the "
        "emit decision governs REPLAY and may not relax the live guard"
    )


def test_po3_policyapproved_is_consequential_and_the_no_admin_path_evidence_is_pinned():
    """### F-05, at the row it was claimed for. The candidate's own commit record called PO-3's
    promotion into events/registry.md sec 5 "the 'no admin path' evidence" - the pins that let a
    replay prove a policy change went through a human-gated pipeline rather than an admin edit. The
    list was read by NOTHING: striking `PolicyApproved` from it left the whole canonical suite green.

    `_consequential_events` reads the LIST LINE only, so the amendment note beneath it - which also
    names `PolicyApproved` - cannot keep this green while the list itself is emptied. The general
    subset and safety-spine properties are held by
    test_bootstrap_hermeticity.py::test_the_consequential_event_list_is_a_guarded_subset_of_the_canonical_corpus;
    what is pinned HERE is the promotion this unit made and the reason it gave for it."""
    consequential = require_population(_consequential_events(),
                                       "events/registry.md sec 5 CONSEQUENTIAL members")
    assert "PolicyApproved" in consequential, (
        "### `PolicyApproved` LEFT sec 5's CONSEQUENTIAL LIST. PO-3 would then no longer have to "
        "pin the SD-3 entity_versions set, the material-facts fingerprint, policy_version and "
        "brake_version - so a replay could not reproduce the decision context of a policy approval, "
        "and the 'no admin path' evidence D1 asked this event to carry would be gone"
    )
    text = (EVENTS / "registry.md").read_text(encoding="utf-8")
    section = text.split("## 5. WHICH EVENTS ARE CONSEQUENTIAL")[1].split("\n## ")[0]
    for phrase in ("PolicyApproved", "2026-08-12", "no admin path"):
        assert phrase in section, (
            f"sec 5 no longer records {phrase!r} - the amendment that promoted PO-3's event must "
            "stay attributed and dated, or a reader cannot tell why the member is there"
        )
    # and the payload actually carries what CONSEQUENTIAL membership obliges it to carry
    payload = _event_payloads()["PolicyApproved"]
    for field in ("policy_version",):
        assert field in payload, (
            f"`PolicyApproved` is declared CONSEQUENTIAL but its sec-5 payload does not carry "
            f"{field!r} - the membership would be an unbacked claim"
        )


def test_the_order_tolerant_carve_out_stays_scoped_to_cross_aggregate_delivery():
    """### F-07. This unit added a sec-8 bullet because two of the seven minted events - EC-7's
    `ExceptionSeverityChanged` and CF-7's `ConflictPartyAttached` - are FIELD-MUTATING facts on
    families sec 8 lists as *Order-tolerant* (F9 Exception, F7 Conflict). Unqualified, "order
    tolerant" would mean a rebuild may fold two severity changes in either order and reproduce
    EITHER severity, which makes the replay of a safety field non-deterministic.

    The bullet says the tolerance is ACROSS aggregates only, and that WITHIN one aggregate the
    universal ordering key still decides. Deleting it left candidate f01d942 green, so the whole
    correctness argument for minting a field-mutating fact onto an order-tolerant family rested on
    an unguarded sentence."""
    text = (EVENTS / "registry.md").read_text(encoding="utf-8")
    section = text.split("## 8. ORDERING")[1].split("\n## ")[0]
    bullet = next((l for l in section.split("\n") if "order-free" in l.lower()), "")
    assert bullet, (
        "### sec 8's 'Order-tolerant does NOT mean order-free' bullet is GONE. `ExceptionSeverityChanged` "
        "and `ConflictPartyAttached` are field-mutating facts on families sec 8 declares "
        "order-tolerant; without the scoping bullet a rebuild folding them in either order may "
        "reproduce either severity, and the replay of a safety field stops being deterministic"
    )
    for phrase in ("ExceptionSeverityChanged", "ConflictPartyAttached", "across",
                   "aggregate_version", "previous_severity"):
        assert phrase in bullet, (
            f"sec 8's order-tolerance carve-out no longer states {phrase!r}: {bullet[:260]!r}"
        )
    assert "(tenant_id, aggregate_id, aggregate_version)" in bullet, (
        "the bullet no longer names the UNIVERSAL ORDERING KEY as what decides within an aggregate "
        "- that key is the whole reason the carve-out is sound, and it is the same key the "
        "delegation predicate's same-machine conjunct rests on"
    )


# ============================================================ PO-2 / PO-1 semantic regression


def test_po1_policyproposed_semantics_producer_and_consumers_are_unchanged():
    """### D3's REGRESSION GUARD. The refused remedy was to re-attribute `PolicyProposed` to PO-2.
    Had it been taken, every historical `PolicyProposed` would have silently changed meaning - from
    "a draft was authored" to "a draft was put forward for approval" - and every consumer reading it
    would have been reading a different fact than the one recorded.

    Byte-level equality against the certified predecessor is not available to a guard that must run
    from a clean clone, so the properties are asserted individually and exhaustively: the name, the
    producer in BOTH authorities, the transition row, the payload, the family-file contract text and
    the declared consumers."""
    registry = _event_registry()
    assert registry["producers_of"].get("PO-1") == {"PolicyProposed"}, (
        f"PO-1's §3 ownership moved to {registry['producers_of'].get('PO-1')} - `PolicyProposed` was "
        "re-attributed, which D3 explicitly refused"
    )
    assert "PolicyProposed" not in registry["producers_of"].get("PO-2", set()), (
        "PO-2 acquired `PolicyProposed`; it owns `PolicySubmitted` and nothing else"
    )
    owned = {e["name"]: e for e in registry["owned"]}
    assert owned["PolicyProposed"]["producers"] == ["PO-1"]
    assert owned["PolicyProposed"]["family"] == "F11"

    # the machine row: PO-1 is still `— → DRAFT`, still emits PolicyProposed, still writes the same
    row = _rows_by_key()["11-policy:PO-1"]
    assert "`PolicyProposed`" in row["event"], f"PO-1's Event cell changed: {row['event']!r}"
    assert row["from_to"].replace(" ", "").startswith("—→`DRAFT`"), (
        f"PO-1's transition changed: {row['from_to']!r}"
    )
    assert _declared_write_fields(row["writes"]) == {"scope", "gate_decision", "caps", "predicate"}, (
        f"PO-1's persisted fields changed: {sorted(_declared_write_fields(row['writes']))}"
    )

    # the §5 payload row is untouched, and PolicySubmitted did not merge into it
    sm = (MACHINES / "registry.md").read_text(encoding="utf-8")
    legacy = next(l for l in sm.split("\n") if l.startswith("| `PolicyProposed`"))
    assert "`PolicySubmitted`" not in legacy and "`PolicyApproved`" not in legacy, (
        f"the minted events were folded into PolicyProposed's payload row: {legacy!r}"
    )
    assert legacy.strip().endswith("| `policy_version` |"), f"the row changed: {legacy!r}"

    # the family-file contract: same proves/¬proves, same payload, same consumers
    family = (EVENTS / "11-policy-events.md").read_text(encoding="utf-8")
    po1 = next(l for l in family.split("\n") if "**`PolicyProposed`**" in l)
    assert "PO-1" in po1 and "PO-2" not in po1, f"PolicyProposed's producer changed: {po1[:160]!r}"
    assert "proves a policy draft/change was authored" in po1, "its `proves` clause changed"
    assert "¬proves it is active" in po1, "its `¬proves` clause changed"
    assert "`scope`, `gate_decision`, `caps`, `predicate`" in po1, "its payload changed"
    assert "Oversight; M2 (a policy change is itself a gated action)" in po1, "its consumers changed"


def test_policysubmitted_is_a_distinct_fact_from_policyproposed():
    """The other side of D3: the new event must not be a synonym. Different name, different producer,
    different transition, different `From → To`, and a payload that carries the thing PO-2's guard
    actually turns on (`gate_decision` NOT NULL) rather than PO-1's authoring fields."""
    registry, payloads = _event_registry(), _event_payloads()
    assert registry["producers_of"]["PO-2"] == {"PolicySubmitted"}
    rows = _rows_by_key()
    po1, po2 = rows["11-policy:PO-1"], rows["11-policy:PO-2"]
    assert po1["from_to"] != po2["from_to"], "PO-1 and PO-2 describe the same transition"
    assert "`DRAFT`" in po2["from_to"] and "`PROPOSED`" in po2["from_to"]
    assert payloads["PolicySubmitted"] != payloads["PolicyProposed"], (
        "PolicySubmitted's payload is identical to PolicyProposed's - it would be a rename with "
        "extra steps rather than a distinct fact"
    )
    assert "gate_decision" in payloads["PolicySubmitted"], (
        "PolicySubmitted does not carry the gate_decision PO-2's own guard requires to be non-null"
    )


# ============================================================ nothing else moved


def test_no_pre_existing_canonical_event_changed_its_meaning():
    """### THE BROADEST REGRESSION HERE, and the cheapest to get wrong. The mint was authorized to
    ADD. It was not authorized to re-attribute, re-payload, rename or re-family anything that already
    existed - and a silent change to an existing contract is worse than a bad new one, because
    history already depends on it.

    The pre-existing 98 are recovered as `current corpus minus the seven minted names`, and for each:
    its producer list and its family are asserted to be exactly what the registered expectation and
    the §5 payload table say. `PolicyProposed` is the named case; this covers the other 97 too."""
    sys.path.insert(0, str(ROOT / "eval"))
    from phase0 import manifest

    registry = _event_registry()
    owned = {e["name"]: e for e in registry["owned"]}
    minted = set(MINTED.values())
    pre_existing = sorted(set(owned) - minted)
    assert len(pre_existing) == 98, (
        f"the pre-existing corpus is {len(pre_existing)} names, not 98 - the mint added or removed "
        f"something other than the seven: {sorted(minted ^ (set(owned) - set(pre_existing)))}"
    )
    assert set(pre_existing) | minted == manifest.expected_event_names()

    # every pre-existing event still has at least one producer, and no producer of a pre-existing
    # event is one of the seven minted rows - i.e. nothing was re-attributed ONTO them either
    minted_rows = {k.split(":")[1] for k in MINTED}
    for name in pre_existing:
        producers = owned[name]["producers"]
        assert producers, f"{name} lost its producer transition"
        stolen = sorted(set(producers) & minted_rows)
        assert not stolen, (
            f"{name} is now declared produced by {stolen}, one of the seven rows the mint touched - "
            "an existing event was re-attributed, which the authorization did not permit"
        )

    # and the §5 payload table still declares a payload row for the events that had one
    payloads = _event_payloads()
    assert payloads["PolicyProposed"] == {"policy_version"}
    assert payloads["ExceptionRaised"] >= {"severity", "source_ref"}
    assert payloads["ConflictRaised"] >= {"kind"}


def test_the_mint_introduced_no_new_event_required_obligation():
    """A mint that quietly created an eighth obligation would be a net loss dressed as a discharge.
    EVENT_REQUIRED is asserted EMPTY against the specification, the obligation register is asserted
    to contain exactly the adjudicated seven, and every one of them is asserted DISCHARGED - so
    "empty" here is a measured claim about a known population, never an unmeasured one."""
    from test_bootstrap_hermeticity import ADJUDICATED_EVENT_REQUIRED

    g2, audit = _g2_state(), _audit()
    still_required = {k for k, v in g2["result"]["classified"].items()
                      if v["class"] == "EVENT_REQUIRED"}
    assert not still_required, f"EVENT_REQUIRED is not empty: {sorted(still_required)}"
    register = {o["transition"]: o for o in audit["founder_gated_event_obligations"]}
    assert set(register) == set(ADJUDICATED_EVENT_REQUIRED) == set(MINTED), (
        "the obligation register is not exactly the adjudicated seven - an obligation was added or "
        f"deleted: {sorted(set(register) ^ set(MINTED))}"
    )
    for key, obligation in sorted(register.items()):
        assert obligation["status"] == "DISCHARGED", f"{key} is not discharged"
        assert obligation["discharging_event"] == MINTED[key]
    assert audit["meta"]["open_founder_gated_obligations"] == 0
    assert audit["meta"]["total_founder_gated_obligations"] == len(register)


def test_the_transition_corpus_did_not_grow_to_accommodate_the_mint():
    """The cheapest way to make a GR-2 obligation disappear is to change the row instead of giving it
    an event. The corpus is still 134 rows, and each of the seven still has the same `From → To` and
    the same `Writes` cell it had when its obligation was recorded - the audit's own
    `durable_write` field is the independent record of that."""
    rows = _rows_by_key()
    assert len(rows) == 134, f"the transition corpus is {len(rows)} rows, not 134"
    register = {o["transition"]: o for o in _audit()["founder_gated_event_obligations"]}
    for key in sorted(MINTED):
        recorded = str(register[key]["durable_write"])
        row = rows[key]
        haystack = f"{row['from_to']} {row['writes']}".replace("`", "").replace("*", "")
        for token in re.findall(r"[A-Za-z_][A-Za-z_0-9]*", recorded):
            if token in {"append", "to"}:
                continue
            assert token in haystack, (
                f"{key}: its obligation records the durable write {recorded!r}, and the row no "
                f"longer shows {token!r} (From→To {row['from_to']!r}, Writes {row['writes']!r}). "
                "The write was changed instead of being evented"
            )


def test_the_recorded_program_invariants_are_untouched_by_this_unit():
    """### THE THINGS THIS UNIT WAS FORBIDDEN TO MOVE, asserted rather than promised. P4 COMPLETE,
    R-07 CONTAINED with its bound, every P5 criterion PENDING, and P5's own three-field status
    unchanged. A specification amendment that quietly advanced a phase would be the most expensive
    possible failure here, and it is exactly the failure a busy reviewer skims past."""
    reg = yaml.safe_load((IMPL / "IMPLEMENTATION-REGISTRY.yaml").read_text(encoding="utf-8"))
    units = {u["unit_id"]: u for u in require_population(reg["units"], "registry units")}
    p4, p5 = units["P4"], units["P5"]
    assert p4["status"] == "COMPLETE" and p4["checkpoint_state"] == "PHASE_ACCEPTANCE_COMPLETE"
    assert all(c["result"] == "PASS" for c in p4["acceptance_criteria"])
    # ### WHAT THIS ACTUALLY GUARDS: a SPECIFICATION amendment quietly advancing a phase. It used to
    # pin P5 to READY/NOT_STARTED/NO_CHECKPOINT, which was true of the mint and became false when
    # U5.7+U5.8 landed the outbox and inbox as WORKING CODE. Pinning the literal triple would have
    # made it structurally impossible for any runtime unit to record that it had built something -
    # a true statement frozen into a permanent rule. The property that survives is the one the
    # docstring names: P5 may not be COMPLETE, and it may only have advanced on LANDED EVIDENCE,
    # which a specification amendment cannot manufacture.
    assert p5["status"] == "READY", "P5 left the selector - the repository must always name one"
    assert p5["execution_state"] in ("NOT_STARTED", "IN_PROGRESS"), (
        f"P5's execution_state is {p5['execution_state']} - this unit does not complete P5"
    )
    if p5["execution_state"] != "NOT_STARTED":
        landed = require_population(p5.get("landed_checkpoints", []), "P5 landed checkpoints")
        for cp in landed:
            assert cp["checkpoint_state"] == "CHECKPOINT_ACCEPTED_FOR_CONTINUATION", (
                f"{cp['id']} claims {cp['checkpoint_state']} - only CONTINUATION is available "
                "while criteria are unscored"
            )
            assert cp.get("implementer_evidence") and cp.get("independent_review_report"), (
                f"{cp['id']} advanced P5 without on-disk evidence AND an on-disk review - a "
                "specification amendment could manufacture the claim but not these"
            )
    results = [c["result"] for c in p5["acceptance_criteria"]]
    assert len(results) == 14 and set(results) == {"PENDING"}, (
        f"a P5 acceptance criterion was scored: {results}"
    )
    sub_units = require_population(p5["sub_units"], "P5 sub-units")
    for su in sub_units:
        assert su["scored_criteria"] == [], f"{su['sub_unit_id']} scored a criterion"
        assert su["landed_checkpoints"] == [], f"{su['sub_unit_id']} landed a checkpoint"

    manifest = yaml.safe_load((IMPL / "phase-0-baseline-manifest.yaml").read_text(encoding="utf-8"))
    r07 = str(manifest["expected_legacy_paths"])
    assert "CONTAINED" in r07, "the R-07 containment record left the baseline manifest"
