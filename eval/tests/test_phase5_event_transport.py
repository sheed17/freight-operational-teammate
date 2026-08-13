"""P5 U5.7 + U5.8 — the transactional outbox and the dedup inbox, attacked.

The battery is organised by RISK, not by taxonomy. Each section is a way this mechanism could be
wrong in production, and the crash sections are the reason the two halves are one unit:

    the dual write            state change without its event, or the reverse            (M-23, I10)
    crash BEFORE publish      the identical event_id is re-sent                       (AC-RACE-006)
    crash AFTER publish       the duplicate is harmless                               (AC-RACE-007)
    consumer crash            before the inbox commit ⇒ reprocessed, same digest       (AC-RACE-008)
                              after it ⇒ not reprocessed                               (AC-RACE-009)
    duplicate delivery        one Observation-shaped fact, one effect                  (AC-ADPT-010)
    out-of-order              strict families park; order-tolerant families converge    (AC-EVT-005)
    concurrent relays         two relays, one publication each, order preserved
    tenant crossing           rejected before the handler, and before any write               [C-1]
    malformed envelopes       refused before the handler, never coerced                  (AC-EVT-001)
    dangling references       parked, drained in arrival order, TTL ⇒ an OWNED problem   (AC-EVT-006)

The state-digest oracle (`phase5_kit.state_digest`) is what makes "no-op" a measurement rather
than a claim: every no-op case asserts the digest is byte-identical across the redelivery.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase5_kit import (  # noqa: E402
    EPOCH,
    STATE_CHANGE_SQL,
    T_A,
    T_B,
    Clock,
    FailingHandler,
    RecordingHandler,
    RecordingSink,
    assert_atomic,
    brake_version,
    deterministic_event_id,
    emit_with_state_change,
    inbox_rows,
    make_envelope,
    make_inbox,
    make_outbox,
    make_relay,
    make_store,
    outbox_rows,
    state_digest,
)

from freight_recon.event_envelope import (  # noqa: E402
    ACTOR_TYPES,
    ENVELOPE_SERIALIZATION_VERSION,
    STRICT_ORDER_AGGREGATE_TYPES,
    EnvelopeError,
    EventEnvelope,
    MalformedEnvelope,
    MissingEnvelopeField,
    UnserializableEvent,
)
from freight_recon.event_inbox import ConsumeOutcome, DedupInbox, InboxError  # noqa: E402
from freight_recon.event_outbox import (  # noqa: E402
    DuplicateEmission,
    OutboxNotInTransaction,
    OutboxTenantMismatch,
    StrictOrderViolation,
    TransactionalOutbox,
    transactional_emit,
)
from freight_recon.fingerprint import Money  # noqa: E402
from freight_recon.migrations.phase5_event_transport import (  # noqa: E402
    P5_INDEXES,
    P5_TENANT_TABLES,
    P5_TRIGGERS,
    phase5_readiness_problems,
)
from freight_recon.schema import schema_readiness_problems  # noqa: E402


# ============================================================ 1. the dual write (M-23, I10, F-06)

def test_a_fresh_database_carries_the_event_transport_with_zero_readiness_problems(tmp_path):
    store = make_store(tmp_path)
    assert schema_readiness_problems(store.conn) == []
    assert phase5_readiness_problems(store.conn) == []
    store.close()


def test_the_state_change_and_its_event_land_in_one_commit(tmp_path):
    store = make_store(tmp_path)
    before = brake_version(store)
    emit_with_state_change(store, make_envelope())
    assert_atomic(store, expect_event=True, baseline_version=before)
    store.close()


def test_a_crash_between_the_state_write_and_the_event_write_leaves_NEITHER(tmp_path):
    """The dual write, killed in its window. This is F-06's exact shape."""
    store = make_store(tmp_path)
    before = brake_version(store)
    with pytest.raises(RuntimeError, match="killed between the two writes"):
        with transactional_emit(store.conn, tenant=T_A) as session:
            session.execute(STATE_CHANGE_SQL)
            raise RuntimeError("killed between the two writes")
    assert_atomic(store, expect_event=False, baseline_version=before)
    store.close()


def test_a_crash_between_the_event_write_and_the_commit_leaves_NEITHER(tmp_path):
    """The other order. Both writes happened; neither survives, because the commit never did."""
    store = make_store(tmp_path)
    before = brake_version(store)
    with pytest.raises(RuntimeError, match="killed after both writes"):
        with transactional_emit(store.conn, tenant=T_A) as session:
            session.execute(STATE_CHANGE_SQL)
            session.emit(make_envelope())
            raise RuntimeError("killed after both writes, before the commit")
    assert_atomic(store, expect_event=False, baseline_version=before)
    store.close()


def test_emitting_outside_a_transaction_is_refused_and_writes_nothing(tmp_path):
    """The mechanism, stated as a refusal: there is no API for an event in a commit of its own."""
    store = make_store(tmp_path)
    outbox = make_outbox(store)
    with pytest.raises(OutboxNotInTransaction, match="SAME commit as the state change"):
        outbox.emit(make_envelope())
    assert outbox_rows(store) == []
    store.close()


def test_the_outbox_has_no_lenient_mode_for_writing_outside_a_transaction():
    """A guard with an off switch is a guard someone turns off. There must be no switch.

    Read from the AST's PARAMETER NAMES, not from the module text: a substring guard over source
    fires on its own explanatory prose, which is how a guard passes while proving nothing (and did
    on this node's first draft).
    """
    import ast

    tree = ast.parse((ROOT / "src" / "freight_recon" / "event_outbox.py").read_text("utf-8"))
    bypass_shaped = ("allow", "force", "skip", "unsafe", "lenient", "autocommit", "bypass")
    parameters: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                parameters.append((node.name, arg.arg))
    assert len(parameters) >= 20, (
        f"only {len(parameters)} parameters inspected — the AST walk found almost nothing and "
        f"this node would pass vacuously"
    )
    offenders = [
        f"{fn}({param})" for fn, param in parameters
        if any(token in param.lower() for token in bypass_shaped)
    ]
    assert not offenders, (
        f"M-23 must not have a parameter that disables it; found {offenders}"
    )
    import inspect

    from freight_recon import event_outbox

    signature = inspect.signature(event_outbox.TransactionalOutbox.emit)
    assert list(signature.parameters) == ["self", "envelope"], (
        f"emit() grew parameters {list(signature.parameters)}; every one of them is a place to "
        f"put a bypass"
    )


def test_exactly_one_commit_carries_the_state_change_and_the_event(tmp_path):
    """Traced from the SQLite statement stream, not inferred from reading the code."""
    store = make_store(tmp_path)
    statements: list[str] = []
    store.conn.set_trace_callback(statements.append)
    try:
        emit_with_state_change(store, make_envelope())
    finally:
        store.conn.set_trace_callback(None)
    normalised = [s.strip().upper() for s in statements]
    begins = [i for i, s in enumerate(normalised) if s.startswith("BEGIN")]
    commits = [i for i, s in enumerate(normalised) if s.startswith("COMMIT")]
    assert len(begins) == 1 and len(commits) == 1, (
        f"expected exactly one BEGIN and one COMMIT, got {len(begins)}/{len(commits)}: "
        f"{normalised}"
    )
    inner = normalised[begins[0]:commits[0]]
    assert any("PLATFORM_BRAKE" in s for s in inner), "the state change is outside the commit"
    assert any("INSERT INTO EVENT_OUTBOX" in s for s in inner), "the event is outside the commit"
    store.close()


def test_the_same_transition_cannot_record_its_fact_twice(tmp_path):
    """§4's transition-natural identity, as a UNIQUE constraint rather than a convention."""
    store = make_store(tmp_path)
    emit_with_state_change(store, make_envelope(seed="first"))
    with pytest.raises(DuplicateEmission, match="already emitted"):
        with transactional_emit(store.conn, tenant=T_A) as session:
            # A DIFFERENT event_id, same (tenant, aggregate, version, transition, name).
            session.emit(make_envelope(seed="second"))
    assert len(outbox_rows(store)) == 1
    store.close()


