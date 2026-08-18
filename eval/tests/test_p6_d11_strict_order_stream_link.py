"""P6-D11 — the STRICT-ORDER F2 version-gap, and the stream link that closes it.

THE DEFECT, IN THE ONLY TERMS THAT MATTER TO A BROKER

    Load 4471 delivered. The attempt to raise its invoice is proposed, policy-checked, validated,
    routed to a human, approved, and checkpointed — and the checkpoint is the moment Neyma is
    allowed to authorize the invoice. `CheckpointPassed` is the fact M3 consumes to MINT that
    authorization. It never arrived. It sat in a park, behind a version that no machine will ever
    emit, and the invoice was never raised — for that load, and for every load after it.

WHY, MECHANICALLY

    `pipeline_instance` is a STRICT-ORDER aggregate (`events/registry.md` §8). Eight of M2's
    twenty-five §14 rows are `CONSUMES`: they advance the attempt's version and emit nothing on
    this stream, because the canonical event belongs to M3 or M4 and GR-2 is discharged by the
    CO-COMMIT. The version sequence on the F2 stream is therefore NOT contiguous **by canonical
    design**. The dedup inbox's gap rule read a missing version as "an earlier event has not
    arrived yet" — true for a lost or reordered event, and false forever for one that was never
    emitted.

THE FIX, AND WHAT IT IS CAREFUL NOT TO GIVE UP

    §8 requires strict ORDER. It never required CONTIGUITY. So the successor declares what it
    follows — `previous_aggregate_version` — and the consumer blocks iff that predecessor is above
    its high-water mark. ### **The park that SHOULD happen still happens**, and half this file
    exists to prove it: a genuinely lost event still parks, a reordered one still parks and then
    drains in order, a duplicate is still a no-op, and a producer cannot declare a predecessor that
    lets a consumer skip a real event.

Every case here is a way this could be wrong in production, and each one costs a broker money.
"""

from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase5_kit import (  # noqa: E402
    Clock,
    T_A,
    T_B,
    emit_with_state_change,
    make_envelope,
    agnostic_drain,
    make_inbox,
    make_outbox,
    state_digest,
)
from phase5_kit import make_store as make_p5_store  # noqa: E402
from phase6_pipeline_kit import (  # noqa: E402
    HUMAN,
    OWNER,
    PIPELINE,
    SYS,
    WORK_ITEM,
    a_proposed_attempt,
    a_world,
    advance_to_checkpoint,
    an_effect,
    checkpoint_inputs,
    kernel_for,
    machine,
    make_store,
)

from freight_recon.event_envelope import EventEnvelope, MalformedEnvelope  # noqa: E402
from freight_recon.event_inbox import ConsumeOutcome, DedupInbox  # noqa: E402
from freight_recon.event_outbox import StreamLinkViolation  # noqa: E402
from freight_recon.event_replay import replay  # noqa: E402
from freight_recon.migrations.phase5_event_transport import (  # noqa: E402
    STRICT_ORDER_AGGREGATE_TYPES,
)
from freight_recon.pipeline_instance import (  # noqa: E402
    AGGREGATE_TYPE,
    TRANSITIONS,
    PipelineState,
    RowKind,
    Trigger,
)

M2_SOURCE = ROOT / "src/freight_recon/pipeline_instance.py"
INBOX_SOURCE = ROOT / "src/freight_recon/event_inbox.py"
EVENTS_REGISTRY = ROOT / "docs/specifications/events/registry.md"


# ------------------------------------------------------------------------------- the real stream

def _attempt_through_checkpoint(tmp_path, name="d11.db"):
    """Drive the REAL M2 through the REAL narrative to CLAIMED. No synthetic envelopes."""
    store = make_store(tmp_path, name=name)
    clk = Clock()
    m = machine(store, clock=clk)
    effect = an_effect()
    a_proposed_attempt(m, effect=effect)
    world = a_world()
    kernel = kernel_for(store, clk)
    advance_to_checkpoint(m)
    r8 = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                 checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    m.apply(PIPELINE, Trigger.CLAIM_ATTEMPTED, **SYS, kernel=kernel, handle=r8.grant_handle)
    return store, m, clk


