"""P5 U5.3 — the canonical event contracts and the upcaster, proven against the RUNTIME.

### WHAT THIS FILE IS FOR, AND HOW IT DIFFERS FROM `test_p5_canonical_event_mint.py`.
That module is deliberately specification-level: it asserts over the registries. This one asserts
over executable code. The distinction is the whole point of U5.3 — the 105 contracts stopped being
a list in a markdown table and became something a fact is CHECKED against before it can be
committed, published, redelivered or consumed.

THE SEVEN-STEP STANDARD, RUN EXHAUSTIVELY OVER ALL 118 CONTRACTS

    produce → serialize → persist through the outbox → publish through the relay →
    deserialize → upcast → recover the canonical representation → and refuse what is invalid

`test_every_canonical_contract_survives_the_whole_transport_round_trip` runs all eight steps for
every contract in the corpus, not for a chosen few. Exhaustive because it is cheap here and because
a sampled version of it would leave 100+ contracts asserted by nothing.

DISCIPLINE, as everywhere in this suite: discover, never enumerate; exact sets, not counts;
a proven population before every negative assertion; and no node may pass by measuring nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from phase5_kit import (  # noqa: E402
    T_A,
    T_B,
    RecordingHandler,
    RecordingSink,
    assert_atomic,
    brake_version,
    canonical_payload,
    make_canonical_envelope,
    make_envelope,
    make_inbox,
    make_relay,
    make_store,
)

from freight_recon.event_contracts import (  # noqa: E402
    HUMAN_ONLY_EVENTS,
    CONSEQUENTIAL_EVENTS,
    CONTRACTS,
    EMITTED_CORPUS,
    UPCASTERS,
    ActorAuthorityViolation,
    AggregateTypeMismatch,
    CanonicalContract,
    ConsequentialPinsMissing,
    ContractError,
    FieldSpec,
    MissingUpcaster,
    PayloadContractViolation,
    ProducerTransitionMismatch,
    UnknownEventName,
    UnsupportedFutureVersion,
    UpcasterRegistry,
    ValidationMode,
    contract_for,
    is_canonical,
    read,
    validate,
)
from freight_recon.event_envelope import EventEnvelope  # noqa: E402
from freight_recon.event_inbox import ConsumeOutcome  # noqa: E402
from freight_recon.event_outbox import transactional_emit  # noqa: E402

import generate_event_contracts as generator  # noqa: E402

ALL_CONTRACTS = sorted(CONTRACTS)


def require_population(population, *, at_least: int, what: str):
    """A negative assertion over an empty set passes vacuously. This is the anchor (CLAUDE.md §9)."""
    assert len(population) >= at_least, (
        f"{what}: expected at least {at_least}, found {len(population)}. A case that iterates an "
        f"empty population proves nothing while reporting success."
    )
    return population


# =============================================== 1. the derivation is the specification's, not ours

def test_the_generated_contract_data_is_exactly_what_the_specification_derives():
    """### THE ANTI-DRIFT NODE. `event_contracts_data.json` is generated from
    `docs/specifications/events/`; if the specification is edited and the data file is not
    regenerated, the runtime serves contracts the specification no longer declares. Re-deriving here
    and comparing byte-for-byte is what makes the markdown remain the single authority instead of
    the first of two.

    ### WHAT IT DOES NOT PROVE, STATED SO NOBODY RELIES ON IT FOR MORE. This compares the
    generator's output to the generator's output, so it catches STALENESS and not a PARSER BUG —
    a mis-parse is identical on both sides. The independently-written oracle in section 1b is what
    covers that, and it exists because four derivation defects passed this node.
    """
    rendered = generator.render(generator.derive())
    committed = (ROOT / "src" / "freight_recon" / "event_contracts_data.json").read_text(
        encoding="utf-8"
    )
    assert committed == rendered, (
        "src/freight_recon/event_contracts_data.json is STALE with respect to "
        "docs/specifications/events/. Run `python3 scripts/generate_event_contracts.py`."
    )


def test_the_runtime_contract_names_are_exactly_the_registry_section_3_names():
    """EXACT SET, both directions — a same-count substitution must fail, not merely a miscount."""
    declared = {e["name"] for e in generator.parse_canonical_list()}
    require_population(declared, at_least=100, what="registry §3 canonical names")
    assert set(CONTRACTS) == declared, {
        "in the runtime but not §3": sorted(set(CONTRACTS) - declared),
        "in §3 but not the runtime": sorted(declared - set(CONTRACTS)),
    }


def test_the_emitted_corpus_is_exactly_the_f1_to_f13_families():
    """"The 105" is F1–F13. F14 is thirteen real contracts that no producer transition emits."""
    expected = {n for n, c in CONTRACTS.items() if int(c.family[1:]) <= 13}
    assert EMITTED_CORPUS == expected
    assert len(EMITTED_CORPUS) == 105, (
        f"the registry records 105 emitted contracts; the runtime derives {len(EMITTED_CORPUS)}"
    )
    audit = set(CONTRACTS) - EMITTED_CORPUS
    assert {CONTRACTS[n].family for n in audit} == {"F14"}
    assert len(audit) == 13


def test_the_consequential_set_is_exactly_registry_section_5():
    """§5 decides which events must be able to reproduce their decision context. Exact, not counted."""
    declared = set(generator.parse_consequential())
    require_population(declared, at_least=15, what="registry §5 CONSEQUENTIAL members")
    assert CONSEQUENTIAL_EVENTS == declared, {
        "runtime only": sorted(CONSEQUENTIAL_EVENTS - declared),
        "spec only": sorted(declared - CONSEQUENTIAL_EVENTS),
    }


def test_every_declared_producer_is_a_transition_id_and_every_emitted_contract_has_one():
    """§1 calls `producer_transition_id` the mechanical link to the state machine. A contract with a
    malformed producer would make that link unenforceable — and one with NO producer would make it
    unenforced, silently."""
    import re

    emitted = require_population(
        [CONTRACTS[n] for n in EMITTED_CORPUS], at_least=100, what="emitted contracts")
    for contract in emitted:
        assert contract.producers, (
            f"{contract.name} is in the emitted corpus (F1-F13) and declares no producer "
            f"transition; its `producer_transition_id` could then never be checked"
        )
        for tid in contract.producers:
            assert re.fullmatch(r"[A-Z]{2}-\d+[a-z]*", tid), (
                f"{contract.name} declares producer {tid!r}, which is not a transition id"
            )


def test_the_coordination_marker_is_carried_from_the_registry_exactly():
    """‡ marks a COORDINATION contract (§9) — one semantic fact with several origins.

    ### WHAT THIS NODE DELIBERATELY DOES NOT ASSERT, AND WHY. An earlier version of it claimed that
    ‡ is the only way a contract may name more than one producer transition, which is how §3's
    prose reads. The corpus says otherwise: eleven unmarked contracts legitimately name several
    transitions OF ONE MACHINE (`ApprovalVoided` AP-4/4p/5, `WorkBlocked` WI-5/6, …), and one marked
    contract (`PolicyVersionChanged` PO-4/6) names two of one machine as well — so neither
    "multi-producer ⇒ ‡" nor "‡ ⇒ multi-machine" holds. That is a prose/data nuance in the
    specification, recorded as nonblocking debt rather than adjudicated here, and asserting either
    false rule would have made this node a decoration that fails on correct data.

    What IS decidable, and is what actually protects the runtime: the marker the runtime carries is
    exactly the marker §3 writes, in both directions.
    """
    marked = {c.name for c in CONTRACTS.values() if c.coordination}
    declared = {e["name"] for e in generator.parse_canonical_list() if e["coordination"]}
    require_population(declared, at_least=3, what="‡-marked contracts in §3")
    assert marked == declared, {"runtime only": sorted(marked - declared),
                                "spec only": sorted(declared - marked)}
    # A ‡ contract names several producer TRANSITIONS — except where §3 states its producer as
    # prose. `IllegalTransitionAttempted‡(any machine, GR-1)` is the one such contract: `GR-1` is a
    # global RULE (§10), not a transition, so the contract correctly carries no producer set and is
    # not producer-checked. An earlier version of this assertion required every ‡ contract to have
    # producers, which locked in the defect of treating `GR-1` as a transition — the exact
    # "a defect and its defending test arrive together" shape CLAUDE.md §9 names.
    prose_producers = {n for n in marked if not CONTRACTS[n].producers}
    assert prose_producers == {"IllegalTransitionAttempted"}, (
        f"‡ contracts carrying no producer set changed: {sorted(prose_producers)}. Only "
        f"IllegalTransitionAttempted may, because §3 states its producer as prose"
    )
    for name in sorted(marked - prose_producers):
        assert len(CONTRACTS[name].producers) >= 2, (
            f"{name} is marked ‡ — one semantic fact with several origins — but names "
            f"{CONTRACTS[name].producers}"
        )


def test_no_contract_is_attributed_to_a_global_rule_instead_of_a_transition():
    """### `GR-n` IS A RULE, NOT A TRANSITION (registry §10, GR-1..GR-16), and it is
    transition-SHAPED, so a producer parser that matches on shape alone accepts it.

    It did. `IllegalTransitionAttempted` carried `producers=('GR-1',)`, which made the runtime
    demand that an illegal-transition record be attributed to a rule id — refusing it no matter
    which real transition attempted the illegal move, which is every one of them.
    """
    offenders = {n: c.producers for n, c in CONTRACTS.items()
                 if any(p.startswith("GR-") for p in c.producers)}
    assert offenders == {}, offenders


def test_the_strict_order_families_are_exactly_the_ones_the_registry_requires():
    """### §8 WRITES BOTH HALVES OF THE ORDERING SPLIT ON ONE LINE.

        **Strict per-aggregate ordering REQUIRED:** F2 … F13 …  **Order-tolerant:** F5 … F14 …

    A regex over the whole line harvests the order-tolerant families too and marks F5, F7, F9 and
    F14 strict — 31 of 118 contracts carrying a flag the registry explicitly contradicts, silently,
    because nothing in this unit reads the flag yet. P6's consumers would have found out instead.
    """
    strict = generator.parse_strict_order_families()
    require_population(strict, at_least=3, what="§8 strict-order families")
    runtime = {c.family for c in CONTRACTS.values() if c.strict_order}
    assert runtime == set(strict), {"runtime": sorted(runtime), "spec": sorted(strict)}

    # The families §8 calls order-tolerant must NOT appear — the positive half of the same rule,
    # asserted from the specification rather than from a remembered list.
    section = (ROOT / "docs" / "specifications" / "events" / "registry.md").read_text(
        encoding="utf-8").split("## 8. ORDERING")[1].split("\n## ")[0]
    line = next(l for l in section.split("\n") if "Strict per-aggregate ordering REQUIRED" in l)
    import re as _re
    tolerant = set(_re.findall(r"\b(F\d+)\b", line.partition("Order-tolerant")[2]))
    require_population(tolerant, at_least=3, what="§8 order-tolerant families")
    assert not (runtime & tolerant), (
        f"{sorted(runtime & tolerant)} are marked strict-order but §8 lists them as order-tolerant"
    )


def test_the_contract_strict_order_agrees_with_the_transport_that_enforces_it():
    """### TWO REPRESENTATIONS OF ONE FACT MUST NOT DISAGREE. The SQLite trigger and the inbox
    enforce ordering from `migrations/phase5_event_transport.STRICT_ORDER_AGGREGATE_TYPES`; the
    contracts carry `strict_order` per family. Two canonical answers to one question is a CLAUDE.md
    §7 stop condition, and this unit's own compatibility requirement forbids a second list.
    """
    from freight_recon.migrations.phase5_event_transport import STRICT_ORDER_AGGREGATE_TYPES

    enforced = set(STRICT_ORDER_AGGREGATE_TYPES)
    require_population(enforced, at_least=3, what="strict-order aggregate types in the transport")
    declared = {c.aggregate_type for c in CONTRACTS.values()
                if c.strict_order and c.aggregate_type}
    assert declared == enforced, {
        "contracts say": sorted(declared), "the transport enforces": sorted(enforced)}


# ======================================== 1b. an INDEPENDENT oracle over the family files (R-18)

# ### WHY THIS SECTION EXISTS, AND WHY THE REST OF THE FILE CANNOT REPLACE IT.
#
# Every fixture in this battery is built by `phase5_kit.canonical_payload`, which reads the SAME
# generated data the battery is checking. So the exhaustive 118-contract sweep, the required-field
# sweep, the enum sweep and the fixed-value sweep are all self-consistent BY CONSTRUCTION: they
# prove the runtime agrees with `event_contracts_data.json`, and nothing about whether that file
# agrees with the specification. And `test_the_generated_contract_data_is_exactly_what_the_
# specification_derives` closes the STALENESS loop only — it compares the generator's output to the
# generator's output, so a parser BUG is green in both.
#
# That is exactly how four derivation defects reached an independent review green: two invented
# fixed values (`ClaimProposed.provenance_class='f'` from `(R = f(match_method))`, and
# `ObservationReceived.natural_key='tenant'`) that made their contracts unsatisfiable, a
# strict-order flag wrong for four families, and a global RULE accepted as a producer transition.
#
# The nodes below are written AGAINST THE MARKDOWN, by hand, with the expected values stated
# literally. They are deliberately NOT derived from anything the generator produces.

# Hand-transcribed from `docs/specifications/events/*.md`. Every value here was read off the family
# file by a human and is asserted literally, so a parser that changes its mind fails.
_HAND_CHECKED_FIXED_VALUES = {
    # the ONLY fixed values in the corpus, each written `` `name=VALUE` `` or `(R, `= VALUE`)``
    ("ApprovalFrozen", "frozen"): "true",
    ("ClaimCorrected", "provenance_class"): "OWNER_ASSERTED",
    ("ClaimEvidenced", "provenance_class"): "MODEL_EXTRACTED",
    ("CompensationRefused", "cause"): "unknown_outcome",
    ("EffectVerified", "verification_outcome"): "VERIFIED_SUCCESS",
    ("VerificationConflict", "unknown_reason"): "OBSERVATION_CONFLICTING",
    ("VerificationUnavailable", "unknown_reason"): "OBSERVATION_UNAVAILABLE",
    ("AutonomousAdmissionRecorded", "gate_decision"): "AUTONOMOUS_WITHIN_CAPS",
}

# Annotations that LOOK like a fixed value and are DERIVATION FORMULAS. Reading these as literals
# is what made two whole families unemittable.
_HAND_CHECKED_NOT_FIXED = {
    ("ClaimProposed", "provenance_class"),      # `(R = f(match_method))`  — a function, SD-6
    ("ObservationReceived", "natural_key"),     # `(R = tenant+source+external_id+content_digest)`
}


def test_the_fixed_values_are_exactly_the_ones_a_human_read_off_the_family_files():
    """An oracle written independently of the generator. See the section note above."""
    actual = {
        (c.name, f.name): f.fixed
        for c in CONTRACTS.values() for f in c.fields if f.fixed is not None
    }
    assert actual == _HAND_CHECKED_FIXED_VALUES, {
        "generated but not hand-checked": sorted(set(actual) - set(_HAND_CHECKED_FIXED_VALUES)),
        "hand-checked but not generated": sorted(set(_HAND_CHECKED_FIXED_VALUES) - set(actual)),
        "value disagreements": {k: (actual.get(k), _HAND_CHECKED_FIXED_VALUES.get(k))
                                for k in set(actual) & set(_HAND_CHECKED_FIXED_VALUES)
                                if actual[k] != _HAND_CHECKED_FIXED_VALUES[k]},
    }


@pytest.mark.parametrize("event_name,field_name", sorted(_HAND_CHECKED_NOT_FIXED))
def test_a_derivation_formula_is_never_read_as_a_fixed_value(event_name, field_name):
    """### THE REGRESSION FOR THE SHARPEST DEFECT THIS UNIT SHIPPED AND AN INDEPENDENT REVIEW
    CAUGHT. `provenance_class`(R = f(match_method)) is a formula (SD-6), not the literal `f`; and
    `natural_key`(R = tenant+source+…) is §4's source-natural identity, not the literal `tenant`.
    Read as fixed values they refused every legitimate `ClaimProposed` and `ObservationReceived` in
    the corpus — the whole external-ingress family, unemittable.
    """
    spec = next(f for f in contract_for(event_name).fields if f.name == field_name)
    assert spec.fixed is None, (
        f"{event_name}.{field_name} carries fixed={spec.fixed!r}; its annotation is a derivation "
        f"formula, and a guessed fixed value makes the contract unsatisfiable"
    )
    # And prove it round-trips for real, rather than only that the flag is clear.
    envelope = make_canonical_envelope(event_name)
    validate(envelope, mode=ValidationMode.PRODUCER)


def test_the_human_only_contracts_are_the_ones_the_family_files_declare_unconditionally():
    """Hand-read from the Notes cells: the rows saying `actor_type=human` ONLY, or AUTHENTICATED
    HUMAN ONLY. `ClaimConfirmed` is deliberately ABSENT — its constraint is conditional
    ("`OWNER_ASSERTED` requires `actor_type=human`"), and forcing it human-only would refuse every
    legitimate deterministic (LINKER_INFERRED / RECONCILED) confirmation the corpus allows."""
    expected = {
        "ApprovalGranted",      # AP-2  "`actor_type=human` ONLY (ER-10)"
        "PolicyApproved",       # PO-3  "`actor_type=human` ONLY"
        "PolicyActivated",      # PO-4  "`actor_type=human` ONLY (ER-11)"
        "RuleActivated",        # RU-5  "`actor_type=human` ONLY"
        "BrakeReleased",        # BR-4  "`actor_type=human` ONLY"
        "BrakeNarrowed",        # BR-3  "AUTHENTICATED HUMAN ONLY (broadens authority — ER-12)"
    }
    assert HUMAN_ONLY_EVENTS == expected, {
        "runtime only": sorted(HUMAN_ONLY_EVENTS - expected),
        "expected only": sorted(expected - HUMAN_ONLY_EVENTS),
    }
    assert "ClaimConfirmed" not in HUMAN_ONLY_EVENTS, (
        "ClaimConfirmed's human requirement is CONDITIONAL on OWNER_ASSERTED provenance (ER-10); "
        "making it unconditional would refuse legitimate deterministic confirmations"
    )


# Hand-transcribed from the family files. These are the axes section 1b did NOT cover until a third
# review closed them by hand and found nothing wrong — the enum-member gap being the sharpest: if
# `parse_payload`'s `∈{…}` split ever dropped a member, every event carrying it would be silently
# refused, and nothing in the suite would notice (the enum test reads the DERIVED data, and
# `canonical_payload` picks `spec.enum[0]`). That is the same shape as the value-type gap that let
# the 14-contract regression through.
_HAND_CHECKED_ENUMS = {
    ("ApprovalVoided", "cause"): ("drift", "policy", "brake"),
    ("ClaimAmbiguous", "reason"): ("model_inferred", "multiple", "single_weak"),
    ("ClaimConfirmed", "provenance_class"): ("LINKER_INFERRED", "RECONCILED", "OWNER_ASSERTED"),
    ("ClaimRefused", "cause"): ("already_claimed", "expired", "revoked", "brake", "policy"),
    ("ConflictRaised", "kind"): ("SYSTEM_VS_SYSTEM", "CLAIM_VS_CLAIM", "CLAIM_VS_OBSERVATION",
                                 "INFERRER_VS_OWNER", "READBACK_VS_APPROVED", "RULE_VS_RULE"),
    ("OutcomeUnknown", "unknown_reason"): ("UNKNOWN_OUTCOME", "OBSERVATION_UNAVAILABLE",
                                           "OBSERVATION_CONFLICTING"),
    ("PolicyRevoked", "direction"): ("narrow", "broaden"),
    ("RealityEstablished", "outcome"): ("VERIFIED", "FAILED"),
    ("RealityEstablished", "subject"): ("effect", "compensation"),
}

_HAND_CHECKED_LISTED = {
    ("ApprovalGranted", "signatures"), ("CheckpointPassed", "projected_observations_used"),
    ("CheckpointPassed", "native_claims_used"), ("ConflictPartyAttached", "parties"),
    ("ConflictRaised", "parties"), ("ExpectationReVersioned", "deadline_history"),
    ("PolicyEvaluated", "rules_matched"), ("RuleCompiled", "test_vectors"),
}

# ### THE `required` FLAG IS ANCHORED HERE, NOT ONLY IN THE BEHAVIOURAL NODE, AND THAT MATTERS.
# `test_a_one_of_group_takes_exactly_one_member` wraps its "carries no value for either" assertion
# in `if group.required:` — so if `parse_payload`'s `"?" not in declaration` ever flipped both
# groups to optional, that branch would simply be SKIPPED, the test would stay green, and
# `ConflictResolved{}` — a conflict declared resolved with no resolution reference — would be
# silently admitted. A guard gated by the value it is guarding cannot fail. Hand-read from the
# annotations: `rule_id \| decision_ref`(R, exactly one) is required; `Reopened`'s is unannotated
# and required by the unmarked-is-required rule.
_HAND_CHECKED_ONE_OF = {
    "ConflictResolved": ((("rule_id", "decision_ref"), True),),
    "Reopened": ((("phase_seq", "linked_work_item_id"), True),),
}


def test_the_enum_members_are_exactly_the_ones_a_human_read_off_the_family_files():
    actual = {(c.name, f.name): f.enum
              for c in CONTRACTS.values() for f in c.fields if f.enum is not None}
    assert actual == _HAND_CHECKED_ENUMS, {
        "generated only": sorted(set(actual) - set(_HAND_CHECKED_ENUMS)),
        "hand-read only": sorted(set(_HAND_CHECKED_ENUMS) - set(actual)),
        "member disagreements": {k: (actual.get(k), _HAND_CHECKED_ENUMS.get(k))
                                 for k in set(actual) & set(_HAND_CHECKED_ENUMS)
                                 if actual[k] != _HAND_CHECKED_ENUMS[k]},
    }


def test_the_list_declared_fields_are_exactly_the_ones_a_human_read_off_the_family_files():
    actual = {(c.name, f.name) for c in CONTRACTS.values() for f in c.fields if f.listed}
    assert actual == _HAND_CHECKED_LISTED, {
        "generated only": sorted(actual - _HAND_CHECKED_LISTED),
        "hand-read only": sorted(_HAND_CHECKED_LISTED - actual),
    }


def test_the_one_of_groups_are_exactly_the_ones_a_human_read_off_the_family_files():
    actual = {c.name: tuple((g.members, g.required) for g in c.one_of)
              for c in CONTRACTS.values() if c.one_of}
    assert actual == _HAND_CHECKED_ONE_OF, actual


def test_every_contract_is_on_the_aggregate_its_family_declares():
    """`aggregate_type` decides which history an event orders against, so a wrong one is a silent
    mis-ordering. F14 correctly carries none — its family default is prose."""
    by_family = {}
    for c in CONTRACTS.values():
        by_family.setdefault(c.family, set()).add(c.aggregate_type)
    expected = {
        "F1": {"work_item"}, "F2": {"pipeline_instance"}, "F3": {"effect_grant"},
        "F4": {"approval"}, "F5": {"observation"}, "F6": {"identity_binding_claim"}, "F7": {"conflict"},
        "F8": {"expectation"}, "F9": {"exception"}, "F10": {"compensation"}, "F11": {"policy"},
        "F12": {"rule"}, "F13": {"brake"}, "F14": {None},
    }
    assert by_family == expected, {k: (by_family.get(k), v) for k, v in expected.items()
                                   if by_family.get(k) != v}


def test_a_hand_checked_sample_of_contracts_matches_the_family_files():
    """Twelve contracts across nine families, transcribed by hand from their family-file rows."""
    expected = {
        "WorkItemCreated": {"owner_id": True, "type": True, "entity_ref": False},
        "WorkBlocked": {"reason": True},
        "PipelineStarted": {"commit_key": True},
        "CheckpointFailed": {"step": True, "reason": True},
        "EffectAttempted": {"grant_id": True},
        "GrantRevoked": {"grant_id": True, "cause": True},
        "ApprovalGranted": {"granted_by": True, "signatures": False},
        "ObservationSuperseded": {"superseded_by": True},
        "ExpectationDischarged": {"discharge_observation_id": True, "late": False},
        "ExceptionRaised": {"severity": True, "exposure": False, "source_ref": True,
                            "specific_question": False, "sub_status": False},
        "PolicyRevoked": {"revoked_reason": True, "direction": True},
        "RuleExpired": {"rule_id": True, "rule_version": True, "expired_at": True},
    }
    for name, fields in expected.items():
        actual = {f.name: f.required for f in contract_for(name).fields}
        assert actual == fields, {name: {"generated": actual, "hand-read": fields}}


# ================================================ 2. the seven-step standard, over ALL 118 contracts

@pytest.mark.parametrize("event_name", ALL_CONTRACTS)
def test_every_canonical_contract_survives_the_whole_transport_round_trip(event_name, tmp_path):
    """produce → serialize → outbox → relay → deserialize → upcast → recover → consume.

    ### THIS IS THE NODE THAT MAKES U5.3 A RUNTIME CLAIM RATHER THAN A DOCUMENT. Every one of the
    118 contracts is built from its own declared contract, committed through the real transactional
    outbox, published by the real relay, rehydrated from the stored JSON, read through the upcaster,
    and consumed by a real dedup inbox — and the fact that comes out the far end is byte-identical
    to the one that went in.
    """
    contract = contract_for(event_name)
    store = make_store(tmp_path)
    envelope = make_canonical_envelope(event_name, aggregate_id="agg-round-trip")

    # 1-2. produce and validate as its producer would.
    validate(envelope, mode=ValidationMode.PRODUCER)

    # 3. persist atomically with a real state change.
    baseline = brake_version(store)
    with transactional_emit(store.conn, tenant=T_A) as session:
        session.execute("UPDATE platform_brake SET brake_version = brake_version + 1 WHERE id = 1")
        session.emit(envelope)
    assert_atomic(store, expect_event=True, baseline_version=baseline)

    # 4. publish through the relay — which rehydrates from the stored JSON and re-checks the digest.
    sink = RecordingSink()
    relay = make_relay(store, sink)
    assert relay.run_once().published == (envelope.event_id,)

    # 5-6. deserialize and upcast; 7. recover the canonical representation, unchanged.
    delivered = sink.delivered[0]
    recovered = read(delivered)
    assert recovered.digest() == envelope.digest(), (
        f"{event_name} did not survive the round trip byte-identically"
    )
    assert recovered.event_version == contract.current_version

    # and it is consumable, exactly once.
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    result = inbox.consume(recovered, handler)
    assert result.outcome is ConsumeOutcome.APPLIED, result.detail
    assert inbox.consume(recovered, handler).outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert len(handler.applied) == 1, "a redelivered canonical event ran the handler twice"
    store.close()


def test_the_round_trip_case_covers_every_contract_and_not_a_sample():
    """The parametrization's own anchor: if `ALL_CONTRACTS` ever narrowed, the sweep above would
    still be green while testing a fraction of the corpus."""
    assert set(ALL_CONTRACTS) == set(CONTRACTS)
    assert len(ALL_CONTRACTS) == 118, len(ALL_CONTRACTS)


# ============================================================= 3. identity — what is NOT a fact here

def test_contract_for_itself_refuses_an_unknown_name():
    """The lookup's OWN refusal, distinct from the validation gate's. Both exist — defence in
    depth — which is why each needs its own guard: a mutant disabling one alone is invisible
    through the other, and an untested refusal is one refactor from being deleted as dead code."""
    with pytest.raises(UnknownEventName, match="not a canonical event contract"):
        contract_for("NotAnEventAnybodyDeclared")
    assert contract_for("PipelineStarted").name == "PipelineStarted"


def test_an_unknown_event_name_is_refused_by_the_validator():
    envelope = make_envelope(event_name="LoadDelivered", payload={})
    with pytest.raises(UnknownEventName, match="not a canonical event contract"):
        validate(envelope)
    assert not is_canonical("LoadDelivered")


def test_an_unknown_event_name_cannot_be_committed_to_the_outbox(tmp_path):
    """### THE ATOMICITY CONSEQUENCE. The contract gate runs INSIDE the caller's transaction and
    before the INSERT, so a non-canonical fact does not merely fail to publish — the state change it
    travelled with is rolled back too. An event that is not a fact cannot take a state change with
    it."""
    store = make_store(tmp_path)
    baseline = brake_version(store)
    with pytest.raises(UnknownEventName):
        with transactional_emit(store.conn, tenant=T_A) as session:
            session.execute(
                "UPDATE platform_brake SET brake_version = brake_version + 1 WHERE id = 1")
            session.emit(make_envelope(event_name="InvoicePaid", payload={}))
    assert_atomic(store, expect_event=False, baseline_version=baseline)
    store.close()


def test_an_unknown_event_name_is_refused_by_the_inbox_as_malformed(tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    result = inbox.consume(make_envelope(event_name="CarrierTendered", payload={}), handler)
    assert result.outcome is ConsumeOutcome.REJECTED_MALFORMED
    assert "not a canonical event contract" in result.detail
    assert handler.applied == [], "a non-canonical event reached a handler"
    store.close()


def test_a_canonical_name_attributed_to_the_wrong_transition_is_refused():
    envelope = make_envelope(event_name="BrakeEngaged", aggregate_type="brake",
                             producer_transition_id="WI-1", actor_type="human", actor_id="ops-1",
                             payload=canonical_payload(contract_for("BrakeEngaged")))
    with pytest.raises(ProducerTransitionMismatch, match="emitted by"):
        validate(envelope)


def test_a_canonical_event_on_the_wrong_aggregate_type_is_refused():
    """The ordering key is (tenant, aggregate_id, aggregate_version). An event on the wrong kind of
    aggregate orders against a history that is not its own."""
    envelope = make_envelope(event_name="BrakeEngaged", aggregate_type="work_item",
                             actor_type="human", actor_id="ops-1",
                             producer_transition_id="BR-1",
                             payload=canonical_payload(contract_for("BrakeEngaged")))
    with pytest.raises(AggregateTypeMismatch, match="belongs to aggregate_type"):
        validate(envelope)


# =========================================================== 4. the body — exhaustive where it pays

@pytest.mark.parametrize(
    "event_name",
    sorted(c.name for c in CONTRACTS.values() if any(f.required for f in c.fields)),
)
def test_dropping_any_single_required_field_is_refused(event_name):
    """EXHAUSTIVE over every required field of every contract that has one. Cheap, and it is the
    check that would catch a field silently losing its required marker in a spec edit."""
    contract = contract_for(event_name)
    required = require_population(
        [f for f in contract.fields if f.required], at_least=1,
        what=f"{event_name} required fields")
    for spec in required:
        payload = canonical_payload(contract)
        payload.pop(spec.name)
        envelope = make_envelope(event_name=event_name, payload=payload,
                                 **_extras_for(contract))
        with pytest.raises(PayloadContractViolation, match="missing required field"):
            validate(envelope)


def _extras_for(contract: CanonicalContract) -> dict:
    """The envelope-level fields a contract needs beyond its payload, so a payload case fails for
    the reason it is testing rather than on an unrelated pin."""
    extras: dict = {}
    if contract.aggregate_type:
        extras["aggregate_type"] = contract.aggregate_type
    if contract.producers:
        extras["producer_transition_id"] = contract.producers[0]
    if contract.consequential:
        extras.update({
            "entity_versions": {"x:1": 1}, "policy_version": "policy-v1",
            "brake_version": "brake-v1",
        })
    if contract.human_only:
        # Derived, not listed. A three-name literal here was exactly the R-04 defect, and having it
        # reappear in the test file would have left `ApprovalGranted`, `PolicyApproved` and
        # `RuleActivated` — the contracts the fix exists for — covered by set membership alone.
        extras.update({"actor_type": "human", "actor_id": "ops-1"})
    return extras


def test_a_required_field_present_as_null_is_refused():
    """`null ≠ absent` (§1): null is a stated "we looked and there is nothing", which a required
    fact cannot be. Silently accepting it would let a fact assert its own absence."""
    contract = contract_for("PipelineStarted")
    payload = canonical_payload(contract)
    payload["commit_key"] = None
    with pytest.raises(PayloadContractViolation, match="present as null"):
        validate(make_envelope(event_name="PipelineStarted", payload=payload,
                               **_extras_for(contract)))


@pytest.mark.parametrize(
    "event_name", sorted(c.name for c in CONTRACTS.values() if any(f.enum for f in c.fields)))
def test_a_value_outside_a_declared_enum_is_refused(event_name):
    contract = contract_for(event_name)
    enums = require_population([f for f in contract.fields if f.enum], at_least=1,
                               what=f"{event_name} enum fields")
    for spec in enums:
        payload = canonical_payload(contract)
        payload[spec.name] = "NOT_A_DECLARED_MEMBER"
        with pytest.raises(PayloadContractViolation, match="contract does not permit"):
            validate(make_envelope(event_name=event_name, payload=payload,
                                   **_extras_for(contract)))


@pytest.mark.parametrize(
    "event_name",
    sorted(c.name for c in CONTRACTS.values() if any(f.fixed for f in c.fields)))
def test_a_fixed_value_cannot_be_changed(event_name):
    """`frozen=true`, `verification_outcome=VERIFIED_SUCCESS`, `unknown_reason=…`. The fixed value
    IS the fact the event exists to record; an event asserting a different one is a different
    event wearing this one's name."""
    contract = contract_for(event_name)
    fixed = require_population([f for f in contract.fields if f.fixed], at_least=1,
                               what=f"{event_name} fixed fields")
    for spec in fixed:
        payload = canonical_payload(contract)
        payload[spec.name] = "something-else"
        with pytest.raises(PayloadContractViolation, match="is fixed to"):
            validate(make_envelope(event_name=event_name, payload=payload,
                                   **_extras_for(contract)))


