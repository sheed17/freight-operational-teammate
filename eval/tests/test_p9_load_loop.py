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
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from freight_corpus.builders import TRACKING, charges, movement, says  # noqa: E402
from freight_corpus.histories import _cover, _stops  # noqa: E402
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
    bare_claims_over_a_human_decision,
    build_mutants,
    claims_dropped_onto_a_quiet_load,
    duplicate_every_record,
    row_counts,
    run_mutant,
    watches_a_window_that_is_gone,
)
from freight_recon.freight_domain.corpus_run import cross_tenant_violations  # noqa: E402
from freight_recon.freight_domain.detectors import arrival_evidence  # noqa: E402
from freight_recon.freight_domain.history import (  # noqa: E402
    COVERAGE_HEALTH,
    OBSERVATION_KINDS,
    UnparseableRecord,
    parse_record,
    utc_datetime,
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


#: An appointment that stands as a TIME: a confirmed window, or the window it was rescheduled to.
_TIMED = ("CONFIRMED", "RESCHEDULED")


def _closes(appointment) -> datetime | None:
    """When the window of the appointment that STANDS at a stop closes, read from the appointment
    and from nothing else. None when no time stands there."""
    window = appointment.value("window")
    if appointment.value("status") not in _TIMED or window is None:
        return None
    return datetime.fromisoformat(window["end_local"]).replace(
        tzinfo=ZoneInfo(window["timezone"]))


def _unwatched_stops(view, setup) -> list[str]:
    """A SECOND ORACLE, written without the detectors: at a brokerage that watches arrivals, a stop
    whose appointment stands as a time has either a STANDING claim that the truck has been there,
    or a live watch ON THE WINDOW THAT STANDS. Neither means nobody is waiting for that truck -
    which is how a load whose only delivery report a human overruled went quiet. `audit_state`
    cannot see it: it reads what the record still OWES, and a watch that was wrongly answered owes
    nothing. A watch on a window the appointment has left is not waiting for THIS appointment."""
    if setup.arrival_tracking_channel is None:
        return []
    out: list[str] = []
    for stop_key, appointment in sorted(view.appointments.items()):
        closes = _closes(appointment)
        if closes is None:
            continue
        kind = view.stops[stop_key].value("stop_type")
        only = len([s for s in view.stops.values() if s.value("stop_type") == kind]) == 1
        been = [t for t in view.tracking if t.overruled_by is None and t.contests is None and (
            (t.stop_key == stop_key and t.value("status") in _AT_A_STOP)
            or (only and t.stop_key is None and t.value("status") in _PAST_A_STOP[kind]))]
        live = [e for e in view.expectations
                if e["expected_type"] == f"arrival:{stop_key}" and e["state"] in _OWED
                and utc_datetime(e["deadline_utc"]) == closes]
        if not been and not live:
            out.append(f"{view.load.value('load_ref')}: UNWATCHED STOP - nothing standing says "
                       f"the truck reached {stop_key}, and nothing is waiting for it")
    return out


def _doubly_watched_stops(view) -> list[str]:
    """THE OTHER HALF OF THAT ORACLE: a stop is waited for ONCE, and for the appointment that
    stands. Two live arrival watches on the standing window are one obligation counted twice -
    which is what an appointment that was moved, and then missed, used to leave behind. A watch
    M8 would have let follow the appointment (RAISED, OVERDUE) and that is still live on a window
    the appointment has left - or after it was cancelled - is a deadline nobody holds.

    Rows that are no longer owed are history and are not counted. Neither is a row M8 judged
    INDETERMINATE against a window that is gone: M8 will not move it, the work engine does not
    read it (`audit_state` checks that), and it is history in place."""
    out: list[str] = []
    for stop_key in sorted(view.stops):
        live = [e for e in view.expectations
                if e["expected_type"] == f"arrival:{stop_key}" and e["state"] in _OWED]
        appointment = view.appointments.get(stop_key)
        closes = _closes(appointment) if appointment is not None else None
        cancelled = appointment is not None and appointment.value("status") == "CANCELLED"
        if closes is None and not cancelled:
            here, left = live, []                # requested, or in dispute: no time stands
        else:
            here = [e for e in live if closes and utc_datetime(e["deadline_utc"]) == closes]
            left = [e for e in live if e not in here and e["state"] != "INDETERMINATE"]
        if len(here) > 1:
            out.append(f"{view.load.value('load_ref')}: DUPLICATE WATCH - {len(here)} live "
                       f"arrival watches at {stop_key}")
        if left:
            out.append(f"{view.load.value('load_ref')}: STALE WATCH - {len(left)} live arrival "
                       f"watch(es) at {stop_key} on a window the appointment has left")
    return out


def _run(path: Path, histories=None, *, setups=LOOP_SETUPS,
         **kw) -> tuple[LoopRunResult, WorkflowStore]:
    histories = build_loop_histories() if histories is None else histories
    path.mkdir(parents=True, exist_ok=True)
    store = WorkflowStore(path / "loop.db", tenant=histories[0].tenant)
    kw.setdefault("audit", lambda state, view, tenant: [
        *audit_state(state, view, tenant=tenant), *_unwatched_stops(view, setups[tenant]),
        *_doubly_watched_stops(view)])
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


# ============================================================ a moved appointment is still watched

ET = "America/New_York"
#: The delivery appointment below is 13:00-15:00 Eastern on the second day ...
RESTORED_CLOSES = "2026-09-02T19:00:00.000Z"
RESTORED_LOOKS_AGAIN = "2026-09-02T19:01:00.000Z"
#: ... and the window it is moved to, and back from, is 09:00-11:00 Eastern that same day.
EARLIER_CLOSES = "2026-09-02T15:00:00.000Z"


def _afternoon(history_id: str, **kw):
    """The load of `_picked_up`, its delivery appointment CONFIRMED for 13:00-15:00 Eastern."""
    return _picked_up(history_id, delivery_window=("13:00", "15:00"), **kw)


def _says_window(h, cargo, label: str, clock: str, start: str, end: str, *,
                 who: str = "dana.ortiz") -> None:
    """A recorded human states the delivery appointment, at `clock` Eastern on the second day."""
    h.human(label, h.t(clock, 1, ET), who, "confirm_appointment", refs=cargo.refs, stop_key="S2",
            window_start_local=h.local(start, 1), window_end_local=h.local(end, 1), timezone=ET)


def _tms_window(h, cargo, label: str, at: str, version: int, start: str, end: str, *,
                appointment: str = "CONFIRMED", status: str = "COVERED") -> None:
    """The system of record's own row for the load, carrying this delivery appointment - and
    saying the appointment is `appointment` and the load is `status`."""
    stops = _stops(h, pickup="Great Lakes Beverage Bloomington", delivery="Maumee Distributing",
                   pickup_status="CONFIRMED", delivery_status=appointment, delivery_zone=ET,
                   delivery_window=(start, end))
    h.tms(label, at, load=cargo.number, status=status, version=version,
          customer=cargo.customer, po=cargo.po, bol=cargo.bol, sell=charges(cargo.sell),
          stops=stops, movements=(movement("M1", cargo.carrier, pro=cargo.pro,
                                           status="DELIVERED" if status == "DELIVERED"
                                           else "BOOKED"),))


def _wrong_then_right(history_id: str, **kw):
    """THE SECOND REVIEW'S REPRODUCTION. At 11:20 Eastern Dana enters the delivery appointment as
    09:00-11:00 - a window that has already closed. At 11:25 she puts it back to 13:00-15:00."""
    h, cargo = _afternoon(history_id, **kw)
    _says_window(h, cargo, "dana-wrong-window", "11:20", "09:00", "11:00")
    _says_window(h, cargo, "dana-corrects-it", "11:25", "13:00", "15:00")
    return h, cargo


def _arrival_rows(view) -> list[tuple[str, str]]:
    return [(e["state"], e["deadline_utc"]) for e in _watches(view, "arrival:S2")]


def test_an_appointment_put_back_after_a_wrong_window_lapsed_is_still_watched(tmp_path):
    """The appointment is entered wrongly, as a window already gone, and corrected five minutes
    later. The watch that followed it to the wrong window was late there and is CANCELLED when the
    appointment leaves - and the appointment she restored is WATCHED: a new generation of the same
    watch, owed until the truck arrives, late when 15:00 passes with nobody at the dock. A watch
    that is history does not stand in for the one that is owed, and with no tracking cadence
    configured nothing else would have: the load read QUIET, next step NOTHING."""
    h, _ = _wrong_then_right("RA")
    h.clock("end", h.t("22:00", 1))
    g, _ = _afternoon("RA")                               # the same load; nobody touches the window
    g.clock("end", g.t("22:00", 1))
    result, store = _run(tmp_path / "moved", [h.build({})], setups=NO_CADENCE)
    untouched, plain_store = _run(tmp_path / "plain", [g.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        wrong = story.at("dana-wrong-window")
        assert wrong.state.stage is Stage.IN_TRANSIT
        # Late against the window she entered, at once - on ONE watch, not two.
        assert [(n.reason_codes, n.due_by) for n in wrong.overdue] \
            == [(("ARRIVAL:S2_OVERDUE",), EARLIER_CLOSES)]

        corrected = story.at("dana-corrects-it")
        assert corrected.state.stage is Stage.IN_TRANSIT and not corrected.quiet
        watch = corrected.state.need(NeedKind.ARRIVAL_PENDING)
        assert watch is not None and watch.due_by == RESTORED_CLOSES
        assert corrected.next_step == "WAIT" and not corrected.overdue

        closed = [m for m in story.moments if m.trigger_kind == "tick"]
        assert [m.as_of for m in closed] == [RESTORED_LOOKS_AGAIN]
        assert [(n.kind, n.reason_codes, n.due_by) for n in closed[0].overdue] \
            == [(NeedKind.CARRIER_STATUS_OVERDUE, ("ARRIVAL:S2_OVERDUE",), RESTORED_CLOSES)]
        assert closed[0].next_step == "NEYMA:REQUEST_CARRIER_STATUS"

        last = story.last
        assert not last.quiet and last.next_step == "NEYMA:REQUEST_CARRIER_STATUS"
        assert [m.trigger for m in story.moments if m.quiet] == []
        # The work is what a truck late for an appointment nobody moved owes: no less, no copy.
        plain_last = untouched.story(NORTHLINE, "LD-59001").last
        assert _work(last) == _work(plain_last) and len(_work(last)) == 1

        # NOTHING WAS REWRITTEN OR REUSED. The watch that went to the wrong window is retained,
        # CANCELLED, with the deadline it was late against; the one owed is a row of its own.
        watches = _watches(view, "arrival:S2")
        assert _arrival_rows(view) == [("CANCELLED", EARLIER_CLOSES), ("OVERDUE", RESTORED_CLOSES)]
        assert len({e["expectation_id"] for e in watches}) == 2
        # No evaluation of this load ever saw a stop unwatched, or watched twice.
        assert result.findings == [] and untouched.findings == []
        assert result.report["metrics"]["external_effect_rows"] == 0
    finally:
        store.close()
        plain_store.close()


def test_the_system_of_record_moving_an_appointment_earlier_and_back_is_still_watched(tmp_path):
    """The same failure with no human in it. The TMS row is edited to 09:00-11:00 the day before;
    the truck misses that; the row is edited back to 13:00-15:00. The restored appointment is
    watched and its miss is called late."""
    h, cargo = _afternoon("RT")
    _tms_window(h, cargo, "tms-pulls-it-earlier", h.t("15:00"), 3, "09:00", "11:00")
    _tms_window(h, cargo, "tms-puts-it-back", h.t("11:30", 1, ET), 4, "13:00", "15:00")
    h.clock("end", h.t("22:00", 1))
    _in_arrival_order(h)
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        earlier = story.at("tms-pulls-it-earlier").state.need(NeedKind.ARRIVAL_PENDING)
        assert earlier is not None and earlier.due_by == EARLIER_CLOSES
        ticks = [m for m in story.moments if m.trigger_kind == "tick"]
        assert [m.as_of for m in ticks] == ["2026-09-02T15:01:00.000Z", RESTORED_LOOKS_AGAIN]
        assert [(n.reason_codes, n.due_by) for n in ticks[0].overdue] \
            == [(("ARRIVAL:S2_OVERDUE",), EARLIER_CLOSES)]
        restored = story.at("tms-puts-it-back")
        watch = restored.state.need(NeedKind.ARRIVAL_PENDING)
        assert watch is not None and watch.due_by == RESTORED_CLOSES and not restored.quiet
        assert [(n.reason_codes, n.due_by) for n in ticks[1].overdue] \
            == [(("ARRIVAL:S2_OVERDUE",), RESTORED_CLOSES)]
        assert not story.last.quiet and story.last.next_step == "NEYMA:REQUEST_CARRIER_STATUS"
        assert [m.trigger for m in story.moments if m.quiet] == []
        assert _arrival_rows(view) == [("CANCELLED", EARLIER_CLOSES), ("OVERDUE", RESTORED_CLOSES)]
        assert story.last.touches.acts == 0 and result.findings == []
        assert result.report["metrics"]["external_effect_rows"] == 0
    finally:
        store.close()


def test_a_missed_restored_appointment_is_work_of_its_own_beside_the_tracking_cadence(tmp_path):
    """The same load at a brokerage WITH a tracking cadence, pinged inside it all day. The cadence
    is satisfied the whole time - and the restored appointment's miss is overdue anyway, under its
    own reason. The cadence is not what keeps a moved appointment from disappearing."""
    h, cargo = _wrong_then_right("RC")
    for clock in ("08:00", "11:30", "15:00", "18:30"):
        cargo.track(f"still-moving-{clock.replace(':', '')}", h.t(clock, 1), "IN_TRANSIT",
                    position="I-75 N")
    h.clock("end", h.t("22:00", 1))
    _in_arrival_order(h)
    result, store = _run(tmp_path, [h.build({})])
    try:
        story, view = _view(result)
        corrected = story.at("dana-corrects-it")
        assert {n.kind for n in corrected.state.needs} \
            == {NeedKind.ARRIVAL_PENDING, NeedKind.TRACKING_UPDATE_PENDING}
        after = [m for m in story.moments if m.as_of >= RESTORED_LOOKS_AGAIN]
        assert len(after) >= 3 and after[0].trigger_kind == "tick"
        for moment in after:
            late = moment.state.need(NeedKind.CARRIER_STATUS_OVERDUE)
            assert late is not None and late.reason_codes == ("ARRIVAL:S2_OVERDUE",)
            assert late.due_by == RESTORED_CLOSES and not moment.quiet
            cadence = moment.state.need(NeedKind.TRACKING_UPDATE_PENDING)
            assert cadence is not None and cadence.status is NeedStatus.PENDING
        assert _arrival_rows(view) == [("CANCELLED", EARLIER_CLOSES), ("OVERDUE", RESTORED_CLOSES)]
        assert result.findings == [] and result.report["metrics"]["external_effect_rows"] == 0
    finally:
        store.close()


def test_however_an_appointment_is_moved_exactly_one_watch_follows_it(tmp_path):
    """Moved to a window never used before; moved and put back before anything lapsed; moved
    three times and back to where it started; put back, moved wrongly again, and put back again.
    Every time the appointment that now stands is watched by exactly ONE live watch - never two,
    never none, at any evaluation - and the watches left behind are history, never reused."""
    late = "2026-09-02T22:00:00.000Z"                      # 18:00 Eastern
    cases = {
        "a window never used": (
            [("11:20", "09:00", "11:00"), ("11:25", "16:00", "18:00")],
            [("CANCELLED", EARLIER_CLOSES), ("OVERDUE", late)]),
        "put back before anything lapsed": (
            [("07:00", "09:00", "11:00"), ("08:00", "13:00", "15:00")],
            [("OVERDUE", RESTORED_CLOSES)]),
        "three moves and home again": (
            [("11:20", "09:00", "11:00"), ("11:25", "16:00", "18:00"),
             ("11:30", "13:00", "15:00")],
            [("CANCELLED", EARLIER_CLOSES), ("OVERDUE", RESTORED_CLOSES)]),
        "put back twice": (
            [("11:20", "09:00", "11:00"), ("11:25", "13:00", "15:00"),
             ("11:30", "09:00", "11:00"), ("11:35", "13:00", "15:00")],
            [("CANCELLED", EARLIER_CLOSES), ("CANCELLED", EARLIER_CLOSES),
             ("OVERDUE", RESTORED_CLOSES)]),
    }
    assert len(cases) == 4
    for index, (name, (moves, rows)) in enumerate(cases.items()):
        h, cargo = _afternoon(f"RM{index}")
        for step, (clock, start, end) in enumerate(moves):
            _says_window(h, cargo, f"window-{step}", clock, start, end)
        h.clock("end", h.t("22:00", 1))
        result, store = _run(tmp_path / str(index), [h.build({})], setups=NO_CADENCE)
        try:
            story, view = _view(result)
            watches = _watches(view, "arrival:S2")
            assert _arrival_rows(view) == rows, name
            assert len({e["expectation_id"] for e in watches}) == len(rows), name
            assert [m.trigger for m in story.moments if m.quiet] == [], name
            last = story.last
            assert [(n.reason_codes, n.due_by) for n in last.overdue] \
                == [(("ARRIVAL:S2_OVERDUE",), rows[-1][1])], name
            # Late for the appointment that STANDS, and for no window it has left behind.
            final = story.at(f"window-{len(moves) - 1}")
            for moment in [m for m in story.moments if final.as_of <= m.as_of < rows[-1][1]]:
                assert not moment.overdue, f"{name}: late for a window nobody holds"
                pending = moment.state.need(NeedKind.ARRIVAL_PENDING)
                assert pending is not None and pending.due_by == rows[-1][1], name
            assert result.findings == [], f"{name}: {result.findings[:2]}"
        finally:
            store.close()


def test_a_moved_appointment_missed_and_then_met_is_one_watch_and_one_exception(tmp_path):
    """`P9-D59`, as it was first found. The appointment is moved to 09:00-11:00 while that is
    still ahead; the truck misses it and arrives an hour late. The watch that followed the
    appointment there is the ONLY one - late, then answered late by the arrival - and the miss
    leaves ONE cured Exception for a human to close: exactly what a load whose appointment was
    09:00-11:00 all along leaves. It used to leave two watches and two Exceptions."""
    h, cargo = _afternoon("RD")
    _says_window(h, cargo, "dana-moves-it-earlier", "07:00", "09:00", "11:00")
    g, plain = _picked_up("RD")                             # 09:00-11:00 from the start
    for load, history in ((cargo, h), (plain, g)):
        load.track("at-delivery", history.t("12:00", 1, ET), "AT_DELIVERY", "S2")
        load.delivered("delivered", history.t("12:30", 1, ET))
        load.pod("pod", history.t("13:00", 1, ET))
        history.clock("end", history.t("22:00", 1))
    result, store = _run(tmp_path / "moved", [h.build({})], setups=NO_CADENCE)
    never_moved, plain_store = _run(tmp_path / "plain", [g.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        plain_story, plain_view = _view(never_moved)
        assert [m.as_of for m in story.moments if m.overdue] == ["2026-09-02T15:01:00.000Z"]

        def answered(a_view) -> list[tuple]:
            return [(e["state"], e["deadline_utc"], bool(e["late"]))
                    for e in _watches(a_view, "arrival:S2")]

        assert answered(view) == [("DISCHARGED", EARLIER_CLOSES, True)] == answered(plain_view)
        # The window it left is kept where M8 keeps it: on the one row, as its history.
        assert json.loads(_watches(view, "arrival:S2")[0]["deadline_history"]) == [RESTORED_CLOSES]
        assert len(story.last.state.housekeeping) == 1 == len(plain_story.last.state.housekeeping)
        assert story.last.quiet and story.last.billing_ready
        assert _work(story.last) == _work(plain_story.last) == []
        assert result.findings == [] and never_moved.findings == []
    finally:
        store.close()
        plain_store.close()


def test_a_restored_appointment_is_answered_by_the_truck_and_the_load_goes_on(tmp_path):
    """After the appointment is put back the truck arrives inside it. THAT record answers the
    restored watch, on time; delivery is reported, the POD comes, and the load is quiet and
    billing-ready - with the wrong window's watch still on the record as what it was."""
    h, cargo = _wrong_then_right("RG")
    cargo.track("at-delivery", h.t("13:30", 1, ET), "AT_DELIVERY", "S2")
    cargo.delivered("delivered", h.t("14:10", 1, ET))
    cargo.pod("pod", h.t("14:40", 1, ET))
    h.clock("end", h.t("22:00", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        corrected = story.at("dana-corrects-it")
        assert corrected.state.need(NeedKind.ARRIVAL_PENDING) is not None
        arrived = story.at("at-delivery")
        assert arrived.state.need(NeedKind.ARRIVAL_PENDING) is None and not arrived.overdue
        watches = _watches(view, "arrival:S2")
        assert [(e["state"], e["deadline_utc"], bool(e["late"])) for e in watches] \
            == [("CANCELLED", EARLIER_CLOSES, False), ("DISCHARGED", RESTORED_CLOSES, False)]
        real = next(o["observation_id"] for o in view.observations
                    if o["parsed"]["kind"] == "tracking_event"
                    and o["parsed"]["payload"]["status"] == "AT_DELIVERY")
        assert watches[1]["discharge_observation_id"] == real
        assert not [m for m in story.moments if m.index > corrected.index and m.overdue], \
            "an on-time arrival at the restored appointment was called late"
        done = story.at("pod")
        assert done.state.stage is Stage.DELIVERED and done.quiet and done.billing_ready
        assert story.last.quiet and result.findings == []
    finally:
        store.close()


def test_looking_again_at_a_restored_appointment_raises_nothing_new(tmp_path):
    """The clock is read five more times after the restored window has closed, with nothing
    arriving. Each look re-derives everything the load owes - and writes nothing: the same two
    rows, the same generation, the same pictures as a run that never looked again."""
    def history(looks: int):
        h, _ = _wrong_then_right("RI")
        for index in range(looks):
            h.clock(f"look-{index}", h.t(f"{16 + index}:10", 1, ET))
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    def rows(result: LoopRunResult) -> list[tuple]:
        _, view = _view(result)
        return [(e["expectation_id"], e["expected_type"], e["state"], e["deadline_utc"])
                for e in view.expectations]

    once, store = _run(tmp_path / "once", [history(0)], setups=NO_CADENCE)
    again, again_store = _run(tmp_path / "again", [history(5)], setups=NO_CADENCE)
    try:
        assert again.report["metrics"]["records_arrived"] \
            == once.report["metrics"]["records_arrived"] + 5
        assert rows(again) == rows(once) and len(rows(once)) == 3
        counted = ("expectations_raised", "expectations_cancelled", "expectations_amended",
                   "expectations_discharged", "exceptions_raised", "writes_after_settle")
        told = {name: getattr(again.intakes[NORTHLINE].stats, name) for name in counted}
        assert told == {name: getattr(once.intakes[NORTHLINE].stats, name) for name in counted}
        assert told["expectations_raised"] == 3 and told["writes_after_settle"] == 0
        assert _digests(again) == _digests(once) and _final(again) == _final(once)
        assert again.story(NORTHLINE, "LD-59001").last.as_of == RESTORED_LOOKS_AGAIN
        assert again.findings == [] and once.findings == []
    finally:
        store.close()
        again_store.close()


def test_a_restored_appointments_watch_survives_replay_restart_and_a_doubled_inbox(tmp_path):
    """The moved-and-restored load again: replayed, restarted before the appointment is touched,
    after the wrong window, after the correction and after the restored window has closed, and
    with every record delivered twice. Every picture is the uninterrupted run's, and so is every
    row - the SAME generation ids, never one more."""
    def history():
        h, cargo = _wrong_then_right("RR")
        cargo.track("still-moving", h.t("16:30", 1, ET), "IN_TRANSIT", position="I-75 N")
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    def rows(result: LoopRunResult) -> list[tuple]:
        _, view = _view(result)
        return [(e["expectation_id"], e["expected_type"], e["state"], e["deadline_utc"])
                for e in view.expectations]

    whole, store = _run(tmp_path / "whole", [history()], setups=NO_CADENCE)
    stores = [store]
    try:
        assert sum(len(v) for v in _digests(whole).values()) >= 10
        assert [r[2:] for r in rows(whole) if r[1] == "arrival:S2"] \
            == [("CANCELLED", EARLIER_CLOSES), ("OVERDUE", RESTORED_CLOSES)]
        assert not whole.story(NORTHLINE, "LD-59001").last.quiet
        again, store = _run(tmp_path / "again", [history()], setups=NO_CADENCE)
        stores.append(store)
        assert _digests(again) == _digests(whole) and rows(again) == rows(whole)
        cuts = ("loaded", "dana-wrong-window", "dana-corrects-it", "still-moving")
        for cut in cuts:
            restarted, store = _run(tmp_path / cut, [history()], setups=NO_CADENCE,
                                    restart_after={"RR": cut})
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


def test_one_brokerages_rescheduling_moves_nothing_at_another(tmp_path):
    """The same load number at two brokerages, the same 13:00-15:00 appointment. Northline's Dana
    moves hers and puts it back. Cedar Ridge's appointment never moves, its one watch is never
    cancelled or re-raised - and Dana's name on a reschedule in Cedar Ridge's inbox moves nothing."""
    watching = {**NO_CADENCE, CEDAR: replace(NO_CADENCE[CEDAR], arrival_tracking_channel=TRACKING)}
    n, _ = _wrong_then_right("RN")
    n.clock("end", n.t("22:00", 1))
    c, cedar_load = _afternoon("RS", tenant=CEDAR, ops=CEDAR_OPS, pods=CEDAR_OPS)
    _says_window(c, cedar_load, "dana-in-cedar", "11:20", "09:00", "11:00")
    c.clock("end", c.t("22:00", 1))
    result, store = _run(tmp_path, [n.build({}), c.build({})], setups=watching)
    try:
        north, north_view = _view(result, NORTHLINE)
        cedar, cedar_view = _view(result, CEDAR)
        assert north.load_id != cedar.load_id
        assert _arrival_rows(north_view) \
            == [("CANCELLED", EARLIER_CLOSES), ("OVERDUE", RESTORED_CLOSES)]
        assert [n.reason_codes for n in north.last.overdue] == [("ARRIVAL:S2_OVERDUE",)]
        # Cedar Ridge has no reading of its tracking channel, so its miss is UNVERIFIED, not late.
        assert _arrival_rows(cedar_view) == [("INDETERMINATE", RESTORED_CLOSES)]
        assert cedar_view.appointments["S2"].value("window")["end_local"] == "2026-09-02T15:00"
        assert cedar.last.touches.acts == 0 and not cedar.last.quiet
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


def test_the_duplicate_watch_oracle_fires_on_two_live_watches_at_one_stop(tmp_path):
    """Anti-vacuity for `_doubly_watched_stops`, which every run in this file applies to every
    evaluation of every load. It is quiet about a stop with one live watch, it objects to a second
    live one, and it does not count a watch that is history."""
    h, _ = _afternoon("RO")
    h.clock("end", h.t("09:00", 1))                         # the window has not opened yet
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        _, view = _view(result)
        live = [e for e in _watches(view, "arrival:S2") if e["state"] in _OWED]
        assert len(live) == 1 and _doubly_watched_stops(view) == []
        view.expectations.append({**live[0], "expectation_id": "exp-a-second-live-watch"})
        assert [f.split(": ", 1)[1][:15] for f in _doubly_watched_stops(view)] \
            == ["DUPLICATE WATCH"]
        view.expectations[-1]["state"] = "CANCELLED"
        assert _doubly_watched_stops(view) == []
        # A watch M8 would let follow the appointment, live on a window it has LEFT, is a deadline
        # nobody holds. One M8 judged blind there is history in place, and is not counted.
        view.expectations[-1].update(state="OVERDUE", deadline_utc=EARLIER_CLOSES)
        assert [f.split(": ", 1)[1][:11] for f in _doubly_watched_stops(view)] == ["STALE WATCH"]
        view.expectations[-1]["state"] = "INDETERMINATE"
        assert _doubly_watched_stops(view) == []
        assert watches_a_window_that_is_gone(view, view.expectations[-1])
    finally:
        store.close()


# ============================================================ a human's answer stands

def _ruled_in_transit(history_id: str, *, first: str = "tms", **kw):
    """THE THIRD REVIEW'S REPRODUCTION, up to her decision. At 08:30 Eastern the system of record's
    row (or, with `first="driver"`, the driver) says DELIVERED; at 08:35 the provider has the truck
    rolling; at 09:00 Dana says: in transit. The delivery appointment is 13:00-15:00."""
    h, cargo = _afternoon(history_id, **kw)
    if first == "tms":
        _tms_window(h, cargo, "tms-says-delivered", h.t("08:30", 1, ET), 3, "13:00", "15:00",
                    status="DELIVERED")
    else:
        cargo.sms("driver-says-delivered", h.t("08:30", 1, ET), "delivered, empty",
                  says("DELIVERED", "S2"))
    cargo.track("provider-says-moving", h.t("08:35", 1, ET), "IN_TRANSIT", position="I-75 N")
    h.human("dana-says-moving", h.t("09:00", 1, ET), "dana.ortiz", "confirm_movement_status",
            refs=cargo.refs, status="IN_TRANSIT", note="receiver has not seen him")
    return h, cargo


def _tms_says_delivered(h, cargo, label: str, clock: str, version: int) -> None:
    """The system of record's row sent again as a NEW version, still saying DELIVERED."""
    _tms_window(h, cargo, label, h.t(clock, 1, ET), version, "13:00", "15:00", status="DELIVERED")


def _about(event) -> str:
    return event.field_of("status").facts[0].as_of


def _her_decision(view) -> str:
    decisions = [t for t in view.tracking if t.value("signal") == "owner_confirmation"]
    return max(decisions, key=_about).origin_observation_id


def _said(view, status: str = "DELIVERED") -> list[tuple[str, str]]:
    """Every claim of `status` that is not a human's, oldest first by the moment it is ABOUT, with
    how it stands now."""
    claims = sorted((t for t in view.tracking if t.value("status") == status
                     and t.value("signal") != "owner_confirmation"),
                    key=lambda t: (_about(t), t.entity_id))
    return [(t.value("signal"),
             "overruled" if t.overruled_by else "contests" if t.contests else "stands")
            for t in claims]


def _disputes(view) -> list[str]:
    return [c["state"] for c in view.conflicts if c["field"] == "tracking_status"]


def test_a_restated_delivery_does_not_undo_a_humans_decision(tmp_path):
    """THE THIRD REVIEW'S FIRST BLOCKER. Dana has said the truck is in transit; the delivery window
    is missed and Neyma is chasing the carrier. Then the system of record's row is sent again as a
    new version, still saying DELIVERED, with nothing new in it. It used to make the load DELIVERED
    again, close the late-truck follow-up and ask for a POD instead - undoing her decision with the
    claim she had rejected, and asking nobody. It is the claim she already answered: it is
    overruled by the same decision, it is still on the record, and nothing that was owed changes.
    The same before the window closes."""
    def history(restated: str | None):
        h, cargo = _ruled_in_transit("HA")
        # The provider goes on showing him on the road after she decided. A reading that the
        # truck is where she said it was is not a reading that it has moved on.
        cargo.track("still-moving", h.t("09:30", 1, ET), "IN_TRANSIT", position="I-75 N")
        if restated:
            _tms_says_delivered(h, cargo, "tms-says-it-again", restated, 4)
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    plain, plain_store = _run(tmp_path / "plain", [history(None)], setups=NO_CADENCE)
    stores = [plain_store]
    try:
        plain_story, plain_view = _view(plain)
        assert _said(plain_view) == [("tms_status", "overruled")]
        for restated in ("16:00", "10:00"):               # after the window was missed; before it
            result, store = _run(tmp_path / restated.replace(":", ""), [history(restated)],
                                 setups=NO_CADENCE)
            stores.append(store)
            story, view = _view(result)
            again = story.at("tms-says-it-again")
            assert again.state.stage is Stage.IN_TRANSIT and not again.quiet, restated
            assert again.state.need(NeedKind.DOCUMENT_REQUIRED) is None, restated
            assert not again.escalations and not again.billing_ready, restated
            # What was owed the moment before it arrived is exactly what is owed after.
            before = [m for m in story.moments if m.index < again.index][-1]
            assert _work(again) == _work(before) and len(_work(again)) == 1, restated

            # IT IS STILL ON THE RECORD, as what the system of record said - twice - and both are
            # answered by her one decision. No second dispute: nobody is asked the same thing.
            assert _said(view) == [("tms_status", "overruled"), ("tms_status", "overruled")]
            assert {t.overruled_by for t in view.tracking if t.overruled_by} \
                == {_her_decision(view)}
            assert len(view.tracking) == len(plain_view.tracking) + 1
            assert _disputes(view) == ["RESOLVED_BY_HUMAN"], restated
            assert (story.last.touches.acts, story.last.touches.open) == (1, 0)

            # The missed delivery is work, exactly as it is on the load nobody restated anything
            # on: no less, and nothing else in its place.
            assert _work(story.last) == _work(plain_story.last), restated
            assert [(n.kind, n.reason_codes, n.due_by) for n in story.last.overdue] \
                == [(NeedKind.CARRIER_STATUS_OVERDUE, ("ARRIVAL:S2_OVERDUE",), RESTORED_CLOSES)]
            assert story.last.next_step == "NEYMA:REQUEST_CARRIER_STATUS"
            assert [e["state"] for e in _watches(view, "arrival:S2")] == ["DISCHARGED", "OVERDUE"]
            assert [m.trigger for m in story.moments if m.quiet or m.billing_ready] == []
            assert result.findings == []
            assert result.report["metrics"]["external_effect_rows"] == 0
    finally:
        for item in stores:
            item.close()


def test_a_restated_delivery_is_not_the_truck_being_heard_from(tmp_path):
    """The same reproduction at a brokerage WITH a tracking cadence. Her decision at 09:00 is the
    last anything standing heard of the truck, so a tracking update is owed by 13:00. The row she
    overruled is sent again at 12:00, and again at 13:30 after that watch has gone overdue. It is
    not the truck being heard from: it answers no watch, it restarts no clock, and the follow-up
    for a truck that has gone silent neither moves nor closes. A real ping does both."""
    silent_by = "2026-09-02T17:00:00.000Z"                  # 09:00 Eastern + the 4-hour cadence

    def history(*restated: str, ping: str | None = None):
        h, cargo = _ruled_in_transit("HT")
        for index, clock in enumerate(restated):
            _tms_says_delivered(h, cargo, f"tms-says-it-again-{index}", clock, 4 + index)
        if ping:
            cargo.track("a-real-ping", h.t(ping, 1, ET), "IN_TRANSIT", position="I-75 N")
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    def tracking_rows(result: LoopRunResult) -> list[tuple]:
        _, view = _view(result)
        return [(e["expectation_id"], e["state"], e["deadline_utc"])
                for e in _watches(view, "tracking_update")]

    plain, plain_store = _run(tmp_path / "plain", [history()])
    result, store = _run(tmp_path / "restated", [history("12:00", "13:30")])
    pinged, pinged_store = _run(tmp_path / "pinged", [history(ping="12:00")])
    try:
        story, view = _view(result)
        decided = story.at("dana-says-moving")
        assert decided.state.need(NeedKind.TRACKING_UPDATE_PENDING).due_by == silent_by
        first = story.at("tms-says-it-again-0")              # 12:00: an hour before it is due
        assert first.state.need(NeedKind.TRACKING_UPDATE_PENDING).due_by == silent_by
        assert _work(first) == _work(decided)
        second = story.at("tms-says-it-again-1")             # 13:30: half an hour after
        assert [(n.reason_codes, n.due_by) for n in second.overdue] \
            == [(("TRACKING_OVERDUE",), silent_by)]
        assert second.next_step == "NEYMA:REQUEST_CARRIER_STATUS"
        # Not one row more than the load nobody restated anything on, and the same work.
        assert tracking_rows(result) == tracking_rows(plain) and len(tracking_rows(plain)) >= 5
        assert tracking_rows(plain)[-1][1:] == ("OVERDUE", silent_by)
        assert _final(result) == _final(plain)
        assert len(story.last.state.housekeeping) \
            == len(plain.story(NORTHLINE, "LD-59001").last.state.housekeeping)
        assert [sorted(n.reason_codes) for n in story.last.overdue] \
            == [["ARRIVAL:S2_OVERDUE", "TRACKING_OVERDUE"]]
        assert result.findings == [] and plain.findings == []

        # The control: a signal that STANDS is the truck being heard from.
        heard = pinged.story(NORTHLINE, "LD-59001").at("a-real-ping")
        assert heard.state.need(NeedKind.TRACKING_UPDATE_PENDING).due_by \
            == "2026-09-02T20:00:00.000Z"
        assert pinged.findings == []
    finally:
        store.close()
        plain_store.close()
        pinged_store.close()


def test_a_restated_delivery_starts_no_clock_of_its_own(tmp_path):
    """The other way the same claim could move a deadline. The driver's "delivered at 7:30"
    arrives late and answers the watch an 08:00 ping started; he says it again at 08:30; then Dana
    records that as of 07:45 he had not delivered. Both of his claims are overruled, the watch his
    word answered is owed again - and it runs from the 08:00 PING, the last signal that stands,
    not from the 08:30 repetition of a claim she rejected."""
    h, cargo = _picked_up("HU")
    cargo.track("ping-0800", h.t("08:00", 1), "IN_TRANSIT", position="I-75 N")
    cargo.sms("driver-says-delivered", h.t("09:00", 1), "delivered at 7:30, empty",
              says("DELIVERED", "S2"))
    h.records[-1] = replace(h.records[-1], as_of=h.t("07:30", 1))
    cargo.sms("driver-says-it-again", h.t("09:10", 1), "delivered", says("DELIVERED", "S2"))
    h.records[-1] = replace(h.records[-1], as_of=h.t("08:30", 1))
    h.human("dana-says-moving", h.t("09:30", 1), "dana.ortiz", "confirm_movement_status",
            refs=cargo.refs, status="IN_TRANSIT", note="as of 07:45 the receiver had not seen him")
    h.records[-1] = replace(h.records[-1], as_of=h.t("07:45", 1))
    h.clock("end", h.t("13:00", 1))
    result, store = _run(tmp_path, [h.build({})])
    try:
        story, view = _view(result)
        assert _said(view) == [("driver_assertion", "overruled")] * 2
        decided = story.at("dana-says-moving")
        assert decided.state.stage is Stage.IN_TRANSIT and not decided.escalations
        assert {n.kind: n.due_by for n in decided.state.needs} == {
            NeedKind.ARRIVAL_PENDING: WINDOW_CLOSES,
            NeedKind.TRACKING_UPDATE_PENDING: "2026-09-02T17:00:00.000Z"}       # 08:00 + 4h
        assert result.findings == []
    finally:
        store.close()


def test_the_overruled_record_delivered_again_is_inert(tmp_path):
    """The very same record - same source, same id - arrives a second time, after her decision. It
    is a duplicate: no new claim, no new row, and the same pictures as the load it never reached."""
    def history(again: bool):
        h, _ = _ruled_in_transit("HB")
        if again:
            h.redeliver("the-same-row-again", h.t("10:00", 1, ET), of="tms-says-delivered")
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    result, store = _run(tmp_path / "again", [history(True)], setups=NO_CADENCE)
    plain, plain_store = _run(tmp_path / "plain", [history(False)], setups=NO_CADENCE)
    try:
        (story, view), (plain_story, plain_view) = _view(result), _view(plain)
        assert result.report["metrics"]["duplicate_records_suppressed"] == 1
        assert plain.report["metrics"]["duplicate_records_suppressed"] == 0
        assert len(view.tracking) == len(plain_view.tracking) and _said(view) == _said(plain_view)
        assert _final(result) == _final(plain) and story.last.state.stage is Stage.IN_TRANSIT
        assert [(e["expectation_id"], e["state"]) for e in view.expectations] \
            == [(e["expectation_id"], e["state"]) for e in plain_view.expectations]
        assert not story.last.quiet and result.findings == []
    finally:
        store.close()
        plain_store.close()


def test_the_overruled_statement_under_a_new_record_id_is_still_overruled(tmp_path):
    """The statement she overruled arrives again under a DIFFERENT record id, an hour after she
    decided, and it is about the same moment it always was. A new id is not a new fact: it is
    judged by the moment it is about, never by when or under what number it arrived."""
    for first, signal in (("tms", "tms_status"), ("driver", "driver_assertion")):
        h, cargo = _ruled_in_transit(f"HC{first[0]}", first=first)
        if first == "tms":
            _tms_says_delivered(h, cargo, "a-copy", "10:00", 4)
        else:
            cargo.sms("a-copy", h.t("10:00", 1, ET), "delivered, empty", says("DELIVERED", "S2"))
        h.records[-1] = replace(h.records[-1], as_of=h.t("08:30", 1, ET),
                                external_id=f"a-new-record-id-{first}")
        h.clock("end", h.t("22:00", 1))
        result, store = _run(tmp_path / first, [h.build({})], setups=NO_CADENCE)
        try:
            story, view = _view(result)
            copy = story.at("a-copy")
            assert copy.disposition != "DUPLICATE", "the copy was not a new record at all"
            assert copy.state.stage is Stage.IN_TRANSIT and not copy.escalations, first
            assert _said(view) == [(signal, "overruled"), (signal, "overruled")], first
            assert _disputes(view) == ["RESOLVED_BY_HUMAN"], first
            assert copy.state.need(NeedKind.ARRIVAL_PENDING) is not None and not copy.quiet
            assert not story.last.quiet and result.findings == []
        finally:
            store.close()


def test_the_source_she_overruled_saying_it_again_does_not_win(tmp_path):
    """The driver whose "delivered" she overruled texts it again an hour later, and again an hour
    after that - new messages, about new moments, with nothing behind them but the same word. He
    has said nothing else in between. It is the same claim, repeated; it does not become true by
    repetition, it reopens no dispute, and the delivery is still watched and still called late."""
    h, cargo = _ruled_in_transit("HD", first="driver")
    cargo.sms("driver-says-it-again", h.t("10:00", 1, ET), "delivered", says("DELIVERED", "S2"))
    cargo.sms("driver-says-it-a-third-time", h.t("11:00", 1, ET), "DELIVERED!!",
              says("DELIVERED"))
    h.clock("end", h.t("22:00", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        for label in ("driver-says-it-again", "driver-says-it-a-third-time"):
            moment = story.at(label)
            assert moment.state.stage is Stage.IN_TRANSIT and not moment.escalations, label
            watch = moment.state.need(NeedKind.ARRIVAL_PENDING)
            assert watch is not None and watch.due_by == RESTORED_CLOSES, label
        assert _said(view) == [("driver_assertion", "overruled")] * 3
        assert _disputes(view) == ["RESOLVED_BY_HUMAN"]
        assert [(n.reason_codes, n.due_by) for n in story.last.overdue] \
            == [(("ARRIVAL:S2_OVERDUE",), RESTORED_CLOSES)]
        assert (story.last.touches.acts, story.last.touches.open) == (1, 0)
        assert [m.trigger for m in story.moments if m.quiet or m.billing_ready] == []
        assert result.findings == []
    finally:
        store.close()


def test_a_new_bare_claim_against_her_decision_is_a_dispute_and_not_an_answer(tmp_path):
    """After she overruled the system of record, a DIFFERENT source says it: the driver texts
    "delivered". That may be news. It is also only a word against hers, with no reading that the
    truck moved on - so it does not become the answer and it does not vanish: it contests her
    decision, the load is DISPUTED and hers to decide again, and until she does the delivery is
    still watched and its window closing is still late. Her answer, either way, settles it."""
    def history(answer: str | None = None):
        h, cargo = _ruled_in_transit("HE")
        cargo.sms("driver-says-delivered", h.t("10:00", 1, ET), "delivered, empty",
                  says("DELIVERED", "S2"))
        if answer:
            h.human("dana-answers", h.t("10:30", 1, ET), "dana.ortiz", "confirm_movement_status",
                    refs=cargo.refs, status=answer,
                    **({"stop_key": "S2"} if answer == "DELIVERED" else {}))
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    result, store = _run(tmp_path / "unanswered", [history()], setups=NO_CADENCE)
    stores = [store]
    try:
        story, view = _view(result)
        claimed = story.at("driver-says-delivered")
        assert claimed.state.stage is Stage.DISPUTED and not claimed.quiet
        assert not claimed.billing_ready and claimed.next_step == "HUMAN:EVIDENCE_CONFLICT"
        assert [e.kind for e in claimed.escalations] == ["EVIDENCE_CONFLICT"]
        # Nothing he said is acted on: no POD is asked for, and the delivery is still watched.
        assert claimed.state.need(NeedKind.DOCUMENT_REQUIRED) is None
        watch = claimed.state.need(NeedKind.ARRIVAL_PENDING)
        assert watch is not None and watch.due_by == RESTORED_CLOSES
        assert _said(view) == [("tms_status", "overruled"), ("driver_assertion", "contests")]
        assert [t.contests for t in view.tracking if t.contests] == [_her_decision(view)]
        # A NEW dispute, with her own decision as a party to it; the settled one keeps its row.
        assert _disputes(view) == ["RESOLVED_BY_HUMAN", "RAISED"]
        raised = [c for c in view.conflicts if c["state"] == "RAISED"]
        assert [c["kind"] for c in raised] == ["INFERRER_VS_OWNER"]
        assert [len(c["parties"]) for c in raised] == [2]
        said = " ".join(e.note for e in claimed.escalations[0].evidence)
        assert "OWNER_ASSERTED says IN_TRANSIT" in said and "says DELIVERED" in said
        last = story.last
        assert last.state.stage is Stage.DISPUTED and not last.quiet and not last.billing_ready
        assert [(n.reason_codes, n.due_by) for n in last.overdue] \
            == [(("ARRIVAL:S2_OVERDUE",), RESTORED_CLOSES)]
        assert (last.touches.acts, last.touches.open) == (1, 1)
        assert [m.trigger for m in story.moments if m.quiet or m.billing_ready] == []
        assert result.findings == [] and result.report["metrics"]["external_effect_rows"] == 0

        still, store = _run(tmp_path / "still-moving", [history("IN_TRANSIT")],
                            setups=NO_CADENCE)
        stores.append(store)
        story, view = _view(still)
        answered = story.at("dana-answers")
        assert answered.state.stage is Stage.IN_TRANSIT and not answered.escalations
        assert _said(view) == [("tms_status", "overruled"), ("driver_assertion", "overruled")]
        assert _disputes(view) == ["RESOLVED_BY_HUMAN", "RESOLVED_BY_HUMAN"]
        assert answered.state.need(NeedKind.ARRIVAL_PENDING) is not None
        assert [(n.reason_codes, n.due_by) for n in story.last.overdue] \
            == [(("ARRIVAL:S2_OVERDUE",), RESTORED_CLOSES)]
        assert (story.last.touches.acts, story.last.touches.open) == (2, 0)
        assert still.findings == []

        delivered, store = _run(tmp_path / "delivered", [history("DELIVERED")],
                                setups=NO_CADENCE)
        stores.append(store)
        story, view = _view(delivered)
        answered = story.at("dana-answers")
        assert answered.state.stage is Stage.DELIVERED and not answered.escalations
        assert answered.state.need(NeedKind.DOCUMENT_REQUIRED) is not None
        assert _disputes(view) == ["RESOLVED_BY_HUMAN", "RESOLVED_BY_HUMAN"]
        assert not [t for t in view.tracking if t.contests] and delivered.findings == []
    finally:
        for item in stores:
            item.close()


def test_a_repeat_is_put_to_her_where_nothing_else_is_asking(tmp_path):
    """A repeat is dropped silently only where the truck is still being asked about. Here it is
    not: the provider has the truck at the receiver and Dana says so too - checked in, not
    unloaded - so the delivery watch is answered and, with no cadence, nothing at all is owed
    (`P9-D67`, untouched). Forty minutes later the same driver says "delivered" again. Dropped
    unasked, that would be a delivery report on a QUIET load, shown to nobody. It contests her
    decision instead: a dispute, hers to settle - and when she does, the load goes on."""
    def history(confirmed: bool):
        h, cargo = _afternoon("HQ")
        cargo.sms("driver-says-delivered", h.t("12:30", 1, ET), "delivered, empty",
                  says("DELIVERED", "S2"))
        cargo.track("provider-at-the-dock", h.t("12:35", 1, ET), "AT_DELIVERY", "S2")
        h.human("dana-says-at-the-dock", h.t("13:00", 1, ET), "dana.ortiz",
                "confirm_movement_status", refs=cargo.refs, status="AT_DELIVERY", stop_key="S2",
                note="checked in, not unloaded")
        cargo.sms("driver-says-it-again", h.t("13:40", 1, ET), "delivered",
                  says("DELIVERED", "S2"))
        if confirmed:
            h.human("dana-confirms-delivery", h.t("13:50", 1, ET), "dana.ortiz",
                    "confirm_movement_status", refs=cargo.refs, status="DELIVERED",
                    stop_key="S2", note="receiver: unloaded")
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    result, store = _run(tmp_path / "unanswered", [history(False)], setups=NO_CADENCE)
    answered, answered_store = _run(tmp_path / "answered", [history(True)], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        decided = story.at("dana-says-at-the-dock")
        assert decided.state.stage is Stage.IN_TRANSIT and decided.quiet, "P9-D67 was changed"
        again = story.at("driver-says-it-again")
        assert again.state.stage is Stage.DISPUTED and not again.quiet
        assert [e.kind for e in again.escalations] == ["EVIDENCE_CONFLICT"]
        assert _said(view) == [("driver_assertion", "overruled"),
                               ("driver_assertion", "contests")]
        assert _disputes(view) == ["RESOLVED_BY_HUMAN", "RAISED"]
        assert not story.last.quiet and not story.last.billing_ready
        assert (story.last.touches.acts, story.last.touches.open) == (1, 1)
        assert result.findings == []

        story, _ = _view(answered)
        done = story.at("dana-confirms-delivery")
        assert done.state.stage is Stage.DELIVERED and not done.escalations
        assert done.state.need(NeedKind.DOCUMENT_REQUIRED) is not None and not done.quiet
        assert answered.findings == []
    finally:
        store.close()
        answered_store.close()


def test_a_repeat_at_a_brokerage_that_watches_no_arrivals_is_put_to_a_human(tmp_path):
    """Cedar Ridge expects arrivals on no channel, so nothing there waits for a truck. Sam says a
    load its system of record calls DELIVERED is still in transit; the row is sent again. At
    Northline that repeat changes nothing, because the delivery watch is owed and will find out.
    Here nothing would: dropped unasked it would leave the load quiet on a delivery report. It is
    put to Sam."""
    h, cargo = _afternoon("HV", tenant=CEDAR, ops=CEDAR_OPS, pods=CEDAR_OPS)
    _tms_window(h, cargo, "tms-says-delivered", h.t("08:30", 1, ET), 3, "13:00", "15:00",
                status="DELIVERED")
    h.human("sam-says-moving", h.t("09:00", 1, ET), "sam.okafor", "confirm_movement_status",
            refs=cargo.refs, status="IN_TRANSIT", note="driver is two hours out")
    _tms_says_delivered(h, cargo, "tms-says-it-again", "16:00", 4)
    h.clock("end", h.t("22:00", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result, CEDAR)
        assert NO_CADENCE[CEDAR].arrival_tracking_channel is None
        assert story.at("sam-says-moving").state.stage is Stage.IN_TRANSIT
        again = story.at("tms-says-it-again")
        assert again.state.stage is Stage.DISPUTED and not again.quiet
        assert [(e.kind, e.owner_id) for e in again.escalations] \
            == [("EVIDENCE_CONFLICT", "sam.okafor")]
        assert _said(view) == [("tms_status", "overruled"), ("tms_status", "contests")]
        assert not story.last.quiet and not story.last.billing_ready
        assert result.findings == []
    finally:
        store.close()


def test_the_projection_and_the_detectors_agree_on_which_stop_a_claim_answers(loop):
    """`LoadView.stops_a_claim_answers` asks of ONE claim what `detectors.arrival_evidence` asks
    stop by stop. Over every standing claim at every stop of the twenty-two loads they give the
    same answer - and both answers occur, so the agreement is not an empty one."""
    result, _ = loop
    compared = answered = 0
    for intake in result.intakes.values():
        for view in intake.projection().loads.values():
            for stop_key in view.stops:
                evidence = arrival_evidence(view, stop_key)
                for claim in view.standing_tracking():
                    compared += 1
                    here = stop_key in view.stops_a_claim_answers(claim)
                    answered += here
                    assert here == (claim.origin_observation_id in evidence), \
                        (view.load.value("load_ref"), stop_key, claim.value("status"))
    assert compared >= 300 and 100 <= answered < compared, (compared, answered)


def test_a_source_that_said_otherwise_and_then_says_it_again_is_asking_anew(tmp_path):
    """Not every later word from the source she overruled is a restatement. The system of record
    is corrected to IN_TRANSIT after her decision, and hours later says DELIVERED: it changed its
    statement and then made a new one. That is new information - a dispute for her, never a
    silent answer, and never silently dropped either."""
    h, cargo = _ruled_in_transit("HF")
    _tms_window(h, cargo, "tms-corrected", h.t("10:00", 1, ET), 4, "13:00", "15:00",
                status="IN_TRANSIT")
    _tms_says_delivered(h, cargo, "tms-says-delivered-anew", "14:00", 5)
    h.clock("end", h.t("22:00", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        assert story.at("tms-corrected").state.stage is Stage.IN_TRANSIT
        anew = story.at("tms-says-delivered-anew")
        assert anew.state.stage is Stage.DISPUTED and anew.next_step == "HUMAN:EVIDENCE_CONFLICT"
        assert _said(view) == [("tms_status", "overruled"), ("tms_status", "contests")]
        assert _disputes(view) == ["RESOLVED_BY_HUMAN", "RAISED"]
        assert anew.state.need(NeedKind.ARRIVAL_PENDING) is not None
        assert not story.last.quiet and not story.last.billing_ready
        assert result.findings == []
    finally:
        store.close()


def test_a_real_later_delivery_advances_the_load_and_nobody_is_asked(tmp_path):
    """A human's decision is about a moment; it is not permanent truth. After Dana says "in
    transit" the tracking provider puts the truck AT the receiver, inside the window. From then on
    a delivery report is believed as it always was - from the very source she overruled, from the
    driver she overruled, from anyone - and with the signed POD the load is quiet and
    billing-ready. Nobody is asked to approve a real delivery because the truck was moving
    earlier: one decision, no second dispute, nothing late."""
    for first, tells in (("tms", "tms"), ("driver", "driver"), ("tms", "driver")):
        h, cargo = _ruled_in_transit(f"HG{first[0]}{tells[0]}", first=first)
        cargo.track("at-delivery", h.t("13:30", 1, ET), "AT_DELIVERY", "S2")
        if tells == "tms":
            _tms_says_delivered(h, cargo, "delivered", "14:10", 4)
        else:
            cargo.sms("delivered", h.t("14:10", 1, ET), "delivered, empty",
                      says("DELIVERED", "S2"))
        cargo.pod("pod", h.t("14:40", 1, ET))
        h.clock("end", h.t("22:00", 1))
        result, store = _run(tmp_path / f"{first}-{tells}", [h.build({})], setups=NO_CADENCE)
        try:
            story, view = _view(result)
            name = f"{first} overruled, {tells} reports"
            arrived = story.at("at-delivery")
            assert arrived.state.stage is Stage.IN_TRANSIT and not arrived.overdue, name
            assert arrived.state.need(NeedKind.ARRIVAL_PENDING) is None, name
            delivered = story.at("delivered")
            assert delivered.state.stage is Stage.DELIVERED and not delivered.escalations, name
            assert delivered.state.need(NeedKind.DOCUMENT_REQUIRED) is not None, name
            done = story.at("pod")
            assert done.state.stage is Stage.DELIVERED and done.quiet and done.billing_ready, name
            assert _said(view)[0][1] == "overruled" and _said(view)[-1][1] == "stands", name
            assert not [t for t in view.tracking if t.contests], name
            assert _disputes(view) == ["RESOLVED_BY_HUMAN"], name
            decided = story.at("dana-says-moving")
            later = [m for m in story.moments if m.index > decided.index]
            assert len(later) >= 3 and not [m for m in later if m.escalations or m.overdue], name
            assert (story.last.touches.acts, story.last.touches.open) == (1, 0), name
            assert [e["state"] for e in _watches(view, "arrival:S2")] \
                == ["DISCHARGED", "DISCHARGED"], name
            assert result.findings == [], name
        finally:
            store.close()


def test_a_restatement_made_before_the_truck_moved_on_stays_overruled(tmp_path):
    """The row she overruled is sent again at 10:00. At 13:30 the provider puts the truck at the
    receiver. That reading says the truck moved on at 13:30; it does not reach back and make a
    10:00 restatement true. The load is at the receiver and not delivered, and nobody is asked to
    settle a dispute that does not exist. Sent again AFTER the truck arrived, the same row is
    believed - and the POD closes the load."""
    h, cargo = _ruled_in_transit("HM")
    _tms_says_delivered(h, cargo, "tms-says-it-again", "10:00", 4)
    cargo.track("at-delivery", h.t("13:30", 1, ET), "AT_DELIVERY", "S2")
    _tms_says_delivered(h, cargo, "delivered", "14:10", 5)
    cargo.pod("pod", h.t("14:40", 1, ET))
    h.clock("end", h.t("22:00", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        arrived = story.at("at-delivery")
        assert arrived.state.stage is Stage.IN_TRANSIT and not arrived.escalations
        assert arrived.state.need(NeedKind.ARRIVAL_PENDING) is None
        assert arrived.state.need(NeedKind.DOCUMENT_REQUIRED) is None
        assert story.at("delivered").state.stage is Stage.DELIVERED
        assert _said(view) == [("tms_status", "overruled"), ("tms_status", "overruled"),
                               ("tms_status", "stands")]
        assert _disputes(view) == ["RESOLVED_BY_HUMAN"]
        done = story.at("pod")
        assert done.quiet and done.billing_ready and story.last.touches.acts == 1
        assert [m.trigger for m in story.moments if m.billing_ready] == ["pod"]
        assert result.findings == []
    finally:
        store.close()


def test_a_pod_does_not_make_a_restated_delivery_true(tmp_path):
    """A signed POD satisfies the document requirement; it reports no delivery (CD-8), and that
    is unchanged. So a POD arriving beside a restatement she already answered makes nothing
    billing-ready: the load is still where she said it was, still watched, still not quiet. When
    she confirms the delivery herself, the POD that is on file counts exactly as it always has."""
    def history(confirmed: bool):
        h, cargo = _ruled_in_transit("HP")
        _tms_says_delivered(h, cargo, "tms-says-it-again", "14:10", 4)
        cargo.pod("pod", h.t("14:40", 1, ET))
        if confirmed:
            h.human("dana-confirms-delivery", h.t("14:50", 1, ET), "dana.ortiz",
                    "confirm_movement_status", refs=cargo.refs, status="DELIVERED",
                    stop_key="S2", note="receiver: unloaded and signed for")
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    result, store = _run(tmp_path / "alone", [history(False)], setups=NO_CADENCE)
    confirmed, confirmed_store = _run(tmp_path / "confirmed", [history(True)], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        pod = story.at("pod")
        assert pod.state.stage is Stage.IN_TRANSIT and not pod.billing_ready and not pod.quiet
        assert pod.state.need(NeedKind.ARRIVAL_PENDING) is not None
        assert [r.state for r in view.requirements] == ["SATISFIED"], "the POD was not usable"
        assert [m.trigger for m in story.moments if m.billing_ready or m.quiet] == []
        assert story.last.next_step == "NEYMA:REQUEST_CARRIER_STATUS" and result.findings == []

        story, _ = _view(confirmed)
        done = story.at("dana-confirms-delivery")
        assert done.state.stage is Stage.DELIVERED and done.billing_ready and done.quiet
        assert [m.trigger for m in story.moments if m.billing_ready] \
            == ["dana-confirms-delivery"]
        assert story.last.touches.acts == 2 and confirmed.findings == []
    finally:
        store.close()
        confirmed_store.close()


def test_a_contradiction_after_real_progress_is_still_a_dispute(tmp_path):
    """Her decision stops governing once the truck has really moved on - and the rules that were
    there before her decision are still there after it. The truck is put at the receiver, the
    delivery is reported and believed, and THEN the provider shows the truck on the road again:
    a later reading of an earlier stage. That is a new dispute, hers to decide."""
    h, cargo = _ruled_in_transit("HK")
    cargo.track("at-delivery", h.t("13:30", 1, ET), "AT_DELIVERY", "S2")
    _tms_says_delivered(h, cargo, "delivered", "14:10", 4)
    cargo.track("provider-moving-again", h.t("15:00", 1, ET), "IN_TRANSIT", position="I-75 S")
    h.clock("end", h.t("22:00", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        assert story.at("delivered").state.stage is Stage.DELIVERED
        again = story.at("provider-moving-again")
        assert again.state.stage is Stage.DISPUTED and not again.quiet and not again.billing_ready
        assert [e.kind for e in again.escalations] == ["EVIDENCE_CONFLICT"]
        assert _disputes(view) == ["RESOLVED_BY_HUMAN", "RAISED"]
        assert not [t for t in view.tracking if t.contests], "progress was called a bare claim"
        assert (story.last.touches.acts, story.last.touches.open) == (1, 1)
        assert result.findings == []
    finally:
        store.close()


def test_her_decision_holds_through_replay_restart_and_a_doubled_inbox(tmp_path):
    """One load carrying all of it: a restatement, a new bare claim she answers, a late real
    arrival, the delivery, the POD. Replayed, restarted after each of its records, and with every
    record delivered twice, every picture is the uninterrupted run's - and so is every Conflict
    and every watch, ids included."""
    def history():
        h, cargo = _ruled_in_transit("HR")
        _tms_says_delivered(h, cargo, "tms-says-it-again", "10:00", 4)
        cargo.sms("driver-says-delivered", h.t("11:00", 1, ET), "delivered, empty",
                  says("DELIVERED", "S2"))
        h.human("dana-answers", h.t("11:30", 1, ET), "dana.ortiz", "confirm_movement_status",
                refs=cargo.refs, status="IN_TRANSIT", note="still not there")
        cargo.track("at-delivery", h.t("16:00", 1, ET), "AT_DELIVERY", "S2")
        _tms_says_delivered(h, cargo, "delivered", "16:30", 5)
        cargo.pod("pod", h.t("17:00", 1, ET))
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    def rows(result: LoopRunResult) -> tuple:
        _, view = _view(result)
        return ([(e["expectation_id"], e["expected_type"], e["state"], e["deadline_utc"])
                 for e in view.expectations],
                [(c["conflict_id"], c["state"], len(c["parties"])) for c in view.conflicts],
                _said(view))

    whole, store = _run(tmp_path / "whole", [history()], setups=NO_CADENCE)
    stores = [store]
    try:
        story, view = _view(whole)
        assert sum(len(v) for v in _digests(whole).values()) >= 14
        assert _said(view) == [("tms_status", "overruled"), ("tms_status", "overruled"),
                               ("driver_assertion", "overruled"), ("tms_status", "stands")]
        assert _disputes(view) == ["RESOLVED_BY_HUMAN", "RESOLVED_BY_HUMAN"]
        assert story.last.quiet and story.last.billing_ready and whole.findings == []
        again, store = _run(tmp_path / "again", [history()], setups=NO_CADENCE)
        stores.append(store)
        assert _digests(again) == _digests(whole) and rows(again) == rows(whole)
        cuts = ("tms-says-delivered", "dana-says-moving", "tms-says-it-again",
                "driver-says-delivered", "dana-answers", "at-delivery", "delivered", "pod")
        for cut in cuts:
            restarted, store = _run(tmp_path / cut, [history()], setups=NO_CADENCE,
                                    restart_after={"HR": cut})
            stores.append(store)
            assert _digests(restarted) == _digests(whole), f"a restart after {cut} differs"
            assert rows(restarted) == rows(whole) and restarted.findings == []
        doubled, store = _run(tmp_path / "doubled", [duplicate_every_record(history())],
                              setups=NO_CADENCE)
        stores.append(store)
        assert _final(doubled) == _final(whole) and rows(doubled) == rows(whole)
        assert doubled.findings == []
    finally:
        for item in stores:
            item.close()


def test_one_brokerages_answer_and_appointment_reach_no_other_brokerage(tmp_path):
    """The same load number at two brokerages, the same records from the same systems: the row
    that says DELIVERED, the row sent again, the appointment RESCHEDULED. Northline's Dana says
    her truck is in transit; nobody at Cedar Ridge says anything. Northline's claims are overruled
    and its load is in transit and watched on the new window. Cedar Ridge's are untouched: its
    load is delivered on its own records, exactly as if Northline did not exist - and its tracking
    channel, which has no health reading, is its own too."""
    watching = {**NO_CADENCE, CEDAR: replace(NO_CADENCE[CEDAR], arrival_tracking_channel=TRACKING)}

    def northline():
        h, cargo = _ruled_in_transit("TN")
        _tms_window(h, cargo, "rescheduled", h.t("09:30", 1, ET), 4, "16:00", "18:00",
                    appointment="RESCHEDULED", status="DELIVERED")
        h.clock("end", h.t("23:30", 1))
        return h.build({})

    def cedar():
        h, cargo = _afternoon("TC", tenant=CEDAR, ops=CEDAR_OPS, pods=CEDAR_OPS)
        _tms_window(h, cargo, "tms-says-delivered", h.t("08:30", 1, ET), 3, "13:00", "15:00",
                    status="DELIVERED")
        _tms_window(h, cargo, "rescheduled", h.t("09:30", 1, ET), 4, "16:00", "18:00",
                    appointment="RESCHEDULED", status="DELIVERED")
        h.clock("end", h.t("23:30", 1))
        return h.build({})

    def shape(result: LoopRunResult, tenant: str) -> tuple:
        story, view = _view(result, tenant)
        return ([m.digest() for m in story.moments], _said(view), _disputes(view),
                [(e["expectation_id"], e["state"], e["deadline_utc"]) for e in view.expectations])

    both, store = _run(tmp_path / "both", [northline(), cedar()], setups=watching)
    north_alone, north_store = _run(tmp_path / "north", [northline()], setups=watching)
    cedar_alone, cedar_store = _run(tmp_path / "cedar", [cedar()], setups=watching)
    try:
        (north, north_view), (ced, cedar_view) = _view(both, NORTHLINE), _view(both, CEDAR)
        assert north.load_id != ced.load_id
        # Northline: her answer holds against the row sent again, and the watch is on 16:00-18:00.
        assert _said(north_view) == [("tms_status", "overruled"), ("tms_status", "overruled")]
        assert north.last.state.stage is Stage.IN_TRANSIT
        assert [(n.reason_codes, n.due_by) for n in north.last.overdue] \
            == [(("ARRIVAL:S2_OVERDUE",), NEW_CLOSES)]
        # Cedar Ridge: nobody overruled anything, so its own records stand.
        assert _said(cedar_view) == [("tms_status", "stands"), ("tms_status", "stands")]
        assert ced.last.state.stage is Stage.DELIVERED and _disputes(cedar_view) == []
        assert not [t for t in cedar_view.tracking if t.overruled_by or t.contests]
        assert shape(both, NORTHLINE) == shape(north_alone, NORTHLINE)
        assert shape(both, CEDAR) == shape(cedar_alone, CEDAR)
        north_ids = {e["expectation_id"] for e in north_view.expectations}
        cedar_ids = {e["expectation_id"] for e in cedar_view.expectations}
        assert len(north_ids) >= 3 and len(cedar_ids) >= 2 and not north_ids & cedar_ids
        assert cross_tenant_violations(store.conn) == [] and both.findings == []
        assert both.report["metrics"]["external_effect_rows"] == 0
    finally:
        store.close()
        north_store.close()
        cedar_store.close()


def test_the_human_decision_oracle_fires_when_a_rejected_claim_regains_authority(tmp_path):
    """Anti-vacuity for `bare_claims_over_a_human_decision`, which `audit_state` applies to every
    evaluation of every load. It is quiet about a load whose restated claim is overruled; it
    objects the moment that claim is let stand again; and it does NOT object to a claim made after
    the provider has put the truck past where she said it was."""
    h, cargo = _ruled_in_transit("HO")
    _tms_says_delivered(h, cargo, "tms-says-it-again", "10:00", 4)
    h.clock("end", h.t("12:00", 1, ET))
    result, store = _run(tmp_path / "restated", [h.build({})], setups=NO_CADENCE)
    g, moved = _ruled_in_transit("HO")
    moved.track("at-delivery", g.t("13:30", 1, ET), "AT_DELIVERY", "S2")
    _tms_says_delivered(g, moved, "delivered", "14:10", 4)
    g.clock("end", g.t("15:00", 1, ET))
    real, real_store = _run(tmp_path / "real", [g.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        restated = [t for t in view.tracking if t.overruled_by and t.value("status") == "DELIVERED"]
        assert len(restated) == 2 and bare_claims_over_a_human_decision(view) == []
        later = max(restated, key=_about)
        later.overruled_by = None                      # as if saying it again had made it stand
        assert len(bare_claims_over_a_human_decision(view)) == 1
        state = evaluate_load_work(view, setup=NO_CADENCE[NORTHLINE], as_of=story.last.as_of)
        assert [f for f in audit_state(state, view, tenant=NORTHLINE)
                if "REJECTED CLAIM REGAINED AUTHORITY" in f]
        _, real_view = _view(real)
        standing = [t for t in real_view.standing_tracking() if t.value("status") == "DELIVERED"]
        assert len(standing) == 1 and bare_claims_over_a_human_decision(real_view) == []

        # The other half: a claim made after her answer may be overruled unasked ONLY while
        # something is still owed. The restated row above is - the delivery is watched - and the
        # check is quiet. Strip the work, as a quiet load would have none, and it objects.
        later.overruled_by = _her_decision(view)
        owed = evaluate_load_work(view, setup=NO_CADENCE[NORTHLINE], as_of=story.last.as_of)
        assert owed.needs and claims_dropped_onto_a_quiet_load(owed, view) == []
        assert len(claims_dropped_onto_a_quiet_load(replace(owed, needs=()), view)) == 1
        assert [f for f in audit_state(replace(owed, needs=()), view, tenant=NORTHLINE)
                if "DROPPED UNASKED ON A QUIET LOAD" in f]
    finally:
        store.close()
        real_store.close()


# ============================================================ the appointment that stands

#: 16:00-18:00 Eastern on the second day, and the instant the loop looks again after it closes.
NEW_CLOSES = "2026-09-02T22:00:00.000Z"
NEW_LOOKS_AGAIN = "2026-09-02T22:01:00.000Z"
EARLIER_LOOKS_AGAIN = "2026-09-02T15:01:00.000Z"
#: 19:00-21:00 Eastern.
EVENING_CLOSES = "2026-09-03T01:00:00.000Z"


def _run_seeing(path: Path, histories, *, setups=SETUPS, **kw):
    """`_run`, keeping every evaluation of every load - not only the moments that were recorded.
    A deadline that must NOT fire leaves no moment behind; what the operator would have been
    shown at that instant is here."""
    seen: list = []

    def audit(state, view, tenant):
        seen.append(state)
        return [*audit_state(state, view, tenant=tenant),
                *_unwatched_stops(view, setups[tenant]), *_doubly_watched_stops(view)]

    result, store = _run(path, histories, setups=setups, audit=audit, **kw)
    return result, store, [s for s in seen if s.load_number == "LD-59001"]


def _arrival_work(state, stop_key: str = "S2") -> list[tuple]:
    """Every need on this evaluation that is about the truck's arrival at a stop."""
    return [(n.kind, n.status, n.due_by) for n in state.needs
            if f"ARRIVAL_EXPECTED:{stop_key}" in n.reason_codes
            or any(c.startswith(f"ARRIVAL:{stop_key}_") for c in n.reason_codes)]


def _instant(h, clock: str) -> str:
    """`clock` Eastern on the second day, as the instant the loop stamps an evaluation with."""
    return utc_datetime(h.t(clock, 1, ET)).astimezone(ZoneInfo("UTC")).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z")


def test_a_rescheduled_appointment_is_watched_on_the_window_it_was_rescheduled_to(tmp_path):
    """THE THIRD REVIEW'S SECOND BLOCKER. The system of record says the 13:00-15:00 delivery
    appointment was RESCHEDULED to 16:00-18:00. The watch used to stay on 13:00-15:00: at 15:01 the
    truck was called provably late against a window nobody held, and 16:00-18:00 was never timed.
    The appointment that stands is the one the record now carries: the watch moves to it, 15:00
    passes with nothing late, and 18:00 passing with no truck is the miss. That the new window is
    not yet CONFIRMED is still work - verifying it - and says so."""
    h, cargo = _afternoon("SA")
    _tms_window(h, cargo, "rescheduled", h.t("08:00", 1, ET), 3, "16:00", "18:00",
                appointment="RESCHEDULED")
    h.clock("after-the-old-window", h.t("15:01", 1, ET))
    h.clock("end", h.t("22:00", 1))
    result, store, seen = _run_seeing(tmp_path, [h.build({})])
    try:
        story, view = _view(result)
        moved = story.at("rescheduled")
        watch = moved.state.need(NeedKind.ARRIVAL_PENDING)
        assert watch is not None and watch.due_by == NEW_CLOSES
        verify = moved.state.need(NeedKind.APPOINTMENT_UNCONFIRMED)
        assert verify is not None and verify.reason_codes == ("APPOINTMENT_RESCHEDULED:S2",)
        assert "is being watched" in verify.why and moved.next_step == "NEYMA:VERIFY_APPOINTMENT"
        assert "16:00" in moved.proposals[0].draft and "13:00" not in moved.proposals[0].draft

        # 15:01 Eastern: the old window has closed, and nothing is late.
        at_1501 = [s for s in seen if s.as_of == _instant(h, "15:01")]
        assert len(at_1501) == 1
        assert _arrival_work(at_1501[0]) \
            == [(NeedKind.ARRIVAL_PENDING, NeedStatus.PENDING, NEW_CLOSES)]
        assert at_1501[0].need(NeedKind.CARRIER_STATUS_OVERDUE) is None
        # Every evaluation from the reschedule to 18:00: pending on 18:00, and on nothing else.
        waiting = [s for s in seen if moved.as_of <= s.as_of < NEW_CLOSES]
        assert len(waiting) >= 2
        for state in waiting:
            assert _arrival_work(state) \
                == [(NeedKind.ARRIVAL_PENDING, NeedStatus.PENDING, NEW_CLOSES)], state.as_of

        # 18:00 passes with no truck: THAT is the missed appointment.
        ticks = [m for m in story.moments if m.trigger_kind == "tick"]
        assert [m.as_of for m in ticks] == [NEW_LOOKS_AGAIN]
        assert [(n.kind, n.reason_codes, n.due_by) for n in story.last.overdue] \
            == [(NeedKind.CARRIER_STATUS_OVERDUE, ("ARRIVAL:S2_OVERDUE",), NEW_CLOSES)]
        assert story.last.state.need(NeedKind.APPOINTMENT_UNCONFIRMED) is not None
        # ONE watch: the row that was there followed the appointment, by amendment.
        watches = _watches(view, "arrival:S2")
        assert [(e["state"], e["deadline_utc"]) for e in watches] == [("OVERDUE", NEW_CLOSES)]
        assert json.loads(watches[0]["deadline_history"]) == [RESTORED_CLOSES]
        assert [m.trigger for m in story.moments if m.quiet] == []
        assert result.findings == [] and result.report["metrics"]["external_effect_rows"] == 0
    finally:
        store.close()


def test_a_cancelled_appointment_is_nobodys_deadline(tmp_path):
    """The system of record says the delivery appointment was CANCELLED - while it was still
    ahead, and again after it had already been missed. Either way nobody is held to that window
    any more: its watch is withdrawn, the truck is never called late against it, and a chase that
    was open only because of it ends. The stop is back to having no appointment anyone holds,
    which is work of the kind that was always there: verify the appointment. Never quiet."""
    cases = {"cancelled while it was still ahead": ("08:00", 0),
             "cancelled after it was missed": ("15:30", 1)}
    assert len(cases) == 2
    for index, (name, (clock, cured)) in enumerate(cases.items()):
        h, cargo = _afternoon(f"SB{index}")
        _tms_window(h, cargo, "cancelled", h.t(clock, 1, ET), 3, "13:00", "15:00",
                    appointment="CANCELLED")
        h.clock("later", h.t("16:00", 1, ET))
        h.clock("end", h.t("22:00", 1))
        result, store, seen = _run_seeing(tmp_path / str(index), [h.build({})])
        try:
            story, view = _view(result)
            gone = story.at("cancelled")
            after = [s for s in seen if s.as_of >= gone.as_of]
            assert len(after) >= 3, name
            for state in after:
                assert _arrival_work(state) == [], f"{name}: {state.as_of}"
                assert state.need(NeedKind.CARRIER_STATUS_OVERDUE) is None, name
                verify = state.need(NeedKind.APPOINTMENT_UNCONFIRMED)
                assert verify is not None \
                    and verify.reason_codes == ("APPOINTMENT_CANCELLED:S2",), name
                assert not state.routine_work_is_zero, name
            assert gone.next_step == "NEYMA:VERIFY_APPOINTMENT", name
            draft = gone.proposals[0].draft
            assert "cancelled" in draft and "13:00" not in draft, name
            before = [m for m in story.moments if m.index < gone.index and m.overdue]
            assert len(before) == cured, f"{name}: the window was (not) missed first"
            assert [(e["state"], e["deadline_utc"]) for e in _watches(view, "arrival:S2")] \
                == [("CANCELLED", RESTORED_CLOSES)], name
            # A miss that was called before the cancellation leaves its Exception: closed by a
            # human, never by a rule, and housekeeping until then - not work.
            assert len(story.last.state.housekeeping) == cured, name
            assert [m.trigger for m in story.moments if m.quiet] == [], name
            assert result.findings == [], name
        finally:
            store.close()


def test_only_the_appointment_that_stands_times_the_truck(tmp_path):
    """Rescheduled EARLIER; rescheduled three times while every window was still ahead;
    rescheduled after each window had already been missed; rescheduled to a window that had
    already closed when the record arrived; rescheduled and then CONFIRMED. Every time: one live
    watch, on the window the appointment now has; nothing late for a window it has left; and the
    miss of the window that stands is called when THAT window closes."""
    cases = {
        "rescheduled earlier": (
            [("07:00", "09:00", "11:00", "RESCHEDULED")],
            [("OVERDUE", EARLIER_CLOSES)], [EARLIER_LOOKS_AGAIN], True),
        "three times, all ahead": (
            [("08:00", "16:00", "18:00", "RESCHEDULED"), ("08:10", "19:00", "21:00", "RESCHEDULED"),
             ("08:20", "16:00", "18:00", "RESCHEDULED")],
            [("OVERDUE", NEW_CLOSES)], [NEW_LOOKS_AGAIN], True),
        "after each was missed": (
            [("15:30", "16:00", "18:00", "RESCHEDULED"),
             ("18:30", "19:00", "21:00", "RESCHEDULED")],
            [("CANCELLED", RESTORED_CLOSES), ("CANCELLED", NEW_CLOSES),
             ("OVERDUE", EVENING_CLOSES)],
            [RESTORED_LOOKS_AGAIN, NEW_LOOKS_AGAIN, "2026-09-03T01:01:00.000Z"], True),
        "to a window already closed": (
            [("12:00", "09:00", "11:00", "RESCHEDULED")],
            [("OVERDUE", EARLIER_CLOSES)], [], True),
        "rescheduled, then confirmed": (
            [("08:00", "16:00", "18:00", "RESCHEDULED"), ("12:00", "16:00", "18:00", "CONFIRMED")],
            [("OVERDUE", NEW_CLOSES)], [NEW_LOOKS_AGAIN], False),
    }
    assert len(cases) == 5
    for index, (name, (moves, rows, ticks, unconfirmed)) in enumerate(cases.items()):
        h, cargo = _afternoon(f"SC{index}")
        for step, (clock, start, end, status) in enumerate(moves):
            _tms_window(h, cargo, f"move-{step}", h.t(clock, 1, ET), 3 + step, start, end,
                        appointment=status)
        h.clock("end", h.t("23:30", 1))
        result, store, seen = _run_seeing(tmp_path / str(index), [h.build({})])
        try:
            story, view = _view(result)
            assert _arrival_rows(view) == rows, name
            assert [m.as_of for m in story.moments if m.trigger_kind == "tick"] == ticks, name
            standing = rows[-1][1]
            final = story.at(f"move-{len(moves) - 1}")
            judged = [s for s in seen if s.as_of >= final.as_of]
            assert len(judged) >= 2, name
            for state in judged:
                want = ((NeedKind.ARRIVAL_PENDING, NeedStatus.PENDING, standing)
                        if state.as_of < standing
                        else (NeedKind.CARRIER_STATUS_OVERDUE, NeedStatus.OVERDUE, standing))
                assert _arrival_work(state) == [want], f"{name}: {state.as_of}"
            assert (story.last.state.need(NeedKind.APPOINTMENT_UNCONFIRMED) is not None) \
                is unconfirmed, name
            assert [(n.reason_codes, n.due_by) for n in story.last.overdue] \
                == [(("ARRIVAL:S2_OVERDUE",), standing)], name
            assert [m.trigger for m in story.moments if m.quiet] == [], name
            assert result.findings == [], f"{name}: {result.findings[:2]}"
        finally:
            store.close()


def test_a_brokerage_that_watches_no_arrivals_is_not_told_a_rescheduled_window_is_watched(
        tmp_path):
    """Cedar Ridge has no tracking channel it expects arrivals on, so nothing there is timed. A
    rescheduled appointment is still work - verify it - named for what it is, and the need does
    not claim a watch that does not exist."""
    h, cargo = _afternoon("SF", tenant=CEDAR, ops=CEDAR_OPS, pods=CEDAR_OPS)
    _tms_window(h, cargo, "rescheduled", h.t("08:00", 1, ET), 3, "16:00", "18:00",
                appointment="RESCHEDULED")
    h.clock("end", h.t("22:00", 1))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result, CEDAR)
        assert NO_CADENCE[CEDAR].arrival_tracking_channel is None
        verify = story.at("rescheduled").state.need(NeedKind.APPOINTMENT_UNCONFIRMED)
        assert verify is not None and verify.reason_codes == ("APPOINTMENT_RESCHEDULED:S2",)
        assert "no arrival deadline is being watched" in verify.why
        assert "is being watched." not in verify.why.replace("deadline is being watched", "")
        assert [e for e in view.expectations if e["expected_type"].startswith("arrival:")] == []
        assert not story.last.quiet and result.findings == []
    finally:
        store.close()


def test_a_truck_that_arrived_owes_nothing_when_its_appointment_is_then_changed(tmp_path):
    """The truck checks in at the receiver at noon. Afterwards the appointment record is
    rescheduled, then cancelled, then confirmed for another time. None of it is the truck's to
    answer: it has been there. No arrival work is manufactured, nothing is late, one watch,
    answered once."""
    h, cargo = _afternoon("SD")
    cargo.track("at-delivery", h.t("12:00", 1, ET), "AT_DELIVERY", "S2")
    _tms_window(h, cargo, "rescheduled", h.t("12:30", 1, ET), 3, "16:00", "18:00",
                appointment="RESCHEDULED")
    _tms_window(h, cargo, "cancelled", h.t("12:40", 1, ET), 4, "16:00", "18:00",
                appointment="CANCELLED")
    _tms_window(h, cargo, "confirmed", h.t("12:50", 1, ET), 5, "09:00", "11:00")
    h.clock("end", h.t("22:00", 1))
    result, store, seen = _run_seeing(tmp_path, [h.build({})])
    try:
        story, view = _view(result)
        after = [s for s in seen if s.as_of >= story.at("at-delivery").as_of]
        assert len(after) >= 5
        for state in after:
            assert _arrival_work(state) == [], state.as_of
            assert state.need(NeedKind.APPOINTMENT_UNCONFIRMED) is None, state.as_of
        assert [(e["state"], bool(e["late"])) for e in _watches(view, "arrival:S2")] \
            == [("DISCHARGED", False)]
        assert not [m for m in story.moments if m.overdue]
        assert story.last.state.housekeeping == () and result.findings == []
    finally:
        store.close()


def test_appointment_changes_delivered_twice_change_nothing(tmp_path):
    """A reschedule and a cancellation, each delivered twice at once and then the whole inbox
    again: the same watches, the same ids, the same pictures - one watch amended once, one
    cancelled once."""
    def history(final: str):
        h, cargo = _afternoon("SE")
        _tms_window(h, cargo, "rescheduled", h.t("08:00", 1, ET), 3, "16:00", "18:00",
                    appointment="RESCHEDULED")
        if final == "CANCELLED":
            _tms_window(h, cargo, "cancelled", h.t("17:00", 1, ET), 4, "16:00", "18:00",
                        appointment="CANCELLED")
        h.clock("end", h.t("22:00", 1))
        return h.build({})

    def rows(result: LoopRunResult) -> list[tuple]:
        _, view = _view(result)
        return [(e["expectation_id"], e["expected_type"], e["state"], e["deadline_utc"])
                for e in view.expectations]

    stores = []
    try:
        for final in ("RESCHEDULED", "CANCELLED"):
            once, store = _run(tmp_path / f"{final}-once", [history(final)], setups=NO_CADENCE)
            stores.append(store)
            twice, store = _run(tmp_path / f"{final}-twice",
                                [duplicate_every_record(history(final))], setups=NO_CADENCE)
            stores.append(store)
            assert twice.report["metrics"]["duplicate_records_suppressed"] >= 10
            assert _final(twice) == _final(once) and rows(twice) == rows(once), final
            counted = ("expectations_raised", "expectations_cancelled", "expectations_amended")
            assert {n: getattr(twice.intakes[NORTHLINE].stats, n) for n in counted} \
                == {n: getattr(once.intakes[NORTHLINE].stats, n) for n in counted}, final
            assert once.intakes[NORTHLINE].stats.writes_after_settle == 0
            assert once.findings == [] and twice.findings == [], final
            # Replayed, and restarted just before and just after the appointment record changed.
            for cut in (None, "loaded", "rescheduled"):
                again, store = _run(tmp_path / f"{final}-{cut}", [history(final)],
                                    setups=NO_CADENCE,
                                    restart_after={"SE": cut} if cut else None)
                stores.append(store)
                assert _digests(again) == _digests(once), f"{final}: differs after {cut}"
                assert rows(again) == rows(once) and again.findings == [], final
    finally:
        for item in stores:
            item.close()


# ============================================================ a blind channel

#: Every way the tracking channel can fail to be provably up: no reading at all, and each reading
#: that is not HEALTHY. Discovered from the vocabulary, so a health state added later is covered.
BLIND = (None, *(health for health in COVERAGE_HEALTH if health != "HEALTHY"))


def _blind(h, health: str | None) -> None:
    """Take away the HEALTHY reading this history has for the tracking channel. With `health`,
    put in its place a reading that says the channel was that; with None, no reading at all."""
    h.records[:] = [r for r in h.records
                    if not (r.kind == "channel_coverage" and r.payload["channel"] == TRACKING)]
    if health is not None:
        _cover(h, TRACKING, health=health, minute=40)
        _in_arrival_order(h)


def _blind_afternoon(history_id: str, health: str | None, moves, **kw):
    h, cargo = _afternoon(history_id, **kw)
    _blind(h, health)
    for step, (clock, start, end) in enumerate(moves):
        _says_window(h, cargo, f"window-{step}", clock, start, end)
    return h, cargo


def test_the_blind_states_are_discovered_and_are_blind(tmp_path):
    """Population first: three unhealthy readings and the absence of any, and each really does
    leave M8 unable to call a missed appointment late - INDETERMINATE, shown as UNVERIFIED."""
    assert BLIND == (None, "DOWN", "UNKNOWN", "PARTIAL")
    for index, health in enumerate(BLIND):
        h, _ = _blind_afternoon(f"BP{index}", health, [])
        h.clock("end", h.t("22:00", 1))
        result, store = _run(tmp_path / str(index), [h.build({})], setups=NO_CADENCE)
        try:
            story, view = _view(result)
            assert _arrival_rows(view) == [("INDETERMINATE", RESTORED_CLOSES)], health
            assert [(n.status, n.reason_codes, n.due_by) for n in story.last.overdue] \
                == [(NeedStatus.UNVERIFIED, ("ARRIVAL:S2_UNVERIFIED",), RESTORED_CLOSES)], health
            assert result.findings == [], health
        finally:
            store.close()


@pytest.mark.parametrize("health", BLIND, ids=lambda health: health or "no-reading")
def test_a_blind_channel_does_not_set_the_appointments_deadline(tmp_path, health):
    """THE THIRD REVIEW'S THIRD BLOCKER (`P9-D66`). A window closes while the tracking channel
    cannot be shown to be up, so M8 rules the watch INDETERMINATE - and will neither amend nor
    cancel it. The appointment then moves: put back where it was, moved on, moved three times,
    moved on and back. That row used to go on driving the work: an "unverified" chase due at the
    window nobody held, and - put back - no watch on the appointment that stood at all.

    The row is left exactly as M8 ruled it. It is history about a window: the appointment that
    stands is watched by a row whose deadline is its own, the operator's work carries THAT
    deadline, and its miss surfaces when it closes - as unverified, because the channel is blind,
    which is the one thing channel health is allowed to decide."""
    cases = {
        "put back": (
            [("11:20", "09:00", "11:00"), ("11:25", "13:00", "15:00")],
            [("INDETERMINATE", EARLIER_CLOSES), ("INDETERMINATE", RESTORED_CLOSES)]),
        "moved on after the window closed": (
            [("15:30", "16:00", "18:00")],
            [("INDETERMINATE", RESTORED_CLOSES), ("INDETERMINATE", NEW_CLOSES)]),
        "three times": (
            [("11:20", "09:00", "11:00"), ("11:25", "13:00", "15:00"),
             ("15:30", "16:00", "18:00")],
            [("INDETERMINATE", EARLIER_CLOSES), ("INDETERMINATE", RESTORED_CLOSES),
             ("INDETERMINATE", NEW_CLOSES)]),
        "moved on, and back onto the window the blind row is on": (
            [("15:30", "16:00", "18:00"), ("15:40", "13:00", "15:00")],
            [("INDETERMINATE", RESTORED_CLOSES), ("CANCELLED", NEW_CLOSES)]),
    }
    assert len(cases) == 4
    for index, (name, (moves, rows)) in enumerate(cases.items()):
        h, _ = _blind_afternoon(f"BA{index}", health, moves)
        h.clock("end", h.t("23:30", 1))
        result, store, seen = _run_seeing(tmp_path / str(index), [h.build({})])
        try:
            story, view = _view(result)
            assert _arrival_rows(view) == rows, name
            assert len({e["expectation_id"] for e in _watches(view, "arrival:S2")}) == len(rows)
            standing = utc_datetime(h.t(moves[-1][2], 1, ET)).astimezone(
                ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            final = story.at(f"window-{len(moves) - 1}")
            judged = [s for s in seen if s.as_of >= final.as_of]
            assert len(judged) >= 2 and judged[-1].as_of > standing, name
            for state in judged:
                # ONE piece of arrival work, on the deadline of the appointment that stands.
                want = ((NeedKind.ARRIVAL_PENDING, NeedStatus.PENDING, standing)
                        if state.as_of < standing
                        else (NeedKind.CARRIER_STATUS_OVERDUE, NeedStatus.UNVERIFIED, standing))
                assert _arrival_work(state) == [want], f"{name}: {state.as_of}"
                assert not state.routine_work_is_zero and not state.billing_ready, name
                assert len(state.human_attention) == 0 and len(state.candidates) <= 1, name
            last = story.last
            assert [n.reason_codes for n in last.overdue] == [("ARRIVAL:S2_UNVERIFIED",)], name
            assert last.next_step == "NEYMA:REQUEST_CARRIER_STATUS", name
            # Every watch M8 judged blind against a window that is gone is still there, as it
            # was ruled - and each is exactly one Exception awaiting a human's closure.
            left = [e for e in _watches(view, "arrival:S2")
                    if watches_a_window_that_is_gone(view, e)]
            assert len(left) == len([r for r in rows[:-1] if r[0] == "INDETERMINATE"]) \
                - (1 if rows[-1][0] == "CANCELLED" else 0), name
            assert len(last.state.housekeeping) == len(left), name
            assert [m.trigger for m in story.moments if m.quiet or m.billing_ready] == [], name
            assert result.intakes[NORTHLINE].stats.writes_after_settle == 0, name
            assert result.findings == [], f"{name}: {result.findings[:2]}"
        finally:
            store.close()


@pytest.mark.parametrize("health", BLIND, ids=lambda health: health or "no-reading")
def test_a_truck_that_arrives_after_a_blind_reschedule_closes_everything_once(tmp_path, health):
    """13:00-15:00 closes blind; the receiver pushes the appointment to 16:00-18:00; the truck
    arrives - inside the new window, and in a second run after it. Its arrival answers every watch
    M8 still holds, the delivery and the POD follow, and the load ends quiet and billing-ready
    with exactly the housekeeping the same load leaves over a healthy channel: no second chase,
    no second question, nothing owed for the window that is gone."""
    for arrives, delivered, pod in (("17:00", "17:20", "17:40"), ("19:00", "19:20", "19:40")):
        def history(blind: bool):
            h, cargo = _afternoon("BT")
            if blind:
                _blind(h, health)
            _says_window(h, cargo, "pushed", "15:30", "16:00", "18:00")
            cargo.track("at-delivery", h.t(arrives, 1, ET), "AT_DELIVERY", "S2")
            cargo.delivered("delivered", h.t(delivered, 1, ET))
            cargo.pod("pod", h.t(pod, 1, ET))
            h.clock("end", h.t("23:30", 1))
            return h.build({})

        name = f"arrives {arrives}"
        result, store, seen = _run_seeing(tmp_path / f"blind-{arrives[:2]}", [history(True)])
        healthy, healthy_store = _run(tmp_path / f"healthy-{arrives[:2]}", [history(False)],
                                      setups=NO_CADENCE)
        try:
            (story, view), (healthy_story, _) = _view(result), _view(healthy)
            pushed = story.at("pushed")
            assert _arrival_work(pushed.state) \
                == [(NeedKind.ARRIVAL_PENDING, NeedStatus.PENDING, NEW_CLOSES)], name
            arrived = story.at("at-delivery")
            assert _arrival_work(arrived.state) == [], name
            assert not [e for e in _watches(view, "arrival:S2") if e["state"] in _OWED], name
            assert [e["state"] for e in _watches(view, "arrival:S2")] \
                == ["DISCHARGED", "DISCHARGED"], name
            done = story.at("pod")
            assert done.quiet and done.billing_ready and _work(done) == [], name
            assert [m.trigger for m in story.moments if m.billing_ready] == ["pod"], name
            assert len(story.last.state.housekeeping) \
                == len(healthy_story.last.state.housekeeping), name
            assert _work(story.last) == _work(healthy_story.last) == [], name
            proposed = {(p.need_id, p.action) for m in story.moments for p in m.proposals}
            assert len([p for p in proposed if p[1] == "REQUEST_CARRIER_STATUS"]) <= 1, name
            assert not [m for m in story.moments if m.escalations], name
            assert result.findings == [] and healthy.findings == [], name
        finally:
            store.close()
            healthy_store.close()


@pytest.mark.parametrize("health", BLIND, ids=lambda health: health or "no-reading")
def test_a_blind_reschedule_is_the_same_looked_at_again_and_delivered_twice(tmp_path, health):
    """The put-back load over a blind channel: the clock read five more times with nothing
    arriving, every record delivered twice, replayed, and restarted after each appointment
    change. The same rows under the same ids, the same counts of what was raised, and the same
    pictures - a row that is history is not raised again on every look."""
    def history(looks: int = 0):
        h, _ = _blind_afternoon("BR", health,
                                [("11:20", "09:00", "11:00"), ("11:25", "13:00", "15:00")])
        for index in range(looks):
            h.clock(f"look-{index}", h.t(f"{16 + index}:10", 1, ET))
        h.clock("end", h.t("23:30", 1))
        return h.build({})

    def rows(result: LoopRunResult) -> list[tuple]:
        _, view = _view(result)
        return [(e["expectation_id"], e["expected_type"], e["state"], e["deadline_utc"])
                for e in view.expectations]

    once, store = _run(tmp_path / "once", [history()], setups=NO_CADENCE)
    stores = [store]
    try:
        counted = ("expectations_raised", "expectations_cancelled", "expectations_amended",
                   "expectations_discharged", "exceptions_raised", "writes_after_settle")
        told = {name: getattr(once.intakes[NORTHLINE].stats, name) for name in counted}
        assert told["expectations_raised"] == 3 and told["writes_after_settle"] == 0
        again, store = _run(tmp_path / "looked", [history(5)], setups=NO_CADENCE)
        stores.append(store)
        assert rows(again) == rows(once) and _final(again) == _final(once)
        assert {name: getattr(again.intakes[NORTHLINE].stats, name) for name in counted} == told
        replayed, store = _run(tmp_path / "replayed", [history()], setups=NO_CADENCE)
        stores.append(store)
        assert _digests(replayed) == _digests(once) and rows(replayed) == rows(once)
        for cut in ("loaded", "window-0", "window-1"):
            restarted, store = _run(tmp_path / cut, [history()], setups=NO_CADENCE,
                                    restart_after={"BR": cut})
            stores.append(store)
            assert _digests(restarted) == _digests(once), f"a restart after {cut} differs"
            assert rows(restarted) == rows(once) and restarted.findings == []
        doubled, store = _run(tmp_path / "doubled", [duplicate_every_record(history())],
                              setups=NO_CADENCE)
        stores.append(store)
        assert _final(doubled) == _final(once) and rows(doubled) == rows(once)
        assert once.findings == [] and again.findings == [] and doubled.findings == []
    finally:
        for item in stores:
            item.close()


def test_a_cancelled_appointment_over_a_blind_channel_is_nobodys_deadline_either(tmp_path):
    """The window closes blind and the appointment is then CANCELLED. M8 will not cancel the watch
    it judged; the appointment it was for is gone all the same. Nothing about that window is
    work: no unverified chase, no deadline - only the stop that has no appointment anyone holds."""
    h, cargo = _afternoon("BC")
    _blind(h, None)
    _tms_window(h, cargo, "cancelled", h.t("15:30", 1, ET), 3, "13:00", "15:00",
                appointment="CANCELLED")
    h.clock("end", h.t("23:30", 1))
    result, store, seen = _run_seeing(tmp_path, [h.build({})])
    try:
        story, view = _view(result)
        gone = story.at("cancelled")
        before = [m for m in story.moments if m.index < gone.index and m.overdue]
        assert [n.reason_codes for m in before for n in m.overdue] == [("ARRIVAL:S2_UNVERIFIED",)]
        after = [s for s in seen if s.as_of >= gone.as_of]
        assert len(after) >= 2
        for state in after:
            assert _arrival_work(state) == [] and not state.routine_work_is_zero
            assert state.need(NeedKind.CARRIER_STATUS_OVERDUE) is None
            assert state.need(NeedKind.APPOINTMENT_UNCONFIRMED).reason_codes \
                == ("APPOINTMENT_CANCELLED:S2",)
        assert _arrival_rows(view) == [("INDETERMINATE", RESTORED_CLOSES)]
        assert len(story.last.state.housekeeping) == 1 and result.findings == []
    finally:
        store.close()


def test_the_current_deadline_oracle_fires_when_work_rests_on_a_window_that_is_gone(tmp_path):
    """Anti-vacuity for the current-deadline check in `audit_state`. Over a blind channel a put-
    back appointment leaves one watch M8 judged against the window that is gone. The oracle knows
    it for what it is, is quiet while no need rests on it - and objects the moment one does, which
    is exactly what the unrepaired work engine did."""
    h, _ = _blind_afternoon("BO", None,
                            [("11:20", "09:00", "11:00"), ("11:25", "13:00", "15:00")])
    h.clock("end", h.t("12:00", 1, ET))
    result, store = _run(tmp_path, [h.build({})], setups=NO_CADENCE)
    try:
        story, view = _view(result)
        left = [e for e in view.owed_expectations() if watches_a_window_that_is_gone(view, e)]
        current = [e for e in view.owed_expectations()
                   if e["expected_type"] == "arrival:S2" and e not in left]
        assert [(e["state"], e["deadline_utc"]) for e in left] \
            == [("INDETERMINATE", EARLIER_CLOSES)]
        assert [(e["state"], e["deadline_utc"]) for e in current] == [("RAISED", RESTORED_CLOSES)]
        state = evaluate_load_work(view, setup=NO_CADENCE[NORTHLINE], as_of=story.last.as_of)
        assert audit_state(state, view, tenant=NORTHLINE) == []
        need = state.need(NeedKind.ARRIVAL_PENDING)
        stale = replace(need, origins=(*need.origins, f"expectation:{left[0]['expectation_id']}"))
        forged = replace(state, needs=tuple(stale if n is need else n for n in state.needs))
        assert [f.split(": ", 1)[1][:14] for f in audit_state(forged, view, tenant=NORTHLINE)] \
            == ["STALE DEADLINE"]
        # A watch that is merely late for the window that STANDS is not one of them.
        assert not watches_a_window_that_is_gone(view, {**left[0],
                                                        "deadline_utc": RESTORED_CLOSES})
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