def _f2_envelopes(store, aggregate_id=PIPELINE, tenant=T_A) -> list[EventEnvelope]:
    return [
        EventEnvelope.from_json(r["envelope_json"])
        for r in store.conn.execute(
            "SELECT envelope_json FROM event_outbox WHERE tenant=? AND aggregate_type=? "
            "AND aggregate_id=? ORDER BY aggregate_version, event_id",
            (tenant, AGGREGATE_TYPE, aggregate_id)).fetchall()
    ]


# ============================================================ A. the failure, end to end

def test_the_checkpoint_reaches_an_m3_shaped_consumer_across_an_intentional_gap(tmp_path):
    """### THE CAPABILITY THIS UNIT DELIVERS, IN ONE CASE.

    M3 mints the Effect Grant on `CheckpointPassed` (EF-1). Before this fix the F2 stream reached
    it as v1, v2, v3, v5, v6 — v4 belonging to PL-6, a `CONSUMES` row whose `ApprovalRequested` is
    M4's — and the inbox parked v5 and v6 forever. The invoice was never authorized.
    """
    store, m, clk = _attempt_through_checkpoint(tmp_path)
    envelopes = _f2_envelopes(store)
    emitted = [e.aggregate_version for e in envelopes]
    final = m.require(PIPELINE).version

    # The GAP IS STILL THERE — this unit did not make every version emit. It made the gap legible.
    assert set(range(1, final + 1)) - set(emitted), (
        "no gap remains in the emitted stream. Either every row now emits on `pipeline_instance` "
        "(a different design from the one adopted) or this narrative stopped crossing a CONSUMES "
        "row. Either way the case below proves nothing and must be re-derived."
    )

    inbox = DedupInbox(store.conn, tenant=T_A, consumer_id="m3-effect-grant", clock=clk)
    outcomes = {e.event_name: inbox.consume(e, handler=lambda _: None).outcome for e in envelopes}

    assert outcomes["CheckpointPassed"] is ConsumeOutcome.APPLIED, (
        f"M3 cannot mint the grant: {outcomes}. This is the P6-D11 stall."
    )
    assert set(outcomes.values()) == {ConsumeOutcome.APPLIED}, outcomes
    assert inbox.parked() == []


def test_every_event_of_a_real_attempt_declares_an_unbroken_chain(tmp_path):
    """The link is a LINKED LIST over the emitted stream: each event's declared predecessor is the
    version of the event actually before it. Measured against the real emitted rows, not asserted."""
    store, _, _ = _attempt_through_checkpoint(tmp_path, name="chain.db")
    envelopes = _f2_envelopes(store)
    assert len(envelopes) >= 5, "the narrative stopped exercising the stream"

    seen: list[int] = []
    for envelope in envelopes:
        assert envelope.previous_aggregate_version is not None, (
            f"{envelope.event_name} at v{envelope.aggregate_version} declares no predecessor on a "
            f"STRICT-ORDER aggregate — a consumer would fall back to contiguity and park"
        )
        expected = max([v for v in seen if v < envelope.aggregate_version], default=0)
        assert envelope.previous_aggregate_version == expected, (
            f"{envelope.event_name} at v{envelope.aggregate_version} claims to follow "
            f"v{envelope.previous_aggregate_version}; the stream says v{expected}"
        )
        seen.append(envelope.aggregate_version)


