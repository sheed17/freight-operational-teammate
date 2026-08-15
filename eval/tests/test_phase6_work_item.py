"""P6 M1 — the Work Item and structurally accountable human ownership, attacked.

The battery is organised by RISK, not by taxonomy. Each section is a way this mechanism could be
wrong in production:

    the transition table lies      the implementation and §14 disagree             (AC-MACH-000)
    a legal transition is wrong    a guard admits what it should refuse       (AC-MACH-101..114)
    an illegal one is admitted     an omitted (state, trigger) pair moves the machine      (GR-1)
    ownership is prose             an owner nobody recorded, or nobody at all       (I1, M-35)
    closure by inference           a decision_ref that references nothing        (I11, GR-14, K-1)
    reopening rewrites history     the prior closure is not byte-identical afterwards      (GR-12)
    terminal is not terminal       a CANCELLED item transitions                       (point 12)
    two writers, one truth         a stale version silently overwrites                     (GR-3)
    redelivery acts twice          a duplicate trigger is not a no-op                      (GR-4)
    tenants leak                   a T_B trigger moves a T_A machine                       [C-1]
    the age is a sweep             WI-10 escalates without a durable timer fired            (§14)
    production wakes up            an effect-capable module enters the import closure     (M-27)

`state_digest` is what makes "no-op" a measurement rather than a claim: every no-op case asserts the
digest is byte-identical across the second delivery.

### THIS IS THE IMPLEMENTING SESSION'S BATTERY, NOT AN INDEPENDENT REVIEW.
"""

from __future__ import annotations

import ast
import re
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase6_kit import (  # noqa: E402
    T_A,
    T_B,
    Clock,
    a_fired_age_timer,
    a_human,
    a_human_decision,
    an_item,
    machine,
    make_store,
    outbox_events,
    security_rows,
    state_digest,
)

from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.event_envelope import EventEnvelope, format_instant  # noqa: E402
from freight_recon.event_inbox import ConsumeOutcome  # noqa: E402
from freight_recon.migrations.phase6_work_items import (  # noqa: E402
    AUTHORITY_ROLES,
    NON_HUMAN_IDENTITIES,
    P6_TRIGGERS,
    TERMINAL_WORK_ITEM_STATES,
    WORK_ITEM_STATES,
    phase6_readiness_problems,
)
from freight_recon.work_item import (  # noqa: E402
    AGE_THRESHOLD_TIMER_KIND,
    AGGREGATE_TYPE,
    HUMAN_DECISION_EVENTS,
    K1_HUMAN_DECISION_EVENT_NAMES,
    K1_NAMES_NOT_YET_CANONICAL,
    PRECEDENCE,
    TRANSITIONS,
    TRANSITIONS_BY_ID,
    AuthorityRefused,
    DecisionRefUnresolvable,
    FailureDisposition,
    GuardNotSatisfied,
    IllegalTransition,
    OwnerAfter,
    OwnershipRefused,
    Trigger,
    UnknownWorkItem,
    VersionConflict,
    WorkItemState,
    human_authority,
    legal_transitions,
    offboard_human,
    open_work_owned_by,
    record_human_authority,
    resolve_decision_ref,
)

MACHINE_SPEC = ROOT / "docs/specifications/state-machines/01-work-item.machine.md"
REGISTRY_SPEC = ROOT / "docs/specifications/state-machines/registry.md"

SYS = {"actor_type": "system", "actor_id": "work-service"}
HUMAN = {"actor_type": "human", "actor_id": "dispatcher-dana"}


# =============================================================================== A. AC-MACH-000
# The structural case: the implementation's declarative table, enumerated and compared to the
# specification by EXACT SET EQUALITY of transition identifiers. A count match with different
# members MUST fail.

def _spec_rows() -> dict[str, dict[str, str]]:
    """Parse §14's transition table out of the machine file. Discovered, never transcribed.

    ### THE `\\|` ESCAPE IS THE WHOLE DIFFICULTY, AND GETTING IT WRONG SHIFTS EVERY COLUMN. §14
    writes an alternation inside a cell as `S\\|X`; a naive split on `|` turns that into two cells
    and every column after it is read as the one to its right — so `WI-6`'s Event cell would be
    compared against its Guards cell and the mismatch would look like a specification disagreement
    rather than a parser bug. Split on an UNESCAPED pipe only.
    """
    rows: dict[str, dict[str, str]] = {}
    in_table = False
    for line in MACHINE_SPEC.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 14."):
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 8 or not cells[0].startswith("**WI-"):
            continue
        identifier = cells[0].strip("*").strip()
        rows[identifier] = {
            "transition": cells[1], "trig": cells[2], "guards": cells[3],
            "writes": cells[4], "event": cells[5], "owner_after": cells[6], "test": cells[7],
        }
    return rows


def test_the_spec_parser_is_not_vacuous():
    """### THE DENOMINATOR, PRINTED. A parser that found nothing would make every comparison below
    pass over an empty set — CLAUDE.md §9's exact failure. Fourteen is the number
    `foundational-machine-acceptance.md` publishes for M1, so this asserts the number the
    specification's own coverage table asserts, not the number the parser happened to reach."""
    rows = _spec_rows()
    assert len(rows) == 14, f"parsed {len(rows)} §14 rows, expected 14: {sorted(rows)}"
    assert all(v["event"] for v in rows.values()), "a parsed row has an empty Event cell"


def test_ac_mach_000_transition_identifiers_are_a_bijection_with_the_specification():
    """### EXACT SET EQUALITY, NOT A COUNT. A transition in §14 with no row here, or a row here with
    no §14 entry, fails the build. `foundational-machine-acceptance.md`: *"The oracle is EXACT SET
    EQUALITY of transition identifiers, not a count. A count match with different members MUST
    fail."*"""
    implemented = {row.id for row in TRANSITIONS}
    declared = set(_spec_rows())
    assert implemented == declared, (
        f"§14 and the implementation disagree. Only in the spec: {sorted(declared - implemented)}; "
        f"only in the implementation: {sorted(implemented - declared)}"
    )


def test_ac_mach_000_the_oracle_is_a_set_comparison_and_a_substitution_fails_it():
    """A POSITIVE CONTROL for the oracle above. If it were a count, a same-count substitution would
    pass — so one is performed here and the comparison is asserted to reject it."""
    implemented = {row.id for row in TRANSITIONS}
    substituted = (implemented - {"WI-7"}) | {"WI-99"}
    assert len(substituted) == len(implemented)
    assert substituted != set(_spec_rows()), (
        "a same-count substitution compared EQUAL to the specification — the oracle is counting"
    )


@pytest.mark.parametrize("identifier", sorted(_spec_rows()))
def test_ac_mach_000_each_row_agrees_with_its_specification_row(identifier):
    """From-states, to-state, trigger types and event name, per row, against §14's own cells."""
    spec = _spec_rows()[identifier]
    row = TRANSITIONS_BY_ID[identifier]

    declared_types = {t for t in re.split(r"[\\|]+", spec["trig"]) if t.strip()}
    assert set(row.trigger_types) == declared_types, (
        f"{identifier}: trigger types {sorted(row.trigger_types)} != §14's {sorted(declared_types)}"
    )

    event_cell = spec["event"].replace("`", "")
    if row.is_delegation:
        assert event_cell.startswith("DELEGATES_TO:"), (
            f"{identifier} is modelled as a delegation and §14 does not declare it one"
        )
        for target in row.delegates_to:
            assert target in event_cell, f"{identifier} delegates to {target}, §14 does not say so"
        return
    assert row.event_name is not None and row.event_name in event_cell, (
        f"{identifier} emits {row.event_name!r}; §14's Event cell is {event_cell!r}"
    )

    to_cell = spec["transition"]
    if row.creates:
        assert to_cell.startswith("—"), f"{identifier} is the creation row and §14 disagrees"
    else:
        assert row.to_state is not None and row.to_state.value in to_cell, (
            f"{identifier} goes to {row.to_state}; §14 says {to_cell!r}"
        )
    for state in row.from_states:
        # Delegation-widened from-states are proven separately; §14's own cell need not list them.
        if state is WorkItemState.ESCALATED and identifier in TRANSITIONS_BY_ID["WI-14"].delegates_to:
            continue
        assert state.value in to_cell or "any non-terminal" in to_cell, (
            f"{identifier} accepts {state.value}; §14's From cell is {to_cell!r}"
        )


def test_wi_14_delegation_is_derived_and_not_hand_copied():
    """WI-14 resolves BY TARGET STATE. Its five targets must accept ESCALATED, and nothing else may
    have acquired it — a delegation applied by hand drifts silently because both halves stay
    internally consistent."""
    delegation = TRANSITIONS_BY_ID["WI-14"]
    assert delegation.delegates_to == ("WI-5", "WI-6", "WI-7", "WI-3", "WI-12")
    accepting = {
        row.id for row in TRANSITIONS
        if not row.is_delegation and WorkItemState.ESCALATED in row.from_states
    }
    # WI-11 is ESCALATED natively — §14 makes it the ONE way out of an escalation by reassignment,
    # and it is not a delegation target. WI-12 already accepts every non-terminal state including
    # ESCALATED on its own row, so WI-14 naming it restates rather than widens. WI-10's from-set
    # deliberately excludes ESCALATED: an already-escalated item does not re-escalate on age.
    assert accepting == {"WI-3", "WI-5", "WI-6", "WI-7", "WI-11", "WI-12"}, (
        f"ESCALATED is accepted by {sorted(accepting)}; WI-14 delegates to "
        f"{sorted(delegation.delegates_to)} and WI-11 owns it natively"
    )
    assert set(delegation.delegates_to) <= accepting
    assert "WI-10" not in accepting, "an escalated item re-escalating on age is not in §14"


