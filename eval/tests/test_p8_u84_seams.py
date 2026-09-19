"""P8 / U8.4 — Conflict, Expectation, Exception and Compensation INTEGRATION seams.

### WHAT THIS UNIT WIRED, AND WHY IT IS DARK. P6 landed M7..M10 as finished, isolated machines. U8.4
closes only the smallest still-real integration gaps that P7 and U8.1..U8.3 left open, THROUGH the
existing canonical authorities — never a parallel implementation:

  * ### M8 → M9 (closes M8-AQ-1). F8 canonically names M9 the consumer of `ExpectationOverdue`,
    `ExpectationIndeterminate` and `ExpectationExpired`. `M9Machine.consume_source_escalation` consumes
    those events idempotently through P5's dedup inbox and raises exactly one Exception through M9's own
    landed raise core. The honesty split is PRESERVED in the human question: OVERDUE asks a counterparty
    follow-up; INDETERMINATE says WE WERE BLIND and must never be read as counterparty fault (I8, M-32).

  * ### M10 → M9 (closes M10-AQ-12). F10 names M9 the consumer of `CompensationFailed` and
    `CompensationImpossible`. The same consumer raises a loud (SEV0), owned, exposure-carrying Exception.
    `CompensationRefused` on UNKNOWN_OUTCOME is NOT escalated here — its owner already lives upstream on
    the effect grant (M-33), and a second owner would be the duplicate resolution path M-33 forbids.

  * ### P6-D4 CLOSED. `work_item.resolve_decision_ref` — the ONE shared resolver M1/M2/M3/M9/M10 use —
    now resolves a RULE decision_ref against M12's ACTIVE `rules`. Non-ACTIVE / missing / cross-tenant
    refuse. The detailed resolver contract lives in `test_phase6_work_item.py` and the M9 closure path in
    `test_phase6_exception.py`; this module proves the cross-machine INTEGRATION.

M8 and M10 stay pure PRODUCERS: they are neither imported nor edited by this seam; only their already
emitted canonical events cross it. Nothing under `src/freight_recon/` invokes `consume_source_escalation`
— it is reached only by this module and the probe, so U8.4 ships dark.
"""

from __future__ import annotations

import sqlite3
import sys
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon.fingerprint import Money  # noqa: E402
from freight_recon.event_envelope import EventEnvelope  # noqa: E402
from freight_recon.event_inbox import ConsumeOutcome, DedupInbox  # noqa: E402
from freight_recon.exception import (  # noqa: E402
    EXPECTATION_ESCALATION_TYPE,
    SOURCE_ESCALATION_CONSUMER_ID,
    EcState,
    M9Machine,
)
from freight_recon.expectation import HEALTHY_COVERAGE, M8Machine  # noqa: E402
from freight_recon.compensation import CmState, M10Machine  # noqa: E402

import phase6_compensation_kit as ck  # noqa: E402

TENANT = ck.T_A
OTHER = ck.T_B
OWNER = "owner:dana"
FAR_WINDOW = ("2020-01-01T00:00:00.000Z", "2035-01-01T00:00:00.000Z")


def _store_clk(tmp_path, name="u84.db"):
    clk = ck.Clock()
    store = ck.make_store(tmp_path, name=name)
    return store, clk


def _human(store, hid=OWNER, *, tenant=TENANT, state="ACTIVE"):
    off = "2026-06-01T00:00:00Z" if state == "OFFBOARDED" else None
    store.conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
        "recorded_at, recorded_by, recorded_by_kind, offboarded_at) VALUES (?,?,?, 'AUTHORIZED_HUMAN', "
        "?, '2026-01-01T00:00:00Z', 'founder', 'human', ?)", (tenant, hid, hid, state, off))
    store.conn.commit()
    return hid


def _set_human_state(store, state, hid=OWNER, tenant=TENANT):
    off = "2026-06-01T00:00:00Z" if state == "OFFBOARDED" else None
    store.conn.execute(
        "UPDATE tenant_humans SET state=?, offboarded_at=? WHERE tenant=? AND human_id=?",
        (state, off, tenant, hid))
    store.conn.commit()