def test_the_consumes_rows_are_why_the_gap_exists_and_they_still_emit_nothing(tmp_path):
    """### THE ROOT CAUSE, RE-DERIVED RATHER THAN REMEMBERED. Eight rows advance the version and
    emit nothing here. This unit did NOT change that, and must not: their canonical events belong
    to M3 and M4, and M2 emitting one would assert a fact about a machine that does not exist."""
    consumes = sorted(r.id for r in TRANSITIONS if r.kind is RowKind.CONSUMES)
    assert consumes == ["PL-10", "PL-10f", "PL-10u", "PL-11", "PL-11c", "PL-15", "PL-6", "PL-9"], (
        f"the CONSUMES population moved: {consumes}. The gap's cause changed; re-derive the case."
    )
    store, m, _ = _attempt_through_checkpoint(tmp_path, name="cause.db")
    # PL-6 (v4) and PL-9 (v7) both ran in this narrative and neither emitted on F2.
    emitted = {e.aggregate_version for e in _f2_envelopes(store)}
    assert 4 not in emitted and 7 not in emitted, emitted
    assert m.require(PIPELINE).state is PipelineState.CLAIMED


# ==================================== B. the park that MUST still happen (the half that can regress)

def _linked(version, previous, **kw):
    return make_envelope(aggregate_version=version, previous_aggregate_version=previous,
                         seed=f"link-{version}-{previous}-{kw.get('event_name', 'CheckpointPassed')}",
                         **kw)


def test_a_genuinely_lost_event_still_parks(tmp_path):
    """### THE CASE THAT PROVES THE FIX DID NOT SIMPLY DISABLE THE GUARD.

    v5 was really emitted and really lost in transport. v6 declares it as its predecessor, the
    consumer has not applied it, and v6 PARKS — exactly as before. A gap the producer left is
    closed by the successor's declaration; a gap the transport made is not.
    """
    store = make_p5_store(tmp_path, name="lost.db")
    inbox = make_inbox(store, consumer_id="m3")
    assert inbox.consume(_linked(1, 0), handler=lambda _: None).outcome is ConsumeOutcome.APPLIED
    result = inbox.consume(_linked(6, 5), handler=lambda _: None)
    assert result.outcome is ConsumeOutcome.PARKED_VERSION_GAP, result
    assert "follows version 5" in result.detail and "only 1 is applied" in result.detail
    assert [p.event_id for p in inbox.parked()] == [_linked(6, 5).event_id]
    store.close()


def test_a_reordered_delivery_parks_and_then_drains_in_order(tmp_path):
    """AC-EVT-005 for a STRICT family, unchanged: v6 before v5 waits for v5."""
    store = make_p5_store(tmp_path, name="reorder.db")
    inbox = make_inbox(store, consumer_id="m3")
    applied: list[int] = []
    handler = lambda e: applied.append(e.aggregate_version)  # noqa: E731

    assert inbox.consume(_linked(1, 0), handler=handler).outcome is ConsumeOutcome.APPLIED
    assert inbox.consume(_linked(6, 5), handler=handler).outcome is ConsumeOutcome.PARKED_VERSION_GAP
    # The park drains through the F-04 factory — semantics derived from the PARKED envelope, never
    # borrowed from the invocation that unblocked it. Without a factory it stays truthfully PARKED
    # and the transport redelivers it, which is the second half of this case.
    released = inbox.consume(_linked(5, 1), handler=handler,
                             drain_handler_for=agnostic_drain(handler))
    assert released.outcome is ConsumeOutcome.APPLIED
    assert released.drained == (_linked(6, 5).event_id,), released.drained
    assert applied == [1, 5, 6], f"applied out of order: {applied}"
    assert inbox.parked() == []
    store.close()


def test_a_reordered_delivery_with_no_drain_factory_stays_parked_until_redelivered(tmp_path):
    """The same shape without the opt-in cascade: the park is not silently drained, it is
    redelivered by the transport, and the ordering still holds when it is."""
    store = make_p5_store(tmp_path, name="reorder2.db")
    inbox = make_inbox(store, consumer_id="m3")
    applied: list[int] = []
    handler = lambda e: applied.append(e.aggregate_version)  # noqa: E731

    inbox.consume(_linked(1, 0), handler=handler)
    assert inbox.consume(_linked(6, 5), handler=handler).outcome is ConsumeOutcome.PARKED_VERSION_GAP
    assert inbox.consume(_linked(5, 1), handler=handler).outcome is ConsumeOutcome.APPLIED
    assert inbox.consume(_linked(6, 5), handler=handler).outcome is ConsumeOutcome.ALREADY_PARKED
    assert applied == [1, 5], f"a parked event was applied without being drained: {applied}"
    assert [p.event_id for p in inbox.parked()] == [_linked(6, 5).event_id]
    store.close()


