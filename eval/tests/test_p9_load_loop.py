"""P9 deep-end 4 — the continuous load loop: complete loads, side by side, booked to billing-ready.

`load_loop.py` keeps one load's operating picture through its whole life: what is happening and on
what evidence, what changed, what work remains, what is overdue, what is waited for, what Neyma
would do, what needs a human and why, whether customer billing is ready, whether carrier-side work
is open, whether the load is genuinely quiet, and how many human touches it has cost.

These tests run twenty-one synthetic loads - one clean, the rest carrying the trouble a brokerage
really has - through the REAL spine in one database, in the order their records arrived, and assert:

  * every labeled moment of every load is what a broker would expect;
  * NO LOAD IS EVER QUIET WHILE ANYTHING IS OWED, WAITED FOR OR DISPUTED - checked by an oracle that
    re-derives it from the canonical record at EVERY evaluation, not only at the moments shown;
  * replay, duplicate delivery, reordering, dropped records and a restart in the middle lose no work
    and invent none;
  * two brokerages with the same load number never touch;
  * human touches are read from the record, and a load nobody had to touch costs zero;
  * a tracking dispute is settled by a named human and by nothing else, and a later contradiction
    is a new dispute;
  * a proposal is words: nothing is sent, nothing is written outside Neyma's own state, and no
    picture carries money.

SYNTHETIC. Nothing here is a design-partner observation and no freight rule is validated by it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from freight_corpus.builders import says  # noqa: E402
from freight_corpus.loop_histories import (  # noqa: E402
    LOOP_SETUPS,
    Load,
    _builder,
    build_loop_histories,
)
from freight_corpus.parties import CEDAR, NORTHLINE  # noqa: E402
from freight_corpus.work_attack import (  # noqa: E402
    _MONEY,
    Mutant,
    audit_state,
    build_mutants,
    duplicate_every_record,
    row_counts,
    run_mutant,
)
from freight_recon.freight_domain.corpus_run import cross_tenant_violations  # noqa: E402
from freight_recon.freight_domain.history import (  # noqa: E402
    OBSERVATION_KINDS,
    UnparseableRecord,
    parse_record,
)
from freight_recon.freight_domain.load_loop import (  # noqa: E402
    LoopRunResult,
    build_moment,
    render_board,
    render_moment,
    render_story,
    render_trace,
    run_load_loop,
    signature,
    without_money,
)
from freight_recon.freight_domain.load_work import (  # noqa: E402
    NeedKind,
    ShadowAction,
    Stage,
    evaluate_load_work,
)
from freight_recon.workflow import WorkflowStore  # noqa: E402

#: What the founder asked the first set of loads to cover, as the tags the histories carry. A tag
#: no history carries is a story nobody wrote.
REQUIRED_TROUBLE = frozenset({
    "clean_load", "late_pickup", "late_delivery", "driver_stops_responding",
    "carrier_promises_and_misses", "carrier_changes_eta_repeatedly", "contradictory_tracking",
    "pickup_reported_without_supporting_evidence", "delivery_reported_pod_missing", "unsigned_pod",
    "corrected_pod", "duplicate_pod", "pod_attached_to_wrong_load",
    "same_load_number_in_another_tenant", "appointment_time_changed", "appointment_unconfirmed",
    "carrier_invoice_before_pod", "carrier_invoice_wrong_amount", "carrier_invoice_unattributed",
    "accessorial_unsupported", "correction_after_a_prior_interpretation",
    "duplicated_inbound_messages", "reordered_observations",
})


def _audit(state, view, tenant):
    return audit_state(state, view, tenant=tenant)


def _run(path: Path, histories=None, **kw) -> tuple[LoopRunResult, WorkflowStore]:
    histories = build_loop_histories() if histories is None else histories
    path.mkdir(parents=True, exist_ok=True)
    store = WorkflowStore(path / "loop.db", tenant=histories[0].tenant)
    kw.setdefault("audit", _audit)
    return run_load_loop(store.conn, LOOP_SETUPS, histories, **kw), store


@pytest.fixture(scope="module")
def loop(tmp_path_factory):
    result, store = _run(tmp_path_factory.mktemp("loop"))
    yield result, store.conn
    store.close()


#: Four loads that between them carry a deadline passing in silence, a tracking dispute a human
#: settles, two unconfirmed appointments and an invoice nobody has decided. Small enough to run in a
#: few seconds, which is what lets a mutation battery turn each guard below RED and green again.
FEW = ("L02", "L07", "L16", "L17")


@pytest.fixture(scope="module")
def few(tmp_path_factory):
    chosen = [h for h in build_loop_histories() if h.history_id in FEW]
    result, store = _run(tmp_path_factory.mktemp("few"), chosen)
    assert len(result.stories) == len(FEW) and result.findings == []
    yield result
    store.close()


def _digests(result: LoopRunResult) -> dict[tuple[str, str | None], list[str]]:
    return {(tenant, story.load_number): [m.digest() for m in story.moments]
            for (tenant, _), story in result.stories.items()}


def _final(result: LoopRunResult) -> dict[tuple[str, str | None], tuple]:
    return {(tenant, story.load_number): signature(story.last.state)
            for (tenant, _), story in result.stories.items()}


# ============================================================ the loads, whole

def test_every_labeled_moment_of_every_load_holds(loop):
    """Twenty-one histories, twenty-two loads, two brokerages, one inbox each. Every moment a
    history LABELS is what the loop said. Counted, not assumed."""
    result, _ = loop
    assert len(result.histories) == 21 and len(result.stories) == 22
    assert {h.history.tenant for h in result.histories} == {NORTHLINE, CEDAR}
    for item in result.histories:
        assert len(item.checkpoints) >= 2, f"{item.history.history_id} labels almost nothing"
        assert item.mismatches == [], item.mismatches
    metrics = result.report["metrics"]
    assert metrics["labeled_checks"] >= 450 and metrics["labeled_checks_failed"] == 0
    assert metrics["wrong_cross_tenant_mappings"] == 0
    assert metrics["external_effect_rows"] == 0


def test_the_loads_carry_the_trouble_they_claim(loop):
    """Each kind of trouble asked for has a load that carries it - and the run shows it happened:
    deadlines did pass in silence, duplicates were suppressed, humans did act."""
    result, _ = loop
    claimed = {tag for h in result.histories for tag in h.history.hostile}
    assert REQUIRED_TROUBLE <= claimed, sorted(REQUIRED_TROUBLE - claimed)
    metrics = result.report["metrics"]
    assert metrics["deadlines_passed_in_silence"] >= 8
    assert metrics["duplicate_records_suppressed"] >= 4
    assert metrics["human_acts_recorded"] >= 5
    # A complete load, not a fragment: every one of them gets as far as a delivery report.
    assert {s.last.state.stage for s in result.stories.values()} == {Stage.DELIVERED}


def test_a_load_that_needs_nobody_costs_zero_touches_and_ends_quiet(loop):
    result, _ = loop
    story = result.story(NORTHLINE, "LD-50001")
    last = story.last
    assert last.quiet and last.billing_ready and last.next_step == "NOTHING"
    assert (last.touches.acts, last.touches.open, last.touches.total) == (0, 0, 0)
    assert not [m for m in story.moments if m.escalations], "a clean load asked a human something"
    # It was not quiet the whole way: it waited, and Neyma would have asked for the POD.
    assert {m.next_step for m in story.moments} >= {"WAIT", "NEYMA:REQUEST_POD", "NOTHING"}


# ============================================================ no false quiet

def test_no_load_is_ever_quiet_while_anything_is_owed_waited_for_or_disputed(loop):
    """The oracle reads the canonical record itself - open Conflicts, owed Expectations, open
    Exceptions whose cause stands, unmet requirements, unplaced paper - and is run on EVERY
    evaluation of every load, thousands of them, not only the moments a story shows."""
    result, _ = loop
    assert result.report["metrics"]["evaluations"] >= 4000
    assert result.findings == [], result.findings[:5]
    quiet = [m for s in result.stories.values() for m in s.moments if m.quiet]
    busy = [m for s in result.stories.values() for m in s.moments if not m.quiet]
    assert len(quiet) >= 30 and len(busy) >= 200, (len(quiet), len(busy))
    for moment in quiet:
        assert moment.state.needs == () and moment.booked
        assert not moment.overdue and not moment.escalations and not moment.proposals


def test_the_oracle_fires_when_a_load_is_made_falsely_quiet(loop):
    """Anti-vacuity: take a moment with work, strip the work, and the oracle must object. A check
    that cannot fail on a falsely quiet load proves nothing about the thousands it passed."""
    result, _ = loop
    story = result.story(NORTHLINE, "LD-50017")              # the overbilled invoice, still open
    view = result.intakes[NORTHLINE].projection().loads[story.load_id]
    honest = evaluate_load_work(view, setup=LOOP_SETUPS[NORTHLINE],
                                as_of=result.intakes[NORTHLINE].foundation.now())
    assert honest.needs and audit_state(honest, view, tenant=NORTHLINE) == []
    findings = audit_state(replace(honest, needs=()), view, tenant=NORTHLINE)
    assert any("FALSE QUIET" in f for f in findings) and any("SILENT STALL" in f for f in findings)


def test_a_load_nobody_has_booked_is_never_called_quiet(few):
    """A tendered load with unconfirmed appointments has no needs - only because finding it a
    carrier is outside this loop. It is reported NOT quiet, and never as finished."""
    tender = few.story(NORTHLINE, "LD-50016").at("tender")
    assert tender.state.stage is Stage.PLANNING and tender.state.needs == ()
    assert not tender.quiet and not tender.booked and tender.next_step == "NOT_BOOKED"


def test_a_disputed_load_stays_a_humans_until_a_human_settles_it(few):
    """The driver says delivered; the tracking provider says moving. Then the provider reports
    arrival, the TMS says delivered and a signed POD arrives - and the load is STILL disputed,
    still not quiet and still not billing-ready, because agreeing later is not a human deciding."""
    story = few.story(NORTHLINE, "LD-50007")
    between = [m for m in story.moments
               if story.at("provider-says-moving").index <= m.index < story.at("dana-confirms").index]
    assert len(between) >= 4
    for moment in between:
        assert moment.state.stage is Stage.DISPUTED and not moment.quiet
        assert not moment.billing_ready
        assert [e.kind for e in moment.escalations] == ["EVIDENCE_CONFLICT"]
    settled = story.at("dana-confirms")
    assert settled.state.stage is Stage.DELIVERED and settled.quiet and settled.billing_ready
    assert (settled.touches.acts, settled.touches.open) == (1, 0)


# ============================================================ time passing

def test_a_deadline_that_passes_in_silence_is_a_moment_of_its_own(few, tmp_path):
    """The pickup window closes at noon and nothing arrives. The loop looks at 12:01 and the late
    pickup is work then - not ninety minutes later, when the truck finally shows up and the lateness
    is already over."""
    story = few.story(NORTHLINE, "LD-50002")
    ticks = [m for m in story.moments if m.trigger_kind == "tick"]
    assert len(ticks) == 1
    tick = ticks[0]
    assert tick.as_of == "2026-08-04T17:01:00.000Z"          # 12:01 Central
    assert [n.kind for n in tick.overdue] == [NeedKind.CARRIER_STATUS_OVERDUE]
    assert [p.action for p in tick.proposals] == ["REQUEST_CARRIER_STATUS"]
    assert tick.proposals[0].draft and "LD-50002" in tick.proposals[0].draft
    assert {c.token() for c in tick.changes} >= {"OPENED:CARRIER_STATUS_OVERDUE"}

    # Without looking at deadlines, the only late-pickup moment is the one where it is cured.
    alone = [h for h in build_loop_histories() if h.history_id == "L02"]
    blind, store = _run(tmp_path, alone, tick_at_deadlines=False)
    try:
        unseen = blind.story(NORTHLINE, "LD-50002")
        assert not [m for m in unseen.moments if m.trigger_kind == "tick"]
        assert not [m for m in unseen.moments if m.overdue]
        assert blind.report["metrics"]["deadlines_passed_in_silence"] == 0
    finally:
        store.close()


def test_many_reasons_for_one_silence_are_one_follow_up(loop):
    """The driver went dark for a day: the cadence passed, then the receiver's window. That is one
    piece of work the whole time, not one per reason."""
    result, _ = loop
    story = result.story(NORTHLINE, "LD-50004")
    silent = [m for m in story.moments if m.overdue]
    assert len(silent) >= 2
    for moment in silent:
        assert [n.kind for n in moment.state.needs
                if n.kind is NeedKind.CARRIER_STATUS_OVERDUE] == [NeedKind.CARRIER_STATUS_OVERDUE]
        assert len({p.action for p in moment.proposals}) == 1
    assert len({n.need_id for m in silent for n in m.overdue}) == 1


# ============================================================ replay, duplicates, restart

def test_replaying_the_inbox_gives_the_same_pictures(loop, tmp_path):
    result, _ = loop
    again, store = _run(tmp_path)
    try:
        assert _digests(again) == _digests(result)
        assert sum(len(v) for v in _digests(result).values()) >= 300
        assert again.report["metrics"] == result.report["metrics"]
    finally:
        store.close()


#: The loads on which a human acted, a dispute was open, paper moved between loads or the inbox
#: was already out of order: where a second copy of a record would do the most damage if it did any.
TWICE = ("L01", "L07", "L12", "L15", "L17", "L18", "L19", "L21")


def test_every_record_arriving_twice_changes_no_load(tmp_path):
    """Each record of each history is delivered a second time right behind itself - a human's act
    included. Every load ends with exactly the work and exactly the touches it had, and every
    second copy is recognized. (Every Northline load is doubled again, one at a time, by the hostile
    layer below; here they are doubled TOGETHER, in one inbox.)"""
    chosen = [h for h in build_loop_histories() if h.history_id in TWICE]
    once, store_once = _run(tmp_path / "once", chosen)
    twice, store_twice = _run(tmp_path / "twice", [duplicate_every_record(h) for h in chosen])
    try:
        assert len(chosen) == len(TWICE) and len(once.stories) == 9
        assert _final(twice) == _final(once)
        observations = sum(1 for h in chosen for r in h.records if r.kind in OBSERVATION_KINDS)
        assert observations >= 140
        assert twice.report["metrics"]["duplicate_records_suppressed"] \
            == observations + once.report["metrics"]["duplicate_records_suppressed"]
        assert once.findings == [] and twice.findings == []
        assert {k: (s.last.touches.acts, s.last.touches.open) for k, s in twice.stories.items()} \
            == {k: (s.last.touches.acts, s.last.touches.open) for k, s in once.stories.items()}
        assert sum(s.last.touches.acts for s in once.stories.values()) == 5
    finally:
        store_once.close()
        store_twice.close()


def test_a_restart_in_the_middle_of_every_load_loses_nothing(loop, tmp_path):
    """The process is thrown away halfway through each history and a new one is built over the same
    database. Every picture after it is the picture an uninterrupted run shows."""
    result, _ = loop
    middles = {h.history_id: h.records[len(h.records) // 2].label for h in build_loop_histories()}
    again, store = _run(tmp_path, restart_after=middles)
    try:
        assert len(middles) == 21
        assert _digests(again) == _digests(result)
        assert again.findings == []
    finally:
        store.close()


def test_a_restart_just_before_a_deadline_still_sees_the_deadline(tmp_path):
    """The process dies right after the rate confirmation. The next thing that happens to this load
    is nothing at all: the pickup window closes. A rebuilt process has not been told the time yet,
    and the deadline is a deadline anyway - the loop remembers when it last looked."""
    alone = [h for h in build_loop_histories() if h.history_id == "L02"]
    whole, store_whole = _run(tmp_path / "whole", alone)
    restarted, store_restarted = _run(tmp_path / "restarted", alone,
                                      restart_after={"L02": "rate-con"})
    try:
        story = restarted.story(NORTHLINE, "LD-50002")
        after = [m.trigger_kind for m in story.moments
                 if m.index > story.at("rate-con").index][:1]
        assert after == ["tick"], f"the first thing after the restart was {after}, not the deadline"
        assert [n.kind for n in story.moments[story.moments.index(story.at("rate-con")) + 1].overdue] \
            == [NeedKind.CARRIER_STATUS_OVERDUE]
        assert _digests(restarted) == _digests(whole)
    finally:
        store_whole.close()
        store_restarted.close()


def test_building_a_picture_writes_nothing(loop):
    """The picture is a read model. Building every load's picture again leaves every canonical table
    exactly as it was."""
    result, conn = loop
    before = row_counts(conn)
    assert sum(before.values()) > 1000
    built = 0
    for tenant, intake in result.intakes.items():
        as_of = intake.foundation.now()
        for load_id, view in intake.projection().loads.items():
            state = evaluate_load_work(view, setup=intake.setup, as_of=as_of)
            moment = build_moment(view, state, previous=result.stories[(tenant, load_id)].last,
                                  index=0, history_id="-", trigger="again", trigger_kind="clock",
                                  disposition="CONTROL", about_this_load=False)
            assert moment.digest() == result.stories[(tenant, load_id)].last.digest() \
                or moment.as_of != result.stories[(tenant, load_id)].last.as_of
            built += 1
    assert built == 22 and row_counts(conn) == before


# ============================================================ two brokerages

def test_two_brokerages_with_one_load_number_never_touch(loop):
    """LD-50014 exists at Cedar Ridge and at Northline: same number, PO, BOL, PRO, carrier, rate
    confirmation and invoice number. Cedar Ridge's POD arrived. Northline's never did. Cedar
    Ridge's paper satisfies nothing at Northline."""
    result, conn = loop
    cedar, north = result.story(CEDAR, "LD-50014"), result.story(NORTHLINE, "LD-50014")
    assert cedar.load_id != north.load_id
    assert cedar.last.quiet and cedar.last.billing_ready
    assert not north.last.billing_ready and not north.last.quiet
    assert [n.kind for n in north.last.overdue] == [NeedKind.DOCUMENT_REQUIRED]
    for story, tenant in ((cedar, CEDAR), (north, NORTHLINE)):
        needs = [n for m in story.moments for n in m.state.needs]
        assert needs and {n.tenant_id for n in needs} == {tenant}
    north_view = result.intakes[NORTHLINE].projection().loads[north.load_id]
    cedar_view = result.intakes[CEDAR].projection().loads[cedar.load_id]
    assert cedar_view.documents and north_view.documents.keys().isdisjoint(cedar_view.documents)
    assert {o["tenant"] for o in north_view.observations} == {NORTHLINE}
    assert cross_tenant_violations(conn) == []