def test_the_state_set_is_the_registrys():
    """§4's canonical state registry for M1, exactly. A local synonym is a defective machine."""
    line = next(
        raw for raw in REGISTRY_SPEC.read_text(encoding="utf-8").splitlines()
        if raw.startswith("`OPEN` `(R)` · `IN_PROGRESS`")
    )
    declared = {token.strip("`") for token in line.split()
                if re.fullmatch(r"`[A-Z_]+`", token)}
    assert declared, "the §4 state line parsed to nothing"
    assert declared == set(WORK_ITEM_STATES), (
        f"machine states {sorted(WORK_ITEM_STATES)} != registry §4's {sorted(declared)}"
    )
    assert set(TERMINAL_WORK_ITEM_STATES) == {"CLOSED", "CANCELLED"}


def test_every_emitted_event_is_a_canonical_contract_produced_by_that_transition():
    """The implementation may not emit a name the event registry does not attribute to it."""
    checked = 0
    for row in TRANSITIONS:
        if row.event_name is None:
            continue
        contract = CONTRACTS.get(row.event_name)
        assert contract is not None, f"{row.id} emits {row.event_name!r}, not a canonical contract"
        assert row.id in contract.producers, (
            f"{row.event_name} is produced by {list(contract.producers)}; {row.id} is not among "
            f"them. An event whose producer id names the wrong transition is a fact about a "
            f"transition that did not happen."
        )
        assert contract.aggregate_type == AGGREGATE_TYPE
        checked += 1
    assert checked == 13, f"checked {checked} emitting rows, expected 13 (14 minus the delegation)"


def test_ownership_moves_on_exactly_three_transitions():
    """### THE UNIT'S CENTRAL STRUCTURAL CLAIM. Twelve of the fourteen rows say `unchanged`; a
    transition that moved the owner as a side effect of unrelated progress is how an obligation ends
    up owned by whoever happened to trigger it."""
    moving = {row.id for row in TRANSITIONS if row.owner_after is not OwnerAfter.UNCHANGED}
    assert moving == {"WI-1", "WI-11", "WI-13"}, (
        f"ownership moves on {sorted(moving)}; §14's Owner-after column names exactly WI-1 "
        f"(the assigned owner), WI-11 (the new owner) and WI-13 (the reopening actor's assignee)"
    )


def test_precedence_covers_every_executable_transition():
    """§16's precedence is data. A row missing from it would raise on the day two rows tie."""
    executable = {row.id for row in TRANSITIONS if not row.is_delegation and not row.creates}
    assert set(PRECEDENCE) == executable, (
        f"§16 precedence covers {sorted(PRECEDENCE)}, executable rows are {sorted(executable)}"
    )
    assert PRECEDENCE[0] == "WI-12" and PRECEDENCE[1] == "WI-3", (
        "§16: cancellation > closure > block > await > advance"
    )


def test_wi_4_and_wi_5_are_total_and_mutually_exclusive_over_their_domain():
    """One trigger, two rows, discriminated by disposition — never by precedence. Every point in the
    (disposition, retries) domain must select exactly one, or a permanent failure could be admitted
    as a retryable one and the item would sit IN_PROGRESS forever."""
    from freight_recon.work_item import WorkItemMachine  # local: the guard body is what is probed
    assert legal_transitions(WorkItemState.IN_PROGRESS, Trigger.PIPELINE_FAILED) != ()
    assert {r.id for r in legal_transitions(WorkItemState.IN_PROGRESS, Trigger.PIPELINE_FAILED)} == \
        {"WI-4", "WI-5"}
    assert WorkItemMachine is not None


@pytest.mark.parametrize(
    "disposition,retries,expected",
    [
        (FailureDisposition.TRANSIENT, 2, "WI-4"),
        (FailureDisposition.TRANSIENT, 0, "WI-5"),
        (FailureDisposition.PERMANENT, 2, "WI-5"),
        (FailureDisposition.PERMANENT, 0, "WI-5"),
    ],
)
def test_pipeline_failed_selects_exactly_one_row(tmp_path, disposition, retries, expected):
    store = make_store(tmp_path, name=f"{disposition.value}-{retries}.db")
    m = machine(store)
    a_human(store)
    an_item(m)
    m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)
    result = m.apply(
        "wi-4471-billing", Trigger.PIPELINE_FAILED, **SYS,
        disposition=disposition, retries_remain=retries, reason="carrier portal 503",
    )
    assert result.transition_id == expected
    store.close()


# ==================================================================== B. the legal transitions
# AC-MACH-101..114: every legal transition succeeds under its EXACT guards.

def _open_item(store, m, clock):
    a_human(store, clock=clock)
    return an_item(m)


def test_ac_mach_101_creation_assigns_an_owner(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    result = _open_item(store, m, clock)
    assert result.transition_id == "WI-1"
    assert result.work_item.state is WorkItemState.OPEN
    assert result.work_item.version == 1 and result.work_item.phase_seq == 1
    assert result.owner_after == "dispatcher-dana"
    events = outbox_events(store)
    assert [e["event_name"] for e in events] == ["WorkItemCreated"]
    assert events[0]["producer_transition_id"] == "WI-1"
    store.close()


def test_ac_mach_102_pipeline_started_advances(tmp_path):
    store = make_store(tmp_path)
    m = machine(store)
    a_human(store)
    an_item(m)
    result = m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)
    assert (result.transition_id, result.to_state) == ("WI-2", WorkItemState.IN_PROGRESS)
    assert result.work_item.version == 2
    store.close()


def test_ac_mach_103_closure_needs_a_resolvable_decision_and_a_satisfied_obligation(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)
    decision = a_human_decision(store, clock=clock)
    result = m.apply(
        "wi-4471-billing", Trigger.PIPELINE_CLOSED, **SYS,
        obligation_satisfied=True, decision_ref=decision, decision_ref_kind="AUDIT_EVENT",
    )
    assert (result.transition_id, result.to_state) == ("WI-3", WorkItemState.CLOSED)
    assert result.work_item.closure_decision_ref == decision
    closed = [e for e in outbox_events(store) if e["event_name"] == "WorkItemClosed"]
    assert len(closed) == 1
    store.close()