def _event(store, name, aggregate_id, *, tenant=TENANT):
    row = store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant=? AND event_name=? AND aggregate_id=? "
        "ORDER BY sequence DESC LIMIT 1", (tenant, name, aggregate_id)).fetchone()
    return EventEnvelope.from_json(row["envelope_json"]) if row is not None else None


def _open_exceptions(store, *, tenant=TENANT):
    return store.conn.execute(
        "SELECT * FROM exceptions WHERE tenant=? AND state != 'RESOLVED'", (tenant,)).fetchall()


def _all_exceptions(store, *, tenant=TENANT):
    return store.conn.execute("SELECT * FROM exceptions WHERE tenant=?", (tenant,)).fetchall()


# ---- M8 drivers: the three F8 escalation events, through M8's real entry points ----

def _overdue_event(store, clk, *, subject="load-4471", src="mailbox", eid=None):
    """Drive an expectation to OVERDUE over a demonstrably HEALTHY channel and return the F8 event."""
    m8 = M8Machine(store.conn, tenant=TENANT, clock=clk)
    r = m8.raise_expectation(subject_ref=subject, expected_type="pod", expected_source=src,
                             owner_id=OWNER, originating_timezone="America/Denver",
                             deadline_utc=clk() + timedelta(hours=1), schedule_timer=False,
                             expectation_id=eid)
    xid = r.expectation.expectation_id
    m8.record_coverage(coverage_id=f"cov-{xid}", channel=src, window_start=FAR_WINDOW[0],
                       window_end=FAR_WINDOW[1], health=HEALTHY_COVERAGE, probe_source="probe")
    clk.t = clk() + timedelta(hours=2)
    ov = m8.evaluate_deadline(xid, owner_id=OWNER)
    assert ov is not None and ov.to_state is not None and ov.to_state.value == "OVERDUE"
    return m8, xid, _event(store, "ExpectationOverdue", xid)


def _indeterminate_event(store, clk, *, subject="load-9", src="down-chan"):
    """Drive an expectation to INDETERMINATE (no coverage record — blindness) and return the F8 event."""
    m8 = M8Machine(store.conn, tenant=TENANT, clock=clk)
    r = m8.raise_expectation(subject_ref=subject, expected_type="pod", expected_source=src,
                             owner_id=OWNER, originating_timezone="America/Denver",
                             deadline_utc=clk() + timedelta(hours=1), schedule_timer=False)
    xid = r.expectation.expectation_id
    clk.t = clk() + timedelta(hours=2)
    ind = m8.evaluate_deadline(xid, owner_id=OWNER)
    assert ind is not None and ind.to_state is not None and ind.to_state.value == "INDETERMINATE"
    return m8, xid, _event(store, "ExpectationIndeterminate", xid)


# ============================================================ M8 → M9 : the honesty split

def test_overdue_raises_one_owned_exception_with_a_counterparty_question(tmp_path):
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ev = _overdue_event(store, clk)
    assert ev is not None and ev.accountable_owner_id == OWNER
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    ct = m9.consume_source_escalation(ev)
    assert ct.consume.applied and ct.transition is not None and not ct.transition.coalesced
    exc = m9.get(ct.transition.exception.exception_id)
    assert exc.owner_id == OWNER and exc.source_kind == "expectation" and exc.source_ref == xid
    assert exc.type == EXPECTATION_ESCALATION_TYPE and exc.severity.value == "SEV1"
    assert exc.state is EcState.OPEN
    # the honesty split: OVERDUE is a counterparty follow-up, never blindness.
    assert "healthy channel" in exc.specific_question
    assert "blind" not in exc.specific_question.lower()
    assert len(_open_exceptions(store)) == 1


