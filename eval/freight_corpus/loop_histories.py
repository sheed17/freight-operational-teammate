"""Complete brokerage loads, written to be run CONTINUOUSLY: booked -> pickup -> tracking and
communications -> delivery -> POD and documents -> reconciliation -> customer billing-ready.

The through-time histories in `work_histories.py` each isolate one piece of work. These are whole
loads. Each starts at the tender and runs until the load is either quiet and billing-ready, or is
honestly left where a real one would be: waiting on a named human. One is clean; the rest each
carry the kind of trouble a brokerage actually has.

A history's `expected["work"]` is the same list of labeled checkpoints the work engine uses, with
the loop's own labels beside them: how many human touches the load has cost so far, what is overdue,
what carrier-side work is open, what Neyma would propose, what a human is asked. Only what a
checkpoint LABELS is checked.

No history carries a `clock` record merely to make a deadline fire. The loop looks again at every
deadline the canonical record holds; a history says only what ARRIVED, and when it ends.

They run in their OWN database, on the work corpus's setups (Northline has a tracking cadence).

SYNTHETIC. Every company, person, number and sentence here is invented development input. Nothing in
this file is a design-partner observation and no freight rule is validated by it.
"""

from __future__ import annotations

from typing import Any

from freight_recon.freight_domain.history import to_utc

from .builders import (
    HistoryBuilder,
    charges,
    claims,
    load_ref,
    movement,
    says,
    states_appointment,
)
from .histories import TRACKING, _cover, _pod, _rate_con, _stops
from .parties import (
    CARRIERS,
    CEDAR,
    CEDAR_OPS,
    CUSTOMERS,
    NORTHLINE,
    NORTHLINE_OPS,
    NORTHLINE_PODS,
    NORTHLINE_SMS,
    dispatcher,
    driver,
)
from .work_histories import WORK_SETUPS, _delivered, _invoice_as, checkpoint, promise

LOOP_SETUPS = WORK_SETUPS


class Load:
    """One load's fixed facts, so a history reads as what happened rather than as its arguments."""

    def __init__(self, h: HistoryBuilder, number: str, *, customer: str, carrier: str, sell: int,
                 buy: int, serial: str, pickup: str, delivery: str,
                 pickup_status: str = "CONFIRMED", delivery_status: str = "CONFIRMED",
                 delivery_zone: str = "America/Chicago",
                 pickup_window: tuple[str, str] = ("10:00", "12:00"),
                 delivery_window: tuple[str, str] = ("09:00", "11:00"),
                 ops: str = NORTHLINE_OPS, pods: str = NORTHLINE_PODS, tag: str = "") -> None:
        self.h, self.number, self.refs, self.tag = h, number, (load_ref(number),), tag
        self.customer_key, self.carrier_key = customer, carrier
        self.sell, self.buy, self.ops, self.pods = sell, buy, ops, pods
        self.po, self.bol, self.pro = f"PO-{serial}", f"BOL-{serial}", f"PRO-{serial}"
        self.delivery_zone = delivery_zone
        self.stops = _stops(h, pickup=pickup, delivery=delivery, pickup_status=pickup_status,
                            delivery_status=delivery_status, delivery_zone=delivery_zone,
                            pickup_window=pickup_window, delivery_window=delivery_window)
        self.customer: dict[str, Any] = CUSTOMERS[customer]
        self.carrier: dict[str, Any] = CARRIERS[carrier]

    def book(self, tender: str = "07:30", cover: str = "08:00", rate_con: str = "08:20") -> None:
        """Tendered, covered, and the rate confirmation signed: a booked load."""
        h = self.h
        h.tms(f"tender{self.tag}", h.t(tender), load=self.number, status="TENDERED", version=1,
              customer=self.customer, po=self.po, bol=self.bol, sell=charges(self.sell),
              stops=self.stops)
        h.tms(f"covered{self.tag}", h.t(cover), load=self.number, status="COVERED", version=2,
              customer=self.customer, po=self.po, bol=self.bol, sell=charges(self.sell),
              stops=self.stops, movements=(movement("M1", self.carrier, pro=self.pro),))
        _rate_con(self.h, f"rate-con{self.tag}", self.h.t(rate_con), load=self.number,
                  number=f"RC-{self.number[3:]}", carrier=self.carrier_key, linehaul=self.buy,
                  via=self.ops)

    def track(self, label: str, at: str, status: str, stop_key: str | None = None,
              position: str | None = None) -> None:
        self.h.track(label, at, status, refs=self.refs, stop_key=stop_key, position=position)

    def pings(self, *times: tuple[str, int]) -> None:
        for clock, day in times:
            self.track(f"ping{self.tag}-{day}-{clock.replace(':', '')}", self.h.t(clock, day),
                       "IN_TRANSIT",
                       position="en route")

    def run_to_delivery(self, *, at_pickup: str = "10:20", loaded: str = "11:05",
                        at_delivery: str = "08:10", delivered: str = "08:55") -> None:
        """Picked up inside the window, tracked inside the cadence, delivered inside the window."""
        h, tag = self.h, self.tag
        self.track(f"at-pickup{tag}", h.t(at_pickup), "AT_PICKUP", "S1")
        self.track(f"loaded{tag}", h.t(loaded), "LOADED", "S1")
        self.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
        self.track(f"at-delivery{tag}", h.t(at_delivery, 1), "AT_DELIVERY", "S2")
        self.delivered(f"delivered{tag}", h.t(delivered, 1))

    def sms(self, label: str, at: str, body: str, *asserts: dict[str, Any],
            who: str = "driver") -> None:
        sender = driver(self.carrier_key) if who == "driver" else dispatcher(self.carrier_key)
        self.h.message(label, at, channel="sms", source_system=NORTHLINE_SMS, sender=sender,
                       thread=f"sms-{self.number}-{who}", body=body, refs=self.refs,
                       asserts=tuple(asserts))

    def email(self, label: str, at: str, body: str, *asserts: dict[str, Any]) -> None:
        self.h.message(label, at, channel="email", source_system=self.ops,
                       sender=dispatcher(self.carrier_key), thread=f"re-{self.number}",
                       subject=f"RE: {self.number}", body=body, refs=self.refs,
                       asserts=tuple(asserts))

    def delivered(self, label: str, at: str, version: int = 3) -> None:
        _delivered(self.h, label, at, load=self.number, customer=self.customer,
                   carrier=self.carrier, po=self.po, bol=self.bol, pro=self.pro, sell=self.sell,
                   stops=self.stops, version=version)

    def pod(self, label: str, at: str, **kw: Any) -> None:
        _pod(self.h, label, at, load=self.number, via=self.pods, **kw)

    def invoice(self, label: str, at: str, *, linehaul: int | None = None, mc: Any = "registered",
                accessorials: dict[str, int] | None = None, rendition: str = "a",
                number: str | None = None) -> str:
        printed = self.carrier["mc"] if mc == "registered" else mc
        return _invoice_as(self.h, label, at, load=self.number,
                           number=number or f"INV-{self.number[3:]}", carrier=self.carrier_key,
                           linehaul=self.buy if linehaul is None else linehaul, via=self.ops,
                           mc=printed, accessorials=accessorials, rendition=rendition)