def test_the_real_ef2_pair_is_emittable_in_one_commit_at_one_version(tmp_path):
    """EF-2 emits `GrantClaimed` AND `EffectAttempted`, on ONE `effect_grant`, at ONE version.

    Straight out of `state-machines/03-external-effect-grant.machine.md`, and it is the reason the
    strict-ordering guarantee is a trigger and not the UNIQUE index it looks like it should be: a
    UNIQUE (tenant, aggregate_type, aggregate_id, aggregate_version) would have read perfectly and
    made the canonical claim path uninsertable at P6.
    """
    store = make_store(tmp_path)
    with transactional_emit(store.conn, tenant=T_A) as session:
        session.execute(STATE_CHANGE_SQL)
        session.emit(make_envelope(event_name="GrantClaimed", aggregate_type="effect_grant",
                                   aggregate_id="eg-1", aggregate_version=2,
                                   producer_transition_id="EF-2", seed="ef2-claim"))
        session.emit(make_envelope(event_name="EffectAttempted", aggregate_type="effect_grant",
                                   aggregate_id="eg-1", aggregate_version=2,
                                   producer_transition_id="EF-2", seed="ef2-attempt"))
    assert len(outbox_rows(store)) == 2
    store.close()


def test_two_different_transitions_cannot_claim_one_strict_version(tmp_path):
    """The invariant the strict families actually need: version-monotonic transitions.

    Two events at one version are fine when ONE transition emitted them (above). Two DIFFERENT
    transitions at one version means the version counter did not move, which is the monotonicity
    failure every strict-family guard is built on top of.
    """
    store = make_store(tmp_path)
    emit_with_state_change(store, make_envelope(
        event_name="GrantClaimed", aggregate_type="effect_grant", aggregate_id="eg-2",
        aggregate_version=2, producer_transition_id="EF-2", seed="owner-1"))
    with pytest.raises(StrictOrderViolation, match="version counter did not advance"):
        with transactional_emit(store.conn, tenant=T_A) as session:
            session.emit(make_envelope(
                event_name="EffectFailed", aggregate_type="effect_grant", aggregate_id="eg-2",
                aggregate_version=2, producer_transition_id="EF-3f", seed="owner-2"))
    assert len(outbox_rows(store)) == 1
    store.close()


def test_an_ordering_violation_is_not_reported_as_a_duplicate(tmp_path):
    """SQLite reports a trigger ABORT and a UNIQUE violation through ONE exception type.

    Collapsing them would send whoever reads the error hunting for a duplicate event that does not
    exist, while the real fault — a version counter that did not move — went unnamed.
    """
    store = make_store(tmp_path)
    envelope = make_envelope(seed="distinct-1")
    emit_with_state_change(store, envelope)

    with pytest.raises(DuplicateEmission):
        with transactional_emit(store.conn, tenant=T_A) as session:
            session.emit(make_envelope(seed="distinct-2"))          # same transition-natural id
    with pytest.raises(StrictOrderViolation):
        with transactional_emit(store.conn, tenant=T_A) as session:
            session.emit(make_envelope(seed="distinct-3", event_name="PolicyEvaluated",
                                       producer_transition_id="PL-2"))
    assert not issubclass(StrictOrderViolation, DuplicateEmission)
    store.close()


def test_an_order_tolerant_family_may_have_two_transitions_at_one_version(tmp_path):
    """The trigger must be scoped to the five strict families and must not police the others."""
    store = make_store(tmp_path)
    with transactional_emit(store.conn, tenant=T_A) as session:
        session.emit(make_envelope(event_name="ConflictRaised", aggregate_type="conflict",
                                   aggregate_id="cf-1", aggregate_version=1,
                                   producer_transition_id="CF-1", seed="tolerant-1"))
        session.emit(make_envelope(event_name="ConflictPartyAttached", aggregate_type="conflict",
                                   aggregate_id="cf-1", aggregate_version=1,
                                   producer_transition_id="CF-7", seed="tolerant-2"))
    assert len(outbox_rows(store)) == 2
    store.close()


def test_the_ef2_sibling_pair_both_reach_the_handler(tmp_path):
    """The inbox half of the same defect: a co-emitted sibling must not be read as superseded.

    A cursor that treated `version <= applied` as stale would apply `GrantClaimed` and then
    silently discard `EffectAttempted` — losing a fact from a version-monotonic history, with a
    green suite.
    """
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    claimed = make_envelope(event_name="GrantClaimed", aggregate_type="effect_grant",
                            aggregate_id="eg-3", aggregate_version=1,
                            producer_transition_id="EF-2", seed="sib-claim")
    attempted = make_envelope(event_name="EffectAttempted", aggregate_type="effect_grant",
                              aggregate_id="eg-3", aggregate_version=1,
                              producer_transition_id="EF-2", seed="sib-attempt")
    assert inbox.consume(claimed, handler).outcome is ConsumeOutcome.APPLIED
    assert inbox.consume(attempted, handler).outcome is ConsumeOutcome.APPLIED, (
        "the co-emitted sibling was not applied — it was read as a superseded version"
    )
    assert [e.event_name for e in handler.applied] == ["GrantClaimed", "EffectAttempted"]
    # And each is still individually dedup-protected.
    assert inbox.consume(attempted, handler).outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert len(handler.applied) == 2
    store.close()


# ================================================ 2. crash BEFORE publish — AC-RACE-006

def test_a_crash_before_publish_re_sends_the_identical_event_id(tmp_path):
    store = make_store(tmp_path)
    clock = Clock()
    envelope = make_envelope()
    emit_with_state_change(store, envelope)

    sink = RecordingSink()
    sink.crash_before_publish = True
    relay = make_relay(store, sink, clock=clock)
    result = relay.run_once()
    assert sink.delivered == [], "the sink was reached despite crashing before publish"
    assert result.failed == (envelope.event_id,)
    assert outbox_rows(store)[0]["delivery_state"] == "PENDING", (
        "a publish that did not happen must leave the row PENDING — a row marked published on a "
        "failed send is an event silently dropped"
    )

    # Recovery: the SAME row, re-sent.
    sink.crash_before_publish = False
    clock.advance(seconds=60)
    recovered = relay.run_once()
    assert recovered.published == (envelope.event_id,)
    assert sink.event_ids == [envelope.event_id]
    assert sink.digests == [envelope.digest()], (
        "the recovered send is not byte-identical to the committed envelope"
    )
    store.close()


def test_a_crashed_relays_lease_expires_and_another_relay_re_sends_the_same_row(tmp_path):
    """Recovery does not require the SAME relay to come back. It usually will not."""
    store = make_store(tmp_path)
    clock = Clock()
    envelope = make_envelope()
    emit_with_state_change(store, envelope)

    dead_sink = RecordingSink()
    dead_sink.crash_before_publish = True
    dead = make_relay(store, dead_sink, relay_id="relay-dead", clock=clock,
                      lease=timedelta(seconds=30))
    dead.run_once()

    fresh_sink = RecordingSink()
    fresh = make_relay(store, fresh_sink, relay_id="relay-fresh", clock=clock)
    clock.advance(seconds=31)
    fresh.run_once()
    assert fresh_sink.event_ids == [envelope.event_id]
    assert fresh_sink.digests == [envelope.digest()]
    store.close()


def test_a_live_lease_stops_a_second_relay_from_touching_the_same_aggregate(tmp_path):
    store = make_store(tmp_path)
    clock = Clock()
    emit_with_state_change(store, make_envelope())
    stalled_sink = RecordingSink()
    stalled_sink.crash_before_publish = True

    # A relay whose sink hangs would hold the lease; simulate by claiming and never releasing.
    holder = make_relay(store, stalled_sink, relay_id="relay-holder", clock=clock)
    claimed = holder._claim(max_aggregates=8)  # noqa: SLF001 — the lease is the thing under test
    assert len(claimed) == 1

    other_sink = RecordingSink()
    other = make_relay(store, other_sink, relay_id="relay-other", clock=clock)
    assert other.run_once().published == (), (
        "a second relay published a row that is under another relay's live lease"
    )
    assert other_sink.delivered == []
    store.close()