def test_ac_mach_103d_a_finishing_pipeline_does_not_auto_close_the_item(tmp_path):
    """### ACCEPTANCE (d), AND THE MOST EXPENSIVE THING THIS MACHINE REFUSES TO GUESS.
    *Billed is not paid.* A `PipelineClosed` for an unmet obligation must leave the item
    IN_PROGRESS — and must emit NOTHING, because a legal trigger whose guard is false is not an
    illegal transition."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)
    decision = a_human_decision(store, clock=clock)
    before = state_digest(store)
    with pytest.raises(GuardNotSatisfied) as caught:
        m.apply(
            "wi-4471-billing", Trigger.PIPELINE_CLOSED, **SYS,
            obligation_satisfied=False, decision_ref=decision, decision_ref_kind="AUDIT_EVENT",
        )
    assert "obligation_satisfied" in str(caught.value)
    assert state_digest(store) == before, "a refused closure changed durable state"
    assert m.require("wi-4471-billing").state is WorkItemState.IN_PROGRESS
    assert not security_rows(store), (
        "an unmet guard produced a security event. A legal trigger whose precondition is false is "
        "not an attack, and filing it as one teaches operators to ignore the real ones."
    )
    store.close()


def test_ac_mach_105_permanent_failure_blocks_and_names_a_reason(tmp_path):
    store = make_store(tmp_path)
    m = machine(store)
    a_human(store)
    an_item(m)
    m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)
    result = m.apply(
        "wi-4471-billing", Trigger.PIPELINE_FAILED, **SYS,
        disposition=FailureDisposition.PERMANENT, retries_remain=0, reason="POD unobtainable",
    )
    assert (result.transition_id, result.to_state) == ("WI-5", WorkItemState.BLOCKED)
    assert result.work_item.blocker_ref == "POD unobtainable"
    assert result.owner_after == "dispatcher-dana", "a blocked item still has its owner"
    store.close()


def test_ac_mach_106_conflict_blocks_from_open(tmp_path):
    store = make_store(tmp_path)
    m = machine(store)
    a_human(store)
    an_item(m)
    result = m.apply("wi-4471-billing", Trigger.CONFLICT_RAISED, **SYS,
                     reason="rate conflicts with the confirmed quote")
    assert (result.transition_id, result.to_state) == ("WI-6", WorkItemState.BLOCKED)
    store.close()


def test_ac_mach_108_unblock_requires_consistent_evidence_and_no_open_conflict(tmp_path):
    store = make_store(tmp_path)
    m = machine(store)
    a_human(store)
    an_item(m)
    m.apply("wi-4471-billing", Trigger.EVIDENCE_MISSING, **SYS, reason="no POD")
    with pytest.raises(GuardNotSatisfied):
        m.apply("wi-4471-billing", Trigger.BLOCKER_CLEARED, **SYS,
                evidence_condition="stale", open_conflict=False)
    with pytest.raises(GuardNotSatisfied) as caught:
        m.apply("wi-4471-billing", Trigger.BLOCKER_CLEARED, **SYS,
                evidence_condition="consistent")
    assert "open_conflict" in str(caught.value), (
        "an unstated conflict was read as no conflict — GR-10 fails CLOSED"
    )
    result = m.apply("wi-4471-billing", Trigger.BLOCKER_CLEARED, **SYS,
                     evidence_condition="consistent", open_conflict=False)
    assert (result.transition_id, result.to_state) == ("WI-8", WorkItemState.IN_PROGRESS)
    assert result.work_item.blocker_ref is None
    store.close()


def test_ac_mach_107_and_109_await_then_resume_on_a_human_decision(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    awaiting = m.apply("wi-4471-billing", Trigger.HUMAN_DECISION_REQUIRED, **SYS,
                       question="short-pay: accept or dispute?")
    assert (awaiting.transition_id, awaiting.to_state) == ("WI-7", WorkItemState.AWAITING_HUMAN)
    decision = a_human_decision(store, clock=clock)
    resumed = m.apply("wi-4471-billing", Trigger.HUMAN_DECIDED, **HUMAN,
                      decision_ref=decision, decision_ref_kind="AUDIT_EVENT")
    assert (resumed.transition_id, resumed.to_state) == ("WI-9", WorkItemState.IN_PROGRESS)
    store.close()


def test_ac_mach_110_escalation_rides_a_durable_timer(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    timer = a_fired_age_timer(store, work_item_id="wi-4471-billing", clock=clock)
    result = m.apply("wi-4471-billing", Trigger.AGE_THRESHOLD_CROSSED,
                     actor_type="system", actor_id="timer-relay", timer_id=timer)
    assert (result.transition_id, result.to_state) == ("WI-10", WorkItemState.ESCALATED)
    assert result.work_item.escalation_at is not None
    store.close()


def test_wi_10_refuses_every_way_of_escalating_without_a_fired_timer(tmp_path):
    """### §14 SAYS "(durable timer, not a sweep)" AND THIS IS WHERE THAT STOPS BEING A PARENTHESIS.

    The mutation battery caught the gap: `test_ac_mach_110` asserts only the happy path, so removing
    the `state == FIRED` check or the `timer_id` requirement left it green — the sweep could come
    back and no test would notice. Each refusal below is a distinct way a caller could escalate an
    obligation on evidence that is not a fired deadline.
    """
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m, work_item_id="wi-a")
    an_item(m, work_item_id="wi-b")

    relay = {"actor_type": "system", "actor_id": "timer-relay"}
    cases = {
        "no timer at all": ({}, "durable timer, not a sweep"),
        "a blank timer id": ({"timer_id": "   "}, "durable timer, not a sweep"),
        "an unknown timer id": ({"timer_id": "no-such-timer"}, "no durable timer"),
    }
    a_fired_age_timer(store, work_item_id="wi-a", timer_id="t-scheduled", state="SCHEDULED",
                      clock=clock)
    cases["a SCHEDULED timer"] = ({"timer_id": "t-scheduled"}, "not FIRED")
    a_fired_age_timer(store, work_item_id="wi-b", timer_id="t-other-item", clock=clock)
    cases["another item's fired timer"] = ({"timer_id": "t-other-item"}, "not to this Work Item")
    a_fired_age_timer(store, work_item_id="wi-a", timer_id="t-wrong-kind",
                      kind="approval_deadline", clock=clock)
    cases["a fired timer of another kind"] = ({"timer_id": "t-wrong-kind"}, "AGE threshold")

    for description, (facts, expected) in cases.items():
        before = state_digest(store)
        with pytest.raises(GuardNotSatisfied) as caught:
            m.apply("wi-a", Trigger.AGE_THRESHOLD_CROSSED, **relay, **facts)
        assert expected in str(caught.value), f"{description}: {caught.value}"
        assert state_digest(store) == before, f"{description}: a refused escalation wrote something"
        assert m.require("wi-a").state is WorkItemState.OPEN

    # ...and the positive control, so the refusals above are not a machine that refuses everything.
    a_fired_age_timer(store, work_item_id="wi-a", timer_id="t-real", clock=clock)
    result = m.apply("wi-a", Trigger.AGE_THRESHOLD_CROSSED, **relay, timer_id="t-real")
    assert (result.transition_id, result.to_state) == ("WI-10", WorkItemState.ESCALATED)
    store.close()


def test_ac_mach_111_reassignment_moves_ownership_to_a_recorded_human(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, "dispatcher-dana", clock=clock)
    a_human(store, "night-lead-nia", clock=clock)
    an_item(m)
    timer = a_fired_age_timer(store, work_item_id="wi-4471-billing", clock=clock)
    m.apply("wi-4471-billing", Trigger.AGE_THRESHOLD_CROSSED,
            actor_type="system", actor_id="timer-relay", timer_id=timer)
    result = m.apply("wi-4471-billing", Trigger.OWNERSHIP_REASSIGNED,
                     actor_type="human", actor_id="dispatcher-dana", to_owner="night-lead-nia")
    assert (result.transition_id, result.to_state) == ("WI-11", WorkItemState.IN_PROGRESS)
    assert (result.owner_before, result.owner_after) == ("dispatcher-dana", "night-lead-nia")
    transferred = next(e for e in outbox_events(store) if e["event_name"] == "OwnershipTransferred")
    envelope = _envelope_for(store, transferred["event_id"])
    assert envelope.payload == {"from_owner": "dispatcher-dana", "to_owner": "night-lead-nia"}
    assert envelope.accountable_owner_id == "night-lead-nia"
    store.close()


def test_ac_mach_112_cancellation_from_any_non_terminal_state(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    decision = a_human_decision(store, clock=clock)
    result = m.apply("wi-4471-billing", Trigger.CANCELLATION_REQUESTED, **HUMAN,
                     decision_ref=decision, decision_ref_kind="AUDIT_EVENT")
    assert (result.transition_id, result.to_state) == ("WI-12", WorkItemState.CANCELLED)
    assert result.work_item.closure_decision_ref == decision
    store.close()


def test_ac_mach_114_an_escalated_item_can_still_block_await_close_and_cancel(tmp_path):
    """WI-14, resolved by TARGET STATE. Four separate items so each path is exercised for real."""
    clock = Clock()
    for index, (trigger, expected_row, expected_state, facts) in enumerate([
        (Trigger.EVIDENCE_MISSING, "WI-6", WorkItemState.BLOCKED, {"reason": "no POD"}),
        (Trigger.HUMAN_DECISION_REQUIRED, "WI-7", WorkItemState.AWAITING_HUMAN, {}),
        (Trigger.PIPELINE_FAILED, "WI-5", WorkItemState.BLOCKED,
         {"disposition": FailureDisposition.PERMANENT, "retries_remain": 0, "reason": "dead"}),
    ]):
        store = make_store(tmp_path, name=f"escalated-{index}.db")
        m = machine(store, clock=clock)
        a_human(store, clock=clock)
        an_item(m)
        timer = a_fired_age_timer(store, work_item_id="wi-4471-billing", clock=clock)
        m.apply("wi-4471-billing", Trigger.AGE_THRESHOLD_CROSSED,
                actor_type="system", actor_id="timer-relay", timer_id=timer)
        result = m.apply("wi-4471-billing", trigger, **SYS, **facts)
        assert (result.transition_id, result.to_state) == (expected_row, expected_state)
        store.close()


# ============================================================================ C. GR-1 — illegal
# The exhaustive (state × trigger) sweep. Every omitted pair raises, persists nothing, and emits
# `IllegalTransitionAttempted` to the audit backbone AND to security_events.

def _drive_to(store, m, clock, state: WorkItemState) -> str:
    """Reach `state` through legal transitions only. Returns the work item id."""
    a_human(store, "dispatcher-dana", clock=clock)
    a_human(store, "night-lead-nia", clock=clock)
    item = "wi-sweep"
    an_item(m, work_item_id=item)
    if state is WorkItemState.OPEN:
        return item
    if state is WorkItemState.ESCALATED:
        timer = a_fired_age_timer(store, work_item_id=item, clock=clock)
        m.apply(item, Trigger.AGE_THRESHOLD_CROSSED, actor_type="system",
                actor_id="timer-relay", timer_id=timer)
        return item
    if state is WorkItemState.AWAITING_HUMAN:
        m.apply(item, Trigger.HUMAN_DECISION_REQUIRED, **SYS)
        return item
    if state is WorkItemState.BLOCKED:
        m.apply(item, Trigger.EVIDENCE_MISSING, **SYS, reason="no POD")
        return item
    m.apply(item, Trigger.PIPELINE_STARTED, **SYS)
    if state is WorkItemState.IN_PROGRESS:
        return item
    decision = a_human_decision(store, clock=clock, seed=f"drive-{state.value}")
    if state is WorkItemState.CLOSED:
        m.apply(item, Trigger.PIPELINE_CLOSED, **SYS, obligation_satisfied=True,
                decision_ref=decision, decision_ref_kind="AUDIT_EVENT")
        return item
    if state is WorkItemState.CANCELLED:
        m.apply(item, Trigger.CANCELLATION_REQUESTED, **HUMAN,
                decision_ref=decision, decision_ref_kind="AUDIT_EVENT")
        return item
    raise AssertionError(state)


_ILLEGAL_PAIRS = [
    (state, trigger)
    for state in WorkItemState
    for trigger in Trigger
    if not legal_transitions(state, trigger)
]


def test_the_illegal_sweep_has_a_proven_population():
    """### A NEGATIVE ASSERTION NEEDS A PROVEN POPULATION. 7 states × 13 triggers = 91 pairs; the
    legal ones are subtracted and the remainder is what the sweep drives. If the legality lookup
    ever returned empty for everything, this count would jump and the number below would fail —
    which is the point of asserting the split rather than only the remainder."""
    total = len(WorkItemState) * len(Trigger)
    legal = [(s, t) for s in WorkItemState for t in Trigger if legal_transitions(s, t)]
    assert total == 91, total
    assert len(legal) == 27, sorted((s.value, t.value) for s, t in legal)
    assert len(_ILLEGAL_PAIRS) == total - len(legal) == 64


@pytest.mark.parametrize(
    "state,trigger", _ILLEGAL_PAIRS, ids=[f"{s.value}+{t.value}" for s, t in _ILLEGAL_PAIRS],
)
def test_gr1_every_omitted_pair_is_illegal_and_recorded(tmp_path, state, trigger):
    clock = Clock()
    store = make_store(tmp_path, name=f"illegal-{state.value}-{trigger.value}.db")
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, state)
    before_item = m.require(item)
    before_events = len(outbox_events(store))
    with pytest.raises(IllegalTransition):
        m.apply(item, trigger, **SYS, reason="probe", to_owner="night-lead-nia",
                decision_ref="x", decision_ref_kind="AUDIT_EVENT", obligation_satisfied=True,
                evidence_condition="consistent", open_conflict=False, assignee="night-lead-nia",
                disposition=FailureDisposition.PERMANENT, retries_remain=0, timer_id="t")
    after_item = m.require(item)
    assert (after_item.state, after_item.version, after_item.owner_id) == (
        before_item.state, before_item.version, before_item.owner_id
    ), "an illegal transition changed the row"
    names = [e["event_name"] for e in outbox_events(store)]
    assert len(names) == before_events + 1 and names[-1] == "IllegalTransitionAttempted"
    security = security_rows(store)
    assert len(security) == 1 and security[0]["event_type"] == "IllegalTransitionAttempted", (
        "GR-1 / [C-4] require the attempt on BOTH the audit and the security surface"
    )
    store.close()


def test_the_illegal_record_survives_the_refusal(tmp_path):
    """### THE DEFECT THIS UNIT SHIPPED AND ITS OWN BATTERY CAUGHT. The first implementation wrote
    the security record inside the transaction it was about to abandon, so the refusal worked and
    the evidence of it was rolled back with everything else — `security_events` was empty after a
    hostile attempt, and every test that only asserted the raise passed."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.OPEN)
    with pytest.raises(IllegalTransition):
        m.apply(item, Trigger.HUMAN_DECIDED, **HUMAN, decision_ref="x",
                decision_ref_kind="AUDIT_EVENT")
    assert security_rows(store), "the security record did not survive the refusal it records"
    store.close()