# ============================================================ human touches

def test_a_humans_decision_is_a_touch_and_so_is_one_still_owed(few):
    """Dana settled the tracking dispute: one decision recorded, nothing owed. The overbilled
    invoice is nobody's decision yet: nothing recorded, one owed. The late pickup cost nobody
    anything."""
    def touches(number: str) -> tuple[int, int, int]:
        last = few.story(NORTHLINE, number).last.touches
        return last.acts, last.open, last.total

    assert touches("LD-50007") == (1, 0, 1)
    assert touches("LD-50017") == (0, 1, 1)
    assert touches("LD-50002") == (0, 0, 0)
    assert few.report["metrics"]["human_touches_total"] == 2
    assert few.report["metrics"]["loads_with_zero_human_touches"] == 2


def test_human_touches_are_read_from_the_record(loop):
    """A touch is a decision a human recorded on the load, or one still owed. Sixteen of these
    twenty-two loads cost none."""
    result, _ = loop
    touches = {s.load_number if t == NORTHLINE else f"cedar:{s.load_number}":
               (s.last.touches.acts, s.last.touches.open)
               for (t, _), s in result.stories.items()}
    costly = {k: v for k, v in touches.items() if v != (0, 0)}
    assert costly == {
        "LD-50007": (1, 0),      # Dana settles the tracking dispute
        "LD-50013": (1, 0),      # Priya moves the misnumbered POD
        "LD-50015": (1, 0),      # Dana confirms the moved appointment
        "LD-50017": (0, 1),      # the overbilled invoice: still nobody's decision
        "LD-50018": (1, 0),      # Marcus places the invoice
        "LD-50019": (1, 1),      # Marcus denies detention; the invoice still bills it
    }, costly
    metrics = result.report["metrics"]
    assert metrics["loads_with_zero_human_touches"] == 16
    assert metrics["human_touches_total"] == 7 and metrics["human_touches_max_on_one_load"] == 2
    assert metrics["human_acts_recorded"] == 5 and metrics["human_questions_open"] == 2