# ================================================= 3. crash AFTER publish — AC-RACE-007

def test_a_crash_after_publish_causes_a_duplicate_delivery_that_the_inbox_absorbs(tmp_path):
    """The full AC-RACE-007 arc, end to end, across BOTH halves of the unit."""
    store = make_store(tmp_path)
    clock = Clock()
    envelope = make_envelope()
    emit_with_state_change(store, envelope)

    sink = RecordingSink()
    sink.crash_after_publish = True
    relay = make_relay(store, sink, clock=clock)
    relay.run_once()
    assert sink.event_ids == [envelope.event_id], "the event did leave — that is the premise"
    assert outbox_rows(store)[0]["delivery_state"] == "PENDING", (
        "the mark-published commit did not happen, so the row must still be PENDING"
    )

    inbox = make_inbox(store, clock=clock)
    handler = RecordingHandler(store.conn)
    first = inbox.consume(sink.delivered[0], handler)
    assert first.outcome is ConsumeOutcome.APPLIED
    digest_after_first = state_digest(store)

    # Recovery re-sends. Same id, same bytes.
    sink.crash_after_publish = False
    clock.advance(seconds=60)
    relay.run_once()
    assert sink.event_ids == [envelope.event_id, envelope.event_id]
    assert sink.digests[0] == sink.digests[1]

    second = inbox.consume(sink.delivered[1], handler)
    assert second.outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert len(handler.applied) == 1, "the handler ran twice for one event"
    assert state_digest(store) == digest_after_first, (
        "the duplicate delivery moved the state digest — it was not a no-op"
    )
    store.close()


def test_a_failed_publish_counts_the_attempt_and_keeps_the_row_pending(tmp_path):
    store = make_store(tmp_path)
    clock = Clock()
    emit_with_state_change(store, make_envelope())
    sink = RecordingSink()
    sink.crash_before_publish = True
    relay = make_relay(store, sink, clock=clock)
    for _ in range(3):
        relay.run_once()
        clock.advance(seconds=60)
    row = outbox_rows(store)[0]
    assert row["delivery_state"] == "PENDING"
    assert row["publish_attempts"] == 3, (
        f"three failed publishes recorded {row['publish_attempts']} attempt(s); an uncounted retry "
        f"is an invisible outage"
    )
    store.close()


# ================================================ 4. duplicate delivery — AC-ADPT-010, AC-EVT-004