def test_a_link_pointing_past_an_unapplied_event_cannot_skip_it(tmp_path):
    """### THE ATTACK THE LINK INVITES, AT THE CONSUMER. An event claiming `previous=0` when the
    consumer is mid-stream must not rewind or skip anything. `previous <= applied` means every
    earlier event is already in, so applying is safe; the cursor never goes backwards."""
    store = make_p5_store(tmp_path, name="skip.db")
    inbox = make_inbox(store, consumer_id="m3")
    for version, previous in ((1, 0), (2, 1), (3, 2)):
        inbox.consume(_linked(version, previous), handler=lambda _: None)
    cursor = lambda: store.conn.execute(  # noqa: E731
        "SELECT applied_version FROM inbox_aggregate_cursor WHERE tenant=? AND consumer_id=?",
        (T_A, "m3")).fetchone()[0]
    assert cursor() == 3
    # A late sibling declaring an old predecessor applies (it is not a gap) and does NOT rewind.
    assert inbox.consume(
        _linked(2, 1, event_name="PipelineVoided", producer_transition_id="PL-7v"),
        handler=lambda _: None).outcome is ConsumeOutcome.APPLIED
    assert cursor() == 3, "the cursor went backwards; a strict stream would replay history"
    store.close()


def test_duplicate_delivery_of_a_linked_event_is_a_noop(tmp_path):
    """GR-4 / AC-EVT-004, on the new path: the dedup key is still `(consumer, tenant, event_id)`
    and the link changes nothing about it. Measured by the state digest, not by a count."""
    store = make_p5_store(tmp_path, name="dupe.db")
    inbox = make_inbox(store, consumer_id="m3")
    calls: list[str] = []
    handler = lambda e: calls.append(e.event_id)  # noqa: E731
    inbox.consume(_linked(1, 0), handler=handler)
    inbox.consume(_linked(5, 1), handler=handler)
    before = state_digest(store)
    for _ in range(3):
        assert inbox.consume(_linked(5, 1), handler=handler).outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert state_digest(store) == before, "a redelivery changed durable state"
    assert len(calls) == 2, calls
    store.close()


def test_a_duplicate_of_a_PARKED_event_stays_parked_and_does_not_loop(tmp_path):
    """The poison-loop shape: redelivering a parked event must be counted, not re-parked, and must
    not raise inside the consuming transaction."""
    store = make_p5_store(tmp_path, name="parkdupe.db")
    inbox = make_inbox(store, consumer_id="m3")
    inbox.consume(_linked(1, 0), handler=lambda _: None)
    assert inbox.consume(_linked(9, 8), handler=lambda _: None).outcome \
        is ConsumeOutcome.PARKED_VERSION_GAP
    for _ in range(4):
        assert inbox.consume(_linked(9, 8), handler=lambda _: None).outcome \
            is ConsumeOutcome.ALREADY_PARKED
    assert len(inbox.parked()) == 1
    store.close()


# ============================================================== C. the link cannot be forged