def test_a_question_the_record_answers_costs_no_touch(loop):
    """The TMS named the wrong carrier, so the right carrier's invoice was a human's question. The
    system of record was corrected before she answered. The question is gone and she never acted."""
    result, _ = loop
    story = result.story(NORTHLINE, "LD-50020")
    asked = story.at("invoice")
    assert [e.kind for e in asked.escalations] == ["INVOICE_UNATTRIBUTED"]
    assert asked.touches.total == 1
    cured = story.at("carrier-corrected")
    assert cured.quiet and cured.touches.total == 0 and cured.touches.answered == 0
    assert story.summary()["human_questions_ever"] == 1


def test_cured_exceptions_awaiting_closure_are_counted_and_are_not_called_touches(loop):
    """An Exception whose cause the record shows cured stays open in M9 until a human closes it.
    That is not work on the load and is not counted as a touch - and it is not hidden either."""
    result, _ = loop
    metrics = result.report["metrics"]
    assert metrics["cured_exceptions_awaiting_human_closure"] >= 10
    story = result.story(NORTHLINE, "LD-50002")                 # the late pickup, long since cured
    assert story.last.quiet and story.last.touches.total == 0
    assert story.summary()["cured_exceptions_awaiting_closure"] == 1


# ============================================================ the tracking dispute and the human