def test_indeterminate_never_converts_blindness_into_counterparty_fault(tmp_path):
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ev = _indeterminate_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    ct = m9.consume_source_escalation(ev)
    exc = m9.get(ct.transition.exception.exception_id)
    assert exc.severity.value == "SEV1" and exc.source_ref == xid
    q = exc.specific_question
    # It names OUR blindness and explicitly forbids treating it as the counterparty's failure.
    assert "blindness" in q and "NOT the counterparty" in q
    assert "not treat it as a counterparty failure" in q
    assert "BLIND" in exc.summary


def test_overdue_and_indeterminate_are_the_two_readings_of_one_missed_deadline(tmp_path):
    """AC-MACH-8xx honesty: the SAME missed deadline reads OVERDUE under healthy coverage and
    INDETERMINATE under absent coverage — the coverage decides, never the model."""
    store, clk = _store_clk(tmp_path)
    _human(store)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    _, _, ov = _overdue_event(store, clk, subject="ld-h", src="chan-healthy")
    _, _, ind = _indeterminate_event(store, clk, subject="ld-b")
    exc_ov = m9.get(m9.consume_source_escalation(ov).transition.exception.exception_id)
    exc_in = m9.get(m9.consume_source_escalation(ind).transition.exception.exception_id)
    assert "healthy channel" in exc_ov.specific_question
    assert "blindness" in exc_in.specific_question and "counterparty" in exc_in.specific_question


# ============================================================ idempotency / redelivery / crash

def test_redelivered_expectation_event_raises_no_second_exception(tmp_path):
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ev = _overdue_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    first = m9.consume_source_escalation(ev)
    assert first.consume.applied
    again = m9.consume_source_escalation(ev)
    assert again.consume.outcome is ConsumeOutcome.DUPLICATE_NOOP and again.transition is None
    assert len(_open_exceptions(store)) == 1


def test_crash_between_source_transition_and_delivery_reaches_the_same_one_exception(tmp_path):
    """The exception row and the inbox row share ONE commit (M-24). Modelled as: the source event is
    durably emitted, a crash loses the in-flight consume (no inbox row, no exception), and redelivery
    reaches exactly the same one exception — never a lost escalation, never a duplicate."""
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ev = _overdue_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)

    # A consume that crashes AFTER the handler but BEFORE the inbox commit leaves NOTHING behind: a
    # handler that raises rolls back its writes and its inbox row together (event_inbox.py §"WHY THE
    # HANDLER RUNS INSIDE THE TRANSACTION"). Model the crash with a handler-side failure.
    boom_box = DedupInbox(store.conn, tenant=TENANT, consumer_id=SOURCE_ESCALATION_CONSUMER_ID,
                          clock=clk)

    def _boom(_event):
        raise RuntimeError("crash after the exception write, before the inbox commit")

    with pytest.raises(RuntimeError):
        boom_box.consume(ev, _boom)
    assert len(_all_exceptions(store)) == 0  # rolled back with the inbox row — nothing half-done
    assert boom_box.seen(ev.event_id) is None  # not recorded as consumed

    # Redelivery after recovery reaches exactly one exception.
    ct = m9.consume_source_escalation(ev)
    assert ct.consume.applied and len(_open_exceptions(store)) == 1
    # And a further redelivery is a no-op.
    assert m9.consume_source_escalation(ev).consume.outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert len(_open_exceptions(store)) == 1


def test_concurrent_duplicate_consumers_yield_exactly_one_exception(tmp_path):
    """Two consumers of the SAME event serialize on the inbox's BEGIN IMMEDIATE + (tenant, consumer,
    event_id) dedup: one APPLIES, the other is a DUPLICATE_NOOP. Modelled with two DedupInbox instances
    on one connection — the write lock makes the second see the first's inbox row."""
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ev = _overdue_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    a = m9.consume_source_escalation(ev)
    b = m9.consume_source_escalation(ev)
    outcomes = {a.consume.outcome, b.consume.outcome}
    assert ConsumeOutcome.APPLIED in outcomes and ConsumeOutcome.DUPLICATE_NOOP in outcomes
    assert len(_open_exceptions(store)) == 1