def _builder(history_id: str, title: str, day: str, *hostile: str,
             tenant: str = NORTHLINE) -> HistoryBuilder:
    h = HistoryBuilder(history_id, title, tenant, day=day, zone="America/Chicago",
                       hostile=tuple(hostile))
    if tenant == NORTHLINE:
        _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    else:
        _cover(h, CEDAR_OPS)
    return h


def _in_arrival_order(h: HistoryBuilder) -> None:
    """Two loads written one after the other are one inbox: put their records in the order they
    arrived. The sort is stable, so records at the same instant keep the order they were written."""
    h.records.sort(key=lambda record: to_utc(record.received_at, what="received_at"))


ARRIVALS = [("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
            ("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC")]
ROLLING = [("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
           ("TRACKING_UPDATE_PENDING", "PENDING", "DETERMINISTIC")]


# ============================================================ L01: the load that needs nobody

def l01_clean() -> Any:
    """Booked, picked up inside its window, tracked inside the cadence, delivered inside its window,
    signed for, billed exactly as agreed. Nobody at the brokerage touches it."""
    h = _builder("L01", "Decatur to Fort Wayne: a load that needs nobody", "2026-08-03",
                 "clean_load", "zero_human_touches")
    load = Load(h, "LD-50001", customer="prairie_ag", carrier="redbird", sell=188000, buy=150000,
                serial="70001", pickup="Prairie Ag Decatur", delivery="Three Rivers Co-op",
                delivery_zone="America/Indiana/Indianapolis")
    n = load.number
    load.book()
    load.track("at-pickup", h.t("10:20"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:05"), "LOADED", "S1")
    load.pings(("13:30", 0), ("16:45", 0), ("20:00", 0), ("23:30", 0), ("03:00", 1), ("06:30", 1))
    load.track("at-delivery", h.t("08:50", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("09:40", 1))
    load.pod("pod", h.t("10:00", 1))
    load.invoice("invoice", h.t("11:00", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("covered", n, stage="DISPATCHED", posture="WAIT", human=False, needs=ARRIVALS,
                   touches=0, next_step="WAIT"),
        checkpoint("loaded", n, stage="IN_TRANSIT", posture="WAIT", needs=ROLLING, overdue=[],
                   changed=["STAGE:IN_TRANSIT"]),
        checkpoint("delivered", n, stage="DELIVERED", posture="NEYMA_CAN_ACT", billing_ready=False,
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")},
                   proposes=["REQUEST_POD"], drafts=1, escalates=[], touches=0,
                   next_step="NEYMA:REQUEST_POD"),
        checkpoint("pod", n, quiet=True, billing_ready=True, carrier_side=[],
                   changed=["BILLING:customer_billing_ready", "QUIET:quiet"]),
        checkpoint("invoice", n, quiet=True, billing_ready=True, carrier_side=[], touches=0),
        checkpoint("end", n, quiet=True, billing_ready=True, posture="QUIET", touches=0, acts=0,
                   overdue=[], next_step="NOTHING"),
    ]})


# ============================================================ L02: the truck is late to the shipper

def l02_late_pickup() -> Any:
    """The pickup window closes at noon and the truck is not there. Nothing arrives to say so: the
    window simply passes. Neyma would ask the carrier. The driver then shows up at 13:30 and the rest
    of the load is ordinary. Nobody at the brokerage decides anything."""
    h = _builder("L02", "Peoria to Dayton: the truck is late to the shipper", "2026-08-04",
                 "late_pickup", "deadline_passes_in_silence")
    load = Load(h, "LD-50002", customer="prairie_ag", carrier="ironwood", sell=205000, buy=162000,
                serial="70002", pickup="Prairie Ag Peoria", delivery="Miami Valley Feed",
                delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.track("at-pickup-late", h.t("13:30"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("14:20"), "LOADED", "S1")
    load.pings(("17:30", 0), ("21:00", 0), ("00:30", 1), ("04:00", 1))
    load.track("at-delivery", h.t("07:40", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("08:30", 1))
    load.pod("pod", h.t("09:10", 1))
    load.invoice("invoice", h.t("10:00", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("covered", n, posture="WAIT", needs=ARRIVALS, overdue=[], touches=0),
        # 13:30 is the first thing to ARRIVE after noon - but the loop looked at 12:01, when the
        # window closed, and by now the late pickup has already been work for an hour and a half.
        checkpoint("at-pickup-late", n, stage="AT_PICKUP", human=False, touches=0,
                   changed=["STAGE:AT_PICKUP"]),
        checkpoint("loaded", n, stage="IN_TRANSIT", posture="WAIT", human=False, overdue=[]),
        checkpoint("pod", n, quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0, carrier_side=[]),
    ]})


def delay(stop_key: str, reason: str) -> dict[str, Any]:
    """The carrier side saying it is running late to a stop. It names no new time the record can
    hold: an ETA is somebody's forecast, and the spine keeps no forecast as a fact."""
    return {"type": "delay", "stop_key": stop_key, "reason": reason}


# ============================================================ L03: late to the receiver

def l03_late_delivery() -> Any:
    """Tracked the whole way and still late: the delivery window closes with the truck two hours
    out. The window passing is the event. The driver then explains, arrives, and the paper follows."""
    h = _builder("L03", "Moline to Cincinnati: the delivery window closes first", "2026-08-05",
                 "late_delivery", "deadline_passes_in_silence", "carrier_reports_delay")
    load = Load(h, "LD-50003", customer="prairie_ag", carrier="summit", sell=241000, buy=200000,
                serial="70003", pickup="Prairie Ag Moline", delivery="Queen City Supply",
                delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.track("at-pickup", h.t("10:15"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:00"), "LOADED", "S1")
    load.pings(("14:00", 0), ("17:30", 0), ("21:00", 0), ("00:30", 1), ("04:00", 1), ("07:30", 1))
    # The window is 09:00-11:00 Eastern on day 1, which is 10:00 Central. Nothing arrives at 10:00.
    load.sms("driver-explains", h.t("10:40", 1), "wreck on 74, crawling. two hours out still",
             delay("S2", "traffic incident"))
    load.track("at-delivery", h.t("12:35", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("13:20", 1))
    load.pod("pod", h.t("13:50", 1))
    load.invoice("invoice", h.t("15:00", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("ping-1-0730", n, stage="IN_TRANSIT", posture="WAIT", overdue=[], touches=0),
        # By the time the driver writes, the window closed 40 minutes ago and the loop already knew.
        checkpoint("driver-explains", n, human=False, overdue=["CARRIER_STATUS_OVERDUE"],
                   touches=0),
        checkpoint("at-delivery", n, human=False, overdue=[], touches=0),
        checkpoint("pod", n, quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0, carrier_side=[]),
    ]})


# ============================================================ L04: the driver goes dark

def l04_driver_goes_dark() -> Any:
    """Loaded, one ping, and then nothing for a day. The cadence passes; then the delivery window
    passes too. It is ONE follow-up the whole time, however many reasons pile up behind it. The
    dispatcher finally writes: the phone died, he delivered on time."""
    h = _builder("L04", "Kankakee to Dayton: the driver goes dark", "2026-08-06",
                 "driver_stops_responding", "tracking_goes_silent", "one_follow_up_many_reasons")
    load = Load(h, "LD-50004", customer="prairie_ag", carrier="bluegrass", sell=169000,
                buy=139000, serial="70004", pickup="Prairie Ag Kankakee",
                delivery="Miami Valley Feed", delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.track("at-pickup", h.t("10:30"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:10"), "LOADED", "S1")
    load.pings(("12:30", 0))
    load.email("dispatcher-explains", h.t("11:30", 1),
               "Hank's phone died yesterday afternoon. He delivered at 9:15 this morning, "
               "paperwork is on its way.", says("DELIVERED", "S2"))
    load.delivered("delivered", h.t("11:45", 1))
    load.pod("pod", h.t("13:00", 1))
    load.invoice("invoice", h.t("14:00", 1))
    h.clock("end", h.t("12:00", 2))
    silent = {"CARRIER_STATUS_OVERDUE": ("OVERDUE", "NEYMA_ACTION_CANDIDATE")}
    return h.build({"work": [
        checkpoint("ping-0-1230", n, stage="IN_TRANSIT", posture="WAIT", needs=ROLLING),
        # Twenty-three hours of nothing. Two deadlines passed in that silence - the cadence, then
        # the receiver's window - and they are one piece of work.
        checkpoint("dispatcher-explains", n, stage="DELIVERED", human=False, touches=0,
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")},
                   proposes=["REQUEST_POD"]),
        checkpoint("pod", n, quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0),
    ], "silence": silent})


# ============================================================ L05: a promise, and then nothing

def l05_promise_missed() -> Any:
    """At the shipper, waiting on a door: "I'll update you by 12:30." Until then it is a wait. At
    12:31, in silence, it is a follow-up. The update comes at 13:15 and the rest is ordinary."""
    h = _builder("L05", "Champaign to Evansville: I'll update you by 12:30", "2026-08-07",
                 "carrier_promises_and_misses", "promise_pending_is_a_wait")
    load = Load(h, "LD-50005", customer="midwest_paper", carrier="redbird", sell=164000,
                buy=131000, serial="70005", pickup="Midwest Paper Champaign",
                delivery="Ohio Valley Print", pickup_window=("09:00", "12:00"))
    n = load.number
    load.book()
    load.sms("check-in", h.t("10:05"), "checked in, waiting on a door. I'll update you by 12:30",
             says("AT_PICKUP", "S1"), promise(h.t("12:30")))
    load.sms("update", h.t("13:15"), "loaded and rolling", says("LOADED", "S1"))
    load.pings(("16:30", 0), ("20:00", 0), ("23:30", 0), ("03:00", 1), ("06:30", 1))
    load.track("at-delivery", h.t("09:10", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("09:55", 1))
    load.pod("pod", h.t("10:20", 1))
    load.invoice("invoice", h.t("11:30", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("check-in", n, stage="AT_PICKUP", posture="WAIT", human=False,
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("CARRIER_UPDATE_PENDING", "PENDING", "WAIT")],
                   due={"CARRIER_UPDATE_PENDING": h.t("12:30")}, overdue=[], touches=0),
        checkpoint("update", n, stage="IN_TRANSIT", posture="WAIT", human=False, overdue=[],
                   touches=0),
        checkpoint("pod", n, quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0),
    ]})


# ============================================================ L06: the ETA keeps moving

def l06_eta_keeps_moving() -> Any:
    """Three messages, three later arrival times, and a receiver's window that closes in the
    middle of them. None of the three forecasts is a fact; the window is."""
    h = _builder("L06", "Rockford to Louisville: 10:30, then noon, then one", "2026-08-08",
                 "carrier_changes_eta_repeatedly", "late_delivery")
    load = Load(h, "LD-50006", customer="midwest_paper", carrier="ironwood", sell=176000,
                buy=143000, serial="70006", pickup="Midwest Paper Rockford",
                delivery="Derby City Cold Storage")
    n = load.number
    load.book()
    load.track("at-pickup", h.t("10:20"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:10"), "LOADED", "S1")
    load.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
    load.sms("eta-1030", h.t("07:30", 1), "running behind, eta 10:30", delay("S2", "behind"))
    load.pings(("08:00", 1))
    load.sms("eta-noon", h.t("09:45", 1), "now looking like noon", delay("S2", "behind"))
    load.sms("eta-one", h.t("11:20", 1), "1pm, sorry", delay("S2", "behind"))
    load.pings(("11:30", 1))
    load.track("at-delivery", h.t("13:10", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("14:00", 1))
    load.pod("pod", h.t("14:30", 1))
    load.invoice("invoice", h.t("15:30", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("eta-1030", n, stage="IN_TRANSIT", human=False, overdue=[], touches=0),
        checkpoint("eta-noon", n, human=False, overdue=[], touches=0),
        # The window closed at 11:00. Twenty minutes later the third forecast arrives.
        checkpoint("eta-one", n, human=False, overdue=["CARRIER_STATUS_OVERDUE"], touches=0),
        checkpoint("at-delivery", n, human=False, overdue=[]),
        checkpoint("pod", n, quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0),
    ]})


# ============================================================ L07: two sources, two stories

def l07_contradictory_tracking() -> Any:
    """The driver texts "delivered". Five minutes later the tracking provider puts the truck on the
    interstate. Neyma does not pick one - and it goes on not picking one after the provider reports
    arrival, the TMS says delivered and a signed POD comes in, because agreeing later is not the
    same as never having disagreed. Dana calls the receiver and says where the load is. That is
    what settles it, and it is the one touch this load costs."""
    h = _builder("L07", "Bloomington to Toledo: delivered, says one of them", "2026-08-09",
                 "contradictory_tracking", "delivery_claimed_against_tracking")
    load = Load(h, "LD-50007", customer="great_lakes_bev", carrier="summit", sell=172000,
                buy=141000, serial="70007", pickup="Great Lakes Beverage Bloomington",
                delivery="Maumee Distributing", delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.track("at-pickup", h.t("10:10"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:00"), "LOADED", "S1")
    load.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
    load.sms("driver-says-delivered", h.t("07:30", 1), "delivered, empty",
             says("DELIVERED", "S2"))
    load.track("provider-says-moving", h.t("07:35", 1), "IN_TRANSIT", position="I-75 N, mile 180")
    load.track("provider-arrives", h.t("08:40", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("09:30", 1))
    load.pod("pod", h.t("10:00", 1))
    load.invoice("invoice", h.t("11:00", 1))
    h.human("dana-confirms", h.t("11:30", 1), "dana.ortiz", "confirm_movement_status",
            refs=load.refs, status="DELIVERED", stop_key="S2",
            note="called the receiver: unloaded and signed for at 8:55")
    h.clock("end", h.t("12:00", 2))
    disputed = {"EVIDENCE_CONFLICT": ("OPEN", "HUMAN_REQUIRED")}
    return h.build({"work": [
        checkpoint("driver-says-delivered", n, stage="DELIVERED", human=False, touches=0),
        checkpoint("provider-says-moving", n, stage="DISPUTED", human=True,
                   escalates=["EVIDENCE_CONFLICT"], reasons={"EVIDENCE_CONFLICT": "TRACKING_STATUS"},
                   billing_ready=False, touches=1, acts=0, next_step="HUMAN:EVIDENCE_CONFLICT"),
        # Everything now agrees - and none of it is a human saying so. Still hers, still not quiet,
        # still not billing-ready, and never silently settled.
        checkpoint("invoice", n, stage="DISPUTED", human=True, needs=disputed, quiet=False,
                   billing_ready=False, touches=1, acts=0),
        checkpoint("dana-confirms", n, stage="DELIVERED", human=False, quiet=True,
                   billing_ready=True, settled={"EVIDENCE_CONFLICT": "RESOLVED"}, touches=1,
                   acts=1, changed=["STAGE:DELIVERED", "CLOSED:EVIDENCE_CONFLICT",
                                    "BILLING:customer_billing_ready", "HUMAN_ACT:human"]),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=1, acts=1, carrier_side=[]),
    ]})


# ============================================================ L08: "loaded", says the driver

def l08_pickup_on_one_word() -> Any:
    """The only thing that says this load was picked up is the driver's text. The tracking provider,
    whose feed is up, shows nothing at the shipper and nothing after. The picture says what it rests
    on. Four hours later, with the provider still silent, that silence is work."""
    h = _builder("L08", "Aurora to Columbus: loaded, on his word alone", "2026-08-10",
                 "pickup_reported_without_supporting_evidence", "single_source_status")
    load = Load(h, "LD-50008", customer="great_lakes_bev", carrier="bluegrass", sell=199000,
                buy=161000, serial="70008", pickup="Great Lakes Beverage Aurora",
                delivery="Scioto Farm Supply", delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.sms("driver-loaded", h.t("11:10"), "loaded, heading out", says("LOADED", "S1"))
    load.track("provider-wakes-up", h.t("16:40"), "IN_TRANSIT", position="I-70 E")
    load.pings(("20:00", 0), ("23:30", 0), ("03:00", 1), ("06:30", 1))
    load.track("at-delivery", h.t("08:30", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("09:20", 1))
    load.pod("pod", h.t("09:50", 1))
    load.invoice("invoice", h.t("11:00", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("driver-loaded", n, stage="IN_TRANSIT", posture="WAIT", human=False,
                   overdue=[], touches=0),
        # 15:10 came and went with the provider silent: the loop asked itself at 15:11.
        checkpoint("provider-wakes-up", n, posture="WAIT", human=False, overdue=[]),
        checkpoint("pod", n, quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0),
    ]})


# ============================================================ L09: delivered, and no paper

def l09_pod_missing_invoice_first() -> Any:
    """Delivered on time. No POD. The carrier's invoice arrives the next morning - before the POD -
    and matches the rate confirmation. The configured day for the POD passes. It turns up the day
    after. Customer billing waits on the paper; the carrier's invoice never did."""
    h = _builder("L09", "Peoria to Indianapolis: the invoice beats the POD", "2026-08-11",
                 "delivery_reported_pod_missing", "carrier_invoice_before_pod", "document_overdue")
    load = Load(h, "LD-50009", customer="midwest_paper", carrier="redbird", sell=158000,
                buy=124000, serial="70009", pickup="Midwest Paper Peoria",
                delivery="Hoosier Distributing", delivery_zone="America/Indiana/Indianapolis")
    n = load.number
    load.book()
    load.track("at-pickup", h.t("10:15"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:00"), "LOADED", "S1")
    load.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
    load.track("at-delivery", h.t("07:50", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("08:40", 1))
    load.invoice("invoice", h.t("09:00", 2))
    load.pod("pod", h.t("10:30", 3))
    h.clock("end", h.t("12:00", 4))
    owed = {"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")}
    late = {"DOCUMENT_REQUIRED": ("OVERDUE", "NEYMA_ACTION_CANDIDATE")}
    return h.build({"work": [
        checkpoint("delivered", n, stage="DELIVERED", needs=owed, billing_ready=False,
                   human=False, proposes=["REQUEST_POD"], overdue=[],
                   due={"DOCUMENT_REQUIRED": h.t("08:40", 2)}),
        # The invoice matches. It opens no work of its own - and it does not make the POD arrive.
        checkpoint("invoice", n, needs=late, billing_ready=False, human=False, carrier_side=[],
                   overdue=["DOCUMENT_REQUIRED"], touches=0),
        checkpoint("pod", n, quiet=True, billing_ready=True, carrier_side=[]),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0),
    ]})


# ============================================================ L10: a POD nobody signed

def l10_pod_unsigned_then_twice() -> Any:
    """The first POD is the driver's copy: no signature. It satisfies nothing, and nobody at the
    brokerage needs to rule on that - it is simply still owed. The signed one arrives, and then
    arrives twice more."""
    h = _builder("L10", "Decatur to Akron: the driver's copy, then the real one, twice",
                 "2026-08-12", "unsigned_pod", "duplicate_pod")
    load = Load(h, "LD-50010", customer="great_lakes_bev", carrier="ironwood", sell=203000,
                buy=166000, serial="70010", pickup="Great Lakes Beverage Decatur",
                delivery="Summit County Beverage", delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.track("at-pickup", h.t("10:20"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:05"), "LOADED", "S1")
    load.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
    load.track("at-delivery", h.t("07:45", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("08:30", 1))
    load.pod("pod-unsigned", h.t("09:00", 1), signed=False, note="(driver copy)")
    load.pod("pod-signed", h.t("13:00", 1))
    h.redeliver("pod-signed-again", h.t("13:05", 1))
    h.document("pod-forwarded", h.t("13:20", 1), "POD",
               f"PROOF OF DELIVERY | load {n} | received in good order ", refs=load.refs,
               via=NORTHLINE_OPS, signed=True)
    load.invoice("invoice", h.t("15:00", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("pod-unsigned", n, billing_ready=False, human=False,
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")},
                   reasons={"DOCUMENT_REQUIRED": "DOCUMENT_RECEIVED_UNUSABLE"},
                   proposes=["REQUEST_POD"], touches=0),
        checkpoint("pod-signed", n, quiet=True, billing_ready=True,
                   settled={"DOCUMENT_REQUIRED": "SATISFIED"}),
        checkpoint("pod-signed-again", n, quiet=True, billing_ready=True),
        checkpoint("pod-forwarded", n, quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0, carrier_side=[]),
    ]})


# ============================================================ L11: half a POD, then all of it

def l11_pod_corrected() -> Any:
    """Page one of two arrives. Half a POD proves nothing and is still owed. The carrier re-sends
    the whole document."""
    h = _builder("L11", "Galesburg to Erie: page one of two", "2026-08-13", "corrected_pod",
                 "incomplete_document")
    load = Load(h, "LD-50011", customer="midwest_paper", carrier="bluegrass", sell=254000,
                buy=200000, serial="70011", pickup="Midwest Paper Galesburg",
                delivery="Lakeshore Print", delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.run_to_delivery()
    load.pod("pod-page-one", h.t("09:30", 1), pages=(1, 2), note="(page 1 of 2)")
    load.pod("pod-complete", h.t("11:15", 1), pages=(2, 2), note="(pages 1-2)")
    load.invoice("invoice", h.t("13:00", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("pod-page-one", n, billing_ready=False, human=False, quiet=False,
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")},
                   reasons={"DOCUMENT_REQUIRED": "DOCUMENT_RECEIVED_UNUSABLE"},
                   proposes=["REQUEST_POD"], touches=0),
        checkpoint("pod-complete", n, quiet=True, billing_ready=True,
                   settled={"DOCUMENT_REQUIRED": "SATISFIED"}),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0, carrier_side=[]),
    ]})


# ============================================================ L12: the POD on the wrong load

def l12_pod_on_the_wrong_load() -> Any:
    """Two loads, same shipper, same carrier, same morning. The carrier sends ONE POD and types the
    other load's number on it. Neyma binds it where it says - exactly, to the wrong load. So one load
    looks finished that is not, and the other waits for paper that already came. Priya reads the
    consignee stamp and moves it. The work moves with it."""
    h = _builder("L12", "Springfield: one POD, two loads, the wrong number", "2026-08-14",
                 "pod_attached_to_wrong_load", "binding_corrected_by_human")
    first = Load(h, "LD-50012", customer="midwest_paper", carrier="redbird", sell=128000,
                 buy=101000, serial="70012", pickup="Midwest Paper Springfield",
                 delivery="Capitol Print One", tag="-a")
    second = Load(h, "LD-50013", customer="midwest_paper", carrier="redbird", sell=131000,
                  buy=104000, serial="70013", pickup="Midwest Paper Springfield",
                  delivery="Capitol Print Two", tag="-b")
    first.book("07:30", "08:00", "08:20")
    second.book("07:35", "08:05", "08:25")
    first.run_to_delivery(at_pickup="10:10", loaded="10:50", at_delivery="08:00",
                          delivered="08:40")
    second.run_to_delivery(at_pickup="10:15", loaded="10:55", at_delivery="08:20",
                           delivered="09:00")
    # The paper is for LD-50013 (Capitol Print Two). The carrier typed LD-50012.
    _pod(h, "pod-misnumbered", h.t("10:00", 1), load=first.number, via=NORTHLINE_PODS,
         note="consignee stamp Capitol Print Two")
    misnumbered = h.records[-1].external_id
    h.human("priya-moves-pod", h.t("15:00", 1), "priya.nair", "correct_binding",
            refs=second.refs, target={"source_system": NORTHLINE_PODS, "external_id": misnumbered},
            note="the consignee stamp is Capitol Print Two, which is LD-50013")
    first.pod("pod-for-first", h.t("16:00", 1))
    first.invoice("invoice-a", h.t("17:00", 1))
    second.invoice("invoice-b", h.t("17:05", 1))
    h.clock("end", h.t("12:00", 2))
    _in_arrival_order(h)
    owed = {"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")}
    return h.build({"work": [
        # Bound exactly where it says. Neyma has no way to know: the number is the number.
        checkpoint("pod-misnumbered", first.number, quiet=True, billing_ready=True, touches=0),
        checkpoint("pod-misnumbered", second.number, needs=owed, billing_ready=False,
                   human=False, touches=0),
        # Her act moves the paper, and the work with it: the first load owes a POD again.
        checkpoint("priya-moves-pod", second.number, quiet=True, billing_ready=True, acts=1,
                   touches=1, settled={"DOCUMENT_REQUIRED": "SATISFIED"}),
        checkpoint("priya-moves-pod", first.number, needs=owed, billing_ready=False, quiet=False,
                   human=False, changed=["BILLING:customer_billing_ready", "QUIET:quiet"]),
        checkpoint("pod-for-first", first.number, quiet=True, billing_ready=True),
        checkpoint("end", first.number, quiet=True, billing_ready=True, carrier_side=[]),
        checkpoint("end", second.number, quiet=True, billing_ready=True, touches=1, acts=1),
    ]})


# ============================================================ L13/L14: one number, two brokerages

def _twin(h: HistoryBuilder, *, ops: str, pods: str) -> Load:
    """Load LD-50014 - same number, PO, BOL, PRO, carrier, rate confirmation and invoice number -
    at whichever brokerage `h` belongs to."""
    load = Load(h, "LD-50014", customer="cedar_building", carrier="ironwood", sell=210000,
                buy=170000, serial="70014", pickup="Ozark Building Supply",
                delivery="Bluff City Lumber", ops=ops, pods=pods)
    load.book()
    return load


def l13_the_same_number_at_cedar_ridge() -> Any:
    """Cedar Ridge's LD-50014. No tracking feed, no cadence, no deadline configured for the POD:
    Cedar Ridge gets no clock nobody chose. It runs clean."""
    h = _builder("L13", "Cedar Ridge LD-50014: the same number, next door", "2026-08-15",
                 "same_load_number_in_another_tenant", tenant=CEDAR)
    load = _twin(h, ops=CEDAR_OPS, pods=CEDAR_OPS)
    n = load.number
    h.message("driver-loaded", h.t("11:00"), channel="email", source_system=CEDAR_OPS,
              sender=dispatcher("ironwood"), thread="re-ld-50014", subject="RE: LD-50014",
              body="Loaded and rolling.", refs=load.refs, asserts=(says("LOADED", "S1"),))
    load.delivered("delivered", h.t("09:00", 1))
    load.pod("pod", h.t("09:30", 1))
    load.invoice("invoice", h.t("10:30", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("pod", n, billing_ready=True, human=False, touches=0),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0, carrier_side=[]),
    ]})


def l14_the_twin_at_northline() -> Any:
    """Northline's LD-50014, the same day. Its POD never comes. Cedar Ridge's did - and that is
    Cedar Ridge's paper, in Cedar Ridge's inbox, and it satisfies nothing here."""
    h = _builder("L14", "Northline LD-50014: the twin whose POD never came", "2026-08-15",
                 "same_load_number_in_another_tenant", "pod_missing")
    load = _twin(h, ops=NORTHLINE_OPS, pods=NORTHLINE_PODS)
    n = load.number
    load.run_to_delivery()
    load.invoice("invoice", h.t("10:45", 1))
    h.clock("end", h.t("12:00", 3))
    return h.build({"work": [
        checkpoint("invoice", n, billing_ready=False, human=False, carrier_side=[],
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")}, touches=0),
        checkpoint("end", n, billing_ready=False, quiet=False, human=False,
                   needs={"DOCUMENT_REQUIRED": ("OVERDUE", "NEYMA_ACTION_CANDIDATE")},
                   overdue=["DOCUMENT_REQUIRED"], proposes=["REQUEST_POD"], touches=0, acts=0),
    ]})


# ============================================================ L15: the receiver moved it

def l15_appointment_changed() -> Any:
    """Confirmed for 9 to 11. The carrier writes that the receiver pushed them to 2. A carrier's
    sentence does not move an appointment: Dana calls the receiver, and her word does. The watch
    moves with it, and a truck that arrives at 2:20 is on time."""
    h = _builder("L15", "Rockford to Louisville: the receiver pushed us to two", "2026-08-16",
                 "appointment_time_changed", "conflict_resolved_by_a_human")
    zone = "America/Kentucky/Louisville"
    load = Load(h, "LD-50015", customer="midwest_paper", carrier="ironwood", sell=176000,
                buy=143000, serial="70015", pickup="Midwest Paper Rockford",
                delivery="Derby City Cold Storage", delivery_zone=zone)
    n = load.number
    load.book()
    load.track("at-pickup", h.t("10:20"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:05"), "LOADED", "S1")
    load.pings(("14:30", 0))
    load.email("receiver-pushed", h.t("15:00"), "Receiver pushed us to 2 tomorrow.",
               states_appointment("S2", h.local("14:00", 1), h.local("14:00", 1), zone))
    h.human("dana-confirms-window", h.t("15:40"), "dana.ortiz", "confirm_appointment",
            refs=load.refs, stop_key="S2", window_start_local=h.local("14:00", 1),
            window_end_local=h.local("16:00", 1), timezone=zone,
            note="receiver confirmed by phone: 2 to 4")
    load.pings(("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1), ("08:00", 1),
               ("11:30", 1))
    load.track("at-delivery", h.t("13:20", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("14:10", 1))
    load.pod("pod", h.t("14:40", 1))
    load.invoice("invoice", h.t("16:00", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("receiver-pushed", n, posture="HUMAN_ATTENTION", human=True, touches=1,
                   acts=0, escalates=["EVIDENCE_CONFLICT"],
                   reasons={"EVIDENCE_CONFLICT": "APPOINTMENT_WINDOW"}),
        checkpoint("dana-confirms-window", n, posture="WAIT", human=False, touches=1, acts=1,
                   settled={"EVIDENCE_CONFLICT": "RESOLVED"},
                   due={"ARRIVAL_PENDING": h.t("16:00", 1, zone)}),
        # 11:00 passed with the truck still rolling. It was not late: the appointment had moved.
        checkpoint("ping-1-1130", n, posture="WAIT", human=False, overdue=[]),
        checkpoint("at-delivery", n, human=False, overdue=[]),
        checkpoint("pod", n, quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=1, acts=1, carrier_side=[]),
    ]})


# ============================================================ L16: nobody confirmed the appointment

def l16_appointment_unconfirmed() -> Any:
    """Both appointments were requested and neither was confirmed. That is work from the moment a
    carrier is on the load: Neyma would verify them. The shipper's portal confirms the pickup. The
    delivery is never confirmed by anyone - and stops being a question when the truck is there."""
    h = _builder("L16", "Pekin to Akron: requested, never confirmed", "2026-08-17",
                 "appointment_unconfirmed")
    load = Load(h, "LD-50016", customer="great_lakes_bev", carrier="summit", sell=203000,
                buy=166000, serial="70016", pickup="Great Lakes Beverage Pekin",
                delivery="Summit County Beverage", delivery_zone="America/New_York",
                pickup_status="REQUESTED", delivery_status="REQUESTED")
    n = load.number
    load.book()
    h.appointment("pickup-confirmed", h.t("08:45"), "S1", h.local("10:00"), h.local("12:00"),
                  "America/Chicago", refs=load.refs)
    load.run_to_delivery()
    load.pod("pod", h.t("09:20", 1))
    load.invoice("invoice", h.t("10:30", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("covered", n, posture="NEYMA_CAN_ACT", human=False, touches=0,
                   proposes=["VERIFY_APPOINTMENT"], drafts=1,
                   reasons={"APPOINTMENT_UNCONFIRMED": ["APPOINTMENT_NOT_CONFIRMED:S1",
                                                        "APPOINTMENT_NOT_CONFIRMED:S2"]}),
        checkpoint("pickup-confirmed", n, posture="NEYMA_CAN_ACT", human=False,
                   proposes=["VERIFY_APPOINTMENT"],
                   reasons={"APPOINTMENT_UNCONFIRMED": "APPOINTMENT_NOT_CONFIRMED:S2"}),
        checkpoint("delivered", n, human=False,
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")}),
        checkpoint("pod", n, quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0),
    ]})


# ============================================================ L17: the invoice is wrong

def l17_invoice_wrong_amount() -> Any:
    """Delivered, signed for, billing-ready - and the carrier's invoice is for more than the rate
    confirmation says. Customer billing does not wait on that. The carrier's money does: a named
    human is asked which figure is owed, nothing is adjusted, and the load is not quiet."""
    h = _builder("L17", "Normal to Lima: the invoice says more than the rate confirmation",
                 "2026-08-18", "carrier_invoice_wrong_amount", "billing_ready_is_not_closed")
    load = Load(h, "LD-50017", customer="prairie_ag", carrier="ironwood", sell=181000, buy=143000,
                serial="70017", pickup="Prairie Ag Normal", delivery="Allen County Feed",
                delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.run_to_delivery()
    load.pod("pod", h.t("09:20", 1))
    load.invoice("invoice-overbilled", h.t("10:30", 1), linehaul=151000)
    h.clock("end", h.t("12:00", 3))
    wrong = {"INVOICE_DISCREPANCY": ("OPEN", "HUMAN_REQUIRED")}
    return h.build({"work": [
        checkpoint("pod", n, quiet=True, billing_ready=True, carrier_side=[], touches=0),
        checkpoint("invoice-overbilled", n, posture="HUMAN_ATTENTION", human=True, needs=wrong,
                   billing_ready=True, quiet=False, carrier_side=["INVOICE_DISCREPANCY"],
                   reasons={"INVOICE_DISCREPANCY": "LINEHAUL_MISMATCH"},
                   escalates=["INVOICE_DISCREPANCY"], touches=1, acts=0,
                   changed=["OPENED:INVOICE_DISCREPANCY", "QUIET:quiet"]),
        # Two days on, nobody has decided. It is still hers, still open, still not quiet.
        checkpoint("end", n, human=True, needs=wrong, billing_ready=True, quiet=False,
                   carrier_side=["INVOICE_DISCREPANCY"], touches=1, acts=0),
    ]})


# ============================================================ L18: whose invoice is this

def l18_invoice_unattributed() -> Any:
    """The invoice prints no MC. It is on the right load and on no movement: nothing is compared
    against it, and nobody is paid on a guess. Marcus says which movement it bills. Then it is
    compared, and it matches."""
    h = _builder("L18", "Peoria to Dayton: an invoice that names no carrier", "2026-08-19",
                 "carrier_invoice_unattributed", "attribution_by_human")
    load = Load(h, "LD-50018", customer="prairie_ag", carrier="bluegrass", sell=205000,
                buy=162000, serial="70018", pickup="Prairie Ag Peoria",
                delivery="Miami Valley Feed", delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.run_to_delivery()
    load.pod("pod", h.t("09:20", 1))
    invoice = load.invoice("invoice-no-mc", h.t("10:30", 1), mc=None)
    h.human("marcus-places-it", h.t("13:00", 1), "marcus.reid", "attribute_carrier_invoice",
            refs=load.refs, movement_key="M1",
            target={"source_system": NORTHLINE_OPS, "external_id": invoice},
            note="Bluegrass's invoice for this load; their template prints no MC")
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("invoice-no-mc", n, posture="HUMAN_ATTENTION", human=True, billing_ready=True,
                   quiet=False, needs={"INVOICE_UNATTRIBUTED": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"INVOICE_UNATTRIBUTED": "CARRIER_NOT_STATED"},
                   carrier_side=["INVOICE_UNATTRIBUTED"], touches=1, acts=0),
        checkpoint("marcus-places-it", n, quiet=True, billing_ready=True, human=False,
                   settled={"INVOICE_UNATTRIBUTED": "RESOLVED"}, carrier_side=[], touches=1,
                   acts=1),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=1, acts=1),
    ]})


# ============================================================ L19: detention nobody agreed to

def l19_accessorial_unsupported() -> Any:
    """The dispatcher texts that the shipper held the truck and they will need detention. Nobody at
    the brokerage has agreed to anything. The invoice then bills it, and the carrier adds that Mike
    approved it. A claimed approval is a reason to look harder. Marcus says no."""
    h = _builder("L19", "Moline to Cincinnati: detention, per approval from Mike", "2026-08-20",
                 "accessorial_unsupported", "counterparty_asserts_approval", "human_denies")
    load = Load(h, "LD-50019", customer="prairie_ag", carrier="summit", sell=241000, buy=200000,
                serial="70019", pickup="Prairie Ag Moline", delivery="Queen City Supply",
                delivery_zone="America/New_York")
    n = load.number
    load.book()
    load.track("at-pickup", h.t("10:20"), "AT_PICKUP", "S1")
    load.sms("detention-claim", h.t("13:40"), "shipper held him 3 hrs, we'll need detention 150",
             claims("DETENTION", 15000), who="dispatcher")
    load.track("loaded", h.t("13:45"), "LOADED", "S1")
    load.pings(("17:00", 0), ("20:30", 0), ("00:00", 1), ("03:30", 1), ("07:00", 1))
    load.track("at-delivery", h.t("09:30", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("10:15", 1))
    load.pod("pod", h.t("10:40", 1))
    load.invoice("invoice", h.t("12:00", 1), accessorials={"DETENTION": 15000})
    load.email("mike-approved", h.t("12:30", 1),
               "Invoice attached. Detention is included per approval from Mike.",
               claims("DETENTION", 15000, approved=True))
    h.human("marcus-denies", h.t("14:00", 1), "marcus.reid", "deny_accessorial", refs=load.refs,
            charge_type="DETENTION", note="nobody here approved detention on this load")
    h.clock("end", h.t("12:00", 3))
    return h.build({"work": [
        checkpoint("detention-claim", n, human=True, escalates=["ACCESSORIAL_UNAUTHORIZED"],
                   reasons={"ACCESSORIAL_UNAUTHORIZED": "CLAIMED_NOT_AUTHORIZED"},
                   carrier_side=["ACCESSORIAL_UNAUTHORIZED"], touches=1, acts=0),
        checkpoint("pod", n, billing_ready=True, human=True, quiet=False,
                   carrier_side=["ACCESSORIAL_UNAUTHORIZED"]),
        checkpoint("mike-approved", n, human=True, billing_ready=True,
                   reasons={"ACCESSORIAL_UNAUTHORIZED": "COUNTERPARTY_CLAIMS_APPROVAL"}),
        # His no settles the accessorial. The invoice still bills it: that is the open question.
        checkpoint("marcus-denies", n, human=True, billing_ready=True, quiet=False, acts=1,
                   settled={"ACCESSORIAL_UNAUTHORIZED": "RESOLVED"},
                   needs={"INVOICE_DISCREPANCY": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"INVOICE_DISCREPANCY": "ACCESSORIAL_DENIED_BUT_BILLED:DETENTION"},
                   carrier_side=["INVOICE_DISCREPANCY"], touches=2),
        checkpoint("end", n, human=True, billing_ready=True, quiet=False, touches=2, acts=1),
    ]})


# ============================================================ L20: the TMS had the wrong carrier

def l20_system_of_record_corrected() -> Any:
    """The TMS row names the wrong carrier. The right carrier's invoice fits no movement of the
    load, so a human is asked. Before she answers, the system of record is corrected - and that,
    not a guess and not her act, is what places the invoice. The question goes away unanswered."""
    h = _builder("L20", "Pekin to Akron: the TMS named the wrong carrier", "2026-08-21",
                 "correction_after_a_prior_interpretation", "attribution_by_system_of_record")
    load = Load(h, "LD-50020", customer="great_lakes_bev", carrier="ironwood", sell=203000,
                buy=166000, serial="70020", pickup="Great Lakes Beverage Pekin",
                delivery="Summit County Beverage", delivery_zone="America/New_York")
    n, wrong, right = load.number, CARRIERS["redbird"], load.carrier
    h.tms("tender", h.t("07:30"), load=n, status="TENDERED", version=1, customer=load.customer,
          po=load.po, bol=load.bol, sell=charges(load.sell), stops=load.stops)
    h.tms("covered-wrong-carrier", h.t("08:00"), load=n, status="COVERED", version=2,
          customer=load.customer, po=load.po, bol=load.bol, sell=charges(load.sell),
          stops=load.stops, movements=(movement("M1", wrong),))
    _rate_con(h, "rate-con", h.t("08:20"), load=n, number="RC-50020", carrier="ironwood",
              linehaul=load.buy, via=NORTHLINE_OPS)
    load.track("at-pickup", h.t("10:20"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:05"), "LOADED", "S1")
    load.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
    load.track("at-delivery", h.t("08:10", 1), "AT_DELIVERY", "S2")
    h.tms("delivered", h.t("08:55", 1), load=n, status="DELIVERED", version=3,
          customer=load.customer, po=load.po, bol=load.bol, sell=charges(load.sell),
          stops=load.stops, movements=(movement("M1", wrong, status="DELIVERED"),))
    load.pod("pod", h.t("09:20", 1))
    load.invoice("invoice", h.t("10:30", 1))
    h.tms("carrier-corrected", h.t("13:00", 1), load=n, status="DELIVERED", version=4,
          customer=load.customer, po=load.po, bol=load.bol, sell=charges(load.sell),
          stops=load.stops, movements=(movement("M1", right, status="DELIVERED"),))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("invoice", n, posture="HUMAN_ATTENTION", human=True, billing_ready=True,
                   needs={"INVOICE_UNATTRIBUTED": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"INVOICE_UNATTRIBUTED": "CARRIER_NOT_ON_LOAD"}, touches=1, acts=0),
        checkpoint("carrier-corrected", n, quiet=True, billing_ready=True, human=False,
                   settled={"INVOICE_UNATTRIBUTED": "SATISFIED"}, touches=0, acts=0,
                   carrier_side=[]),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0),
    ]})


# ============================================================ L21: the inbox, in the wrong order

def l21_out_of_order_and_twice() -> Any:
    """Nothing is wrong with this load except the order things arrived in. The invoice beats the
    rate confirmation. The POD beats the news that it delivered. A stale ping lands after delivery.
    And the carrier's mail server sends everything twice."""
    h = _builder("L21", "Decatur to Dayton: everything out of order, some of it twice",
                 "2026-08-22", "reordered_observations", "duplicated_inbound_messages",
                 "stale_news_after_delivery")
    load = Load(h, "LD-50021", customer="prairie_ag", carrier="redbird", sell=188000, buy=150000,
                serial="70021", pickup="Prairie Ag Decatur", delivery="Miami Valley Feed",
                delivery_zone="America/New_York")
    n = load.number
    h.tms("tender", h.t("07:30"), load=n, status="TENDERED", version=1, customer=load.customer,
          po=load.po, bol=load.bol, sell=charges(load.sell), stops=load.stops)
    h.tms("covered", h.t("08:00"), load=n, status="COVERED", version=2, customer=load.customer,
          po=load.po, bol=load.bol, sell=charges(load.sell), stops=load.stops,
          movements=(movement("M1", load.carrier, pro=load.pro),))
    load.track("at-pickup", h.t("10:20"), "AT_PICKUP", "S1")
    load.sms("driver-loaded", h.t("11:05"), "loaded and rolling", says("LOADED", "S1"))
    h.redeliver("driver-loaded-again", h.t("11:06"))
    load.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
    # The paper outruns the status: a signed POD at 08:20, the TMS says delivered at 08:55.
    load.pod("pod-early", h.t("08:20", 1))
    h.redeliver("pod-early-again", h.t("08:21", 1))
    load.delivered("delivered", h.t("08:55", 1))
    # The invoice, and only then the rate confirmation it is to be compared against.
    load.invoice("invoice-before-rate-con", h.t("09:30", 1))
    h.redeliver("invoice-again", h.t("09:31", 1))
    _rate_con(h, "rate-con-late", h.t("10:15", 1), load=n, number="RC-50021", carrier="redbird",
              linehaul=load.buy, via=NORTHLINE_OPS)
    # A ping from 07:00 that the provider delivers at 10:40.
    h.track("stale-ping", h.t("10:40", 1), "IN_TRANSIT", refs=load.refs, position="I-70 E",
            as_of=h.t("07:00", 1))
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("driver-loaded-again", n, stage="IN_TRANSIT", posture="WAIT", human=False),
        checkpoint("delivered", n, stage="DELIVERED", quiet=True, billing_ready=True, touches=0),
        checkpoint("rate-con-late", n, quiet=True, billing_ready=True, carrier_side=[], touches=0),
        checkpoint("stale-ping", n, stage="DELIVERED", quiet=True, billing_ready=True),
        checkpoint("end", n, quiet=True, billing_ready=True, touches=0, acts=0, carrier_side=[]),
    ]})


LOOP_HISTORY_FACTORIES = (
    l01_clean, l02_late_pickup, l03_late_delivery, l04_driver_goes_dark, l05_promise_missed,
    l06_eta_keeps_moving, l07_contradictory_tracking, l08_pickup_on_one_word,
    l09_pod_missing_invoice_first, l10_pod_unsigned_then_twice, l11_pod_corrected,
    l12_pod_on_the_wrong_load, l13_the_same_number_at_cedar_ridge, l14_the_twin_at_northline,
    l15_appointment_changed, l16_appointment_unconfirmed, l17_invoice_wrong_amount,
    l18_invoice_unattributed, l19_accessorial_unsupported, l20_system_of_record_corrected,
    l21_out_of_order_and_twice,
)


def build_loop_histories() -> list[Any]:
    """Each history built fresh. Within a brokerage the order is chronological."""
    return [factory() for factory in LOOP_HISTORY_FACTORIES]


__all__ = ["LOOP_HISTORY_FACTORIES", "LOOP_SETUPS", "Load", "build_loop_histories"]