def _disputed(history_id: str):
    """A load on which the driver has said delivered and the tracking provider then says moving."""
    h = _builder(history_id, "a tracking dispute", "2026-09-01", "contradictory_tracking")
    load = Load(h, "LD-59001", customer="great_lakes_bev", carrier="summit", sell=172000,
                buy=141000, serial="79001", pickup="Great Lakes Beverage Bloomington",
                delivery="Maumee Distributing", delivery_zone="America/New_York")
    load.book()
    load.track("at-pickup", h.t("10:10"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:00"), "LOADED", "S1")
    load.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
    load.sms("driver-says-delivered", h.t("07:30", 1), "delivered, empty",
             says("DELIVERED", "S2"))
    load.track("provider-says-moving", h.t("07:35", 1), "IN_TRANSIT", position="I-75 N")
    return h, load


def _story_and_view(tmp_path: Path, h):
    result, store = _run(tmp_path, [h.build({})])
    story = result.story(NORTHLINE, "LD-59001")
    view = result.intakes[NORTHLINE].projection().loads[story.load_id]
    return result, store, story, view


def test_a_later_contradiction_after_a_humans_decision_is_a_new_dispute(tmp_path):
    """Dana says it delivered. An hour later the provider puts the truck on the road again. Her
    decision is kept, with its parties; the new statement is a NEW Conflict, and hers to decide."""
    h, load = _disputed("PA")
    h.human("dana-confirms", h.t("08:00", 1), "dana.ortiz", "confirm_movement_status",
            refs=load.refs, status="DELIVERED", stop_key="S2", note="receiver confirmed")
    load.track("provider-moving-again", h.t("09:00", 1), "IN_TRANSIT", position="I-75 S")
    result, store, story, view = _story_and_view(tmp_path, h)
    try:
        decided = story.at("dana-confirms")
        assert decided.state.stage is Stage.DELIVERED and not decided.escalations
        again = story.at("provider-moving-again")
        assert again.state.stage is Stage.DISPUTED
        assert [e.kind for e in again.escalations] == ["EVIDENCE_CONFLICT"]
        assert (again.touches.acts, again.touches.open) == (1, 1)
        conflicts = [c for c in view.conflicts if c["field"] == "tracking_status"]
        assert sorted(c["state"] for c in conflicts) == ["RAISED", "RESOLVED_BY_HUMAN"]
        assert len({c["conflict_id"] for c in conflicts}) == 2
        assert all(len(c["parties"]) == 2 for c in conflicts), "a party's statement was dropped"
        assert result.findings == []
    finally:
        store.close()


def test_a_human_who_says_it_has_not_delivered_overrules_the_claim(tmp_path):
    """Dana says the driver hit the wrong button. His "delivered" stays on the record as what he
    said and stops counting as a delivery: the load is in transit, no POD is asked for, and Neyma
    goes back to watching it - so it is not quiet. Then it really delivers."""
    h, load = _disputed("PB")
    h.human("dana-says-moving", h.t("08:00", 1), "dana.ortiz", "confirm_movement_status",
            refs=load.refs, status="IN_TRANSIT", note="receiver has not seen him")
    load.track("at-delivery", h.t("13:30", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("14:00", 1))
    load.pod("pod", h.t("14:30", 1))
    result, store, story, view = _story_and_view(tmp_path, h)
    try:
        moving = story.at("dana-says-moving")
        assert moving.state.stage is Stage.IN_TRANSIT and not moving.quiet
        assert not moving.escalations and not moving.billing_ready
        assert moving.state.need(NeedKind.DOCUMENT_REQUIRED) is None
        assert moving.state.need(NeedKind.TRACKING_UPDATE_PENDING) is not None
        overruled = [t for t in view.tracking if t.overruled_by]
        assert [(t.value("signal"), t.value("status")) for t in overruled] \
            == [("driver_assertion", "DELIVERED")]
        assert len(view.tracking) >= 10, "the overruled claim must stay on the record"
        done = story.at("pod")
        assert done.state.stage is Stage.DELIVERED and done.quiet and done.billing_ready
        assert result.findings == []
    finally:
        store.close()


def test_only_a_recorded_human_and_only_a_real_status_can_settle_it(tmp_path):
    """An assertion in the name of nobody this brokerage has recorded settles nothing, and is
    itself put in front of a human. A status that is not a movement status is not an act at all."""
    h, load = _disputed("PC")
    h.human("nobody-confirms", h.t("08:00", 1), "mallory.x", "confirm_movement_status",
            refs=load.refs, status="DELIVERED")
    h.clock("end", h.t("12:00", 1))
    result, store, story, view = _story_and_view(tmp_path, h)
    try:
        assert story.last.state.stage is Stage.DISPUTED and not story.last.quiet
        assert [c["state"] for c in view.conflicts if c["field"] == "tracking_status"] == ["RAISED"]
        assert story.last.touches.acts == 0
        unplaced = result.unplaced[NORTHLINE]
        assert [n.reason_codes for n in unplaced] == [("UNAUTHENTICATED_HUMAN_ASSERTION",)]
        assert "(no load)" in render_board(result)
        assert result.report["metrics"]["work_on_no_load_needing_a_human"] == 1
    finally:
        store.close()

    g, other = _disputed("PD")
    g.human("nonsense", g.t("08:00", 1), "dana.ortiz", "confirm_movement_status",
            refs=other.refs, status="PROBABLY_FINE")
    with pytest.raises(UnparseableRecord, match="PROBABLY_FINE"):
        parse_record(g.records[-1])


def test_no_source_but_a_recorded_human_can_speak_as_the_owner():
    """The owner's confirmation is produced only by the human act. A tracking record that names
    itself the owner's confirmation is not a tracking record: it has no way in."""
    h, load = _disputed("PE")
    h.track("provider-claims-to-be-the-owner", h.t("08:00", 1), "DELIVERED", refs=load.refs,
            stop_key="S2")
    forged = replace(h.records[-1], payload={**h.records[-1].payload,
                                             "signal": "owner_confirmation"})
    with pytest.raises(UnparseableRecord, match="owner_confirmation"):
        parse_record(forged)
    assert parse_record(h.records[-1])["payload"]["signal"] == "tracking_provider_position"


# ============================================================ words, not effects

def test_a_proposal_is_words_and_nothing_is_sent(few):
    """Every proposal says it was not sent, every message action has a draft a human could read, and
    the effect and authority ledgers hold zero rows."""
    result = few
    proposals = [p for s in result.stories.values() for m in s.moments for p in m.proposals]
    assert len(proposals) >= 10
    assert {p.as_document()["sent"] for p in proposals} == {False}
    drafted = {p.action for p in proposals if p.draft}
    assert drafted == {ShadowAction.REQUEST_CARRIER_STATUS.value, ShadowAction.REQUEST_POD.value,
                       ShadowAction.VERIFY_APPOINTMENT.value}
    assert all(p.draft for p in proposals if p.action in drafted)
    assert result.report["metrics"]["external_effect_rows"] == 0
    assert {tenant: sum(rows.values())
            for tenant, rows in result.report["effect_surface_rows"].items()} == {NORTHLINE: 0}


def test_twenty_one_loads_leave_no_row_in_any_effect_or_authority_ledger(loop):
    result, _ = loop
    proposals = [p for s in result.stories.values() for m in s.moments for p in m.proposals]
    assert len(proposals) >= 50 and {p.as_document()["sent"] for p in proposals} == {False}
    assert {tenant: sum(rows.values())
            for tenant, rows in result.report["effect_surface_rows"].items()} \
        == {CEDAR: 0, NORTHLINE: 0}


def test_an_escalation_carries_what_a_human_needs_to_decide(loop):
    result, _ = loop
    escalations = [e for s in result.stories.values() for m in s.moments for e in m.escalations]
    assert len(escalations) >= 20
    for item in escalations:
        assert item.owner_id and item.why and item.evidence and item.reason_codes
    asked = result.story(NORTHLINE, "LD-50017").last.escalations[0]
    assert asked.kind == "INVOICE_DISCREPANCY" and asked.owner_id == "dana.ortiz"
    assert asked.question and "LINEHAUL_MISMATCH" in asked.reason_codes


def test_no_picture_carries_money(few):
    """A picture names a discrepancy by its code. The timeline sentences it quotes have their
    amounts withheld - and the withholding is seen to work on a sentence that has one."""
    moments = [m for s in few.stories.values() for m in s.moments]
    assert len(moments) >= 40
    carrying = [(m.load_number, m.trigger) for m in moments
                if _MONEY.search(json.dumps(m.as_document(), default=str))]
    assert carrying == []
    withheld = [e for m in moments for e in m.evidence if "[amount withheld]" in e]
    assert len(withheld) >= 5, "no amount was ever withheld: these loads exercised nothing"
    assert without_money("rate confirmation RC-1 received: buy USD 1,610.00 OUT") \
        == "rate confirmation RC-1 received: buy [amount withheld]"
    assert _MONEY.search("buy USD 1,610.00 OUT") and not _MONEY.search(
        without_money("linehaul +USD 80.00 vs $1,430.00"))


def test_no_picture_of_any_of_the_twenty_two_loads_carries_money(loop):
    result, _ = loop
    moments = [m for s in result.stories.values() for m in s.moments]
    assert len(moments) >= 300
    assert [(m.load_number, m.trigger) for m in moments
            if _MONEY.search(json.dumps(m.as_document(), default=str))] == []


# ============================================================ the hostile layer

def test_the_hostile_mutation_layer_finds_nothing_in_the_complete_loads(tmp_path):
    """Every Northline load, with one thing an inbox really does done to it: every record twice, the
    first record again at the end, a restart in the middle, the same load already at another
    brokerage, neighbours swapped, a message delayed to the end, a promise repeated - and every
    record that is not a routine ping, never arriving at all. The oracle audits every load after
    every record. No stall, no stale work, no false quiet, no leak."""
    bases = [h for h in build_loop_histories() if h.tenant == NORTHLINE]
    mutants = [m for m in build_mutants(bases)
               if m.operator != "never_arrives" or "ping" not in m.mutant_id]
    operators = {m.operator for m in mutants}
    assert operators == {"duplicate_arrival", "late_redelivery", "restart",
                         "same_load_at_another_brokerage", "never_arrives", "reordered",
                         "arrives_late", "repeated_promise"}
    assert len(bases) == 20 and len(mutants) >= 250

    def one(mutant: Mutant, name: str):
        store = WorkflowStore(tmp_path / f"{name}.db", tenant=NORTHLINE)
        try:
            return run_mutant(store.conn, mutant, setups=LOOP_SETUPS)
        finally:
            store.close()

    base_runs = {h.history_id: one(Mutant(f"{h.history_id}:base", "base", h.history_id, (h,)),
                                   f"base-{h.history_id}") for h in bases}
    findings = [f for r in base_runs.values() for f in r.findings]
    evaluations = 0
    for index, mutant in enumerate(mutants):
        run = one(mutant, f"m{index}")
        evaluations += run.evaluations
        findings.extend(run.findings)
        if mutant.same_final_work_as_base and run.final != base_runs[mutant.base].final:
            findings.append(f"{mutant.mutant_id}: the final work differs from the unmutated load's")
    assert evaluations >= 5000
    assert findings == [], findings[:5]


# ============================================================ what an operator sees

def test_the_board_the_story_and_the_moment_read_like_an_operators_answer(loop):
    result, _ = loop
    board = render_board(result).splitlines()
    assert len(board) == 23 and board[0].split()[:4] == ["LOAD", "BROKERAGE", "STAGE", "POSTURE"]
    story = result.story(NORTHLINE, "LD-50007")
    assert len(render_trace(story).splitlines()) == len(story.moments) + 1
    text = render_moment(story.at("provider-says-moving"))
    for number in range(1, 14):
        assert f"\n{number:2d} " in "\n" + text, f"answer {number} is missing"
    assert "Which statement is right?" in text and "dana.ortiz" in text
    whole = render_story(result.story(NORTHLINE, "LD-50002"), detail=True)
    assert "DRAFT, NOT SENT:" in whole and "(a deadline passed; nothing arrived)" in whole