def test_a_terminal_item_refuses_everything(tmp_path):
    """`CANCELLED + anything → ILLEGAL`; `CLOSED + PipelineClosed → ILLEGAL` (already closed)."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.CANCELLED)
    for trigger in Trigger:
        assert legal_transitions(WorkItemState.CANCELLED, trigger) == (), trigger
    assert legal_transitions(WorkItemState.CLOSED, Trigger.PIPELINE_CLOSED) == ()
    assert m.require(item).state is WorkItemState.CANCELLED
    store.close()


def test_inactivity_never_closes_a_work_item(tmp_path):
    """I11. There is no trigger, no timer and no elapsed-time path to CLOSED — time passing is not
    an event, and the only way in is WI-3 with a resolvable decision."""
    closing = [row.id for row in TRANSITIONS if row.to_state is WorkItemState.CLOSED]
    assert closing == ["WI-3"], closing
    assert TRANSITIONS_BY_ID["WI-3"].triggers == (Trigger.PIPELINE_CLOSED,)
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.IN_PROGRESS)
    before = state_digest(store)
    clock.advance(days=400)
    assert m.require(item).state is WorkItemState.IN_PROGRESS
    assert state_digest(store) == before, "time alone changed durable state"
    store.close()


# ============================================================================== D. ownership (I1)

def test_creation_without_a_recorded_owner_fails_and_writes_nothing(tmp_path):
    store = make_store(tmp_path)
    m = machine(store)
    before = state_digest(store)
    with pytest.raises(OwnershipRefused) as caught:
        an_item(m, owner_id="dispatcher-dana")
    assert "not a recorded human" in str(caught.value)
    assert m.get("wi-4471-billing") is None
    assert state_digest(store) == before, "a refused creation left a trace"
    store.close()


@pytest.mark.parametrize("owner", ["", "   ", "system", "SYSTEM", "model", "unassigned"])
def test_creation_refuses_a_blank_or_non_human_owner(tmp_path, owner):
    """*"Never null. Never 'the system.'"* — M-35. Refused at the API AND unwritable at the
    database, so the two cannot drift into disagreeing."""
    store = make_store(tmp_path, name=f"owner-{owner.strip() or 'blank'}.db")
    m = machine(store)
    with pytest.raises(OwnershipRefused):
        an_item(m, owner_id=owner)
    store.close()


@pytest.mark.parametrize("identity", sorted(NON_HUMAN_IDENTITIES))
def test_a_non_human_identity_cannot_be_recorded_as_an_authority(tmp_path, identity):
    store = make_store(tmp_path, name=f"identity-{identity}.db")
    with pytest.raises(AuthorityRefused):
        record_human_authority(
            store.conn, tenant=T_A, human_id=identity, display_name=identity,
            authority_role="AUTHORIZED_HUMAN", recorded_by="founder-sam",
        )
    store.close()


def test_only_a_human_may_record_an_authority(tmp_path):
    """### THE TRANSITIVE HALF. If a model could record a human's authority, the model would be
    choosing who may own work, and rule 13 would be enforced against a roster the model wrote."""
    store = make_store(tmp_path)
    for kind in ("model", "system", "detector", ""):
        with pytest.raises(AuthorityRefused):
            record_human_authority(
                store.conn, tenant=T_A, human_id="dispatcher-dana", display_name="Dana",
                authority_role="AUTHORIZED_HUMAN", recorded_by="a-model", recorded_by_kind=kind,
            )
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
            " recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,?,?,?,?,?)",
            (T_A, "dispatcher-dana", "Dana", "AUTHORIZED_HUMAN", "ACTIVE", "2026-08-14T09:00:00.000Z",
             "gpt", "model"),
        )
    store.close()


@pytest.mark.parametrize("role", ["DETECTOR", "MODEL", "AGENT", "OPERATOR", ""])
def test_only_section_7s_two_human_roles_are_recordable(tmp_path, role):
    """§7's other rows — Automated detector, Agent/model — are not roles a human holds, and neither
    may own work: a detector may engage a brake and never release one; a model may emit a
    ProposedIntent and nothing else."""
    store = make_store(tmp_path, name=f"role-{role or 'blank'}.db")
    with pytest.raises(AuthorityRefused):
        record_human_authority(
            store.conn, tenant=T_A, human_id="dispatcher-dana", display_name="Dana",
            authority_role=role, recorded_by="founder-sam",
        )
    assert set(AUTHORITY_ROLES) == {"POLICY_OWNER", "AUTHORIZED_HUMAN"}
    store.close()


def test_an_offboarded_human_cannot_be_given_work(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, "leaver-lee", clock=clock)
    offboard_human(store.conn, tenant=T_A, human_id="leaver-lee", offboarded_by="founder-sam",
                   now=clock())
    with pytest.raises(OwnershipRefused) as caught:
        an_item(m, owner_id="leaver-lee")
    assert "OFFBOARDED" in str(caught.value)
    store.close()


def test_offboarding_refuses_while_open_work_is_owned_and_names_it(tmp_path):
    """### POINT 36'S FAIL-CLOSED HALF. The ownerless state is not detected after the fact, it is
    made unreachable through the supported path — and the refusal NAMES the items so the operator
    reassigns rather than being told 'no'."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, "leaver-lee", clock=clock)
    a_human(store, "night-lead-nia", clock=clock)
    an_item(m, work_item_id="wi-a", owner_id="leaver-lee")
    an_item(m, work_item_id="wi-b", owner_id="leaver-lee")
    with pytest.raises(OwnershipRefused) as caught:
        offboard_human(store.conn, tenant=T_A, human_id="leaver-lee",
                       offboarded_by="founder-sam", now=clock())
    assert "wi-a" in str(caught.value) and "wi-b" in str(caught.value)
    assert human_authority(store.conn, tenant=T_A, human_id="leaver-lee").is_active

    for item in ("wi-a", "wi-b"):
        timer = a_fired_age_timer(store, work_item_id=item, timer_id=f"t-{item}", clock=clock)
        m.apply(item, Trigger.AGE_THRESHOLD_CROSSED, actor_type="system",
                actor_id="timer-relay", timer_id=timer)
        m.apply(item, Trigger.OWNERSHIP_REASSIGNED, actor_type="human", actor_id="night-lead-nia",
                to_owner="night-lead-nia")
    assert open_work_owned_by(store.conn, tenant=T_A, owner_id="leaver-lee") == []
    retired = offboard_human(store.conn, tenant=T_A, human_id="leaver-lee",
                             offboarded_by="founder-sam", now=clock())
    assert not retired.is_active and retired.offboarded_at is not None
    store.close()


def test_no_transition_leaves_a_work_item_ownerless(tmp_path):
    """`test_no_ownerless_work_item_can_exist` — driven over EVERY reachable state, with the owner
    re-resolved against the roster afterwards rather than merely asserted non-empty."""
    clock = Clock()
    for state in WorkItemState:
        store = make_store(tmp_path, name=f"ownerless-{state.value}.db")
        m = machine(store, clock=clock)
        item = _drive_to(store, m, clock, state)
        row = m.require(item)
        assert row.owner_id, f"{state.value}: the item has no owner"
        authority = human_authority(store.conn, tenant=T_A, human_id=row.owner_id)
        assert authority is not None and authority.is_active, (
            f"{state.value}: owner {row.owner_id!r} is not a recorded active human — a non-empty "
            f"string is not an accountable owner"
        )
        store.close()