def test_the_outbox_refuses_an_envelope_whose_declared_predecessor_is_a_lie(tmp_path):
    """### WHY THE OUTBOX VERIFIES INSTEAD OF TRUSTING. A producer that could state any predecessor
    could tell every consumer to apply past a real event — silently, permanently, and on a fact that
    is otherwise perfectly canonical. It is checked against the emitted record, in the caller's
    transaction, BEFORE the insert: the state change travelling with it is rolled back too."""
    store = make_p5_store(tmp_path, name="forge.db")
    emit_with_state_change(store, _linked(1, 0), clock=Clock())
    emit_with_state_change(store, _linked(2, 1, event_name="PipelineRejected",
                                          producer_transition_id="PL-3"), clock=Clock())
    with pytest.raises(StreamLinkViolation) as exc:
        emit_with_state_change(
            store,
            make_envelope(aggregate_version=3, previous_aggregate_version=1, seed="forged",
                          event_name="PipelineClosed", producer_transition_id="PL-14"),
            clock=Clock())
    assert "declares previous_aggregate_version 1" in str(exc.value)
    assert "already emitted below 3 is 2" in str(exc.value)
    rows = store.conn.execute("SELECT COUNT(*) FROM event_outbox").fetchone()[0]
    assert rows == 2, "the refused event reached the durable log"
    store.close()


def test_a_predecessor_at_or_above_its_own_version_is_not_an_envelope(tmp_path):
    """A self-referential or forward link would make the stream a cycle and a consumer would never
    advance. Refused at construction, before anything can commit against it."""
    for previous in (1, 2, 9):
        with pytest.raises(MalformedEnvelope, match="not BELOW aggregate_version"):
            make_envelope(aggregate_version=1, previous_aggregate_version=previous, seed="cycle")


def test_the_link_is_derived_per_tenant_and_per_aggregate(tmp_path):
    """[C-1]. Tenant B's stream cannot supply tenant A's predecessor, and a second attempt's
    versions cannot supply the first's — the derivation is keyed on both."""
    store = make_p5_store(tmp_path, name="tenant.db")
    emit_with_state_change(store, _linked(1, 0), clock=Clock())
    emit_with_state_change(store, _linked(4, 1, event_name="PipelineClosed",
                                          producer_transition_id="PL-14"), clock=Clock())
    outbox_a = make_outbox(store, tenant=T_A)
    assert outbox_a.last_emitted_version(AGGREGATE_TYPE, "pi-4471") == 4
    assert outbox_a.last_emitted_version(AGGREGATE_TYPE, "pi-4471", below=4) == 1
    # A DIFFERENT attempt and a DIFFERENT tenant both read an empty stream.
    assert outbox_a.last_emitted_version(AGGREGATE_TYPE, "pi-9999") == 0
    assert make_outbox(store, tenant=T_B).last_emitted_version(AGGREGATE_TYPE, "pi-4471") == 0
    store.close()


def test_a_tenant_b_event_cannot_move_a_tenant_a_stream(tmp_path):
    """The link did not open a new cross-tenant path: the tenant gate still fires first."""
    store = make_p5_store(tmp_path, name="xtenant.db")
    inbox = make_inbox(store, tenant=T_A, consumer_id="m3")
    inbox.consume(_linked(1, 0), handler=lambda _: None)
    before = state_digest(store)
    foreign = make_envelope(tenant=T_B, aggregate_version=5, previous_aggregate_version=1,
                            seed="foreign")
    result = inbox.consume(foreign, handler=lambda _: pytest.fail("a T_B event ran a T_A handler"))
    assert result.outcome is ConsumeOutcome.REJECTED_CROSS_TENANT, result
    assert state_digest(store) == before
    store.close()


# ================================================ D. backward compatibility, replay and restart

def test_an_unlinked_envelope_still_uses_the_contiguity_rule(tmp_path):
    """### EVERY HISTORICAL EVENT IS UNLINKED, AND ITS BEHAVIOUR IS UNCHANGED BYTE FOR BYTE.
    Absence may NOT be read as "there is nothing before me" — that would turn every pre-existing
    stream into one a consumer skips through. Absent ⇒ the old rule, verbatim."""
    store = make_p5_store(tmp_path, name="legacy.db")
    inbox = make_inbox(store, consumer_id="m3")
    plain = make_envelope(aggregate_version=1, seed="legacy-1")
    assert plain.previous_aggregate_version is None
    assert inbox.consume(plain, handler=lambda _: None).outcome is ConsumeOutcome.APPLIED
    gap = make_envelope(aggregate_version=4, seed="legacy-4")
    result = inbox.consume(gap, handler=lambda _: None)
    assert result.outcome is ConsumeOutcome.PARKED_VERSION_GAP
    assert "expected version 2, got 4" in result.detail
    store.close()


