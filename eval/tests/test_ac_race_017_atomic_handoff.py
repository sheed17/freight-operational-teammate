"""AC-RACE-017 — downstream Work Item creation and the source transition are ONE atomic handoff.

recovery-and-compensation-acceptance.md AC-RACE-017:
    "downstream Work Item creation crash ⇒ the source transition does NOT advance (atomic handoff)
     — no responsibility gap."

The frozen P8 phase-acceptance review (p8-phase-acceptance-review-319debc.md §4) recorded that
AC-RACE-017 had **no oracle anywhere** in eval/ or scripts/. This is that oracle, and only that.

### THE HANDOFF UNDER TEST IS REAL PRODUCT ATOMICITY, NOT A MODEL.
In an event-sourced system the "downstream Work Item creation" is the durable emission of
`WorkItemCreated` (WI-1) and the "source transition advancing" is the source trigger being marked
consumed. `event_inbox.DedupInbox.consume` runs the handler and writes its own receipt in ONE
commit (M-24): "A handler exception is not an outcome — it propagates, having rolled everything
back" (event_inbox.py §ConsumeOutcome). So the atomic handoff we assert is the inbox's real
one-commit contract — the same primitive the M1/M2 machines rely on.

### THE CRASH IS STAGED THROUGH THE REAL WRITE PATH (phase6_crash_kit), NEVER by luck or sleep.
`event_outbox` carries `UNIQUE (tenant, idempotency_identity)`; planting a row on the identity the
downstream `WorkItemCreated` is about to occupy makes the SECOND half of the handler's work — the
emission that IS the downstream creation — fail after the handler has begun, exactly where a crash
is dangerous. No monkeypatch, no thread timing.

### THE INVARIANT. The handoff is atomic iff the source advance and the downstream creation move
TOGETHER OR NOT AT ALL: `source_advanced == downstream_created`. A responsibility gap is precisely
`source_advanced and not downstream_created` — the source moved on while nothing owns the downstream
work. The discrimination control drives exactly that non-atomic ordering (advance the source and
commit, THEN create downstream and crash) and proves this oracle goes RED on it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase6_pipeline_kit import (  # noqa: E402
    Clock, T_A, a_human, a_work_item, canonical_event, make_store, outbox_events,
)
from phase6_crash_kit import outbox_count, plant_colliding_emission  # noqa: E402
from freight_recon.event_inbox import ConsumeOutcome, DedupInbox  # noqa: E402
from freight_recon.event_outbox import TransactionalOutbox  # noqa: E402

CONSUMER = "ac-race-017-downstream-spawner"
DOWNSTREAM_WI = "wi-downstream-ar-collections"      # the downstream Work Item the source hands off to
DOWNSTREAM_TXN = "WI-1"                              # WI-1 originates a Work Item (its creation)


def _source_trigger(store, *, seed: str):
    """A real contract-valid source event whose consumption is the SOURCE transition advancing. It is
    also emitted to the outbox so the crash kit has a template envelope to copy."""
    # aggregate_version=1: the inbox consumes an aggregate's events in version order, so the first
    # event this consumer sees for the source aggregate must be v1 or it parks (a version gap), and a
    # parked trigger never reaches the handler where the handoff happens.
    return canonical_event(
        store, event_name="PipelineClosed", producer_transition_id="PL-14",
        aggregate_type="pipeline_instance", aggregate_id="pl-source-4471", aggregate_version=1,
        seed=seed, emit=True,
    )


def _downstream_creation_envelope(store, seed: str):
    """The downstream Work Item CREATION, as its canonical `WorkItemCreated` (WI-1) event. Built with
    emit=False (no store write); the handler emits it INSIDE the inbox transaction."""
    return canonical_event(
        store, event_name="WorkItemCreated", producer_transition_id=DOWNSTREAM_TXN,
        aggregate_type="work_item", aggregate_id=DOWNSTREAM_WI, aggregate_version=1,
        seed=seed, work_item_id=DOWNSTREAM_WI, emit=False,
    )


def _downstream_created(store, event_id: str) -> bool:
    """Whether the REAL downstream creation is durable — the handler's own event_id in the outbox.
    The crash-kit scaffold occupies the same IDENTITY with a DIFFERENT event_id, so this asks about
    the genuine creation, never the scaffold."""
    return any(e["event_id"] == event_id for e in outbox_events(store))


def _source_advanced(store, event_id: str) -> bool:
    """Whether the source transition advanced — the trigger has a durable inbox receipt."""
    row = store.conn.execute(
        "SELECT COUNT(*) FROM event_inbox WHERE tenant = ? AND consumer_id = ? AND event_id = ?",
        (T_A, CONSUMER, event_id)).fetchone()
    return int(row[0]) == 1


def _responsibility_gap(source_advanced: bool, downstream_created: bool) -> bool:
    """The forbidden state: the source moved on while nothing owns the downstream work."""
    return source_advanced and not downstream_created


# --------------------------------------------------------------------------- the oracle
def test_ac_race_017_a_crash_creating_the_downstream_work_item_does_not_advance_the_source(tmp_path):
    """THE ORACLE. The handler emits the downstream `WorkItemCreated` (the creation) inside the
    inbox's one commit; the crash kit occupies that emission's identity so it fails. The source
    trigger must therefore NOT be consumed, the downstream must NOT exist, and there is no
    responsibility gap — both halves rolled back together."""
    store = make_store(tmp_path)
    a_human(store)
    a_work_item(store)

    trigger = _source_trigger(store, seed="s1")
    downstream = _downstream_creation_envelope(store, "d1")
    inbox = DedupInbox(store.conn, tenant=T_A, consumer_id=CONSUMER)

    def handler(_event):
        # The downstream Work Item creation — emitted INSIDE the inbox transaction (M-24).
        TransactionalOutbox(store.conn, tenant=T_A, clock=Clock()).emit(downstream)

    # Stage the crash exactly at the downstream-creation boundary.
    plant_colliding_emission(
        store.conn, T_A, aggregate_type="work_item", aggregate_id=DOWNSTREAM_WI,
        aggregate_version=1, transition_id=DOWNSTREAM_TXN, event_name="WorkItemCreated")

    with pytest.raises(Exception) as crash:
        inbox.consume(trigger, handler)
    assert "already emitted" in str(crash.value), str(crash.value)

    source_advanced = _source_advanced(store, trigger.event_id)
    downstream_created = _downstream_created(store, downstream.event_id)

    # AC-RACE-017: the source transition did NOT advance.
    assert source_advanced is False, "the source trigger was consumed even though the downstream crashed"
    # No orphan / no open consequential state: the downstream creation did not happen.
    assert downstream_created is False, "a downstream WorkItemCreated survived the crash"
    # The atomic-handoff invariant and its no-gap corollary.
    assert source_advanced == downstream_created, "the handoff was not atomic (halves diverged)"
    assert not _responsibility_gap(source_advanced, downstream_created), (
        "a responsibility gap opened: the source advanced while nothing owns the downstream work")


def test_ac_race_017_retry_reaches_exactly_one_canonical_result(tmp_path):
    """Recovery: on a clean retry (no injected fault) the SAME handoff completes exactly once — one
    source receipt, one downstream creation — and a redelivery is a no-op. Measured on a fresh store
    because `event_outbox` is append-only and the crash kit's scaffold cannot be cleanly removed
    (the M5 crash-recovery convention, phase6_crash_kit)."""
    store = make_store(tmp_path)
    a_human(store)
    a_work_item(store)

    trigger = _source_trigger(store, seed="s2")
    downstream = _downstream_creation_envelope(store, "d2")
    inbox = DedupInbox(store.conn, tenant=T_A, consumer_id=CONSUMER)

    def handler(_event):
        TransactionalOutbox(store.conn, tenant=T_A, clock=Clock()).emit(downstream)

    before = outbox_count(store.conn, T_A)
    result = inbox.consume(trigger, handler)
    assert result.outcome is ConsumeOutcome.APPLIED
    assert _source_advanced(store, trigger.event_id) is True
    assert _downstream_created(store, downstream.event_id) is True
    assert outbox_count(store.conn, T_A) == before + 1, "exactly one downstream creation was emitted"

    # A redelivery of the same trigger is a no-op: still exactly one downstream, one receipt.
    redelivery = inbox.consume(trigger, handler)
    assert redelivery.outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert outbox_count(store.conn, T_A) == before + 1, "a redelivery created a second downstream"


# --------------------------------------------------------------------------- the RED control
def test_ac_race_017_control_a_non_atomic_handoff_opens_a_responsibility_gap(tmp_path):
    """THE DISCRIMINATION CONTROL. It reintroduces the exact forbidden behaviour the oracle forbids —
    the source advances (and COMMITS) BEFORE downstream ownership exists — and proves this oracle's
    invariant goes RED on it. Without this, the oracle above could pass vacuously (CLAUDE.md §6)."""
    store = make_store(tmp_path)
    a_human(store)
    a_work_item(store)

    trigger = _source_trigger(store, seed="s3")
    downstream = _downstream_creation_envelope(store, "d3")

    # Phase 1 (NON-ATOMIC): advance the source and COMMIT, with a no-op handler — the source moves on.
    inbox = DedupInbox(store.conn, tenant=T_A, consumer_id=CONSUMER)
    assert inbox.consume(trigger, lambda _e: None).outcome is ConsumeOutcome.APPLIED
    source_advanced = _source_advanced(store, trigger.event_id)
    assert source_advanced is True, "the control could not advance the source"

    # Phase 2 (SEPARATE transaction): now create the downstream — and crash it.
    plant_colliding_emission(
        store.conn, T_A, aggregate_type="work_item", aggregate_id=DOWNSTREAM_WI,
        aggregate_version=1, transition_id=DOWNSTREAM_TXN, event_name="WorkItemCreated")
    store.conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(Exception):
            TransactionalOutbox(store.conn, tenant=T_A, clock=Clock()).emit(downstream)
    finally:
        store.conn.rollback()
    downstream_created = _downstream_created(store, downstream.event_id)
    assert downstream_created is False

    # The forbidden state is realised, and the oracle's invariant DETECTS it (goes RED).
    assert _responsibility_gap(source_advanced, downstream_created), (
        "the control failed to realise a responsibility gap")
    with pytest.raises(AssertionError):
        assert source_advanced == downstream_created, "the handoff was not atomic (halves diverged)"