def test_a_redelivered_event_is_a_noop_not_an_error(tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    envelope = make_envelope()
    assert inbox.consume(envelope, handler).outcome is ConsumeOutcome.APPLIED
    digest = state_digest(store)
    for _ in range(5):
        result = inbox.consume(envelope, handler)
        assert result.outcome is ConsumeOutcome.DUPLICATE_NOOP
        assert result.is_noop
    assert len(handler.applied) == 1
    assert state_digest(store) == digest
    assert len(inbox_rows(store)) == 1
    store.close()


def test_two_consumers_each_get_the_event_once_and_do_not_dedup_each_other(tmp_path):
    """The dedup key is `(tenant, consumer_id, event_id)`. A shared namespace would starve one."""
    store = make_store(tmp_path)
    envelope = make_envelope()
    first = make_inbox(store, consumer_id="consumer-m2")
    second = make_inbox(store, consumer_id="consumer-m4")
    h1, h2 = RecordingHandler(store.conn), RecordingHandler(store.conn)
    assert first.consume(envelope, h1).outcome is ConsumeOutcome.APPLIED
    assert second.consume(envelope, h2).outcome is ConsumeOutcome.APPLIED
    assert first.consume(envelope, h1).outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert len(h1.applied) == 1 and len(h2.applied) == 1
    store.close()


def test_consuming_inside_a_callers_transaction_is_refused(tmp_path):
    """M-24 requires the handler's writes and the inbox row to share ONE commit, and only the
    owner of the transaction can guarantee that. A caller who opened their own would decide the
    commit boundary instead — the guarantee would become their discipline, which is the thing
    M-24 exists to stop being."""
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    store.conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(InboxError, match="transaction already open"):
            inbox.consume(make_envelope(), RecordingHandler(store.conn))
    finally:
        store.conn.rollback()
    store.close()


def test_a_handler_that_commits_is_a_defect_the_inbox_surfaces(tmp_path):
    """A handler that ends the transaction itself breaks the one-commit guarantee. It must not be
    absorbed silently — the exception is the correct outcome."""
    store = make_store(tmp_path)
    inbox = make_inbox(store)

    def committing_handler(envelope):
        store.conn.execute(STATE_CHANGE_SQL)
        store.conn.commit()
        raise RuntimeError("handler ended the transaction and then failed")

    with pytest.raises(RuntimeError):
        inbox.consume(make_envelope(), committing_handler)
    store.close()


def test_an_anonymous_consumer_is_refused(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(InboxError, match="consumer must be identifiable"):
        DedupInbox(store.conn, tenant=T_A, consumer_id="   ")
    store.close()


def test_the_inbox_row_survives_a_restart_and_the_redelivery_is_still_a_noop(tmp_path):
    """Durability, not memoisation. New store objects, new connection, same database file."""
    store = make_store(tmp_path)
    envelope = make_envelope()
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    inbox.consume(envelope, handler)
    digest = state_digest(store)
    store.close()

    restarted = make_store(tmp_path)
    fresh_inbox = make_inbox(restarted)
    fresh_handler = RecordingHandler(restarted.conn)
    assert fresh_inbox.consume(envelope, fresh_handler).outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert fresh_handler.applied == []
    assert state_digest(restarted) == digest
    restarted.close()


# ======================================= 5. consumer crashes — AC-RACE-008 / AC-RACE-009

def test_a_consumer_crash_before_the_inbox_commit_leaves_nothing_and_is_reprocessed(tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    envelope = make_envelope()
    before = state_digest(store)
    failing = FailingHandler(store.conn)
    with pytest.raises(RuntimeError, match="simulated consumer crash"):
        inbox.consume(envelope, failing)
    assert failing.calls == 1
    assert state_digest(store) == before, (
        "the failed handler's writes survived its rollback — the consumer's state change and its "
        "inbox row are not in one transaction"
    )
    assert inbox.seen(envelope.event_id) is None, (
        "a crashed consumption recorded an inbox row, so the event will never be retried"
    )

    good = RecordingHandler(store.conn)
    assert inbox.consume(envelope, good).outcome is ConsumeOutcome.APPLIED
    assert len(good.applied) == 1
    store.close()


def test_reprocessing_after_a_consumer_crash_reaches_the_same_state_digest(tmp_path):
    """AC-RACE-008's oracle is the DIGEST, not the absence of an exception."""
    store = make_store(tmp_path)
    clean = make_store(tmp_path, name="clean.db")
    envelope = make_envelope()

    make_inbox(clean).consume(envelope, RecordingHandler(clean.conn))
    reference = state_digest(clean)

    inbox = make_inbox(store)
    with pytest.raises(RuntimeError):
        inbox.consume(envelope, FailingHandler(store.conn))
    inbox.consume(envelope, RecordingHandler(store.conn))
    assert state_digest(store) == reference, (
        "a reprocessed event produced a different state than a cleanly processed one"
    )
    store.close()
    clean.close()


def test_a_consumer_crash_after_the_inbox_commit_is_not_reprocessed(tmp_path):
    """AC-RACE-009. The commit happened; the process died on the way to the next thing."""
    store = make_store(tmp_path)
    envelope = make_envelope()
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    inbox.consume(envelope, handler)
    store.close()

    restarted = make_store(tmp_path)
    fresh = make_inbox(restarted)
    fresh_handler = RecordingHandler(restarted.conn)
    assert fresh.consume(envelope, fresh_handler).outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert fresh_handler.applied == []
    restarted.close()


# ================================================== 6. ordering — AC-EVT-005, events/registry §8

@pytest.mark.parametrize("aggregate_type", sorted(STRICT_ORDER_AGGREGATE_TYPES))
def test_a_version_gap_in_a_strict_family_parks_instead_of_applying(aggregate_type, tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    later = make_envelope(aggregate_type=aggregate_type, aggregate_id="agg-1",
                          aggregate_version=3, seed=f"{aggregate_type}-v3")
    result = inbox.consume(later, handler)
    assert result.outcome is ConsumeOutcome.PARKED_VERSION_GAP, result.detail
    assert handler.applied == [], "a strict-family event applied out of order"
    assert [p.event_id for p in inbox.parked()] == [later.event_id]
    store.close()


def test_a_parked_gap_drains_in_order_when_the_missing_versions_arrive(tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    v2 = make_envelope(aggregate_version=2, seed="v2")
    v3 = make_envelope(aggregate_version=3, seed="v3")
    v1 = make_envelope(aggregate_version=1, seed="v1")

    assert inbox.consume(v3, handler).outcome is ConsumeOutcome.PARKED_VERSION_GAP
    assert inbox.consume(v2, handler).outcome is ConsumeOutcome.PARKED_VERSION_GAP
    result = inbox.consume(v1, handler)
    assert result.outcome is ConsumeOutcome.APPLIED
    assert [e.aggregate_version for e in handler.applied] == [1, 2, 3], (
        f"the drain applied versions {[e.aggregate_version for e in handler.applied]}; a strict "
        f"family must see 1, 2, 3 in that order"
    )
    assert inbox.parked() == []
    assert set(result.drained) == {v2.event_id, v3.event_id}
    store.close()


def test_an_order_tolerant_family_converges_without_parking(tmp_path):
    """F5 Observation is natural-key idempotent; §8 says such families tolerate arrival order."""
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    v3 = make_envelope(aggregate_type="observation", event_name="ObservationReceived",
                       producer_transition_id="OB-1", aggregate_version=3, seed="obs3")
    v1 = make_envelope(aggregate_type="observation", event_name="ObservationParsed",
                       producer_transition_id="OB-2", aggregate_version=1, seed="obs1")
    assert inbox.consume(v3, handler).outcome is ConsumeOutcome.APPLIED
    assert inbox.consume(v1, handler).outcome is ConsumeOutcome.STALE_NOOP, (
        "an order-tolerant family must not park, and a superseded version must not re-apply"
    )
    assert inbox.parked() == []
    assert len(handler.applied) == 1
    store.close()


def test_a_superseded_version_in_an_order_tolerant_family_is_recorded_and_not_reapplied(tmp_path):
    """STALE_NOOP belongs to the ORDER-TOLERANT families, and only to them.

    F5 is natural-key idempotent, so a version below the high-water mark is a superseded fact and
    applying it would let an older observation overwrite a newer one. A strict family reads the
    same shape differently (see the EF-2 sibling node): it is gap-parked, so a low version can only
    be a co-emitted sibling, and discarding it would lose a fact.
    """
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    common = dict(aggregate_type="observation", aggregate_id="obs-s",
                  event_name="ObservationReceived", producer_transition_id="OB-1")
    inbox.consume(make_envelope(aggregate_version=1, seed="s1", **common), handler)
    inbox.consume(make_envelope(aggregate_version=2, seed="s2", **common), handler)
    late = make_envelope(aggregate_version=1, seed="late-sibling-of-v1", **common)
    result = inbox.consume(late, handler)
    assert result.outcome is ConsumeOutcome.STALE_NOOP
    assert len(handler.applied) == 2
    assert inbox.seen(late.event_id) == "STALE_NOOP", (
        "a stale event must be RECORDED, or it is reconsidered on every redelivery forever"
    )
    store.close()


def test_a_strict_family_never_discards_a_late_sibling_as_stale(tmp_path):
    """The inverse of the node above, stated as its own assertion so a regression is unambiguous."""
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    inbox.consume(make_envelope(aggregate_version=1, seed="strict-1"), handler)
    inbox.consume(make_envelope(aggregate_version=2, seed="strict-2",
                                event_name="EffectRecorded",
                                producer_transition_id="PL-12"), handler)
    late_sibling = make_envelope(aggregate_version=1, seed="strict-late-sibling",
                                 event_name="PolicyEvaluated", producer_transition_id="PL-2")
    assert inbox.consume(late_sibling, handler).outcome is ConsumeOutcome.APPLIED, (
        "a strict family discarded a co-emitted sibling as superseded — that is a lost fact in a "
        "version-monotonic history"
    )
    assert len(handler.applied) == 3
    store.close()


def test_the_relay_publishes_one_aggregate_in_version_order(tmp_path):
    store = make_store(tmp_path)
    clock = Clock()
    for version in (1, 2, 3, 4):
        emit_with_state_change(store, make_envelope(aggregate_version=version, seed=f"o{version}"))
    sink = RecordingSink()
    make_relay(store, sink, clock=clock).run_once()
    assert [e.aggregate_version for e in sink.delivered] == [1, 2, 3, 4]
    store.close()


def test_a_failed_publish_withholds_the_rest_of_that_aggregate(tmp_path):
    """Sending version 4 after version 3 failed is the out-of-order delivery the lease prevents."""
    store = make_store(tmp_path)
    clock = Clock()
    for version in (1, 2, 3):
        emit_with_state_change(store, make_envelope(aggregate_version=version, seed=f"w{version}"))

    class FailsOnSecond(RecordingSink):
        def __call__(self, envelope):
            if envelope.aggregate_version == 2:
                raise RuntimeError("sink refused version 2")
            super().__call__(envelope)

    sink = FailsOnSecond()
    result = make_relay(store, sink, clock=clock).run_once()
    assert [e.aggregate_version for e in sink.delivered] == [1]
    assert len(result.withheld_for_order) == 1, (
        f"version 3 was not withheld after version 2 failed: {result}"
    )
    assert {r["delivery_state"] for r in outbox_rows(store)} == {"PENDING", "PUBLISHED"}
    store.close()


# ============================================================= 7. concurrent relays

def test_two_concurrent_relays_publish_every_event_exactly_once(tmp_path):
    """Duplicate delivery is HARMLESS, but it should not be GRATUITOUS."""
    store = make_store(tmp_path)
    clock = Clock()
    for i in range(6):
        emit_with_state_change(
            store, make_envelope(aggregate_id=f"pi-{i}", aggregate_version=1, seed=f"c{i}"))

    second = sqlite3.connect(store.db_path, timeout=30.0)
    second.row_factory = sqlite3.Row
    second.execute("PRAGMA busy_timeout=30000")
    try:
        sink_a, sink_b = RecordingSink(), RecordingSink()
        relay_a = make_relay(store, sink_a, relay_id="relay-a", clock=clock)
        from freight_recon.event_outbox import OutboxRelay

        relay_b = OutboxRelay(second, tenant=T_A, publish=sink_b, relay_id="relay-b", clock=clock)
        relay_a.run_once(max_aggregates=3)
        relay_b.run_once(max_aggregates=3)
        relay_a.run_once()
        relay_b.run_once()
        delivered = sink_a.event_ids + sink_b.event_ids
        assert len(delivered) == 6, f"expected 6 deliveries, got {len(delivered)}"
        assert len(set(delivered)) == 6, (
            f"two relays published the same event: {sorted(delivered)}"
        )
        assert set(sink_a.event_ids) & set(sink_b.event_ids) == set()
    finally:
        second.close()
    store.close()


# ================================================== 8. tenant isolation — [C-1], AC-RACE-015

def test_an_event_for_another_tenant_is_rejected_before_the_handler_and_before_any_write(tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store, tenant=T_A)
    handler = RecordingHandler(store.conn)
    foreign = make_envelope(tenant=T_B, seed="foreign")
    before = state_digest(store)
    result = inbox.consume(foreign, handler)
    assert result.outcome is ConsumeOutcome.REJECTED_CROSS_TENANT
    assert handler.applied == [], "a cross-tenant event reached a handler"
    assert state_digest(store) == before, (
        "a cross-tenant rejection wrote something — even an inbox row keyed by the foreign tenant "
        "would itself be the cross-tenant write"
    )
    assert inbox_rows(store, T_B) == []
    store.close()


def test_the_cross_tenant_rejection_is_observable_as_a_security_signal(tmp_path):
    store = make_store(tmp_path)
    seen: list[dict] = []
    inbox = make_inbox(store, tenant=T_A, observer=seen.append)
    inbox.consume(make_envelope(tenant=T_B, seed="foreign-observed"), RecordingHandler(store.conn))
    kinds = [e["kind"] for e in seen]
    assert "CrossTenantAccessAttempted" in kinds, (
        f"a tenant boundary crossing must be observable, not merely refused; saw {kinds}"
    )
    store.close()


def test_the_outbox_refuses_an_envelope_for_another_tenant(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(OutboxTenantMismatch, match="never crosses a tenant"):
        with transactional_emit(store.conn, tenant=T_A) as session:
            session.emit(make_envelope(tenant=T_B, seed="foreign-emit"))
    assert outbox_rows(store, T_B) == []
    store.close()


def test_two_tenants_may_hold_the_same_event_shape_without_interference(tmp_path):
    """AC-RACE-015 at the transport: identical aggregates, two tenants, zero collision."""
    store_a = make_store(tmp_path, tenant=T_A, name="shared.db")
    store_b = make_store(tmp_path, tenant=T_B, name="shared.db")
    emit_with_state_change(store_a, make_envelope(tenant=T_A, seed="same-shape-a"))
    emit_with_state_change(store_b, make_envelope(tenant=T_B, seed="same-shape-b"))
    assert len(outbox_rows(store_a, T_A)) == 1
    assert len(outbox_rows(store_a, T_B)) == 1

    sink = RecordingSink()
    make_relay(store_a, sink, tenant=T_A).run_once()
    assert [e.tenant_id for e in sink.delivered] == [T_A], (
        "a relay bound to one tenant published another tenant's event"
    )
    store_a.close()
    store_b.close()


@pytest.mark.parametrize("sentinel", ["default", "global", "test", "unknown", "shared"])
def test_a_sentinel_tenant_cannot_carry_an_event(sentinel, tmp_path):
    """`require_tenant` is reused, so "default" is not a tenant here either.

    It surfaces as a `MalformedEnvelope` rather than the bare `InvalidTenant`, deliberately: every
    way an envelope can be invalid must be ONE exception family, or the inbox's malformed-event
    refusal has a hole shaped exactly like a missing tenant.
    """
    with pytest.raises(MalformedEnvelope, match="not a tenant identity"):
        make_envelope(tenant=sentinel, seed=f"sentinel-{sentinel}")

    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    document = make_envelope(seed="sentinel-doc").as_document()
    document["tenant_id"] = sentinel
    assert inbox.consume(document, handler).outcome is ConsumeOutcome.REJECTED_MALFORMED
    assert handler.applied == []
    store.close()


# ======================================== 9. malformed envelopes — AC-EVT-001/002, injection

def test_a_malformed_envelope_is_rejected_before_the_handler(tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    before = state_digest(store)
    result = inbox.consume({"event_id": "not-a-uuid"}, handler)
    assert result.outcome is ConsumeOutcome.REJECTED_MALFORMED
    assert handler.applied == []
    assert state_digest(store) == before
    store.close()


@pytest.mark.parametrize("field_name", [
    "event_id", "event_name", "event_version", "occurred_at", "recorded_at", "tenant_id",
    "aggregate_type", "aggregate_id", "aggregate_version", "causation_id", "correlation_id",
    "producer_component", "producer_transition_id", "actor_type", "actor_id", "trace_id",
    "payload",
])
def test_every_always_required_envelope_field_must_be_supplied(field_name):
    """§1's `R` column, one node per field. A defaulted `R` field is a field nobody had to think
    about, and `causation_id` is in this list on purpose: `None` is legal, silence is not."""
    document = make_envelope(seed=f"required-{field_name}").as_document()
    document.pop(field_name, None)
    with pytest.raises(MissingEnvelopeField):
        EventEnvelope.from_document(document)


@pytest.mark.parametrize("field_name,value,expected", [
    ("event_id", "not-a-uuid", MalformedEnvelope),
    ("event_id", "00000000-0000-1000-8000-000000000000", MalformedEnvelope),   # v1, not v4
    ("event_name", "checkpoint_passed", MalformedEnvelope),
    ("event_version", 0, MalformedEnvelope),
    ("aggregate_version", 0, MalformedEnvelope),
    ("aggregate_type", "PipelineInstance", MalformedEnvelope),
    ("producer_transition_id", "the pipeline step", MalformedEnvelope),
    ("actor_type", "robot", MalformedEnvelope),
    ("occurred_at", "2026-08-12T09:00:00Z", MalformedEnvelope),        # no ms precision
    ("recorded_at", "2026-08-12 09:00:00.000Z", MalformedEnvelope),    # not RFC-3339
    ("tenant_id", "  ", EnvelopeError),
    ("payload", "a string", MalformedEnvelope),
])
def test_a_field_that_cannot_mean_what_it_claims_is_refused(field_name, value, expected):
    document = make_envelope(seed=f"bad-{field_name}-{value}").as_document()
    document[field_name] = value
    with pytest.raises(expected):
        EventEnvelope.from_document(document)


def test_recorded_at_may_not_precede_occurred_at():
    document = make_envelope(seed="time-travel").as_document()
    document["recorded_at"] = "2026-08-12T08:59:59.999Z"
    with pytest.raises(MalformedEnvelope, match="precedes occurred_at"):
        EventEnvelope.from_document(document)


def test_an_unknown_envelope_field_is_refused_rather_than_dropped():
    """A rider on a fact is either a newer schema or an injection. Both are refusals."""
    document = make_envelope(seed="rider").as_document()
    document["provenance_class"] = "OWNER_ASSERTED"
    with pytest.raises(MalformedEnvelope, match="does not define"):
        EventEnvelope.from_document(document)


def test_a_payload_claiming_authority_is_still_only_data(tmp_path):
    """CLAUDE.md rule 9 / AC-EVT-012: an event payload cannot authorize anything.

    The transport hands the payload to a handler and does nothing with its contents. This node
    proves the negative structurally: the modules never read a payload key at all.
    """
    import inspect

    from freight_recon import event_envelope, event_inbox, event_outbox

    for module in (event_outbox, event_inbox):
        source = inspect.getsource(module)
        assert 'payload[' not in source and '.payload.get' not in source, (
            f"{module.__name__} reads inside an event payload; a transport that inspects payload "
            f"contents is one edit away from acting on them"
        )
    assert 'payload' in inspect.getsource(event_envelope), "the envelope must at least carry one"

    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    crafted = make_envelope(
        seed="crafted-authority",
        payload={"approved": True, "authority": "owner", "gate_decision": "AUTONOMOUS_WITHIN_CAPS",
                 "provenance_class": "OWNER_ASSERTED"},
    )
    assert inbox.consume(crafted, handler).outcome is ConsumeOutcome.APPLIED
    grants = store.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
    witnesses = store.conn.execute("SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0]
    assert (grants, witnesses) == (0, 0), (
        "consuming a payload that asserts approval produced authorization state"
    )
    store.close()


# ================================================= 10. dangling references — AC-EVT-006, M-26

def test_an_event_referencing_a_missing_aggregate_is_parked_not_dropped(tmp_path):
    store = make_store(tmp_path)
    existing: set[tuple[str, str]] = set()
    inbox = make_inbox(store, reference_resolver=lambda t, i: (t, i) in existing)
    handler = RecordingHandler(store.conn)
    event = make_envelope(seed="dangling", entity_versions={"work_item:wi-9": 1})
    result = inbox.consume(event, handler)
    assert result.outcome is ConsumeOutcome.PARKED_MISSING_AGGREGATE, result.detail
    assert handler.applied == []
    parks = inbox.parked()
    assert [(p.referenced_type, p.referenced_id) for p in parks] == [("work_item", "wi-9")]
    assert parks[0].park_reason == "MISSING_AGGREGATE"
    store.close()


def test_parked_events_drain_in_arrival_order_when_the_referent_appears(tmp_path):
    store = make_store(tmp_path)
    existing: set[tuple[str, str]] = set()
    inbox = make_inbox(store, reference_resolver=lambda t, i: (t, i) in existing)
    handler = RecordingHandler(store.conn)

    # Three order-tolerant events, all waiting on the same missing work item, parked in this order.
    waiting = [
        make_envelope(aggregate_type="observation", event_name="ObservationReceived",
                      producer_transition_id="OB-1", aggregate_id=f"obs-{n}",
                      aggregate_version=1, seed=f"park-{n}",
                      entity_versions={"work_item:wi-9": 1})
        for n in ("alpha", "beta", "gamma")
    ]
    for event in waiting:
        assert inbox.consume(event, handler).outcome is ConsumeOutcome.PARKED_MISSING_AGGREGATE
    assert [p.arrival_sequence for p in inbox.parked()] == [1, 2, 3]

    # The work item is created. Its own creation event names no missing reference.
    existing.add(("work_item", "wi-9"))
    creation = make_envelope(aggregate_type="work_item", event_name="WorkItemCreated",
                             producer_transition_id="WI-1", aggregate_id="wi-9",
                             aggregate_version=1, seed="wi-creation")
    result = inbox.consume(creation, handler)
    assert result.outcome is ConsumeOutcome.APPLIED
    assert list(result.drained) == [e.event_id for e in waiting], (
        f"parked events drained out of arrival order: {result.drained}"
    )
    assert [e.event_id for e in handler.applied][1:] == [e.event_id for e in waiting]
    assert inbox.parked() == []
    store.close()


def test_a_chain_of_parks_across_aggregates_drains_all_the_way_down(tmp_path):
    """Draining one park can bring the aggregate a SECOND cohort is waiting on into existence.

    Scanning only the originally-applied aggregate would drain the first link and leave the rest
    parked until their TTLs expired — a correctness failure that looks exactly like a slow system.
    """
    store = make_store(tmp_path)
    existing: set[tuple[str, str]] = set()

    def resolver(aggregate_type: str, aggregate_id: str) -> bool:
        return (aggregate_type, aggregate_id) in existing

    inbox = make_inbox(store, reference_resolver=resolver)

    class CreatingHandler(RecordingHandler):
        """A handler whose applying an event is what makes its aggregate exist."""

        def __call__(self, envelope):
            super().__call__(envelope)
            existing.add((envelope.aggregate_type, envelope.aggregate_id))

    handler = CreatingHandler(store.conn)

    # obs-2 waits on obs-1's aggregate; obs-1 waits on the work item. Neither exists yet.
    link_two = make_envelope(aggregate_type="observation", event_name="ObservationBound",
                             producer_transition_id="OB-3", aggregate_id="obs-2",
                             aggregate_version=1, seed="chain-2",
                             entity_versions={"observation:obs-1": 1})
    link_one = make_envelope(aggregate_type="observation", event_name="ObservationReceived",
                             producer_transition_id="OB-1", aggregate_id="obs-1",
                             aggregate_version=1, seed="chain-1",
                             entity_versions={"work_item:wi-root": 1})
    assert inbox.consume(link_two, handler).outcome is ConsumeOutcome.PARKED_MISSING_AGGREGATE
    assert inbox.consume(link_one, handler).outcome is ConsumeOutcome.PARKED_MISSING_AGGREGATE

    existing.add(("work_item", "wi-root"))
    root = make_envelope(aggregate_type="work_item", event_name="WorkItemCreated",
                         producer_transition_id="WI-1", aggregate_id="wi-root",
                         aggregate_version=1, seed="chain-root")
    result = inbox.consume(root, handler)
    assert result.outcome is ConsumeOutcome.APPLIED
    assert result.drain_limit_reached is False
    assert set(result.drained) == {link_one.event_id, link_two.event_id}, (
        f"the drain stopped at the first link: {result.drained}"
    )
    assert inbox.parked() == []
    store.close()


def test_a_drained_park_is_resolved_in_the_same_commit_that_applies_it(tmp_path):
    """A park still marked PARKED for a consumed event would later expire onto someone's desk."""
    store = make_store(tmp_path)
    existing: set[tuple[str, str]] = set()
    inbox = make_inbox(store, reference_resolver=lambda t, i: (t, i) in existing)
    handler = RecordingHandler(store.conn)
    waiting = make_envelope(aggregate_type="observation", event_name="ObservationReceived",
                            producer_transition_id="OB-1", aggregate_id="obs-x",
                            aggregate_version=1, seed="same-commit",
                            entity_versions={"work_item:wi-2": 1})
    inbox.consume(waiting, handler)
    existing.add(("work_item", "wi-2"))
    inbox.consume(make_envelope(aggregate_type="work_item", event_name="WorkItemCreated",
                                producer_transition_id="WI-1", aggregate_id="wi-2",
                                aggregate_version=1, seed="same-commit-root"), handler)
    row = store.conn.execute(
        "SELECT park_state, resolved_at FROM pending_references WHERE event_id = ?",
        (waiting.event_id,),
    ).fetchone()
    assert row["park_state"] == "DRAINED" and row["resolved_at"] is not None
    assert inbox.expire_overdue() == []
    store.close()


def test_a_redelivery_of_a_parked_event_is_counted_and_changes_nothing_else(tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store, reference_resolver=lambda t, i: False)
    handler = RecordingHandler(store.conn)
    event = make_envelope(seed="parked-redelivery", entity_versions={"work_item:wi-1": 1})
    inbox.consume(event, handler)
    result = inbox.consume(event, handler)
    assert result.outcome is ConsumeOutcome.ALREADY_PARKED
    assert result.is_noop
    assert len(inbox.parked()) == 1
    assert inbox.parked()[0].attempts == 2
    store.close()


def test_a_parked_reference_that_never_resolves_expires_with_an_accountable_owner(tmp_path):
    """M-26: *a permanently dangling reference is a real problem, and it gets a human.*"""
    store = make_store(tmp_path)
    clock = Clock()
    inbox = make_inbox(store, clock=clock, reference_resolver=lambda t, i: False,
                       park_ttl=timedelta(hours=6))
    handler = RecordingHandler(store.conn)
    event = make_envelope(seed="never-resolves", entity_versions={"work_item:wi-lost": 1},
                          accountable_owner_id="owner-dispatch-lead")
    inbox.consume(event, handler)

    clock.advance(hours=5)
    assert inbox.expire_overdue() == [], "a park expired before its TTL"

    clock.advance(hours=2)
    expired = inbox.expire_overdue()
    assert len(expired) == 1
    assert expired[0].accountable_owner_id == "owner-dispatch-lead", (
        "an expired park must name the human who inherits it (I1), not merely record a failure"
    )
    assert inbox.parked() == [], "an expired park is still listed as parked"
    store.close()


def test_the_expiry_sweep_is_observable(tmp_path):
    store = make_store(tmp_path)
    clock = Clock()
    seen: list[dict] = []
    inbox = make_inbox(store, clock=clock, reference_resolver=lambda t, i: False,
                       park_ttl=timedelta(hours=1), observer=seen.append)
    inbox.consume(make_envelope(seed="observed-expiry", entity_versions={"work_item:w": 1},
                                accountable_owner_id="owner-1"), RecordingHandler(store.conn))
    clock.advance(hours=2)
    inbox.expire_overdue()
    assert any(e["kind"] == "PendingReferenceExpired" for e in seen), [e["kind"] for e in seen]
    store.close()


def test_reference_parking_is_off_and_says_so_when_no_resolver_is_supplied(tmp_path):
    """An inbox that cannot answer "does this exist" must not pretend the answer is yes."""
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    assert inbox.reference_parking_enabled is False
    with_resolver = make_inbox(store, consumer_id="c2", reference_resolver=lambda t, i: True)
    assert with_resolver.reference_parking_enabled is True
    store.close()


def test_an_event_never_parks_waiting_for_its_own_aggregate(tmp_path):
    """The creation event IS the aggregate arriving; requiring it to pre-exist parks it forever."""
    store = make_store(tmp_path)
    inbox = make_inbox(store, reference_resolver=lambda t, i: False)
    handler = RecordingHandler(store.conn)
    creation = make_envelope(aggregate_type="work_item", event_name="WorkItemCreated",
                             producer_transition_id="WI-1", aggregate_id="wi-new",
                             aggregate_version=1, seed="self-reference",
                             entity_versions={"work_item:wi-new": 1})
    assert inbox.consume(creation, handler).outcome is ConsumeOutcome.APPLIED
    store.close()


# ================================================ 11. immutability and append-only — S8, C-8

def test_the_stored_envelope_cannot_be_edited(tmp_path):
    store = make_store(tmp_path)
    emit_with_state_change(store, make_envelope())
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        store.conn.execute("UPDATE event_outbox SET envelope_json = '{}'")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        store.conn.execute("UPDATE event_outbox SET tenant = 'tenant-beta'")
    store.close()


def test_an_emitted_event_cannot_be_deleted(tmp_path):
    store = make_store(tmp_path)
    emit_with_state_change(store, make_envelope())
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.conn.execute("DELETE FROM event_outbox")
    store.close()


def test_an_inbox_row_cannot_be_updated_or_deleted(tmp_path):
    """Both are the same attack: re-arm a duplicate delivery so it becomes a second effect."""
    store = make_store(tmp_path)
    make_inbox(store).consume(make_envelope(), RecordingHandler(store.conn))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.conn.execute("UPDATE event_inbox SET outcome = 'STALE_NOOP'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.conn.execute("DELETE FROM event_inbox")
    store.close()


def test_a_parked_row_cannot_be_deleted_or_have_its_arrival_order_rewritten(tmp_path):
    store = make_store(tmp_path)
    inbox = make_inbox(store, reference_resolver=lambda t, i: False)
    inbox.consume(make_envelope(seed="immutable-park", entity_versions={"work_item:w": 1}),
                  RecordingHandler(store.conn))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.conn.execute("DELETE FROM pending_references")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        store.conn.execute("UPDATE pending_references SET arrival_sequence = 99")
    store.close()


def test_the_delivery_bookkeeping_columns_remain_writable(tmp_path):
    """The immutability trigger must not be so broad that the relay cannot do its job."""
    store = make_store(tmp_path)
    clock = Clock()
    emit_with_state_change(store, make_envelope())
    make_relay(store, RecordingSink(), clock=clock).run_once()
    assert outbox_rows(store)[0]["delivery_state"] == "PUBLISHED"
    store.close()


@pytest.mark.parametrize("trigger", sorted(P5_TRIGGERS))
def test_a_missing_append_only_trigger_is_a_readiness_problem(trigger, tmp_path):
    """Mutate the real structure and confirm the oracle notices. A guard never seen to fail is a
    decoration."""
    store = make_store(tmp_path)
    assert phase5_readiness_problems(store.conn) == []
    store.conn.execute(f"DROP TRIGGER {trigger}")
    problems = phase5_readiness_problems(store.conn)
    assert any(trigger in p for p in problems), problems
    assert any(trigger in p for p in schema_readiness_problems(store.conn)), (
        "the phase-5 oracle noticed but the composed readiness contract did not"
    )
    store.close()


@pytest.mark.parametrize("index", sorted(P5_INDEXES))
def test_a_missing_event_transport_index_is_a_readiness_problem(index, tmp_path):
    store = make_store(tmp_path)
    store.conn.execute(f"DROP INDEX {index}")
    assert any(index in p for p in phase5_readiness_problems(store.conn))
    store.close()


@pytest.mark.parametrize("table", sorted(P5_TENANT_TABLES))
def test_every_event_transport_table_is_tenant_first(table, tmp_path):
    """[C-1]. A tenant COLUMN is not tenant isolation; tenant must be FIRST in the key."""
    store = make_store(tmp_path)
    pk = [r[1] for r in sorted(
        (r for r in store.conn.execute(f"PRAGMA table_info({table})").fetchall() if r[5]),
        key=lambda r: r[5],
    )]
    assert pk and pk[0] == "tenant", f"{table} primary key is {pk}; tenant must come first"
    store.close()


def test_no_event_transport_table_is_a_second_effect_ledger(tmp_path):
    """ADR-009 / CLAUDE.md rule 8: the Commit Key identifies an EFFECT and lives in ONE ledger."""
    store = make_store(tmp_path)
    for table in P5_TENANT_TABLES:
        columns = {r[1] for r in store.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        assert "commit_key" not in columns, (
            f"{table} carries a commit_key: the outbox records FACTS, it does not reserve effects, "
            f"and a second table holding effect identity is a second effect authority"
        )
    store.close()


def test_a_tampered_outbox_row_is_refused_rather_than_republished(tmp_path):
    """The digest is checked on read, so editing around the triggers still does not produce a fact."""
    store = make_store(tmp_path)
    emit_with_state_change(store, make_envelope())
    store.conn.execute("DROP TRIGGER trg_event_outbox_envelope_immutable")
    tampered = make_envelope(seed="tampered", payload={"pipeline_instance_id": "someone-elses"})
    store.conn.execute("UPDATE event_outbox SET envelope_json = ?", (tampered.to_json(),))
    store.conn.commit()
    from freight_recon.event_outbox import OutboxError

    with pytest.raises(OutboxError, match="does not match its recorded digest"):
        make_outbox(store).pending()
    store.close()


# ============================================== 12. serialization — ev_v1, floats, determinism

def test_the_canonical_bytes_are_stable_across_processes_and_orderings():
    """Two systems, same fact, same bytes — including when the caller built the dict differently."""
    first = make_envelope(seed="stable", payload={"b": 2, "a": 1, "nested": {"z": 1, "y": 2}})
    second = make_envelope(seed="stable", payload={"nested": {"y": 2, "z": 1}, "a": 1, "b": 2})
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.digest() == second.digest()
    assert first.canonical_bytes().startswith(ENVELOPE_SERIALIZATION_VERSION.encode())


def test_a_json_round_trip_reproduces_the_digest_exactly():
    """This is what makes a redelivery byte-identical: the stored form IS the canonical form."""
    original = make_envelope(seed="roundtrip", payload={
        "amount": Money(285000, "GBP"), "note": "café", "refs": ["b", "a"], "missing": None,
    })
    rehydrated = EventEnvelope.from_json(original.to_json())
    assert rehydrated.digest() == original.digest()
    assert rehydrated.to_json() == original.to_json()


def test_a_list_keeps_its_declared_order_unlike_a_material_fact_set():
    """`ConflictRaised.parties[]` is an ordered fact. fp_v1 sorts; ev_v1 must not."""
    forward = make_envelope(seed="ordered", payload={"parties": ["carrier", "broker"]})
    reversed_ = make_envelope(seed="ordered", payload={"parties": ["broker", "carrier"]})
    assert forward.digest() != reversed_.digest(), (
        "reordering a list did not change the event's identity — the payload's order is not "
        "being preserved"
    )


def test_null_and_absent_are_different_facts_in_a_payload():
    looked = make_envelope(seed="nullness", payload={"delivered_at": None})
    did_not_look = make_envelope(seed="nullness", payload={})
    assert looked.digest() != did_not_look.digest()


@pytest.mark.parametrize("value", [2850.00, 2850.5])
def test_a_float_anywhere_in_a_payload_is_refused(value):
    with pytest.raises(UnserializableEvent, match="floats are forbidden"):
        make_envelope(seed=f"float-{value}", payload={"amount": value})


def test_money_travels_as_integer_minor_units():
    envelope = make_envelope(seed="money", payload={"amount": Money(285000, "GBP")})
    assert '"amount_minor":285000' in envelope.to_json()
    assert "285000.0" not in envelope.to_json()


def test_a_set_is_refused_because_it_has_no_declared_order():
    with pytest.raises(UnserializableEvent, match="no declared order"):
        make_envelope(seed="setty", payload={"parties": {"a", "b"}})


def test_the_three_derived_keys_are_what_the_registry_says_they_are():
    envelope = make_envelope(seed="keys", aggregate_id="pi-7", aggregate_version=4)
    assert envelope.ordering_key == (T_A, "pi-7", 4)
    assert envelope.partition_key == T_A
    assert envelope.dedup_key == (T_A, envelope.event_id)


def test_the_strict_ordering_families_are_exactly_the_five_the_registry_names():
    """Exact SET equality, not a count: a same-count substitution must fail."""
    assert set(STRICT_ORDER_AGGREGATE_TYPES) == {
        "pipeline_instance",   # F2 Pipeline
        "effect_grant",        # F3 External Effect / Grant
        "approval",            # F4 Approval
        "policy",              # F11 Policy
        "brake",               # F13 Brake
    }


def test_the_actor_types_are_exactly_the_four_the_envelope_defines():
    assert ACTOR_TYPES == {"human", "system", "detector", "model"}


def test_the_idempotency_identity_is_transition_natural_and_excludes_the_commit_key():
    """ADR-009: the Commit Key answers "is this the same EFFECT". Dedup answers "the same FACT".

    They are different questions and may not share a field (CLAUDE.md rule 8). An outbox identity
    that contained a commit key would make two events about one effect indistinguishable, and an
    approval amount change would split an event identity that must not split.
    """
    envelope = make_envelope(seed="identity", payload={"commit_key": "ck_v1:whatever"})
    identity = envelope.idempotency_identity
    assert identity.startswith("tn_v1|")
    assert "ck_v1" not in identity
    for part in (T_A, "pipeline_instance", "pi-4471", "1", "PL-8", "CheckpointPassed"):
        assert part in identity.split("|"), f"{part!r} missing from {identity!r}"


def test_an_externally_observed_event_may_carry_a_source_natural_identity():
    """§4's other branch: a webhook's identity is the source's, not a transition's."""
    envelope = make_envelope(
        seed="source-natural", aggregate_type="observation", event_name="ObservationReceived",
        producer_transition_id="OB-1",
        idempotency_identity="sn_v1|tenant-alpha|tms:truckingoffice|ext-99|sha256:abc",
    )
    assert envelope.idempotency_identity.startswith("sn_v1|")


# ================================================ 13. the capability ships DARK

def test_the_event_transport_imports_no_adapter_and_reaches_no_external_system():
    """P4's containment is not weakened by P5. An event is a FACT, never authority."""
    import ast

    src = ROOT / "src" / "freight_recon"
    forbidden = {
        "requests", "httpx", "urllib", "socket", "smtplib", "imaplib", "subprocess",
        "playwright", "selenium",
    }
    # DISCOVERED, never listed (H-6). A hand-typed list would silently stop covering a fifth
    # transport module the moment one is added - which is exactly how containment decays.
    modules = sorted(src.glob("event_*.py")) + sorted(src.glob("migrations/phase5_*.py"))
    assert len(modules) >= 4, f"transport-module discovery collapsed: {modules}"
    for path in modules:
        name = path.relative_to(src).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        leaked = imported & forbidden
        assert not leaked, f"{name} imports {sorted(leaked)}: the transport must reach nothing"


def test_a_relay_cannot_be_constructed_without_an_explicit_sink(tmp_path):
    """No default egress. A relay that knew how to reach the world would be an unreviewed path."""
    from freight_recon.event_outbox import OutboxError, OutboxRelay

    store = make_store(tmp_path)
    with pytest.raises(TypeError):
        OutboxRelay(store.conn, tenant=T_A, relay_id="r")           # type: ignore[call-arg]
    with pytest.raises(OutboxError, match="no default sink"):
        OutboxRelay(store.conn, tenant=T_A, publish=None, relay_id="r")  # type: ignore[arg-type]
    store.close()


def test_consuming_events_produces_no_witness_no_grant_and_no_claim(tmp_path):
    """Replay is U5.5's, but the inbox must already be inert: events cannot mint authority."""
    store = make_store(tmp_path)
    inbox = make_inbox(store)
    handler = RecordingHandler(store.conn)
    for version, name, transition in (
        (1, "CheckpointPassed", "PL-8"), (2, "EffectRecorded", "PL-12"),
        (3, "PipelineClosed", "PL-14"),
    ):
        inbox.consume(make_envelope(aggregate_version=version, event_name=name,
                                    producer_transition_id=transition, seed=f"dark-{version}"),
                      handler)
    counts = {
        table: store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("checkpoint_witnesses", "effect_grants")
    }
    assert counts == {"checkpoint_witnesses": 0, "effect_grants": 0}, counts
    assert len(handler.applied) == 3, "the battery would be vacuous if nothing was consumed"
    store.close()


def test_the_production_gate_registry_is_untouched_by_this_unit():
    """R-07 stays CONTAINED: no production gate is registered, and none is registered here."""
    import inspect

    from freight_recon import event_envelope, event_inbox, event_outbox

    for module in (event_envelope, event_outbox, event_inbox):
        source = inspect.getsource(module)
        for symbol in ("GateRegistry", "GateEntry", "execute_effect", "mint_grant",
                       "CheckpointPassed("):
            assert symbol not in source, (
                f"{module.__name__} names {symbol!r}: the transport must not touch the effect "
                f"boundary or the checkpoint kernel"
            )


# ==================================================== 14. the battery is not vacuous

def test_the_state_digest_oracle_actually_moves_when_state_changes(tmp_path):
    """Every no-op assertion in this file rests on this. An inert oracle would pass them all."""
    store = make_store(tmp_path)
    before = state_digest(store)
    make_inbox(store).consume(make_envelope(), RecordingHandler(store.conn))
    assert state_digest(store) != before, (
        "the digest did not move for a real applied event — every no-op assertion in this module "
        "would then be vacuous"
    )
    store.close()


def test_deterministic_event_ids_are_v4_shaped_and_reproducible():
    import uuid as _uuid

    first, second = deterministic_event_id("seed-a"), deterministic_event_id("seed-a")
    assert first == second
    assert first != deterministic_event_id("seed-b")
    assert _uuid.UUID(first).version == 4


def test_the_required_field_battery_covers_every_defaultless_envelope_field():
    """The parametrized list above must not silently fall behind the dataclass."""
    from dataclasses import MISSING

    defaultless = {
        name for name, f in EventEnvelope.__dataclass_fields__.items()
        if f.default is MISSING and f.default_factory is MISSING
    }
    covered = {
        "event_id", "event_name", "event_version", "occurred_at", "recorded_at", "tenant_id",
        "aggregate_type", "aggregate_id", "aggregate_version", "causation_id", "correlation_id",
        "producer_component", "producer_transition_id", "actor_type", "actor_id", "trace_id",
        "payload",
    }
    assert defaultless == covered, (
        f"the required-field battery and the envelope disagree: only-in-envelope "
        f"{sorted(defaultless - covered)}, only-in-battery {sorted(covered - defaultless)}"
    )


def test_the_epoch_clock_is_used_rather_than_the_wall_clock():
    assert EPOCH.tzinfo is not None
    clock = Clock()
    assert clock() == EPOCH
    clock.advance(hours=3)
    assert clock() != EPOCH