@pytest.mark.parametrize(
    "event_name", sorted(c.name for c in CONTRACTS.values() if c.one_of))
def test_a_one_of_group_takes_exactly_one_member(event_name):
    """`rule_id \\| decision_ref`(R, exactly one). Two answers to a one-of is not extra information;
    it is an unresolvable fact, and neither is a missing one."""
    contract = contract_for(event_name)
    for group in require_population(contract.one_of, at_least=1, what=f"{event_name} one-of groups"):
        both = canonical_payload(contract)
        for member in group.members:
            both[member] = f"{member}-value"
        with pytest.raises(PayloadContractViolation, match="EXACTLY ONE"):
            validate(make_envelope(event_name=event_name, payload=both, **_extras_for(contract)))

        if group.required:
            neither = canonical_payload(contract)
            for member in group.members:
                neither.pop(member, None)
            with pytest.raises(PayloadContractViolation, match="carries no value for either"):
                validate(make_envelope(event_name=event_name, payload=neither,
                                       **_extras_for(contract)))


def test_a_constrained_field_refuses_a_collection():
    """`ClaimRefused.cause` is THE cause a claim was refused. `["already_claimed", "expired"]` says
    two incompatible things at once — and it passed, because the enum check iterates a collection
    and approved each member individually."""
    contract = contract_for("ClaimRefused")
    for bad in (["already_claimed", "expired"], ("already_claimed",), {"cause": "expired"}):
        payload = {**canonical_payload(contract), "cause": bad}
        with pytest.raises(PayloadContractViolation, match="constrained to a single declared value"):
            validate(make_envelope(event_name="ClaimRefused", payload=payload,
                                   **_extras_for(contract)))