def test_same_source_different_event_coalesces_to_one_open_exception(tmp_path):
    """entity §14: OVERDUE/INDETERMINATE/EXPIRED for one expectation is ONE Exception. An EXPIRED that
    follows an OPEN overdue-derived exception coalesces on (source_ref, type) — no duplicate open."""
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ov = _overdue_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    m9.consume_source_escalation(ov)
    expired = EventEnvelope(
        event_id=str(uuid.uuid4()), event_name="ExpectationExpired", event_version=ov.event_version,
        occurred_at=ov.occurred_at, recorded_at=ov.recorded_at, tenant_id=TENANT,
        aggregate_type="expectation", aggregate_id=xid, aggregate_version=99,
        previous_aggregate_version=None, causation_id=None, correlation_id=xid,
        producer_component="expectation_service", producer_transition_id="EX-7", actor_type="system",
        actor_id="timer", trace_id=f"trace-{xid}", payload={}, accountable_owner_id=OWNER)
    ct = m9.consume_source_escalation(expired)
    assert ct.transition is not None and ct.transition.coalesced
    assert len(_open_exceptions(store)) == 1


def test_expiry_after_resolution_raises_a_human_owned_exception_exactly_once(tmp_path):
    """Expiry is never silence. If the overdue-derived exception was RESOLVED, a later EXPIRED raises a
    fresh human-owned exception — exactly once (a redelivery is a no-op)."""
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ov = _overdue_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    exc_id = m9.consume_source_escalation(ov).transition.exception.exception_id
    # resolve the overdue exception with an authenticated human decision.
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=OWNER, seed="resolve-ov", clock=clk)
    m9.resolve(exc_id, decision_ref=dref, decision_human_id=OWNER)
    assert m9.get(exc_id).state is EcState.RESOLVED
    expired = EventEnvelope(
        event_id=str(uuid.uuid4()), event_name="ExpectationExpired", event_version=ov.event_version,
        occurred_at=ov.occurred_at, recorded_at=ov.recorded_at, tenant_id=TENANT,
        aggregate_type="expectation", aggregate_id=xid, aggregate_version=99,
        previous_aggregate_version=None, causation_id=None, correlation_id=xid,
        producer_component="expectation_service", producer_transition_id="EX-7", actor_type="system",
        actor_id="timer", trace_id=f"trace-{xid}", payload={}, accountable_owner_id=OWNER)
    ct = m9.consume_source_escalation(expired)
    assert ct.transition is not None and not ct.transition.coalesced
    assert len(_open_exceptions(store)) == 1  # exactly one, fresh, owned
    assert m9.consume_source_escalation(expired).consume.outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert len(_open_exceptions(store)) == 1


def test_late_discharge_after_escalation_does_not_auto_resolve_the_exception(tmp_path):
    """A late observation discharges the EXPECTATION (EX-4), month four included — but an Exception
    NEVER auto-closes. After a late discharge the expectation is DISCHARGED and the exception is still
    OPEN, awaiting a human's decision_ref."""
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ov = _overdue_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    exc_id = m9.consume_source_escalation(ov).transition.exception.exception_id
    # a late POD arrives and discharges the OVERDUE expectation (EX-4). BOUND to the expectation's
    # subject so M8's discharge guard accepts it.
    store.conn.execute(
        "INSERT INTO observations (tenant, observation_id, source_system, external_id, content_digest, "
        "raw_value, as_of, received_at, state, version, provenance_class, bound_entity_ref, "
        "created_at, updated_at) VALUES (?,?, 'carrier', ?, ?, 'v', 't', 't', 'BOUND', 1, "
        "'SYSTEM_IMPORTED', ?, 't', 't')", (TENANT, "obs-late", "obs-late", "obs-late", "load-4471"))
    store.conn.commit()
    disc = m8.discharge(xid, observation_id="obs-late")
    assert disc.to_state.value == "DISCHARGED" and disc.late is True
    # the exception is untouched — still OPEN, no auto-close.
    assert m9.get(exc_id).state is EcState.OPEN
    assert len(_open_exceptions(store)) == 1