def test_the_ownerless_detector_runs_over_a_proven_population(tmp_path):
    """A Sev-0 query that returns nothing over an empty table is a green check that parsed nothing."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    for index in range(3):
        an_item(m, work_item_id=f"wi-{index}")
    assert len(open_work_owned_by(store.conn, tenant=T_A, owner_id="dispatcher-dana")) == 3
    assert m.ownerless() == []
    # Now break it the only way the database permits — retire the human around the API, which is
    # exactly the residual P6-D3 records — and prove the detector SEES it.
    store.conn.execute(
        "UPDATE tenant_humans SET state='OFFBOARDED', offboarded_at=? WHERE tenant=? AND human_id=?",
        (format_instant(clock()), T_A, "dispatcher-dana"))
    store.conn.commit()
    assert m.ownerless() == ["wi-0", "wi-1", "wi-2"], (
        "the ownerless detector cannot fail — it did not notice three items whose owner had left"
    )
    store.close()


def test_reassignment_to_an_unrecorded_or_identical_human_refuses(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    timer = a_fired_age_timer(store, work_item_id="wi-4471-billing", clock=clock)
    m.apply("wi-4471-billing", Trigger.AGE_THRESHOLD_CROSSED, actor_type="system",
            actor_id="timer-relay", timer_id=timer)
    with pytest.raises(GuardNotSatisfied) as caught:
        m.apply("wi-4471-billing", Trigger.OWNERSHIP_REASSIGNED, **HUMAN, to_owner="ghost-greg")
    assert "not a recorded human" in str(caught.value)
    with pytest.raises(GuardNotSatisfied):
        m.apply("wi-4471-billing", Trigger.OWNERSHIP_REASSIGNED, **HUMAN, to_owner="")
    with pytest.raises(GuardNotSatisfied) as caught:
        m.apply("wi-4471-billing", Trigger.OWNERSHIP_REASSIGNED, **HUMAN,
                to_owner="dispatcher-dana")
    assert "current owner" in str(caught.value)
    store.close()


def test_a_model_can_never_drive_this_machine(tmp_path):
    """C-6 / GR-7. A model may propose that work is needed; it may never own, advance, close or
    cancel an obligation — at ANY confidence, because confidence is not a guard input (GR-8)."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    with pytest.raises(AuthorityRefused):
        an_item(m, actor_type="model", actor_id="extractor-v3")
    an_item(m)
    for trigger in Trigger:
        with pytest.raises(AuthorityRefused):
            m.apply("wi-4471-billing", trigger, actor_type="model", actor_id="extractor-v3")
    assert not security_rows(store), "a refused actor produced a spurious M1 security event"
    store.close()


def test_a_system_actor_cannot_perform_a_human_transition(tmp_path):
    """§7: automation may narrow authority and never broaden it. WI-9/11/12/13 are the four places a
    human changes what the business owes, and each is checked against the RECORDED roster."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    decision = a_human_decision(store, clock=clock)
    with pytest.raises(GuardNotSatisfied) as caught:
        m.apply("wi-4471-billing", Trigger.CANCELLATION_REQUESTED, **SYS,
                decision_ref=decision, decision_ref_kind="AUDIT_EVENT")
    assert "H transition" in str(caught.value)
    with pytest.raises(GuardNotSatisfied) as caught:
        m.apply("wi-4471-billing", Trigger.CANCELLATION_REQUESTED, actor_type="human",
                actor_id="ghost-greg", decision_ref=decision, decision_ref_kind="AUDIT_EVENT")
    assert "not a recorded human" in str(caught.value)
    store.close()


# ================================================================ E. closure and the decision_ref

def test_k1s_resolvable_set_is_non_vacuous_and_named():
    """### K-1 NAMES SIX EVENT TYPES AND ONE OF THEM IS NOT CANONICAL. The resolvable set is the
    intersection with the event registry, asserted by NAME so a silent shrink fails here rather than
    turning every closure into a refusal that looks like strictness."""
    assert HUMAN_DECISION_EVENTS == {
        "HumanDecided", "ApprovalGranted", "RealityEstablished", "CompensationApproved",
        "BrakeReleased",
    }, sorted(HUMAN_DECISION_EVENTS)
    assert K1_NAMES_NOT_YET_CANONICAL == ("HumanResolved",), (
        "K-1's canonical/non-canonical split moved. Debt P6-D1 records that `HumanResolved` is not "
        "among the 118 contracts and that M9 owns the determination, not this unit."
    )
    assert set(HUMAN_DECISION_EVENTS) < set(K1_HUMAN_DECISION_EVENT_NAMES)
    for name in HUMAN_DECISION_EVENTS:
        assert name in CONTRACTS


@pytest.mark.parametrize("trigger,extra", [
    (Trigger.PIPELINE_CLOSED, {"obligation_satisfied": True}),
    (Trigger.CANCELLATION_REQUESTED, {}),
])
def test_a_terminal_transition_without_a_decision_ref_is_refused(tmp_path, trigger, extra):
    clock = Clock()
    store = make_store(tmp_path, name=f"nodecision-{trigger.value}.db")
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.IN_PROGRESS)
    actor = SYS if trigger is Trigger.PIPELINE_CLOSED else HUMAN
    with pytest.raises(GuardNotSatisfied):
        m.apply(item, trigger, **actor, **extra)
    with pytest.raises(GuardNotSatisfied):
        m.apply(item, trigger, **actor, **extra, decision_ref="   ",
                decision_ref_kind="AUDIT_EVENT")
    assert m.require(item).state is WorkItemState.IN_PROGRESS
    store.close()


def test_closed_with_the_string_done_is_refused(tmp_path):
    """K-1's own worked example: *"the CHECK is not 'non-null' but 'resolves to an authenticated
    human decision event or an active rule id'."*"""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.IN_PROGRESS)
    with pytest.raises(GuardNotSatisfied) as caught:
        m.apply(item, Trigger.PIPELINE_CLOSED, **SYS, obligation_satisfied=True,
                decision_ref="done", decision_ref_kind="AUDIT_EVENT")
    assert "resolves to no canonical event" in str(caught.value)
    store.close()


@pytest.mark.parametrize("event_name,aggregate_type,aggregate_id,transition", [
    ("HumanDecided", AGGREGATE_TYPE, "wi-other", "WI-9"),
    ("RealityEstablished", "effect_grant", "eg-1", "EF-5"),
    ("CompensationApproved", "compensation", "cm-1", "CM-2"),
])
def test_a_system_emitted_human_decision_event_does_not_resolve(
    tmp_path, event_name, aggregate_type, aggregate_id, transition
):
    """### AUTHORITY LAUNDERING, REFUSED — AND THIS CHECK IS LOAD-BEARING, NOT REDUNDANT.

    Two of K-1's five resolvable types (`ApprovalGranted`, `BrakeReleased`) are `human_only` at the
    P5 contract layer, so the transport already refuses a machine-emitted one. **The other three are
    not**, so a `HumanDecided` / `RealityEstablished` / `CompensationApproved` recorded with
    `actor_type='system'` is a perfectly canonical event — and it would close a Work Item on a
    machine decision wearing a human decision's name (ER-11) if this resolver only checked the type.
    """
    clock = Clock()
    store = make_store(tmp_path, name=f"laundered-{event_name}.db")
    laundered = a_human_decision(
        store, clock=clock, event_name=event_name, actor_type="system",
        actor_id="auto-approver", seed=f"laundered-{event_name}", aggregate_type=aggregate_type,
        aggregate_id=aggregate_id, producer_transition_id=transition,
    )
    with pytest.raises(DecisionRefUnresolvable) as caught:
        resolve_decision_ref(store.conn, tenant=T_A, ref=laundered, kind="AUDIT_EVENT")
    assert "AUTHENTICATED HUMAN" in str(caught.value)
    store.close()


def test_the_two_human_only_decision_types_are_refused_upstream_by_p5(tmp_path):
    """The POSITIVE CONTROL for the case above: the upstream refusal is asserted to EXIST, so
    "P5 already covers those two" is a measured fact rather than a claim about somebody else's code.
    """
    from freight_recon.event_contracts import HUMAN_ONLY_EVENTS

    covered_upstream = HUMAN_DECISION_EVENTS & HUMAN_ONLY_EVENTS
    assert covered_upstream == {"ApprovalGranted", "BrakeReleased"}, sorted(covered_upstream)
    assert HUMAN_DECISION_EVENTS - HUMAN_ONLY_EVENTS == {
        "HumanDecided", "RealityEstablished", "CompensationApproved",
    }, "the set this resolver must defend on its own has changed"

    clock = Clock()
    store = make_store(tmp_path)
    with pytest.raises(Exception) as caught:
        a_human_decision(
            store, clock=clock, event_name="ApprovalGranted", actor_type="system",
            actor_id="auto-approver", seed="upstream", aggregate_type="approval",
            aggregate_id="ap-1", producer_transition_id="AP-2",
        )
    assert "actor_type=human" in str(caught.value)
    store.close()


def test_a_non_decision_event_does_not_resolve(tmp_path):
    """A `WorkItemCreated` is a system fact about an obligation existing, not a human deciding it is
    discharged. Closing on one would be closure by system convenience."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    created = an_item(m).event_id
    with pytest.raises(DecisionRefUnresolvable) as caught:
        resolve_decision_ref(store.conn, tenant=T_A, ref=created, kind="AUDIT_EVENT")
    assert "not one of K-1" in str(caught.value)
    store.close()


def test_a_rule_kind_decision_ref_fails_closed_today(tmp_path):
    """M12 does not exist yet. A stub that accepted any rule id would make 'closed by an active
    rule' true of rules that do not exist — refused, and the refusal says why (debt P6-D4)."""
    store = make_store(tmp_path)
    with pytest.raises(DecisionRefUnresolvable) as caught:
        resolve_decision_ref(store.conn, tenant=T_A, ref="rule-net-30", kind="RULE")
    assert "M12" in str(caught.value) and "not implemented yet" in str(caught.value)
    with pytest.raises(DecisionRefUnresolvable):
        resolve_decision_ref(store.conn, tenant=T_A, ref="x", kind="SOMETHING_ELSE")
    store.close()


# ==================================================================================== F. reopening