# The fields the SPECIFICATION declares as collections WITHOUT the `[]` marker — it uses the
# annotation instead. Hand-read from the family files; see the section-1b note.
_SPEC_DECLARED_STRUCTURED = [
    ("CheckpointPassed", "entity_versions", {"work_item:wi-1": 3, "load:ld-9": 7}),   # "(R, SD-3 set)"
    ("EffectGranted", "entity_versions", {"effect_grant:eg-1": 1}),
    ("AutonomousAdmissionRecorded", "caps_evaluated", {"cap-1": {"limit": 100, "observed": 40}}),
    ("PolicyApproved", "evidence_refs", ["sha256:aa", "sha256:bb"]),
    ("ApprovalRequested", "rendered_facts", {"amount_minor": 12500, "carrier": "ACME"}),
    ("BrakeEngaged", "scope", {"tenant": "t-1", "action_class": "invoice_write"}),
    ("PolicyProposed", "caps", {"per_load_minor": 50000}),
    ("ApprovalVoided", "drift_diff", {"amount_minor": [12500, 13000]}),
    ("FraudSignalRaised", "refs", ["obs-1", "obs-2"]),
    ("ObservationParsed", "parsed_value", {"total_minor": 4200}),
    ("ProjectionRebuildDiverged", "live", {"status": "DELIVERED"}),
]