def test_an_unlinked_envelope_round_trips_and_keeps_its_digest(tmp_path):
    """§6: an additive optional field leaves an existing event's canonical bytes untouched. A
    historical envelope must hash to what it always hashed to, or `GC-1` is a different corpus."""
    plain = make_envelope(aggregate_version=2, seed="digest-stable")
    assert "previous_aggregate_version" not in plain.as_document()
    assert EventEnvelope.from_json(plain.to_json()).digest() == plain.digest()
    linked = make_envelope(aggregate_version=2, previous_aggregate_version=0, seed="digest-stable")
    assert linked.as_document()["previous_aggregate_version"] == 0
    assert linked.digest() != plain.digest(), "the link is not inside the hashed bytes"
    assert EventEnvelope.from_json(linked.to_json()).previous_aggregate_version == 0


def test_replay_of_a_gap_carrying_stream_is_deterministic_and_gap_tolerant(tmp_path):
    """### REPLAY NEVER NEEDED CONTIGUITY AND STILL DOES NOT. It folds per aggregate in
    `aggregate_version` order (§8) and asserts nothing about which versions exist — which is why the
    fold was always right and only the inbox's INFERENCE was wrong. Run twice ⇒ one digest."""
    store, _, _ = _attempt_through_checkpoint(tmp_path, name="replay.db")
    envelopes = _f2_envelopes(store)
    first = replay(envelopes)
    second = replay(list(reversed(envelopes)))
    assert first.digest() == second.digest(), "replay depends on arrival order"
    assert first.aggregates[(T_A, AGGREGATE_TYPE, PIPELINE)].version == max(
        e.aggregate_version for e in envelopes)


def test_a_restart_mid_stream_resumes_without_reapplying_or_stalling(tmp_path):
    """AC-RACE-008/009 across a process boundary: the cursor and the inbox rows are durable, a new
    consumer object on the same store resumes exactly where the old one stopped, and the events it
    already applied are no-ops rather than a second application."""
    store, _, clk = _attempt_through_checkpoint(tmp_path, name="restart.db")
    envelopes = _f2_envelopes(store)
    applied: list[str] = []
    handler = lambda e: applied.append(e.event_name)  # noqa: E731

    first = DedupInbox(store.conn, tenant=T_A, consumer_id="m3-effect-grant", clock=clk)
    for envelope in envelopes[:3]:
        assert first.consume(envelope, handler=handler).outcome is ConsumeOutcome.APPLIED
    del first  # the process dies here

    resumed = DedupInbox(store.conn, tenant=T_A, consumer_id="m3-effect-grant", clock=clk)
    outcomes = [resumed.consume(e, handler=handler).outcome for e in envelopes]
    assert outcomes[:3] == [ConsumeOutcome.DUPLICATE_NOOP] * 3
    assert set(outcomes[3:]) == {ConsumeOutcome.APPLIED}
    assert applied == [e.event_name for e in envelopes], applied
    assert resumed.parked() == []


# ================================================================= E. concurrency, on one store

def test_a_lost_update_emits_nothing_so_it_claims_no_link(tmp_path):
    """GR-3 under the link: the loser of a race writes no row, so it also contributes no version to
    the chain. A chain with a phantom link in it would park every later event."""
    from freight_recon.pipeline_instance import VersionConflict

    store = make_store(tmp_path, name="race.db")
    clk = Clock()
    m = machine(store, clock=clk)
    a_proposed_attempt(m, effect=an_effect())
    stale = m.require(PIPELINE)
    facts = dict(policy_version="pv1", gate_decision=__import__(
        "freight_recon.checkpoint", fromlist=["GateDecision"]).GateDecision.HUMAN_APPROVAL_REQUIRED,
        policy_decision="PERMIT", rules_matched=["r-1"], reason="x",
        model_inferred_material_fact=False)
    m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, expected_version=stale.version, **facts)
    with pytest.raises(VersionConflict):
        m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, expected_version=stale.version, **facts)

    envelopes = _f2_envelopes(store)
    assert [e.aggregate_version for e in envelopes] == [1, 2]
    assert [e.previous_aggregate_version for e in envelopes] == [0, 1]
    inbox = DedupInbox(store.conn, tenant=T_A, consumer_id="m3", clock=clk)
    assert all(inbox.consume(e, handler=lambda _: None).outcome is ConsumeOutcome.APPLIED
               for e in envelopes)