def test_owner_deactivation_during_escalation_fails_closed_then_recovers(tmp_path):
    """AC-RACE-016: no consequential action proceeds without a reassigned owner. If the source owner is
    deactivated before M9 consumes, the raise FAILS CLOSED (no ownerless/inactive-owner exception, no
    silent drop). Reactivation lets the redelivered event reach exactly one exception."""
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ev = _overdue_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    _set_human_state(store, "OFFBOARDED")
    with pytest.raises(Exception):
        m9.consume_source_escalation(ev)
    assert len(_all_exceptions(store)) == 0
    _set_human_state(store, "ACTIVE")
    ct = m9.consume_source_escalation(ev)
    assert ct.consume.applied and len(_open_exceptions(store)) == 1


def test_replay_of_the_escalation_exception_mints_no_authority(tmp_path):
    """GR-11/K-3: rebuilding the escalation exception's event stream creates nothing — no authority, no
    decision_ref, no state flip. Re-consuming the source event mints nothing either."""
    store, clk = _store_clk(tmp_path)
    _human(store)
    m8, xid, ev = _overdue_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    exc_id = m9.consume_source_escalation(ev).transition.exception.exception_id
    rebuilt = m9.rebuild(exc_id)
    assert rebuilt.state is EcState.OPEN and rebuilt.new_authority == 0
    assert rebuilt.decision_refs_minted == 0 and rebuilt.external_effects == 0
    # re-consume the source event: no new exception, no new authority.
    assert m9.consume_source_escalation(ev).consume.outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert len(_all_exceptions(store)) == 1


# ============================================================ M10 → M9 : loud, owned, exposure-carrying

def test_compensation_failed_escalates_once_with_owner_and_exposure(tmp_path):
    store, clk = _store_clk(tmp_path)
    m, r, gid = ck_required(store, clk, exposure=Money(285000, "GBP"))
    cid = r.compensation.compensation_id
    m = _drive_to(store, clk, m, r, gid, target="FAILED")
    r4 = m.observe_pipeline(cid, actor_id="compensation")
    assert r4.event_names == ("CompensationFailed",)
    ev = _event(store, "CompensationFailed", cid)
    assert ev is not None and ev.accountable_owner_id == OWNER and ev.payload["exposure"] == "285000|GBP"
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    ct = m9.consume_source_escalation(ev)
    exc = m9.get(ct.transition.exception.exception_id)
    assert exc.source_kind == "compensation" and exc.source_ref == cid
    assert exc.severity.value == "SEV0" and exc.exposure == "285000|GBP" and exc.type == "compensation_failed"
    assert exc.owner_id == OWNER and exc.state is EcState.OPEN
    # exactly once: a redelivery raises no second exception.
    assert m9.consume_source_escalation(ev).consume.outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert len(_open_exceptions(store)) == 1


def test_compensation_impossible_escalates_once_loud_and_owned(tmp_path):
    store, clk = _store_clk(tmp_path)
    m, r, gid = ck_required(store, clk, exposure=Money(99900, "GBP"))
    cid = r.compensation.compensation_id
    r2 = m.mark_not_possible(cid, impossibility_evidence="a completed ACH wire has no reversal endpoint")
    assert r2.event_names == ("CompensationImpossible",)
    ev = _event(store, "CompensationImpossible", cid)
    assert ev is not None and ev.payload["exposure"] == "99900|GBP"
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    exc = m9.get(m9.consume_source_escalation(ev).transition.exception.exception_id)
    assert exc.severity.value == "SEV0" and exc.exposure == "99900|GBP"
    assert exc.type == "compensation_impossible" and exc.owner_id == OWNER
    assert len(_open_exceptions(store)) == 1