@pytest.mark.parametrize("event_name,field_name,value", _SPEC_DECLARED_STRUCTURED)
def test_a_spec_declared_structured_field_is_accepted(event_name, field_name, value):
    """### THE REGRESSION FOR A DEFECT THE REMEDIATION ITSELF INTRODUCED, AND A RE-REVIEW CAUGHT.

    The first fix for `ClaimRefused.cause` refused ANY collection in ANY field not written
    `name[]`. But the corpus marks a collection with the ANNOTATION at least as often as with the
    marker — `entity_versions`(R, **SD-3 set**), `caps_evaluated`(R — each cap id with its limit and
    the observed value), `scope` (tenant + action_class), plural `evidence_refs` and `refs`. That
    rule made **14 canonical contracts unsatisfiable**, including `CheckpointPassed`, the most
    load-bearing contract in the corpus.

    It was the same mistake as reading a derivation formula as a fixed value: a rule the
    specification does not write, refusing values it explicitly requires. The refusal is now
    confined to fields constrained by an enum or a fixed value — which is exactly where the defect
    lived, and none of these has either.

    ### AND THIS IS THE ORACLE GAP THAT LET IT THROUGH. Section 1b hand-checks required/fixed/
    human-only and NO VALUE TYPES, while `canonical_payload` synthesises every non-`[]` field as a
    string — so nothing in the suite ever fed a structured value to a scalar field.
    """
    contract = contract_for(event_name)
    payload = {**canonical_payload(contract), field_name: value}
    validate(make_envelope(event_name=event_name, payload=payload, **_extras_for(contract)))