def test_reopening_preserves_the_prior_closure_event_byte_identically(tmp_path):
    """GR-12 / acceptance (e). The closure event is compared BYTE-for-byte before and after, via the
    stored canonical `ev_v1` bytes — not by re-reading a field and finding it unchanged."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    a_human(store, "night-lead-nia", clock=clock)
    item = "wi-4471-billing"
    an_item(m)
    m.apply(item, Trigger.PIPELINE_STARTED, **SYS)
    closure_decision = a_human_decision(store, clock=clock, seed="close")
    closed = m.apply(item, Trigger.PIPELINE_CLOSED, **SYS, obligation_satisfied=True,
                     decision_ref=closure_decision, decision_ref_kind="AUDIT_EVENT")
    before_bytes = _raw_envelope(store, closed.event_id)

    reopen_decision = a_human_decision(store, clock=clock, seed="reopen")
    reopened = m.apply(item, Trigger.REOPEN_REQUESTED, **HUMAN, decision_ref=reopen_decision,
                       decision_ref_kind="AUDIT_EVENT", assignee="night-lead-nia")

    assert (reopened.transition_id, reopened.to_state) == ("WI-13", WorkItemState.IN_PROGRESS)
    assert reopened.work_item.phase_seq == 2, "reopening must open a NEW phase"
    assert reopened.owner_after == "night-lead-nia"
    assert reopened.work_item.prior_closure_ref == closure_decision
    assert reopened.work_item.closure_decision_ref is None
    assert _raw_envelope(store, closed.event_id) == before_bytes, (
        "the prior closure event changed when the item was reopened — history was rewritten"
    )
    payload = _envelope_for(store, reopened.event_id).payload
    assert payload["prior_closure_ref"] == closure_decision and payload["phase_seq"] == 2
    store.close()


def test_reopening_requires_a_named_active_assignee(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.CLOSED)
    decision = a_human_decision(store, clock=clock, seed="reopen-2")
    with pytest.raises(GuardNotSatisfied) as caught:
        m.apply(item, Trigger.REOPEN_REQUESTED, **HUMAN, decision_ref=decision,
                decision_ref_kind="AUDIT_EVENT")
    assert "assignee" in str(caught.value)
    with pytest.raises(GuardNotSatisfied):
        m.apply(item, Trigger.REOPEN_REQUESTED, **HUMAN, decision_ref=decision,
                decision_ref_kind="AUDIT_EVENT", assignee="ghost-greg")
    assert m.require(item).state is WorkItemState.CLOSED
    store.close()


def test_a_cancelled_item_can_never_be_reopened(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.CANCELLED)
    decision = a_human_decision(store, clock=clock, seed="reopen-3")
    with pytest.raises(IllegalTransition):
        m.apply(item, Trigger.REOPEN_REQUESTED, **HUMAN, decision_ref=decision,
                decision_ref_kind="AUDIT_EVENT", assignee="night-lead-nia")
    store.close()


# ===================================================== G. the database refuses what the API refuses

def test_the_schema_is_ready_and_its_triggers_are_present(tmp_path):
    store = make_store(tmp_path)
    assert phase6_readiness_problems(store.conn) == []
    live = {r[0] for r in store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
    missing = sorted(set(P6_TRIGGERS) - live)
    assert not missing, f"P6 triggers missing from a fresh canonical database: {missing}"
    store.close()


def test_an_ownerless_row_is_unwritable_even_by_raw_sql(tmp_path):
    """### THE API REFUSES AND THE DATABASE REFUSES. Two independent mechanisms, because a rule that
    only one layer enforces is a rule the next caller can go around."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    for owner in (None, "", "   ", "system", "ghost-greg"):
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute(
                "UPDATE work_items SET owner_id = ?, version = version + 1 "
                " WHERE tenant = ? AND work_item_id = ?", (owner, T_A, "wi-4471-billing"))
        store.conn.rollback()
    assert m.require("wi-4471-billing").owner_id == "dispatcher-dana"
    store.close()


def test_the_version_counter_cannot_stand_still(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    for version_expression in ("version", "version + 2", "version - 1"):
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute(
                f"UPDATE work_items SET state='BLOCKED', version = {version_expression} "
                f" WHERE tenant = ? AND work_item_id = ?", (T_A, "wi-4471-billing"))
        store.conn.rollback()
    store.close()


def test_a_terminal_row_cannot_be_moved_by_raw_sql(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.CANCELLED)
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "UPDATE work_items SET state='OPEN', version=version+1 "
            " WHERE tenant=? AND work_item_id=?", (T_A, item))
    store.conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute("DELETE FROM work_items WHERE tenant=? AND work_item_id=?", (T_A, item))
    store.conn.rollback()
    store.close()


def test_a_closed_row_may_only_leave_through_a_new_phase(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.CLOSED)
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "UPDATE work_items SET state='IN_PROGRESS', version=version+1 "
            " WHERE tenant=? AND work_item_id=?", (T_A, item))
    store.conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "UPDATE work_items SET state='OPEN', version=version+1, phase_seq=phase_seq+1 "
            " WHERE tenant=? AND work_item_id=?", (T_A, item))
    store.conn.rollback()
    store.close()


def test_a_terminal_row_cannot_shed_its_decision_reference(tmp_path):
    """### TWO BARRIERS, AND THE SECOND ONE IS NOT DECORATION — THE MUTATION BATTERY PROVED IT.

    The table CHECK refuses a terminal row whose `closure_decision_ref` is NULL. Disabling the
    trigger left this case green, which is a MISS that says the trigger looks redundant. It is not:
    the CHECK sees NULL and nothing else, so **the blank string sails straight past it** —
    `closure_decision_ref=''` is a terminal Work Item closed by a value that references nothing,
    which is precisely the hole K-1 exists to close. That is the trigger's own job, and it is
    asserted here so the trigger can fail.
    """
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.IN_PROGRESS)
    # Barrier 1 — the table CHECK: a terminal row with a NULL reference.
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "UPDATE work_items SET state='CLOSED', version=version+1, closure_decision_ref=NULL "
            " WHERE tenant=? AND work_item_id=?", (T_A, item))
    store.conn.rollback()
    # Barrier 2 — the trigger: a terminal row with a BLANK reference, which the CHECK cannot see.
    for blank in ("", "   "):
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute(
                "UPDATE work_items SET state='CLOSED', version=version+1, "
                " closure_decision_ref=?, closure_decision_ref_kind='AUDIT_EVENT' "
                " WHERE tenant=? AND work_item_id=?", (blank, T_A, item))
        store.conn.rollback()
    # ...and the kind, which is a separate way to arrive terminal without a resolvable reference.
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "UPDATE work_items SET state='CANCELLED', version=version+1, "
            " closure_decision_ref='some-event', closure_decision_ref_kind=NULL "
            " WHERE tenant=? AND work_item_id=?", (T_A, item))
    store.conn.rollback()
    assert m.require(item).state is WorkItemState.IN_PROGRESS
    store.close()


def test_a_recorded_authority_is_append_only(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    a_human(store, clock=clock)
    for column, value in (("human_id", "someone-else"), ("recorded_by", "a-model"),
                          ("recorded_by_kind", "model"), ("recorded_at", "2020-01-01T00:00:00.000Z")):
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute(
                f"UPDATE tenant_humans SET {column} = ? WHERE tenant=? AND human_id=?",
                (value, T_A, "dispatcher-dana"))
        store.conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute("DELETE FROM tenant_humans WHERE tenant=? AND human_id=?",
                           (T_A, "dispatcher-dana"))
    store.conn.rollback()
    store.close()


# ================================================================================ H. concurrency

def test_a_stale_expected_version_fails_deterministically(tmp_path):
    """GR-3: zero rows ⇒ lost update ⇒ raise. Never a silent overwrite."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS, expected_version=1)
    with pytest.raises(VersionConflict):
        m.apply("wi-4471-billing", Trigger.PIPELINE_FAILED, **SYS, expected_version=1,
                disposition=FailureDisposition.PERMANENT, retries_remain=0, reason="stale")
    assert m.require("wi-4471-billing").state is WorkItemState.IN_PROGRESS
    store.close()


def test_two_writers_one_transition(tmp_path):
    """Two machines on two connections against ONE database. One wins by version; the loser sees
    zero rows and raises rather than clobbering."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    other_store = make_store(tmp_path)          # same path, second connection
    other = machine(other_store, clock=clock)

    first = m.require("wi-4471-billing")
    second = other.require("wi-4471-billing")
    assert first.version == second.version == 1

    m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS, expected_version=first.version)
    with pytest.raises(VersionConflict):
        other.apply("wi-4471-billing", Trigger.HUMAN_DECISION_REQUIRED, **SYS,
                    expected_version=second.version)
    final = m.require("wi-4471-billing")
    assert (final.state, final.version) == (WorkItemState.IN_PROGRESS, 2)
    other_store.close()
    store.close()