def test_no_consumer_clears_a_failed_compensation_it_stays_loud_and_owned(tmp_path):
    """CompensationFailed never auto-resolves. Consuming the event a second time does not clear the
    compensation and does not resolve the exception — both stay loud and owned."""
    store, clk = _store_clk(tmp_path)
    m, r, gid = ck_required(store, clk, exposure=Money(1, "GBP"))
    cid = r.compensation.compensation_id
    _drive_to(store, clk, m, r, gid, target="FAILED")
    m.observe_pipeline(cid, actor_id="compensation")
    ev = _event(store, "CompensationFailed", cid)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    exc_id = m9.consume_source_escalation(ev).transition.exception.exception_id
    m9.consume_source_escalation(ev)  # redelivery
    assert m.get(cid).state is CmState.COMPENSATION_FAILED  # the compensation is unchanged
    assert m9.get(exc_id).state is EcState.OPEN  # the exception is still open, owned


def test_unknown_outcome_refusal_is_not_escalated_by_m9_m33(tmp_path):
    """### M-33. Compensation is REFUSED on UNKNOWN_OUTCOME (CompensationRefused, zero compensating
    effect). The M9 consumer does NOT raise an exception for it: its owner already lives upstream on the
    effect grant's UNKNOWN_OUTCOME (resolved by a human via M3 EF-5), so a second M9 owner would be a
    duplicate resolution path M-33 forbids. The event is consumed once; nothing is created."""
    store, clk = _store_clk(tmp_path)
    _human(store)
    gid = ck.an_original_effect_in(store, "UNKNOWN_OUTCOME", tenant=TENANT, clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=OWNER, seed=f"d-{gid}", clock=clk)
    m = M10Machine(store.conn, tenant=TENANT, clock=clk)
    r = m.raise_from_correction(original_effect_id=gid, owner_id=OWNER, exposure=Money(285000, "GBP"),
                                reason="POD rebound", decision_ref=dref)
    assert r.event_names == ("CompensationRefused",)
    # zero compensating effect: no compensations row, no compensating grant.
    assert store.conn.execute("SELECT COUNT(*) FROM compensations WHERE tenant=?", (TENANT,)).fetchone()[0] == 0
    row = store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant=? AND event_name='CompensationRefused' "
        "ORDER BY sequence DESC LIMIT 1", (TENANT,)).fetchone()
    assert row is not None
    ev = EventEnvelope.from_json(row["envelope_json"])
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    ct = m9.consume_source_escalation(ev)
    assert ct.consume.applied and ct.transition is None and ct.refusal is not None
    assert len(_all_exceptions(store)) == 0  # M-33: no second resolution path


# ============================================================ P6-D4 across the shared resolver

def test_active_rule_decision_ref_is_accepted_and_model_closure_is_refused(tmp_path):
    """### P6-D4 CLOSED. A human closes an escalation Exception citing an ACTIVE M12 rule; a MODEL is
    refused before any resolution (EC-3 is trigger H). The RULE ref resolves in the ONE shared resolver."""
    from freight_recon.rule import M12Machine

    store, clk = _store_clk(tmp_path)
    _human(store)
    _human(store, "po")
    m12 = M12Machine(store.conn, tenant=TENANT, clock=clk)
    pod = [{"field": "pod", "attr": "evidence_condition", "op": "==", "literal": "consistent",
            "provenance_class": "SYSTEM_IMPORTED", "modelled": True}]
    m12.propose(scope="action_class:raise_invoice", kind="GATE_PRECONDITION", effect="DENY",
                source_instruction="never bill without a pod", authored_by="po", clauses=pod,
                rule_id="rule-live")
    m12.compile("rule-live")
    m12.confirm("rule-live", confirmed_by="po")
    m12.activate("rule-live", activated_by="po")

    m8, xid, ev = _overdue_event(store, clk)
    m9 = M9Machine(store.conn, tenant=TENANT, clock=clk)
    exc_id = m9.consume_source_escalation(ev).transition.exception.exception_id

    # a MODEL cannot resolve — refused before any decision_ref resolution.
    with pytest.raises(Exception):
        m9.resolve(exc_id, decision_ref="rule-live", decision_human_id=OWNER,
                   decision_ref_kind="RULE", actor_kind="model")
    assert m9.get(exc_id).state is EcState.OPEN

    # a human closing on the ACTIVE rule succeeds.
    m9.resolve(exc_id, decision_ref="rule-live", decision_human_id=OWNER, decision_ref_kind="RULE")
    assert m9.get(exc_id).state is EcState.RESOLVED


