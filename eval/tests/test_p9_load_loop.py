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

from freight_corpus.builders import TRACKING, says  # noqa: E402
from freight_corpus.loop_histories import (  # noqa: E402
    LOOP_SETUPS,
    Load,
    _builder,
    _in_arrival_order,
    build_loop_histories,
)
from freight_corpus.parties import CEDAR, CEDAR_OPS, NORTHLINE, SETUPS  # noqa: E402
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
    NeedStatus,
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


_OWED = ("RAISED", "OVERDUE", "INDETERMINATE")
_AT_A_STOP = frozenset({"AT_PICKUP", "LOADED", "AT_DELIVERY", "DELIVERED"})
_PAST_A_STOP = {"PICKUP": frozenset({"LOADED", "IN_TRANSIT", "AT_DELIVERY", "DELIVERED"}),
                "DELIVERY": frozenset({"AT_DELIVERY", "DELIVERED"})}


def _unwatched_stops(view, setup) -> list[str]:
    """A SECOND ORACLE, written without the detectors: at a brokerage that watches arrivals, a stop
    with a confirmed appointment has either a STANDING claim that the truck has been there, or a
    live watch. Neither means nobody is waiting for that truck - which is how a load whose only
    delivery report a human overruled went quiet. `audit_state` cannot see it: it reads what the
    record still OWES, and a watch that was wrongly answered owes nothing."""
    if setup.arrival_tracking_channel is None:
        return []
    out: list[str] = []
    for stop_key, appointment in sorted(view.appointments.items()):
        if appointment.value("status") != "CONFIRMED" or appointment.value("window") is None:
            continue
        kind = view.stops[stop_key].value("stop_type")
        only = len([s for s in view.stops.values() if s.value("stop_type") == kind]) == 1
        been = [t for t in view.tracking if t.overruled_by is None and (
            (t.stop_key == stop_key and t.value("status") in _AT_A_STOP)
            or (only and t.stop_key is None and t.value("status") in _PAST_A_STOP[kind]))]
        live = [e for e in view.expectations
                if e["expected_type"] == f"arrival:{stop_key}" and e["state"] in _OWED]
        if not been and not live:
            out.append(f"{view.load.value('load_ref')}: UNWATCHED STOP - nothing standing says "
                       f"the truck reached {stop_key}, and nothing is waiting for it")
    return out


def _run(path: Path, histories=None, *, setups=LOOP_SETUPS,
         **kw) -> tuple[LoopRunResult, WorkflowStore]:
    histories = build_loop_histories() if histories is None else histories
    path.mkdir(parents=True, exist_ok=True)
    store = WorkflowStore(path / "loop.db", tenant=histories[0].tenant)
    kw.setdefault("audit", lambda state, view, tenant: [
        *audit_state(state, view, tenant=tenant), *_unwatched_stops(view, setups[tenant])])
    return run_load_loop(store.conn, setups, histories, **kw), store


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


def test_the_second_oracle_fires_when_a_stop_is_left_unwatched(loop):
    """Anti-vacuity for `_unwatched_stops`, which every run in this file applies to every
    evaluation of every load. It is quiet about the loads as they are - over a population that is
    counted - and it objects the moment every claim that answered a watch is overruled and no
    watch is owed in its place: the state the unrepaired spine left a load in."""
    result, _ = loop
    setup = LOOP_SETUPS[NORTHLINE]
    views = result.intakes[NORTHLINE].projection().loads
    confirmed = [(view, key) for view in views.values() for key, a in view.appointments.items()
                 if a.value("status") == "CONFIRMED"]
    assert len(views) == 21 and len(confirmed) >= 30
    assert [f for view in views.values() for f in _unwatched_stops(view, setup)] == []

    late = views[result.story(NORTHLINE, "LD-50014").load_id]         # delivered, POD never came
    answered = [t for t in late.tracking if t.stop_key == "S2"]
    assert answered and not [e for e in late.expectations
                             if e["expected_type"] == "arrival:S2" and e["state"] in _OWED]
    for event in answered:
        event.overruled_by = "obs-nobody"                # as if a human had overruled every one
    bare = [t for t in late.tracking if t.stop_key is None and t.overruled_by is None
            and t.value("status") in _PAST_A_STOP["DELIVERY"]]
    for event in bare:
        event.overruled_by = "obs-nobody"
    assert [f.split(": ", 1)[1][:14] for f in _unwatched_stops(late, setup)] == ["UNWATCHED STOP"]
    assert _unwatched_stops(late, replace(setup, arrival_tracking_channel=None)) == []


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
        # ... and to watching the DELIVERY: the appointment his "delivered" had answered is owed.
        assert moving.state.need(NeedKind.ARRIVAL_PENDING) is not None
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