def test_the_occ_where_clause_carries_the_version_predicate(tmp_path):
    """### THE MUTATION BATTERY FOUND THIS GAP AND IT WAS REAL — TWICE, AND THE SECOND TIME TAUGHT
    MORE THAN THE FIRST.

    `test_two_writers_one_transition` passes `expected_version`, so it is satisfied by the PYTHON
    pre-check and never reaches the SQL. Removing `AND version = ?` from the UPDATE left it green.

    The first replacement was still not enough. It used a state-CHANGING interleaving, so the
    UPDATE's other predicate (`AND state = ?`) caught the mutant on its own — a MISS that proved the
    probe was weak, not that the code was safe. The interleaving here is a **self-loop** (WI-4,
    `IN_PROGRESS → IN_PROGRESS`): the state predicate cannot see it, and only the version predicate
    can.

    ### AND IT REQUIRES EXACTLY `VersionConflict`, NOT "SOME ERROR". The version trigger is a real
    second barrier and would abort the mutant with an `IntegrityError` — but a caller told to
    reload-and-retry (GR-3) gets a lost-update signal from the OCC layer, not a database constraint
    abort escaping through it. Accepting either would let the mutant pass while the failure mode
    silently got worse.
    """
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)

    other_store = make_store(tmp_path)
    other = machine(other_store, clock=clock)

    from freight_recon import work_item as module

    observed: dict[str, int] = {}
    real_require = module.WorkItemMachine.require

    def moving_require(self, work_item_id):                       # noqa: ANN001, ANN202
        item = real_require(self, work_item_id)
        if self is m and "done" not in observed:
            # The read has happened; now let the OTHER writer land a SELF-LOOP before this one
            # issues its UPDATE. `state` is identical on both sides; only `version` moved.
            observed["done"] = 1
            other.apply(work_item_id, Trigger.PIPELINE_FAILED, **SYS,
                        disposition=FailureDisposition.TRANSIENT, retries_remain=2,
                        reason="carrier portal 503")
        return item

    monkey = pytest.MonkeyPatch()
    monkey.setattr(module.WorkItemMachine, "require", moving_require)
    try:
        with pytest.raises(VersionConflict):
            m.apply("wi-4471-billing", Trigger.HUMAN_DECISION_REQUIRED, **SYS)
    finally:
        monkey.undo()
    assert observed.get("done") == 1, "the interleaving never happened — this case proved nothing"
    final = other.require("wi-4471-billing")
    assert (final.state, final.version) == (WorkItemState.IN_PROGRESS, 3), (
        "the stale writer overwrote the transition that actually won"
    )
    other_store.close()
    store.close()


def test_no_two_transitions_claim_one_aggregate_version(tmp_path):
    """The outbox's identity constraint, exercised through the machine: every M1 event sits at a
    distinct `(aggregate_id, aggregate_version)` because every transition advances the counter."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.CLOSED)
    versions = [(e["aggregate_id"], e["aggregate_version"]) for e in outbox_events(store)
                if e["aggregate_id"] == item]
    assert versions == sorted(versions) and len(versions) == len(set(versions)), versions
    assert len(versions) >= 3, versions
    store.close()


# ============================================================================== I. idempotency

def _trigger_envelope(store, *, seed: str, clock: Clock, tenant: str = T_A,
                      event_name: str = "PipelineClosed", aggregate_id: str = "pi-1",
                      producer_transition_id: str = "PL-14", actor_type: str = "system",
                      actor_id: str = "pipeline-service") -> EventEnvelope:
    from phase6_kit import deterministic_event_id, minimal_payload
    now = format_instant(clock())
    return EventEnvelope(
        event_id=deterministic_event_id(seed), event_name=event_name, event_version=1,
        occurred_at=now, recorded_at=now, tenant_id=tenant, aggregate_type="pipeline_instance",
        aggregate_id=aggregate_id, aggregate_version=1, causation_id=None,
        correlation_id=f"corr-{seed}", producer_component="pipeline",
        producer_transition_id=producer_transition_id, actor_type=actor_type, actor_id=actor_id,
        # Derived from the contract, not `{}`: a `PipelineStarted` with no `commit_key` is refused
        # by the real contract gate as REJECTED_MALFORMED, which would make a parking test pass for
        # the wrong reason. It did, on the first run.
        trace_id=f"trace-{seed}", payload=minimal_payload(event_name),
    )


def test_a_redelivered_trigger_is_a_no_op_and_the_digest_is_byte_identical(tmp_path):
    """GR-4 / M-24. The idempotency is P5's inbox, not a memory in this machine — and "no-op" is a
    measured digest, not an absence of assertions."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)
    decision = a_human_decision(store, clock=clock)
    envelope = _trigger_envelope(store, seed="closed-1", clock=clock)

    first = m.consume(envelope, work_item_id="wi-4471-billing", trigger=Trigger.PIPELINE_CLOSED,
                      obligation_satisfied=True, decision_ref=decision,
                      decision_ref_kind="AUDIT_EVENT")
    assert first.consume.outcome is ConsumeOutcome.APPLIED and first.moved
    assert m.require("wi-4471-billing").state is WorkItemState.CLOSED
    after_first = state_digest(store)

    second = m.consume(envelope, work_item_id="wi-4471-billing", trigger=Trigger.PIPELINE_CLOSED,
                       obligation_satisfied=True, decision_ref=decision,
                       decision_ref_kind="AUDIT_EVENT")
    assert second.consume.outcome is ConsumeOutcome.DUPLICATE_NOOP and not second.moved
    assert state_digest(store) == after_first, "a redelivery changed durable state"
    store.close()


def test_a_consumed_trigger_whose_guard_is_unsatisfied_is_consumed_once_and_changes_nothing(tmp_path):
    """### A REFUSAL IS A CONSUMPTION. If the handler raised, the inbox would roll back its own row
    and the transport would redeliver forever — an unmet obligation would become an infinite loop."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)
    decision = a_human_decision(store, clock=clock)
    envelope = _trigger_envelope(store, seed="closed-unmet", clock=clock)
    result = m.consume(envelope, work_item_id="wi-4471-billing", trigger=Trigger.PIPELINE_CLOSED,
                       obligation_satisfied=False, decision_ref=decision,
                       decision_ref_kind="AUDIT_EVENT")
    assert result.consume.outcome is ConsumeOutcome.APPLIED
    assert not result.moved and result.refusal_kind == "GUARD"
    assert m.require("wi-4471-billing").state is WorkItemState.IN_PROGRESS
    assert not security_rows(store)
    store.close()


def test_a_trigger_for_a_work_item_that_does_not_exist_yet_is_parked_not_looped(tmp_path):
    """### A LIVE DEFECT THIS UNIT SHIPPED AND FIXED. With no reference resolver the inbox had
    nothing to check, the handler raised `UnknownWorkItem`, the inbox rolled back its own row along
    with the failure, and the transport redelivered the same event **forever**.

    M-26 already had the answer: park it with its arrival order, its accountable human and a TTL;
    drain it in that order when the referent appears. So the parking is asserted, and so is the
    DRAIN — a park that never drains is a queue nobody empties.
    """
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    envelope = _trigger_envelope(store, seed="early-arrival", clock=clock,
                                 event_name="PipelineStarted", producer_transition_id="PL-1")

    parked = m.consume(envelope, work_item_id="wi-not-yet", trigger=Trigger.PIPELINE_STARTED,
                       accountable_owner_id="dispatcher-dana")
    assert parked.consume.outcome is ConsumeOutcome.PARKED_MISSING_AGGREGATE
    assert not parked.moved
    held = store.conn.execute(
        "SELECT * FROM pending_references WHERE tenant = ? ORDER BY arrival_sequence",
        (T_A,)).fetchall()
    assert len(held) == 1 and held[0]["park_state"] == "PARKED"
    assert held[0]["referenced_id"] == "wi-not-yet"
    assert held[0]["accountable_owner_id"] == "dispatcher-dana", (
        "M-26 parks an event WITH its accountable human; an unowned park is a queue nobody empties"
    )
    assert held[0]["expires_at"], "a park with no TTL is a place events go to be forgotten"

    # A redelivery while parked is counted, not re-run, and certainly not applied.
    again = m.consume(envelope, work_item_id="wi-not-yet", trigger=Trigger.PIPELINE_STARTED)
    assert again.consume.outcome is ConsumeOutcome.ALREADY_PARKED

    # ### AND ON TTL IT BECOMES AN OWNED PROBLEM, NOT A LOG LINE. This is the half that matters for
    # safety and it is the half that is complete: the event is never dropped, never retried forever,
    # and when its deadline passes it surfaces WITH the human accountable for it.
    #
    # ### WHAT IS *NOT* HERE, STATED RATHER THAN IMPLIED (debt P6-D6). P5's drain is keyed on the
    # APPLIED event's own aggregate, so a park on `work_item:X` drains when an event whose aggregate
    # IS `work_item:X` is consumed. Creating the item through WI-1 is an ORIGINATED act, not a
    # consumed one, so it does not itself drain the cohort. Draining on creation needs the parked
    # trigger's FACTS to travel with the event — `obligation_satisfied`, the failure disposition,
    # the block reason — and those are supplied by the producer, which is the Pipeline Instance.
    # Building a facts-carrying drain here would be building infrastructure the next unit owns.
    m.create(work_item_id="wi-not-yet", type="delivered_load_closure",
             owner_id="dispatcher-dana", actor_type="system", actor_id="work-service")
    clock.advance(days=30)
    overdue = m.consume(  # any consume pass; expiry is checked explicitly below
        _trigger_envelope(store, seed="unrelated", clock=clock, event_name="PipelineStarted",
                          producer_transition_id="PL-1", aggregate_id="pi-2"),
        work_item_id="wi-not-yet", trigger=Trigger.PIPELINE_STARTED)
    assert overdue.consume.outcome is ConsumeOutcome.APPLIED

    from freight_recon.event_inbox import DedupInbox

    box = DedupInbox(store.conn, tenant=T_A, consumer_id="m1-work-item", clock=clock,
                     reference_resolver=m.reference_resolver)
    expired = box.expire_overdue()
    assert len(expired) == 1, f"the parked event did not surface on TTL: {expired}"
    assert expired[0].accountable_owner_id == "dispatcher-dana", (
        "an expired park with no accountable human is exactly the silent drop M-26 forbids"
    )
    store.close()


def test_a_consumed_illegal_trigger_records_once_and_does_not_loop(tmp_path):
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.CLOSED)
    envelope = _trigger_envelope(store, seed="closed-again", clock=clock)
    first = m.consume(envelope, work_item_id=item, trigger=Trigger.PIPELINE_CLOSED,
                      obligation_satisfied=True)
    assert first.refusal_kind == "ILLEGAL" and not first.moved
    assert len(security_rows(store)) == 1
    after = state_digest(store)
    second = m.consume(envelope, work_item_id=item, trigger=Trigger.PIPELINE_CLOSED,
                       obligation_satisfied=True)
    assert second.consume.outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert len(security_rows(store)) == 1, "a redelivery wrote a second security record"
    assert state_digest(store) == after
    store.close()


# =========================================================================== J. tenant isolation

def test_a_tenant_b_trigger_never_moves_a_tenant_a_machine(tmp_path):
    """[C-1]. Every case in this battery runs one tenant; this one runs both, and asserts that the
    boundary is structural rather than checked."""
    clock = Clock()
    store_a = make_store(tmp_path, tenant=T_A, name="both.db")
    store_b = make_store(tmp_path, tenant=T_B, name="both.db")
    m_a = machine(store_a, tenant=T_A, clock=clock)
    m_b = machine(store_b, tenant=T_B, clock=clock)
    a_human(store_a, tenant=T_A, clock=clock)
    a_human(store_b, tenant=T_B, clock=clock)

    an_item(m_a, work_item_id="wi-shared-id")
    before = m_a.require("wi-shared-id")
    with pytest.raises(UnknownWorkItem):
        m_b.apply("wi-shared-id", Trigger.PIPELINE_STARTED, **SYS)
    assert m_a.require("wi-shared-id").version == before.version

    # The SAME id in both tenants is two independent obligations, not a collision.
    an_item(m_b, work_item_id="wi-shared-id")
    m_b.apply("wi-shared-id", Trigger.PIPELINE_STARTED, **SYS)
    assert m_a.require("wi-shared-id").state is WorkItemState.OPEN
    assert m_b.require("wi-shared-id").state is WorkItemState.IN_PROGRESS
    store_a.close()
    store_b.close()


def test_a_foreign_tenants_human_cannot_own_work(tmp_path):
    clock = Clock()
    store_a = make_store(tmp_path, tenant=T_A, name="cross.db")
    store_b = make_store(tmp_path, tenant=T_B, name="cross.db")
    m_a = machine(store_a, tenant=T_A, clock=clock)
    a_human(store_b, "beta-only-bea", tenant=T_B, clock=clock)
    with pytest.raises(OwnershipRefused):
        an_item(m_a, owner_id="beta-only-bea")
    assert human_authority(store_a.conn, tenant=T_A, human_id="beta-only-bea") is None
    store_a.close()
    store_b.close()


def test_a_foreign_tenants_decision_and_timer_do_not_resolve(tmp_path):
    clock = Clock()
    store_a = make_store(tmp_path, tenant=T_A, name="refs.db")
    store_b = make_store(tmp_path, tenant=T_B, name="refs.db")
    m_a = machine(store_a, tenant=T_A, clock=clock)
    a_human(store_a, tenant=T_A, clock=clock)
    a_human(store_b, tenant=T_B, clock=clock)
    an_item(m_a)
    m_a.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)

    foreign_decision = a_human_decision(store_b, tenant=T_B, clock=clock, seed="beta-decision")
    with pytest.raises(DecisionRefUnresolvable):
        resolve_decision_ref(store_a.conn, tenant=T_A, ref=foreign_decision, kind="AUDIT_EVENT")
    with pytest.raises(GuardNotSatisfied):
        m_a.apply("wi-4471-billing", Trigger.PIPELINE_CLOSED, **SYS, obligation_satisfied=True,
                  decision_ref=foreign_decision, decision_ref_kind="AUDIT_EVENT")

    a_fired_age_timer(store_b, work_item_id="wi-4471-billing", tenant=T_B,
                      timer_id="beta-timer", clock=clock)
    with pytest.raises(GuardNotSatisfied) as caught:
        m_a.apply("wi-4471-billing", Trigger.AGE_THRESHOLD_CROSSED, actor_type="system",
                  actor_id="timer-relay", timer_id="beta-timer")
    assert "no durable timer" in str(caught.value)
    store_a.close()
    store_b.close()


# ================================================================= K. the P5 path, and the dark

def test_the_state_change_and_its_event_are_one_commit(tmp_path, monkeypatch):
    """M-23 / GR-2. An event that cannot be written must take its state change with it — the commit
    that would have made BOTH real never happens."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    a_human(store, clock=clock)
    an_item(m)
    before = state_digest(store)

    from freight_recon import work_item as module

    class ExplodingOutbox(module.TransactionalOutbox):
        def emit(self, envelope):                       # noqa: ANN001
            raise RuntimeError("the sink is on fire")

    monkeypatch.setattr(module, "TransactionalOutbox", ExplodingOutbox)
    with pytest.raises(RuntimeError, match="on fire"):
        m.apply("wi-4471-billing", Trigger.PIPELINE_STARTED, **SYS)
    assert state_digest(store) == before, (
        "the state row moved while its event did not — the dual write M-23 abolishes"
    )
    assert m.require("wi-4471-billing").state is WorkItemState.OPEN
    store.close()