def test_an_illegal_attempt_records_evidence_that_a_consumer_can_still_read(tmp_path):
    """### THE SECOND-ORDER STALL, AND IT IS THE ONE AN OPERATOR IS PAGED FROM.

    `IllegalTransitionAttempted` is an F14 security record riding on this STRICT aggregate at the
    attempt's **UNCHANGED** version. The inbox keys strictness on the AGGREGATE, so under the old
    contiguity rule an attack recorded after a run of `CONSUMES` rows parked too — the refusal
    worked and the evidence of it could not be consumed.

    ### BOTH POSITIONS ARE EXERCISED, BECAUSE THEY FAIL DIFFERENTLY. An attack at a version that
    ALREADY carries an event is where the predecessor derivation could take the event ITSELF (a
    self-loop, and an unwritable security record); an attack at a version a `CONSUMES` row left
    silent is where the consumer could park. One case covering only one of them would leave the
    other free to regress.
    """
    from freight_recon.checkpoint import GateDecision

    store = make_store(tmp_path, name="ita.db")
    clk = Clock()
    m = machine(store, clock=clk)
    effect = an_effect()
    a_proposed_attempt(m, effect=effect)

    def illegal(trigger, **kw):
        with pytest.raises(Exception):
            m.apply(PIPELINE, trigger, **SYS, **kw)

    # (1) POLICY_CHECKED is reached by PL-2, a PRODUCER row: v2 CARRIES an event.
    m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, policy_version="pv1",
            gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_decision="PERMIT",
            rules_matched=["r-1"], reason="gate resolved", model_inferred_material_fact=False)
    assert m.require(PIPELINE).version == 2
    illegal(Trigger.PROJECTION_UPDATED)
    at_two = [e for e in _f2_envelopes(store)
              if e.event_name == "IllegalTransitionAttempted" and e.aggregate_version == 2]
    assert len(at_two) == 1, "the attack at an OCCUPIED version was not recorded"
    assert at_two[0].previous_aggregate_version == 1, (
        f"the security record took v{at_two[0].previous_aggregate_version} as its predecessor at "
        f"v2, where the highest event BELOW it is v1. A record whose predecessor is itself is a "
        f"self-loop no consumer can pass."
    )

    # (2) AWAITING_APPROVAL is reached by PL-6, a CONSUMES row: v4 carries NOTHING.
    m.apply(PIPELINE, Trigger.VALIDATION_COMPLETED, **SYS, validation_passed=True,
            money_fence_passed=True, document_fence_passed=True,
            material_fields_consistent=True, open_conflict=False)
    m.apply(PIPELINE, Trigger.GATE_ROUTED, **SYS,
            gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED)
    assert m.require(PIPELINE).version == 4
    illegal(Trigger.PROJECTION_UPDATED)
    at_four = [e for e in _f2_envelopes(store)
               if e.event_name == "IllegalTransitionAttempted" and e.aggregate_version == 4]
    assert len(at_four) == 1, "the attack at a SILENT version was not recorded"
    assert at_four[0].previous_aggregate_version == 3

    # And a consumer can read every one of them, in order, with nothing parked.
    envelopes = _f2_envelopes(store)
    inbox = DedupInbox(store.conn, tenant=T_A, consumer_id="m3-effect-grant", clock=clk)
    outcomes = {(e.event_name, e.aggregate_version): inbox.consume(e, handler=lambda _: None).outcome
                for e in envelopes}
    assert set(outcomes.values()) == {ConsumeOutcome.APPLIED}, outcomes
    assert inbox.parked() == []