def test_the_conditionally_consequential_member_is_not_pinned_unconditionally():
    """§5 writes `` `ClaimConfirmed`(when it backs a money action) ``. Whether a binding backs a
    money action is a property of the DECISION, not the envelope, so this layer cannot decide it —
    exactly as with `material_facts_fingerprint`'s "where an amount is involved". Enforcing the pins
    anyway refused every ordinary deterministic (LINKER_INFERRED / RECONCILED) confirmation."""
    conditional = {n for n, c in CONTRACTS.items() if c.consequential_conditional}
    assert conditional == {"ClaimConfirmed"}, sorted(conditional)
    contract = contract_for("ClaimConfirmed")
    validate(make_envelope(
        event_name="ClaimConfirmed", payload=canonical_payload(contract),
        aggregate_type=contract.aggregate_type, producer_transition_id=contract.producers[0],
        entity_versions=None, policy_version=None, brake_version=None))
    # The unqualified members are still pinned — the exemption is not a hole in §5.
    unqualified = require_population(
        [n for n in CONSEQUENTIAL_EVENTS if n not in conditional], at_least=15,
        what="unqualified §5 members")
    other = contract_for(sorted(unqualified)[0])
    with pytest.raises(ConsequentialPinsMissing):
        validate(make_envelope(event_name=other.name, payload=canonical_payload(other),
                               **{**_extras_for(other), "policy_version": None}))


def test_a_blank_consequential_pin_is_no_pin_at_all():
    """A pin that is `""` or `"   "` reproduces exactly as much decision context as an absent one.
    ER-13 is about being able to REPRODUCE the decision, not about the field being present."""
    contract = contract_for("BrakeEngaged")
    for pin, blank in (("policy_version", ""), ("brake_version", "   "), ("entity_versions", {})):
        with pytest.raises(ConsequentialPinsMissing, match=pin):
            validate(make_envelope(event_name="BrakeEngaged",
                                   payload=canonical_payload(contract),
                                   **{**_extras_for(contract), pin: blank}))


def test_a_producer_must_emit_the_current_version():
    """### READING AN OLD VERSION IS THE CONSUMER'S JOB; WRITING ONE IS NOBODY'S.

    Only the FUTURE case was checked. On the day a contract goes to v2, an emitter could stamp
    `event_version=1` on a body validated against the v2 field set and commit it — and a consumer
    would then either fail on a missing upcaster or run a v1→v2 upcaster over a body that is already
    v2-shaped, corrupting the fact instead of refusing it.

    Today every contract is v1, so the case is constructed by asking a v1 contract to accept a v2
    envelope (refused as a future version) and by asserting the PRODUCER rule is version-exact.
    """
    import inspect

    from freight_recon import event_contracts

    # `validate` is a thin binding to the canonical registry; the rule lives in the one shared
    # implementation both it and the reconstruction seam call, so that is what must carry it.
    source = inspect.getsource(event_contracts._validate_against)
    assert "envelope.event_version != contract.current_version" in source, (
        "the PRODUCER path no longer requires the version to be exactly the contract's current one"
    )
    envelope = make_canonical_envelope("PipelineStarted")
    stale = EventEnvelope.from_document({**envelope.as_document(), "event_version": 2})
    with pytest.raises(ContractError):
        validate(stale, mode=ValidationMode.PRODUCER)
    validate(envelope, mode=ValidationMode.PRODUCER)          # the positive anchor