def test_every_emitted_event_carries_the_accountable_owner(tmp_path):
    """§1 marks `accountable_owner_id` `C`; on a Work Item it is ALWAYS applicable. This is what
    lets an audit reconstruct who was accountable from the beliefs of that day rather than from
    today's roster."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    item = _drive_to(store, m, clock, WorkItemState.CLOSED)
    events = [e for e in outbox_events(store) if e["aggregate_id"] == item]
    assert len(events) >= 3
    for event in events:
        envelope = _envelope_for(store, event["event_id"])
        assert envelope.accountable_owner_id, f"{event['event_name']} carries no accountable owner"
        assert envelope.work_item_id == item
        assert envelope.aggregate_type == AGGREGATE_TYPE
    store.close()


def test_the_work_item_import_closure_reaches_nothing_effect_capable(tmp_path):
    """### M1 SHIPS DARK, STRUCTURALLY. A Work Item performs no external effect (point 38), and this
    asserts the import CLOSURE rather than counting zeros afterwards — a module that cannot reach the
    capability cannot use it, and no future edit can make M1 act without first making this red.

    The walk sees every import spelling, for the reason `test_p5_replay_and_audit` records: relative
    from-imports, absolute from-imports, plain imports and `importlib.import_module`. CLAUDE.md §9
    lists that blind spot as a repeat offender in this repository.
    """
    forbidden = {
        "effect_boundary", "checkpoint", "cdp_actuator", "cdp_session", "tms_write",
        "truckingoffice_write", "discovered_write", "multistep_write", "browser_use_write",
        "browser_use_adapter", "slack_adapter", "email_adapter", "brake", "operator_agent",
        "operation_router", "governed_write_route",
    }
    src = ROOT / "src" / "freight_recon"

    def reached_by(tree: ast.AST) -> list[str]:
        found: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    found.append(node.module.split(".")[-1])
                for alias in node.names:
                    found.append(alias.name.split(".")[-1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    found.append(alias.name.split(".")[-1])
            elif isinstance(node, ast.Call):
                target = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if target in {"import_module", "__import__"}:
                    for argument in node.args:
                        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                            found.append(argument.value.split(".")[-1])
        return found

    seen: set[str] = set()
    frontier = ["work_item"]
    while frontier:
        module = frontier.pop()
        if module in seen:
            continue
        seen.add(module)
        for candidate in (src / f"{module}.py", src / "migrations" / f"{module}.py"):
            if candidate.exists():
                frontier.extend(reached_by(ast.parse(candidate.read_text(encoding="utf-8"))))
                break

    assert "work_item" in seen and len(seen) > 3, f"the closure walk inspected nothing: {seen}"
    reached = sorted(seen & forbidden)
    assert not reached, (
        f"M1's import closure reaches {reached}. A Work Item performs no external effect; an "
        f"effect-capable module inside the closure turns that from a structural property into a "
        f"discipline. Closure walked: {sorted(seen)}"
    )


def test_no_transition_mints_a_witness_or_a_grant(tmp_path):
    """The measured half of the same claim, over REAL tables and a REAL population."""
    clock = Clock()
    store = make_store(tmp_path)
    m = machine(store, clock=clock)
    before = {
        table: store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("checkpoint_witnesses", "effect_grants", "brakes")
    }
    for index, state in enumerate(WorkItemState):
        item_store = make_store(tmp_path, name=f"dark-{index}.db")
        item_machine = machine(item_store, clock=clock)
        _drive_to(item_store, item_machine, clock, state)
        for table, count in before.items():
            assert item_store.conn.execute(
                f"SELECT COUNT(*) FROM {table}").fetchone()[0] == count, table
        item_store.close()
    assert len(list(WorkItemState)) == 7, "the sweep stopped covering the state set"
    m.conn.commit()
    store.close()


def test_nothing_in_production_calls_this_machine_yet(tmp_path):
    """### IT SHIPS DARK, AND THAT IS ASSERTED RATHER THAN ANNOUNCED. Discovered by scanning the
    package and the operator scripts, never by an enumerated file list."""
    importers: list[str] = []
    for path in sorted((ROOT / "src" / "freight_recon").rglob("*.py")) + \
            sorted((ROOT / "scripts").rglob("*.py")):
        if path.name == "work_item.py":
            continue
        text = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.module and \
                    node.module.split(".")[-1] == "work_item":
                importers.append(str(path.relative_to(ROOT)))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[-1] == "work_item":
                        importers.append(str(path.relative_to(ROOT)))
    assert not importers, (
        f"M1 has acquired production callers: {sorted(set(importers))}. P6 ships dark; a caller "
        f"means the rollout posture in the registry is no longer true."
    )


# ------------------------------------------------------------------------------------- helpers

def _raw_envelope(store, event_id: str) -> str:
    row = store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND event_id = ?",
        (T_A, event_id)).fetchone()
    assert row is not None, event_id
    return row["envelope_json"]


def _envelope_for(store, event_id: str) -> EventEnvelope:
    return EventEnvelope.from_json(_raw_envelope(store, event_id))