# ============================================================ an overruled claim answers nothing

#: Northline as the freight corpus ships it: an arrival watch and NO tracking cadence. Whatever
#: keeps a load from going falsely quiet under these setups is not the optional cadence.
NO_CADENCE = SETUPS
#: The delivery appointment below is 09:00-11:00 Eastern on the second day.
WINDOW_CLOSES = "2026-09-02T15:00:00.000Z"
LOOKS_AGAIN = "2026-09-02T15:01:00.000Z"


def _picked_up(history_id: str, *, tenant: str = NORTHLINE, **load):
    """A booked load, picked up inside its window and pinged inside the cadence overnight."""
    h = _builder(history_id, "an overruled claim", "2026-09-01", "contradictory_tracking",
                 tenant=tenant)
    cargo = Load(h, "LD-59001", customer="great_lakes_bev", carrier="summit", sell=172000,
                 buy=141000, serial="79001", pickup="Great Lakes Beverage Bloomington",
                 delivery="Maumee Distributing", delivery_zone="America/New_York", **load)
    cargo.book()
    cargo.track("at-pickup", h.t("10:10"), "AT_PICKUP", "S1")
    cargo.track("loaded", h.t("11:00"), "LOADED", "S1")
    cargo.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
    return h, cargo


def _falsely_delivered(history_id: str, *, overruled: bool = True, **load):
    """The driver says delivered before the delivery window opens. The provider puts him on the
    road. Then - unless `overruled` is False - Dana says he has NOT delivered."""
    h, cargo = _picked_up(history_id, **load)
    cargo.sms("driver-says-delivered", h.t("07:30", 1), "delivered, empty",
              says("DELIVERED", "S2"))
    cargo.track("provider-says-moving", h.t("07:35", 1), "IN_TRANSIT", position="I-75 N")
    if overruled:
        h.human("dana-says-moving", h.t("08:00", 1), "dana.ortiz", "confirm_movement_status",
                refs=cargo.refs, status="IN_TRANSIT", note="receiver has not seen him")
    return h, cargo


def _watches(view, expected_type: str) -> list[dict]:
    return [e for e in view.expectations if e["expected_type"] == expected_type]


def _work(moment) -> list[tuple]:
    return [(n.kind, n.status, n.reason_codes, n.due_by) for n in moment.state.needs]


def _view(result: LoopRunResult, tenant: str = NORTHLINE):
    story = result.story(tenant, "LD-59001")
    return story, result.intakes[tenant].projection().loads[story.load_id]