# ============================================================ ships dark

def test_u84_ships_dark_no_production_module_invokes_the_consumer(tmp_path):
    """The F8/F10 escalation is reachable only from tests and the probe. No module under
    `src/freight_recon/` calls `consume_source_escalation` — U8.4 wires the seam without a production
    entry point, notifier, queue or live channel."""
    import ast

    src = ROOT / "src" / "freight_recon"
    offenders = []
    for path in src.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "consume_source_escalation":
                offenders.append(path.name)
    assert offenders == [], f"a production module invokes the U8.4 consumer: {offenders}"


# ### HOW THE CHANGED VERIFICATION THIS UNIT DELIVERED IS OPERATED (the product driver runs pytest and
# reads each command's exit status; it credits a file only when a command TARGETS that file, never a
# transitive import from another test). So each changed guard carries its OWN pytest-collected entry
# point, exactly as the repository already does for M3/M13 (`scripts/mutate_phase6_brake.py`):
#   * the U8.4 mutation battery — the firing-case proof for the absence guards below — is operated by
#         .venv/bin/python -m pytest scripts/mutate_p8_u84_seams.py -q -rf -p no:cacheprovider
#     (its own `test_the_u84_seam_mutation_battery_catches_every_mutant`, main()==0 over >=9 mutants);
#   * each reconciled probe is operated by
#         .venv/bin/python -m pytest scripts/probe_phase6_{exception,expectation,compensation}.py -q ...
#     (its own `test_the_*_probe_behaves_as_specified`, main([])==0 on "0 wrong");
#   * the changed test files (this file, work_item, exception, policy, rule, brake, compensation) are
#     each operated by `.venv/bin/python -m pytest <file>` — they collect their own tests.
# None of these are swept by a bare `pytest eval` (the scripts are outside `testpaths` and are not named
# `test_*.py`), so the slow battery runs only when named — on purpose, never by accident.


# --- a small adapter so the compensation-kit `_required`/`_drive_to` helpers read cleanly here ---

def ck_required(store, clk, *, exposure=None, grant_state="VERIFIED"):
    _human(store)
    gid = ck.an_original_effect_in(store, grant_state, tenant=TENANT, clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=OWNER, seed=f"d-{gid}", clock=clk)
    m = M10Machine(store.conn, tenant=TENANT, clock=clk)
    r = m.raise_from_correction(
        original_effect_id=gid, owner_id=OWNER, exposure=exposure or Money(285000, "GBP"),
        reason="POD rebound to load 4471", decision_ref=dref)
    return m, r, gid


def _drive_to(store, clk, m, r, gid, *, target, pid="pi-cmp", ap="ap-cmp", wi="wi-cmp"):
    cid = r.compensation.compensation_id
    original = m._require_original_effect(gid)
    effect = m.compensating_effect(original, cid)
    world = ck.a_world(resource=original.target_resource_id)
    ck.a_granted_m4_approval(store, effect, world, approval_id=ap, tenant=m.tenant, granter=OWNER,
                             clock=clk)
    m.approve(cid, approval_id=ap, actor_id=OWNER)
    ck.a_work_item(store, tenant=m.tenant, work_item_id=wi, owner_id=OWNER, clock=clk)
    m.start_execution(cid, work_item_id=wi, pipeline_instance_id=pid, actor_id="compensation")
    ck.drive_compensating_pipeline(store, effect, world, pipeline_instance_id=pid, tenant=m.tenant,
                                   approval_id=ap, granter=OWNER, target=target, clock=clk)
    return m