def test_a_required_one_of_is_not_answered_by_a_null():
    """### `null` IS AN ANSWER, NOT A VALUE — AND THE TWO TESTS ARE DIFFERENT QUESTIONS.

    A key-membership test alone accepted `ConflictResolved{"rule_id": None}` — an event declaring a
    conflict resolved while carrying no resolution reference at all — because the member was
    "present". That is the same `null != absent` rule the required-field check applies, applied
    inconsistently 60 lines apart.

    Both halves are asserted here so they cannot drift: null does not SATISFY a required one-of, and
    null still COUNTS as a second answer.
    """
    contract = contract_for("ConflictResolved")
    with pytest.raises(PayloadContractViolation, match="present but null"):
        validate(make_envelope(event_name="ConflictResolved", payload={"rule_id": None},
                               **_extras_for(contract)))
    with pytest.raises(PayloadContractViolation, match="EXACTLY ONE"):
        validate(make_envelope(event_name="ConflictResolved",
                               payload={"rule_id": None, "decision_ref": "d-1"},
                               **_extras_for(contract)))
    validate(make_envelope(event_name="ConflictResolved", payload={"rule_id": "r-1"},
                           **_extras_for(contract)))


def test_an_enum_member_reads_the_same_way_for_an_enum_field_and_a_fixed_field():
    """### THE ASYMMETRY `_token` EXISTS TO ABOLISH, SURVIVING IN THE ONE BRANCH THAT DID NOT CALL IT.

    §1 mandates "enums by name" for canonical serialization, so an `Enum` member is a legitimate
    payload value. The enum check resolved it by `.name`; the fixed check used a bare `str()` and
    saw `Prov.OWNER_ASSERTED`, refusing a value the other branch had just accepted. Fail-closed, so
    never a security hole — but the module claims one resolver serves both readings, and it did not.
    """
    import enum

    class Prov(enum.Enum):
        OWNER_ASSERTED = "OWNER_ASSERTED"

    class Outcome(enum.Enum):
        VERIFIED_SUCCESS = "VERIFIED_SUCCESS"

    fixed_contract = contract_for("ClaimCorrected")
    payload = {**canonical_payload(fixed_contract), "provenance_class": Prov.OWNER_ASSERTED}
    validate(make_envelope(event_name="ClaimCorrected", payload=payload,
                           **{**_extras_for(fixed_contract),
                              "actor_type": "human", "actor_id": "owner-1"}))

    verified = contract_for("EffectVerified")
    validate(make_envelope(
        event_name="EffectVerified",
        payload={**canonical_payload(verified),
                 "verification_outcome": Outcome.VERIFIED_SUCCESS},
        **_extras_for(verified)))

    # And a WRONG enum member is still refused — the fix resolves the value, it does not skip it.
    class Wrong(enum.Enum):
        SOMETHING_ELSE = "SOMETHING_ELSE"

    with pytest.raises(PayloadContractViolation, match="is fixed to"):
        validate(make_envelope(
            event_name="EffectVerified",
            payload={**canonical_payload(verified), "verification_outcome": Wrong.SOMETHING_ELSE},
            **_extras_for(verified)))


def test_a_list_declared_field_refuses_a_scalar():
    contract = contract_for("ConflictRaised")
    listed = require_population([f for f in contract.fields if f.listed], at_least=1,
                                what="ConflictRaised list fields")
    payload = canonical_payload(contract)
    payload[listed[0].name] = "not-a-list"
    with pytest.raises(PayloadContractViolation, match="must be a list"):
        validate(make_envelope(event_name="ConflictRaised", payload=payload,
                               **_extras_for(contract)))


# ============================================ 5. §6's asymmetry — the one rule the two modes differ by

def test_a_producer_may_not_invent_a_payload_field_but_a_consumer_ignores_one():
    """### THE ASYMMETRY IS §6's, NOT A CONVENIENCE. "a `vN+1` producer + a `vN` consumer ⇒
    additive fields are ignored". A consumer that refused an unrecognised field would turn every
    additive schema change into a coordinated outage; a producer that accepted one would let a typo
    become durable history. Both halves are asserted here, on ONE envelope, so the pair cannot drift
    apart.
    """
    contract = contract_for("PipelineStarted")
    payload = {**canonical_payload(contract), "an_additive_field_from_a_newer_producer": "v2"}
    envelope = make_envelope(event_name="PipelineStarted", payload=payload,
                             **_extras_for(contract))

    with pytest.raises(PayloadContractViolation, match="undeclared field"):
        validate(envelope, mode=ValidationMode.PRODUCER)

    validate(envelope, mode=ValidationMode.CONSUMER)      # no raise: §6's mixed-version rule


def test_the_outbox_refuses_an_invented_field_and_the_inbox_accepts_it(tmp_path):
    """The same asymmetry, through the real transport rather than the validator."""
    contract = contract_for("PipelineStarted")
    payload = {**canonical_payload(contract), "rider": "from-a-newer-producer"}
    envelope = make_envelope(event_name="PipelineStarted", payload=payload,
                             **_extras_for(contract))
    store = make_store(tmp_path)

    with pytest.raises(PayloadContractViolation):
        with transactional_emit(store.conn, tenant=T_A) as session:
            session.emit(envelope)

    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    assert inbox.consume(envelope, handler).outcome is ConsumeOutcome.APPLIED
    store.close()


# ================================================= 6. consequential events pin their decision context

@pytest.mark.parametrize(
    "event_name",
    sorted(n for n in CONSEQUENTIAL_EVENTS if not CONTRACTS[n].consequential_conditional))
def test_a_consequential_event_without_its_pins_is_refused(event_name):
    """EXHAUSTIVE over §5. ER-13: a consequential event carries enough refs to reproduce its
    decision context AT THAT TIME. Without them the audit can say what was decided and never why it
    was allowed — the difference between a log and evidence."""
    contract = contract_for(event_name)
    for pin in ("entity_versions", "policy_version", "brake_version"):
        # Explicitly None, not popped: `make_envelope` supplies a consequential contract's pins by
        # default, so a popped key would simply be re-added and this case would assert nothing.
        envelope = make_envelope(event_name=event_name,
                                 payload=canonical_payload(contract),
                                 **{**_extras_for(contract), pin: None})
        with pytest.raises(ConsequentialPinsMissing, match=pin):
            validate(envelope)


def test_a_non_consequential_event_is_not_required_to_pin_anything():
    """The positive anchor: the pin rule must not be silently applied to the whole corpus, or the
    case above would pass for the wrong reason."""
    ordinary = require_population(
        [c for c in CONTRACTS.values() if not c.consequential and not c.fields],
        at_least=1, what="non-consequential contracts with no declared payload")
    contract = ordinary[0]
    validate(make_envelope(event_name=contract.name, payload={}, **_extras_for(contract)))


# ================================================================ 7. actor authority — ER-9/10/11/12

@pytest.mark.parametrize("event_name", sorted(HUMAN_ONLY_EVENTS))
@pytest.mark.parametrize("actor_type", ["system", "detector", "model"])
def test_an_automated_actor_may_never_broaden_authority(event_name, actor_type):
    """ER-11/ER-12. Activating policy, releasing a brake and narrowing one all BROADEN authority.
    Automation may narrow authority; it may never broaden it, and the canonical response to an
    attempt is an `Unauthorized*Attempted` record — not acceptance."""
    contract = contract_for(event_name)
    envelope = make_envelope(event_name=event_name, payload=canonical_payload(contract),
                             **{**_extras_for(contract),
                                "actor_type": actor_type, "actor_id": "automation-1"})
    with pytest.raises(ActorAuthorityViolation, match="ER-11/ER-12"):
        validate(envelope)


def test_an_authenticated_human_may_broaden_authority():
    """The positive anchor for the case above — otherwise "refused" could mean "always refused"."""
    require_population(HUMAN_ONLY_EVENTS, at_least=6, what="human-only contracts")
    for event_name in sorted(HUMAN_ONLY_EVENTS):
        validate(make_canonical_envelope(event_name))