def test_an_overruled_delivery_claim_stops_answering_the_delivery_watch(tmp_path):
    """THE REVIEW'S REPRODUCTION, with no tracking cadence to hide behind. The driver's "delivered"
    answered the delivery appointment's watch. Dana overrules him - and the watch his word answered
    is OWED AGAIN: the load is not quiet, the window closes with nobody at the dock, and the late
    delivery is work, exactly as it is for a truck that is simply late. His claim, the watch it
    once answered and her decision are all still on the record."""
    h, cargo = _falsely_delivered("QA")
    cargo.track("still-moving", h.t("16:30", 1), "IN_TRANSIT", position="I-75 N")
    h.clock("end", h.t("22:00", 1))
    g, plain = _picked_up("QA")
    plain.track("provider-says-moving", g.t("07:35", 1), "IN_TRANSIT", position="I-75 N")
    plain.track("still-moving", g.t("16:30", 1), "IN_TRANSIT", position="I-75 N")
    g.clock("end", g.t("22:00", 1))
    result, store = _run(tmp_path / "overruled", [h.build({})], setups=NO_CADENCE)
    simply_late, late_store = _run(tmp_path / "late", [g.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        assert story.at("driver-says-delivered").state.stage is Stage.DELIVERED
        decided = story.at("dana-says-moving")
        assert decided.state.stage is Stage.IN_TRANSIT and not decided.quiet
        watch = decided.state.need(NeedKind.ARRIVAL_PENDING)
        assert watch is not None and watch.due_by == WINDOW_CLOSES
        assert decided.next_step == "WAIT" and not decided.escalations

        closed = [m for m in story.moments if m.trigger_kind == "tick"]
        assert [m.as_of for m in closed] == [LOOKS_AGAIN]
        assert [n.kind for n in closed[0].overdue] == [NeedKind.CARRIER_STATUS_OVERDUE]
        assert closed[0].overdue[0].reason_codes == ("ARRIVAL:S2_OVERDUE",)
        assert closed[0].next_step == "NEYMA:REQUEST_CARRIER_STATUS"

        last = story.last
        assert not last.quiet and last.next_step == "NEYMA:REQUEST_CARRIER_STATUS"
        assert [m.trigger for m in story.moments if m.quiet] == []
        # The work is what a truck that is simply late owes: no less, and no second copy.
        plain_last = simply_late.story(NORTHLINE, "LD-59001").last
        assert _work(last) == _work(plain_last) and len(_work(last)) == 1

        # NOTHING WAS REWRITTEN TO GET THERE. The watch his claim answered is still DISCHARGED, by
        # his record; the watch that is owed is a second row; his claim is still on the load,
        # overruled; and her decision still holds the dispute it settled, with both parties.
        watches = _watches(view, "arrival:S2")
        assert [e["state"] for e in watches] == ["DISCHARGED", "OVERDUE"]
        claim = [t for t in view.tracking if t.overruled_by]
        assert [(t.value("signal"), t.value("status")) for t in claim] \
            == [("driver_assertion", "DELIVERED")]
        assert watches[0]["discharge_observation_id"] == claim[0].origin_observation_id
        conflicts = [c for c in view.conflicts if c["field"] == "tracking_status"]
        assert [(c["state"], len(c["parties"])) for c in conflicts] == [("RESOLVED_BY_HUMAN", 2)]
        # ... and the picture never says his overruled word SATISFIED anything.
        told = {(s.kind, s.how, s.by) for m in story.moments if m.index >= decided.index
                for s in m.state.settled}
        assert len(told) >= 4
        assert not [t for t in told if t[1] == "SATISFIED"
                    and t[2] == f"observation:{claim[0].origin_observation_id}"]
        assert (NeedKind.ARRIVAL_PENDING, "SUPERSEDED",
                f"observation:{claim[0].overruled_by}") in told
        assert result.findings == [] and simply_late.findings == []
        assert result.report["metrics"]["external_effect_rows"] == 0
    finally:
        store.close()
        late_store.close()


def test_a_missed_delivery_is_work_of_its_own_beside_the_tracking_cadence(tmp_path):
    """The same load at a brokerage that DOES have a tracking cadence, with the provider pinging
    inside it all day. The cadence is satisfied the whole time - and the missed delivery
    appointment is overdue anyway, under its own reason. The cadence is extra work; it is not what
    stands between this load and silence."""
    h, cargo = _falsely_delivered("QB")
    for clock in ("10:30", "13:30", "16:30", "19:30"):
        cargo.track(f"still-moving-{clock.replace(':', '')}", h.t(clock, 1), "IN_TRANSIT",
                    position="I-75 N")
    h.clock("end", h.t("22:00", 1))
    result, store = _run(tmp_path, [h.build({})])
    try:
        story, view = _view(result)
        decided = story.at("dana-says-moving")
        assert {n.kind for n in decided.state.needs} \
            == {NeedKind.ARRIVAL_PENDING, NeedKind.TRACKING_UPDATE_PENDING}
        after = [m for m in story.moments if m.as_of >= LOOKS_AGAIN]
        assert len(after) >= 5 and after[0].trigger_kind == "tick"
        for moment in after:
            late = moment.state.need(NeedKind.CARRIER_STATUS_OVERDUE)
            assert late is not None and late.reason_codes == ("ARRIVAL:S2_OVERDUE",)
            assert late.due_by == WINDOW_CLOSES and not moment.quiet
            cadence = moment.state.need(NeedKind.TRACKING_UPDATE_PENDING)
            assert cadence is not None and cadence.status is NeedStatus.PENDING
        assert [e["state"] for e in _watches(view, "arrival:S2")] == ["DISCHARGED", "OVERDUE"]
        assert result.findings == [] and result.report["metrics"]["external_effect_rows"] == 0
    finally:
        store.close()


def test_the_watch_an_overruled_claim_answered_is_answered_by_a_real_delivery(tmp_path):
    """After Dana overrules him the truck really arrives, inside the window. The watch that became
    owed again is discharged by THAT record, on time; there is one owed watch at a time and never
    a third row; and with the POD on file the load is quiet and billing-ready."""
    h, cargo = _falsely_delivered("QC")
    cargo.track("at-delivery", h.t("08:40", 1), "AT_DELIVERY", "S2")
    cargo.delivered("delivered", h.t("08:55", 1))
    cargo.pod("pod", h.t("09:30", 1))
    h.clock("end", h.t("12:00", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        assert story.at("dana-says-moving").state.need(NeedKind.ARRIVAL_PENDING) is not None
        arrived = story.at("at-delivery")
        assert arrived.state.need(NeedKind.ARRIVAL_PENDING) is None and not arrived.overdue
        watches = _watches(view, "arrival:S2")
        assert [(e["state"], bool(e["late"])) for e in watches] \
            == [("DISCHARGED", False), ("DISCHARGED", False)]
        assert len({e["expectation_id"] for e in watches}) == 2
        real = next(o["observation_id"] for o in view.observations
                    if o["parsed"]["kind"] == "tracking_event"
                    and o["parsed"]["payload"]["status"] == "AT_DELIVERY")
        assert watches[1]["discharge_observation_id"] == real
        waiting = [[n for n in m.state.needs if n.reason_codes == ("ARRIVAL_EXPECTED:S2",)]
                   for m in story.moments]
        assert max(len(w) for w in waiting) == 1 and len([w for w in waiting if w]) >= 5
        assert not [m for m in story.moments if m.overdue], "an on-time delivery was called late"
        done = story.at("pod")
        assert done.state.stage is Stage.DELIVERED and done.quiet and done.billing_ready
        assert story.last.quiet and result.findings == []
    finally:
        store.close()


def test_a_watch_other_standing_evidence_answers_is_not_reopened(tmp_path):
    """The driver says delivered; the provider has him AT the dock. Dana says: at the dock, not
    unloaded. His "delivered" is overruled - and the delivery appointment's watch is NOT owed
    again, because the truck's arrival is still evidenced by the provider and by her."""
    h, cargo = _picked_up("QD")
    cargo.sms("driver-says-delivered", h.t("07:30", 1), "delivered, empty",
              says("DELIVERED", "S2"))
    cargo.track("provider-at-the-dock", h.t("07:35", 1), "AT_DELIVERY", "S2")
    h.human("dana-says-at-the-dock", h.t("08:00", 1), "dana.ortiz", "confirm_movement_status",
            refs=cargo.refs, status="AT_DELIVERY", stop_key="S2", note="checked in, not unloaded")
    h.clock("end", h.t("12:00", 1))                          # two hours after the window closed
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        assert story.at("provider-at-the-dock").state.stage is Stage.DISPUTED
        decided = story.at("dana-says-at-the-dock")
        assert [(t.value("signal"), t.value("status")) for t in view.tracking if t.overruled_by] \
            == [("driver_assertion", "DELIVERED")]
        assert [e["state"] for e in _watches(view, "arrival:S2")] == ["DISCHARGED"]
        later = [m for m in story.moments if m.index >= decided.index]
        assert later and not [m for m in later if m.overdue]
        assert not [m for m in later if m.state.need(NeedKind.ARRIVAL_PENDING)]
        assert decided.state.stage is Stage.IN_TRANSIT and not decided.billing_ready
        assert result.findings == []
    finally:
        store.close()


def test_an_overruled_claim_reaches_no_stop(tmp_path):
    """The delivery appointment was never confirmed, so verifying it is work while the truck is on
    its way. The driver's "delivered" ends that work; Dana overrules him; and the work is back -
    an overruled claim does not make a stop reached."""
    h = _falsely_delivered("QU", delivery_status="REQUESTED")[0]
    h.clock("end", h.t("12:00", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, _ = _view(result)
        before = story.at("loaded").state.need(NeedKind.APPOINTMENT_UNCONFIRMED)
        assert before is not None and before.reason_codes == ("APPOINTMENT_NOT_CONFIRMED:S2",)
        assert story.at("driver-says-delivered").state.need(
            NeedKind.APPOINTMENT_UNCONFIRMED) is None
        decided = story.at("dana-says-moving")
        assert not decided.quiet and decided.next_step == "NEYMA:VERIFY_APPOINTMENT"
        assert _work(decided) == _work(story.at("loaded"))
        assert not story.last.quiet and result.findings == []
    finally:
        store.close()


def test_the_stage_of_a_load_does_not_rest_on_an_overruled_claim(tmp_path):
    """The driver says loaded; the provider still has him at the pickup. Dana says: at the pickup.
    The picture says so too - it does not go on calling the load picked up and rolling."""
    h = _builder("QP", "an overruled claim", "2026-09-01", "contradictory_tracking")
    cargo = Load(h, "LD-59001", customer="great_lakes_bev", carrier="summit", sell=172000,
                 buy=141000, serial="79001", pickup="Great Lakes Beverage Bloomington",
                 delivery="Maumee Distributing", delivery_zone="America/New_York")
    cargo.book()
    cargo.track("at-pickup", h.t("10:10"), "AT_PICKUP", "S1")
    cargo.sms("driver-says-loaded", h.t("10:30"), "loaded, rolling", says("LOADED", "S1"))
    cargo.track("provider-still-at-pickup", h.t("10:40"), "AT_PICKUP", "S1")
    h.human("dana-says-at-pickup", h.t("11:00"), "dana.ortiz", "confirm_movement_status",
            refs=cargo.refs, status="AT_PICKUP", stop_key="S1", note="shipper: still on the dock")
    h.clock("end", h.t("11:30"))
    result, store = _run(tmp_path / "plain", [h.build({})], setups=NO_CADENCE)
    timed, timed_store = _run(tmp_path / "cadence", [h.build({})])
    try:
        story, view = _view(result)
        assert story.at("driver-says-loaded").state.stage is Stage.IN_TRANSIT
        assert story.at("provider-still-at-pickup").state.stage is Stage.DISPUTED
        decided = story.at("dana-says-at-pickup")
        assert decided.state.stage is Stage.AT_PICKUP
        assert "at the pickup" in decided.happening and "in transit" not in decided.happening
        # The pickup itself was evidenced by the provider, and still is: nothing there is reopened.
        assert [e["state"] for e in _watches(view, "arrival:S1")] == ["DISCHARGED"]
        assert not decided.quiet and decided.state.need(NeedKind.ARRIVAL_PENDING) is not None
        assert result.findings == []

        # Where there IS a tracking cadence, his "loaded" started its clock - and, overruled, it
        # starts none: a truck a human says is still on the dock is not under way.
        clocked = timed.story(NORTHLINE, "LD-59001")
        assert clocked.at("driver-says-loaded").state.need(
            NeedKind.TRACKING_UPDATE_PENDING) is not None
        settled = clocked.at("dana-says-at-pickup")
        assert settled.state.stage is Stage.AT_PICKUP
        assert {n.kind for n in settled.state.needs} == {NeedKind.ARRIVAL_PENDING}
        assert timed.findings == []
    finally:
        store.close()
        timed_store.close()


def test_a_tracking_watch_an_overruled_claim_answered_is_owed_again(tmp_path):
    """The driver's "delivered at 7:30" arrives late, after an 08:00 ping, and answers the watch
    that ping started. Dana records that as of 07:45 he had not delivered: her decision is about a
    moment BEFORE the ping, so the ping is still the last anyone heard - and the watch it started
    is owed again, with the delivery's, rather than left answered by a word she overruled."""
    h, cargo = _picked_up("QT")
    cargo.track("ping-0800", h.t("08:00", 1), "IN_TRANSIT", position="I-75 N")
    cargo.sms("driver-says-delivered", h.t("09:00", 1), "delivered at 7:30, empty",
              says("DELIVERED", "S2"))
    h.records[-1] = replace(h.records[-1], as_of=h.t("07:30", 1))
    h.human("dana-says-moving", h.t("09:30", 1), "dana.ortiz", "confirm_movement_status",
            refs=cargo.refs, status="IN_TRANSIT", note="as of 07:45 the receiver had not seen him")
    h.records[-1] = replace(h.records[-1], as_of=h.t("07:45", 1))
    h.clock("end", h.t("13:00", 1))
    result, store = _run(tmp_path, [h.build({})])
    try:
        story, view = _view(result)
        decided = story.at("dana-says-moving")
        assert decided.state.stage is Stage.IN_TRANSIT and not decided.escalations
        assert {n.kind: n.due_by for n in decided.state.needs} == {
            NeedKind.ARRIVAL_PENDING: WINDOW_CLOSES,
            NeedKind.TRACKING_UPDATE_PENDING: "2026-09-02T17:00:00.000Z"}       # 08:00 + 4h
        assert [sorted(n.reason_codes) for n in story.last.overdue] \
            == [["ARRIVAL:S2_OVERDUE", "TRACKING_OVERDUE"]]
        owed = [e for e in view.expectations if e["state"] in _OWED]
        assert sorted(e["expected_type"] for e in owed) == ["arrival:S2", "tracking_update"]
        assert result.findings == []
    finally:
        store.close()


def test_a_record_a_human_moves_to_another_load_stops_answering_this_ones_watch(tmp_path):
    """The same rule, reached by the other human act that invalidates evidence. The provider
    reports a truck at the dock under THIS load's number; that answers this load's delivery watch.
    Priya moves the record to the load it is really about. Nothing standing now says this truck
    reached its dock, so its watch is owed again - and the window closing is work."""
    h = _builder("QM", "a misfiled arrival", "2026-09-01", "pod_attached_to_wrong_load")
    same = dict(customer="great_lakes_bev", carrier="summit", sell=172000, buy=141000,
                pickup="Great Lakes Beverage Bloomington", delivery="Maumee Distributing",
                delivery_zone="America/New_York")
    this = Load(h, "LD-59001", serial="79001", **same)
    other = Load(h, "LD-59002", serial="79002", tag="-b", **same)
    for cargo, clock in ((this, ("07:30", "08:00", "08:20", "10:10", "11:00")),
                         (other, ("07:35", "08:05", "08:25", "10:15", "11:05"))):
        cargo.book(tender=clock[0], cover=clock[1], rate_con=clock[2])
        cargo.track(f"at-pickup{cargo.tag}", h.t(clock[3]), "AT_PICKUP", "S1")
        cargo.track(f"loaded{cargo.tag}", h.t(clock[4]), "LOADED", "S1")
    h.track("misfiled-at-the-dock", h.t("07:30", 1), "AT_DELIVERY", refs=this.refs, stop_key="S2",
            external_id="ping-misfiled")
    h.human("priya-moves-it", h.t("08:00", 1), "priya.nair", "correct_binding", refs=other.refs,
            target={"source_system": TRACKING, "external_id": "ping-misfiled"},
            note="that is LD-59002's truck")
    h.clock("end", h.t("12:00", 1))
    _in_arrival_order(h)
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        assert story.at("misfiled-at-the-dock").state.need(NeedKind.ARRIVAL_PENDING) is None
        moved = story.at("priya-moves-it")
        watch = moved.state.need(NeedKind.ARRIVAL_PENDING)
        assert watch is not None and watch.due_by == WINDOW_CLOSES and not moved.quiet
        assert [e["state"] for e in _watches(view, "arrival:S2")] == ["DISCHARGED", "OVERDUE"]
        assert not [t for t in view.tracking if t.stop_key == "S2"], "the record is still here"
        assert [n.reason_codes for n in story.last.overdue] == [("ARRIVAL:S2_OVERDUE",)]
        assert not story.last.quiet and result.findings == []
    finally:
        store.close()


# ============================================================ a human act cannot know the future

def test_a_future_dated_human_act_is_not_authority_and_silences_nothing(tmp_path):
    """THE REVIEW'S SECOND ATTACK. Dana's confirmation carries an `as_of` ten days after it was
    received. A decision settles what was said BEFORE it, so a decision dated in the future would
    settle everything said for ten days. It is not applied at all: it is held, unreadable, in front
    of a named human; the dispute it was meant to settle is still open; and the provider's later
    contradiction is not silenced."""
    h, cargo = _falsely_delivered("QF", overruled=False)
    h.human("dana-confirms", h.t("08:00", 1), "dana.ortiz", "confirm_movement_status",
            refs=cargo.refs, status="DELIVERED", stop_key="S2", note="receiver confirmed")
    honest = h.records[-1]
    h.records[-1] = replace(honest, as_of=h.t("08:00", 11))
    cargo.pod("pod", h.t("08:30", 1))
    cargo.track("provider-moving-again", h.t("09:00", 1), "IN_TRANSIT", position="I-75 S")
    h.clock("end", h.t("12:00", 1))
    with pytest.raises(UnparseableRecord, match="later than"):
        parse_record(h.records[-4])
    result, store = _run(tmp_path, [h.build({})])
    try:
        story, view = _view(result)
        assert h.records[-4].label == "dana-confirms"
        assert not [t for t in view.tracking if t.value("signal") == "owner_confirmation"]
        assert [c["state"] for c in view.conflicts if c["field"] == "tracking_status"] == ["RAISED"]
        last = story.last
        assert last.state.stage is Stage.DISPUTED and not last.quiet and not last.billing_ready
        assert [e.kind for e in last.escalations] == ["EVIDENCE_CONFLICT"]
        assert last.touches.acts == 0
        moving = story.at("provider-moving-again")
        assert moving.state.stage is Stage.DISPUTED and not moving.quiet
        held = result.unplaced[NORTHLINE]
        assert [(n.kind, n.reason_codes, n.owner_id) for n in held] \
            == [(NeedKind.IDENTITY_UNRESOLVED, ("UNREADABLE_RECORD",), "priya.nair")]
        assert result.findings == [] and result.report["metrics"]["external_effect_rows"] == 0
    finally:
        store.close()

    # The rule is about a HUMAN ACT and about the FUTURE, and about nothing else: an act dated at
    # the instant it was received is read, so is one about an earlier moment, and so is a tracking
    # record whose source's clock runs ahead.
    assert parse_record(honest)["payload"]["status"] == "DELIVERED"
    assert parse_record(replace(honest, as_of=h.t("07:00", 1)))["payload"]["act"] \
        == "confirm_movement_status"
    with pytest.raises(UnparseableRecord, match="later than"):
        parse_record(replace(honest, as_of=h.t("08:01", 1)))
    ahead = next(r for r in h.records if r.label == "provider-says-moving")
    assert parse_record(replace(ahead, as_of=h.t("08:00", 11)))["kind"] == "tracking_event"


def test_a_human_act_about_an_earlier_moment_still_settles_the_dispute(tmp_path):
    """Refusing the future refuses nothing else: recorded at 08:00 about 07:40, her decision is
    applied, and it settles what was said up to 07:40."""
    h, cargo = _falsely_delivered("QG", overruled=False)
    h.human("dana-says-moving", h.t("08:00", 1), "dana.ortiz", "confirm_movement_status",
            refs=cargo.refs, status="IN_TRANSIT", note="as of 07:40 he was still rolling")
    h.records[-1] = replace(h.records[-1], as_of=h.t("07:40", 1))
    h.clock("end", h.t("08:30", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        decided = story.at("dana-says-moving")
        assert decided.state.stage is Stage.IN_TRANSIT and decided.touches.acts == 1
        assert [c["state"] for c in view.conflicts if c["field"] == "tracking_status"] \
            == ["RESOLVED_BY_HUMAN"]
        assert decided.state.need(NeedKind.ARRIVAL_PENDING) is not None
        assert result.unplaced[NORTHLINE] == () and result.findings == []
    finally:
        store.close()


# ============================================================ the repaired load, replayed

def test_the_reopened_watch_survives_replay_restart_and_a_doubled_inbox(tmp_path):
    """The overruled-claim load again: replayed, restarted just before Dana acts, just after she
    acts, and after the window has closed, and with every record delivered twice. Every picture is
    the uninterrupted run's, and the delivery appointment has exactly two watches - the one his
    claim answered and the one owed again - never a third."""
    def history():
        h, cargo = _falsely_delivered("QR")
        cargo.track("still-moving", h.t("16:30", 1), "IN_TRANSIT", position="I-75 N")
        cargo.track("still-moving-late", h.t("19:30", 1), "IN_TRANSIT", position="I-75 N")
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    def rows(result: LoopRunResult) -> list[tuple]:
        _, view = _view(result)
        return [(e["expected_type"], e["state"]) for e in view.expectations]

    whole, store = _run(tmp_path / "whole", [history()], setups=NO_CADENCE)
    stores = [store]
    try:
        assert sum(len(v) for v in _digests(whole).values()) >= 10
        assert rows(whole).count(("arrival:S2", "DISCHARGED")) == 1
        assert rows(whole).count(("arrival:S2", "OVERDUE")) == 1 and not whole.story(
            NORTHLINE, "LD-59001").last.quiet
        again, store = _run(tmp_path / "again", [history()], setups=NO_CADENCE)
        stores.append(store)
        assert _digests(again) == _digests(whole) and rows(again) == rows(whole)
        cuts = ("provider-says-moving", "dana-says-moving", "still-moving")
        for cut in cuts:
            restarted, store = _run(tmp_path / cut, [history()], setups=NO_CADENCE,
                                    restart_after={"QR": cut})
            stores.append(store)
            assert _digests(restarted) == _digests(whole), f"a restart after {cut} differs"
            assert rows(restarted) == rows(whole) and restarted.findings == []
        doubled, store = _run(tmp_path / "doubled", [duplicate_every_record(history())],
                              setups=NO_CADENCE)
        stores.append(store)
        assert _final(doubled) == _final(whole) and rows(doubled) == rows(whole)
        assert doubled.findings == [] and whole.findings == []
    finally:
        for item in stores:
            item.close()


def test_one_brokerages_decision_reopens_nothing_at_another(tmp_path):
    """The same load number at two brokerages, the same false "delivered", the same contradiction.
    Northline's Dana overrules it. At Northline the delivery watch is owed again. At Cedar Ridge
    nobody has decided anything: the claim stands, its watch stays answered, the dispute is still
    open - and Dana's name in Cedar Ridge's inbox is nobody's authority there."""
    watching = {**NO_CADENCE, CEDAR: replace(NO_CADENCE[CEDAR], arrival_tracking_channel=TRACKING)}
    n = _falsely_delivered("QN")[0]
    n.clock("end", n.t("12:00", 1))
    c, cedar_load = _falsely_delivered("QS", overruled=False, tenant=CEDAR, ops=CEDAR_OPS,
                                       pods=CEDAR_OPS)
    c.human("dana-in-cedar", c.t("08:10", 1), "dana.ortiz", "confirm_movement_status",
            refs=cedar_load.refs, status="IN_TRANSIT")
    c.clock("end", c.t("12:00", 1))
    result, store = _run(tmp_path, [n.build({}), c.build({})], setups=watching)
    try:
        north, north_view = _view(result, NORTHLINE)
        cedar, cedar_view = _view(result, CEDAR)
        assert north.load_id != cedar.load_id
        assert [e["state"] for e in _watches(north_view, "arrival:S2")] == ["DISCHARGED", "OVERDUE"]
        assert north.last.state.stage is Stage.IN_TRANSIT and north.last.overdue
        assert [e["state"] for e in _watches(cedar_view, "arrival:S2")] == ["DISCHARGED"]
        assert not [t for t in cedar_view.tracking if t.overruled_by]
        assert cedar.last.state.stage is Stage.DISPUTED and not cedar.last.quiet
        assert [c["state"] for c in cedar_view.conflicts if c["field"] == "tracking_status"] \
            == ["RAISED"]
        assert cedar.last.touches.acts == 0 and not cedar.last.overdue
        assert [n.reason_codes for n in result.unplaced[CEDAR]] \
            == [("UNAUTHENTICATED_HUMAN_ASSERTION",)]
        assert {e["tenant"] for e in north_view.expectations} == {NORTHLINE}
        assert {e["tenant"] for e in cedar_view.expectations} == {CEDAR}
        assert {e["expectation_id"] for e in north_view.expectations}.isdisjoint(
            e["expectation_id"] for e in cedar_view.expectations)
        assert cross_tenant_violations(store.conn) == [] and result.findings == []
        assert {tenant: sum(counts.values())
                for tenant, counts in result.report["effect_surface_rows"].items()} \
            == {CEDAR: 0, NORTHLINE: 0}
    finally:
        store.close()


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