# ======================================================= F. structural guards (derived, not listed)

def test_m2_builds_every_envelope_in_exactly_one_place(tmp_path):
    """### A NEW EMISSION SITE MUST NOT BE ABLE TO SKIP THE LINK.

    Discovered by AST over the module's own source, never by a list of line numbers: the only
    `EventEnvelope(...)` construction in `pipeline_instance.py` is inside `_envelope`, which is the
    method that derives the predecessor. Adding a second one breaks this case rather than shipping
    an event a consumer will park on.
    """
    tree = ast.parse(M2_SOURCE.read_text(encoding="utf-8"))
    sites: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(node):
            if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                    and inner.func.id == "EventEnvelope"):
                sites.append(node.name)
    assert sites, "no EventEnvelope construction was found at all — the walk is broken"
    assert set(sites) == {"_envelope"}, (
        f"`pipeline_instance.py` constructs an EventEnvelope outside `_envelope`: {sorted(set(sites))}. "
        f"Every one must go through the factory that declares `previous_aggregate_version`, or the "
        f"F2 stream acquires an event that a strict consumer parks on."
    )


def test_the_strict_population_is_read_from_the_canonical_source(tmp_path):
    """The rule is keyed on §8's strict families, and `pipeline_instance` is one of them. A case
    that hard-coded the list would keep passing after the list changed."""
    assert AGGREGATE_TYPE in STRICT_ORDER_AGGREGATE_TYPES
    assert set(STRICT_ORDER_AGGREGATE_TYPES) == {
        "pipeline_instance", "effect_grant", "approval", "policy", "brake"}


def test_the_canonical_registry_states_the_contract_this_code_implements():
    """### A MECHANISM WHOSE SPECIFICATION DOES NOT STATE IT IS A LOCAL CONVENTION, NOT A CONTRACT.
    §1 must declare the field and §8 must say order rather than contiguity, or the next machine's
    author has no way to know they owe the link."""
    text = EVENTS_REGISTRY.read_text(encoding="utf-8")
    assert "`previous_aggregate_version`" in text, "§1 does not declare the envelope field"
    assert "P6-D11" in text, "the decision is not traceable to the defect it closes"
    section8 = text.split("## 8. ORDERING")[1].split("## 9.")[0]
    assert "previous_aggregate_version" in section8, "§8 does not name the field a consumer orders on"
    assert "contiguous" in section8.lower(), "§8 does not distinguish order from contiguity"
    assert "POSITIVE evidence" in section8, "§8 does not state WHY an absence is not evidence"
    # The eight rows the decision is about, named in the canonical text rather than only in code.
    for row in ("PL-6", "PL-9", "PL-10", "PL-10f", "PL-10u", "PL-11", "PL-11c", "PL-15"):
        assert f"`{row}`" in section8, f"§8 does not name the CONSUMES row {row}"
    # ### AND THE LINE THE CONTRACT GENERATOR PARSES IS STILL ONE LINE CARRYING BOTH HALVES.
    # This amendment inserted bullets into §8 and, on its first attempt, split the strict half from
    # the order-tolerant half — which would have left `generate_event_contracts.py` unable to
    # delimit the strict family set. The generator's own `--check` caught it; this asserts it here
    # too, because the next §8 edit will be made by someone who did not make that mistake once.
    declarations = [line for line in section8.splitlines()
                    if "Strict per-aggregate ordering REQUIRED" in line]
    assert len(declarations) == 1, f"§8's family declaration is not one line: {declarations}"
    assert "Order-tolerant:" in declarations[0], (
        "§8's ordering declaration lost its `Order-tolerant:` half — the strict family set can no "
        "longer be delimited, and the generator would silently absorb the other half"
    )