def test_a_model_actor_may_only_claim_or_propose_never_state_a_fact():
    """ER-9. A model-generated fact stays a claim; it does not become truth by being written to an
    event stream."""
    # F6 ∪ *Proposed, MINUS `ClaimConfirmed` — which is in F6 by family but states a FACT: its row
    # says a binding is canonical "via a deterministic method or an authenticated human", and its
    # notes say a MODEL_INFERRED claim lands at `ClaimAmbiguous`, "never CONFIRMED, at any
    # confidence (GR-8)". Blanket family membership read the LABEL and let a model confirm a
    # consequential identity binding.
    permitted = require_population(
        sorted(n for n, c in CONTRACTS.items()
               if (c.family == "F6" or n.endswith("Proposed")) and n != "ClaimConfirmed"),
        at_least=6, what="contracts a model may produce")

    with pytest.raises(ActorAuthorityViolation, match="ER-9"):
        validate(make_envelope(
            event_name="ClaimConfirmed", payload=canonical_payload(contract_for("ClaimConfirmed")),
            **{**_extras_for(contract_for("ClaimConfirmed")),
               "actor_type": "model", "actor_id": "extractor-1"}))
    # `ClaimCorrected` is in the F6 family AND fixes `provenance_class=OWNER_ASSERTED`, so ER-10
    # forbids a machine actor from producing it regardless of ER-9. The two rules compose; excluding
    # it here keeps this node about ER-9 alone, and ER-10 is asserted on its own below.
    owner_asserted = {n for n in permitted
                      if any(f.name == "provenance_class" and f.fixed == "OWNER_ASSERTED"
                             for f in contract_for(n).fields)}
    require_population(owner_asserted, at_least=1, what="F6 contracts that fix OWNER_ASSERTED")
    for name in [n for n in permitted if n not in owner_asserted]:
        contract = contract_for(name)
        validate(make_envelope(event_name=name, payload=canonical_payload(contract),
                               **{**_extras_for(contract),
                                  "actor_type": "model", "actor_id": "extractor-1"}))

    # Human-only contracts are excluded from this sample: ER-11/ER-12 refuses them FIRST and with a
    # different message, so including them would assert ER-9 against a rule that never ran.
    refused = require_population(
        [n for n in EMITTED_CORPUS if n not in permitted and n not in HUMAN_ONLY_EVENTS],
        at_least=90, what="contracts a model may NOT produce")
    for name in sorted(refused)[:12]:                   # representative: the rule is name-derived
        contract = contract_for(name)
        with pytest.raises(ActorAuthorityViolation, match="ER-9"):
            validate(make_envelope(event_name=name, payload=canonical_payload(contract),
                                   **{**_extras_for(contract),
                                      "actor_type": "model", "actor_id": "extractor-1"}))


def test_a_machine_actor_cannot_assert_owner_asserted_provenance():
    """ER-10. Letting a machine write `OWNER_ASSERTED` would launder an inference into an owner's
    word — and B3/GR-9 exist because that is the failure that does not look like one."""
    contract = contract_for("ClaimConfirmed")
    payload = {**canonical_payload(contract), "provenance_class": "OWNER_ASSERTED"}
    # `model` is excluded here because ER-9 refuses it FIRST for this contract (see
    # `_MODEL_FORBIDDEN_CLAIMS`); this node is about the machine actors ER-10 governs.
    for actor_type in ("system", "detector"):
        with pytest.raises(ActorAuthorityViolation, match="ER-10"):
            validate(make_envelope(event_name="ClaimConfirmed", payload=payload,
                                   **{**_extras_for(contract),
                                      "actor_type": actor_type, "actor_id": "machine-1"}))
    validate(make_envelope(event_name="ClaimConfirmed", payload=payload,
                           **{**_extras_for(contract),
                              "actor_type": "human", "actor_id": "owner-1"}))


def test_owner_asserted_provenance_cannot_be_smuggled_past_er_10():
    """### THREE EVASIONS AN INDEPENDENT REVIEW FOUND, ALL OF WHICH PASSED WITH `actor_type=system`.

    The old check was one scalar `payload.get("provenance_class") == "OWNER_ASSERTED"`.

      1. **`provenance_refs` at the envelope level** — which §1 DEFINES as "the `provenance_class`
         + lineage of any claim/value carried". The canonical home for provenance was the one place
         the check never looked.
      2. **An `Enum` member** rather than a string. `_check_payload` resolves an enum by `.name`
         (§1 mandates "enums by name"), so it ACCEPTED the member into the declared enum, while the
         authority check compared the object to a `str` and got False. The payload validator and
         the authority validator disagreed about the same value in one call.
      3. **Nesting** it one level down in the payload.
    """
    import enum

    class Provenance(enum.Enum):
        OWNER_ASSERTED = "OWNER_ASSERTED"

    contract = contract_for("ClaimConfirmed")
    base = _extras_for(contract) | {"actor_type": "system", "actor_id": "machine-1"}

    smuggles = {
        "envelope provenance_refs": dict(
            payload=canonical_payload(contract),
            provenance_refs={"provenance_class": "OWNER_ASSERTED", "lineage": ["x"]}),
        "an Enum member": dict(
            payload={**canonical_payload(contract),
                     "provenance_class": Provenance.OWNER_ASSERTED}),
        "nested inside a provenance lineage": dict(
            payload=canonical_payload(contract),
            provenance_refs={"lineage": [{"step": 1},
                                         {"step": 2, "provenance_class": "OWNER_ASSERTED"}]}),
    }
    for label, overrides in smuggles.items():
        try:
            with pytest.raises(ActorAuthorityViolation, match="ER-10"):
                validate(make_envelope(event_name="ClaimConfirmed", **{**base, **overrides}))
        except BaseException as exc:                       # noqa: BLE001 - re-raised with context
            raise AssertionError(f"the {label} smuggle was NOT refused") from exc

    # Positive anchor: an ordinary machine-actor event with honest provenance still validates, so
    # the recursive scan has not simply started refusing everything.
    validate(make_envelope(event_name="ClaimConfirmed", **base))


# ================================================================ 8. versions and the upcaster (§6)

def test_every_canonical_contract_is_at_v1_today():
    """### STATED AS A FACT ABOUT THE SPECIFICATION, NOT AS AN ASPIRATION. The corpus has not
    evolved yet, which is exactly why the canonical registry holds zero upcasters. If this node ever
    fails, an event has been versioned and its upcaster is now REQUIRED — that is the signal, and it
    is better delivered by a red test than discovered by an unreadable history."""
    versions = {c.name: c.current_version for c in CONTRACTS.values() if c.current_version != 1}
    assert versions == {}, versions
    assert UPCASTERS.registered_steps() == (), (
        "an upcaster is registered against a corpus where nothing has evolved"
    )


@pytest.mark.parametrize("event_name", ["CheckpointPassed", "WorkItemCreated", "BrakeEngaged"])
def test_an_event_from_an_unsupported_future_version_is_refused(event_name):
    """§6 gates a breaking change on a coordinated rollout, so a future version arriving here is a
    DEPLOYMENT error. It fails closed rather than reading fields it cannot understand."""
    envelope = make_canonical_envelope(event_name)
    future = EventEnvelope.from_document({**envelope.as_document(), "event_version": 2})
    with pytest.raises(UnsupportedFutureVersion, match="v2"):
        validate(future)
    with pytest.raises(UnsupportedFutureVersion):
        read(future)


def test_a_future_version_is_refused_by_the_inbox_and_reaches_no_handler(tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    envelope = make_canonical_envelope("PipelineStarted")
    future = EventEnvelope.from_document({**envelope.as_document(), "event_version": 7})
    result = inbox.consume(future, handler)
    assert result.outcome is ConsumeOutcome.REJECTED_MALFORMED
    assert handler.applied == []
    store.close()


def test_an_identity_upcast_returns_the_same_object_and_the_same_digest():
    """Identity must be genuinely free: a v1 read under a v1 contract may not reallocate, because a
    reallocation is one serialization bug away from changing a digest that history depends on."""
    envelope = make_canonical_envelope("CheckpointPassed")
    assert UPCASTERS.upcast(envelope) is envelope
    assert read(envelope).digest() == envelope.digest()


# --- the chaining mechanism, proven on a SYNTHETIC contract set --------------------------------
#
# ### WHY SYNTHETIC, STATED PLAINLY. Every canonical contract is at v1, so the corpus cannot
# exercise a real v1→v2→v3 chain. The alternative would be to mint a fake v2 of a real canonical
# event, which would amend a protected specification to make a test look impressive. So the CHAINING
# is proven for what it is — mechanism — while the canonical corpus above proves what IT is:
# identity, and the refusals. Neither node pretends to be the other.

def _synthetic(current_version: int) -> dict[str, CanonicalContract]:
    return {
        "SyntheticEvolvingFact": CanonicalContract(
            name="SyntheticEvolvingFact", family="F1", source="(synthetic)",
            current_version=current_version, producers=("WI-1",), coordination=False,
            aggregate_type="work_item", emitted_corpus=True, consequential=False,
            strict_order=False, human_only=False, consequential_conditional=False,
            fields=(FieldSpec("value", True, False, None, None),), one_of=(),
        )
    }


def test_the_upcaster_chain_applies_every_step_in_order():
    registry = UpcasterRegistry(_synthetic(3))
    registry.register("SyntheticEvolvingFact", 1, lambda p: {**p, "steps": [*p.get("steps", []), 1]})
    registry.register("SyntheticEvolvingFact", 2, lambda p: {**p, "steps": [*p.get("steps", []), 2]})
    assert registry.registered_steps() == (("SyntheticEvolvingFact", 1),
                                           ("SyntheticEvolvingFact", 2))
    out = registry.upcast_payload("SyntheticEvolvingFact", 1, {"value": "v"})
    assert out == {"value": "v", "steps": [1, 2]}, out
    # Deterministic: a full-history rebuild runs it again, every time (M-25).
    assert registry.upcast_payload("SyntheticEvolvingFact", 1, {"value": "v"}) == out
    # Starting mid-chain applies only the remaining steps.
    assert registry.upcast_payload("SyntheticEvolvingFact", 2, {"value": "v"}) == {
        "value": "v", "steps": [2]}
    # Already current: identity.
    assert registry.upcast_payload("SyntheticEvolvingFact", 3, {"value": "v"}) == {"value": "v"}


def test_a_missing_upcaster_link_is_refused_never_passed_through():
    """### THE DEFECT THIS FORECLOSES: a v1 document read as a v3 is a fact carrying two versions of
    assumptions the reader does not know it is making. M-25 says no historical event may become
    unreadable because current code changed — the honest answer to a missing link is to say so."""
    registry = UpcasterRegistry(_synthetic(3))
    registry.register("SyntheticEvolvingFact", 2, lambda p: p)      # the 1→2 link is absent
    with pytest.raises(MissingUpcaster, match="no v1→v2 upcaster is registered"):
        registry.upcast_payload("SyntheticEvolvingFact", 1, {"value": "v"})


def test_the_upcaster_registry_refuses_incoherent_registrations():
    registry = UpcasterRegistry(_synthetic(3))
    with pytest.raises(ContractError, match="later than the contract's current"):
        registry.register("SyntheticEvolvingFact", 3, lambda p: p)
    with pytest.raises(ContractError, match=">= 1"):
        registry.register("SyntheticEvolvingFact", 0, lambda p: p)
    with pytest.raises(UnknownEventName):
        registry.register("NotAContract", 1, lambda p: p)
    registry.register("SyntheticEvolvingFact", 1, lambda p: p)
    with pytest.raises(ContractError, match="already registered"):
        registry.register("SyntheticEvolvingFact", 1, lambda p: p)


def test_the_read_path_validates_after_upcasting_not_before():
    """### `read` IS "upcast, THEN validate", AND THE ORDER IS THE POINT. Validating first would
    judge a historical body against a contract it was never written to; not validating after would
    make evolution the one path into the system contract checking does not cover. The composition is
    asserted on the real path — a canonical event whose body violates its contract is refused BY
    `read`, not merely by `validate`.
    """
    contract = contract_for("PipelineStarted")
    broken = make_envelope(event_name="PipelineStarted", payload={}, **_extras_for(contract))
    with pytest.raises(PayloadContractViolation, match="missing required field"):
        read(broken)

    # An upcaster is a pure payload transform: it does not validate, by design, because the body it
    # produces mid-chain is not yet at the current version and judging it there would be wrong.
    registry = UpcasterRegistry(_synthetic(3))
    registry.register("SyntheticEvolvingFact", 1, lambda p: {"midway": True})
    registry.register("SyntheticEvolvingFact", 2, lambda p: {"value": "restored"})
    assert registry.upcast_payload("SyntheticEvolvingFact", 1, {"value": "v"}) == {
        "value": "restored"}, "a mid-chain body must be allowed to be incomplete"


# ============================================================ 9. the contract gate is not a bypass

def test_contract_validation_never_becomes_authority(tmp_path):
    """CLAUDE.md rule 9. A validated event is a well-formed FACT. It is not permission for anything,
    and consuming the whole corpus mints no witness, no grant and no claim."""
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    consumed = 0
    for index, name in enumerate(ALL_CONTRACTS):
        envelope = make_canonical_envelope(name, aggregate_id=f"agg-{index}", seed=f"auth-{name}")
        if inbox.consume(envelope, handler).outcome is ConsumeOutcome.APPLIED:
            consumed += 1
    assert consumed == len(ALL_CONTRACTS), f"only {consumed} of {len(ALL_CONTRACTS)} were consumed"
    counts = {
        table: store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("checkpoint_witnesses", "effect_grants")
    }
    assert counts == {"checkpoint_witnesses": 0, "effect_grants": 0}, counts
    store.close()


def test_the_contract_layer_reads_payloads_only_to_refuse_them():
    """### THE ARCHITECTURAL LINE THIS UNIT ADDS, MADE EXPLICIT RATHER THAN ACCIDENTAL. The
    transport still never reads inside a payload (that node lives in the transport battery).
    Validation necessarily DOES — that is what checking a body means — so the property that keeps it
    safe is different: `event_contracts` may look at a payload, and the only thing it may do with
    what it finds is raise.
    """
    import ast
    import inspect

    from freight_recon import event_contracts

    source = inspect.getsource(event_contracts)
    tree = ast.parse(source)

    # ### THIS CHECK WAS A NO-OP AND THE PROPERTY IT NAMED WAS FALSE. It read
    # `n.__class__.__name__` (which is `"Import"`, never `"import"`) over `ast.Import` nodes — of
    # which this module has ZERO, because its sibling imports are `ImportFrom`. So it compared
    # `"import" not in set()` and passed unconditionally while the module did import two siblings.
    # CLAUDE.md §9: "a green check that parsed nothing is worse than no check."
    #
    # The real property: a validator may reach the envelope type it validates and nothing else. It
    # must not reach the transport, an adapter, a store or the effect boundary — reach is what
    # turns a checker into something that can act on what it finds.
    INERT_SIBLINGS = {"event_envelope"}
    reached = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level and node.module:
            reached.add(node.module.split(".")[0])
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("freight_recon"):
                    reached.add(alias.name.split(".")[-1])
    assert reached, "the import scan found nothing — it cannot conclude anything"
    assert reached <= INERT_SIBLINGS, (
        f"event_contracts reaches {sorted(reached - INERT_SIBLINGS)}; a validator that can reach "
        f"the transport, a store or an adapter is one edit away from acting on what it validates. "
        f"Permitted: {sorted(INERT_SIBLINGS)}"
    )

    subscript_writes = [n for n in ast.walk(tree)
                        if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Store)]
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load)]
    require_population(reads, at_least=1, what="subscript reads in event_contracts")
    for node in subscript_writes:
        # The WHOLE target, not just its base: `document["payload"] = ...` names payload in the
        # slice, and inspecting `node.value` alone missed it.
        target = ast.unparse(node)
        assert "payload" not in target or "document[" in target, (
            f"event_contracts writes into a payload at `{target}`; validation inspects a fact, "
            f"it never edits one"
        )


def test_tenant_isolation_survives_the_contract_gate(tmp_path):
    """[C-1] outranks every other question about an event, including whether it is canonical: a
    foreign-tenant event must be refused before this consumer spends any judgement on what it says."""
    store = make_store(tmp_path)
    inbox = make_inbox(store, tenant=T_A)
    handler = RecordingHandler(store.conn)
    foreign = make_canonical_envelope("PipelineStarted", tenant=T_B)
    result = inbox.consume(foreign, handler)
    assert result.outcome is ConsumeOutcome.REJECTED_CROSS_TENANT
    assert handler.applied == []

    # And a foreign-tenant event that is ALSO non-canonical is still reported as the tenant
    # violation, because that is the finding that matters and the one that must be recorded.
    foreign_junk = make_envelope(event_name="NotAContract", tenant=T_B, payload={})
    assert inbox.consume(foreign_junk, handler).outcome is ConsumeOutcome.REJECTED_CROSS_TENANT
    store.close()


def test_a_refused_event_leaves_no_inbox_row_so_a_corrected_redelivery_can_still_apply(tmp_path):
    """### A REFUSAL IS NOT A CONSUMPTION. Recording a rejected event in the inbox would make its
    corrected redelivery a DUPLICATE_NOOP — the event would be permanently unconsumable, which is
    silent event loss wearing an idempotency guarantee."""
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    contract = contract_for("PipelineStarted")

    broken = make_envelope(event_name="PipelineStarted", payload={}, seed="repairable",
                           **_extras_for(contract))
    assert inbox.consume(broken, handler).outcome is ConsumeOutcome.REJECTED_MALFORMED
    assert store.conn.execute("SELECT COUNT(*) FROM event_inbox").fetchone()[0] == 0

    repaired = EventEnvelope.from_document(
        {**broken.as_document(), "payload": canonical_payload(contract)})
    assert repaired.event_id == broken.event_id, "the repair must be the SAME event, redelivered"
    assert inbox.consume(repaired, handler).outcome is ConsumeOutcome.APPLIED
    assert len(handler.applied) == 1
    store.close()
