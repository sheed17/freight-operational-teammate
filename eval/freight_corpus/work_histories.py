"""Load histories written to be evaluated THROUGH TIME: what work remains on this load right now?

The twenty hostile histories assert what Neyma concluded at the END of a load. These assert what it
should say at chosen moments ALONG the way — after a record arrives, and after time passes with
nothing arriving at all — so that operational work is seen to OPEN and to CLOSE.

A history's `expected["work"]` is an ordered list of checkpoints. Each names the record it is taken
after, the load, and only what it LABELS: the stage, the posture, the open needs as
`{kind: (status, handling)}`, which shadow actions are offered, whether a human is needed, and
whether the load is billing-ready. An unlabeled attribute is measured, never graded.

They run in their OWN database. Northline here is the corpus brokerage with ONE added piece of its
own configuration — a tracking-update cadence — because no cadence is ever assumed.

SYNTHETIC. Every company, person, number and sentence here is invented development input. Nothing in
this file is a design-partner observation and no freight rule is validated by it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from freight_recon.freight_domain.history import TenantSetup

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
    SETUPS,
    dispatcher,
    driver,
)

#: Northline's own tracking cadence for these histories: a moving truck is expected to be heard from
#: at least this often. Tenant CONFIGURATION — the corpus default configures none, so none is assumed.
TRACKING_CADENCE_MINUTES = 240

WORK_SETUPS: dict[str, TenantSetup] = {
    **SETUPS,
    NORTHLINE: replace(SETUPS[NORTHLINE], tracking_update_cadence_minutes=TRACKING_CADENCE_MINUTES),
}


def checkpoint(after: str, load: str, **labels: Any) -> dict[str, Any]:
    """One labeled moment: the work on `load` just after the record labeled `after` arrived."""
    return {"after": after, "load": load, **labels}


def _invoice_as(h: HistoryBuilder, label: str, at: str, *, load: str, number: str, carrier: str,
                linehaul: int, via: str, mc: str | None, movement_key: str | None = None,
                accessorials: dict[str, int] | None = None, rendition: str = "a") -> str:
    """A carrier invoice whose printed MC is whatever `mc` says — the registered one, another
    spelling of it, or none at all."""
    total = linehaul + sum((accessorials or {}).values())
    h.document(label, at, "CARRIER_INVOICE",
               f"INVOICE {number} rendition {rendition} | {CARRIERS[carrier]['name']} "
               f"{mc or '(no MC printed)'} | load {load} | linehaul {linehaul} | "
               f"{accessorials or {}} | total {total}",
               refs=(load_ref(load),), via=via, external_id=f"<invoice-{number}-{rendition}>",
               extracted={"invoice_number": number, "carrier_mc": mc,
                          "movement_key": movement_key,
                          **charges(linehaul, 0, accessorials, total=total)})
    return f"<invoice-{number}-{rendition}>"


def _covered(h: HistoryBuilder, *, load: str, customer: str, carrier: str, po: str, bol: str,
             pro: str, sell: int, stops: tuple[dict[str, Any], ...], at: tuple[str, str],
             ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Tender then cover: the two TMS rows every one-carrier load starts with."""
    buyer, mover = CUSTOMERS[customer], CARRIERS[carrier]
    h.tms("tender", h.t(at[0]), load=load, status="TENDERED", version=1, customer=buyer, po=po,
          bol=bol, sell=charges(sell), stops=stops)
    h.tms("covered", h.t(at[1]), load=load, status="COVERED", version=2, customer=buyer, po=po,
          bol=bol, sell=charges(sell), stops=stops, movements=(movement("M1", mover, pro=pro),))
    return buyer, mover


def _delivered(h: HistoryBuilder, label: str, at: str, *, load: str, customer: dict[str, Any],
               carrier: dict[str, Any], po: str, bol: str, pro: str, sell: int,
               stops: tuple[dict[str, Any], ...], version: int = 3) -> None:
    h.tms(label, at, load=load, status="DELIVERED", version=version, customer=customer, po=po,
          bol=bol, sell=charges(sell), stops=stops,
          movements=(movement("M1", carrier, pro=pro, status="DELIVERED"),))


# ============================================================ P9-D23: the invoice nobody can place

def w01_invoice_without_a_carrier() -> Any:
    """An invoice that prints no MC, overbilled, on a one-carrier load. It is bound to the load by
    its exact load number, and it must not be invisible: nothing reconciles, nothing is payable, and
    a named human is asked which movement it bills. Her answer is what closes it."""
    h = HistoryBuilder("W01", "Peoria to Dayton: an invoice that names no carrier", NORTHLINE,
                       day="2026-06-01", zone="America/Chicago",
                       hostile=("invoice_unattributed", "carrier_mc_omitted",
                                "attribution_corrected_by_human"))
    load = "LD-49001"
    stops = _stops(h, pickup="Prairie Ag Peoria", delivery="Miami Valley Feed",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    customer, carrier = _covered(h, load=load, customer="prairie_ag", carrier="ironwood",
                                 po="PO-2301", bol="BOL-56001", pro="PRO-60001", sell=205000,
                                 stops=stops, at=("08:00", "08:40"))
    _rate_con(h, "rate-con", h.t("09:00"), load=load, number="RC-49001", carrier="ironwood",
              linehaul=162000, via=NORTHLINE_OPS)
    _delivered(h, "delivered", h.t("10:30", 1), load=load, customer=customer, carrier=carrier,
               po="PO-2301", bol="BOL-56001", pro="PRO-60001", sell=205000, stops=stops)
    _pod(h, "pod", h.t("10:45", 1), load=load, via=NORTHLINE_PODS)
    invoice = _invoice_as(h, "invoice-no-mc", h.t("13:00", 1), load=load, number="IW-9001",
                          carrier="ironwood", linehaul=1162000, via=NORTHLINE_OPS, mc=None)
    h.clock("a-day-later", h.t("13:00", 2))
    h.human("attributed", h.t("14:00", 2), "marcus.reid", "attribute_carrier_invoice",
            refs=(load_ref(load),), movement_key="M1",
            target={"source_system": NORTHLINE_OPS, "external_id": invoice},
            note="Ironwood's invoice for this load; their template prints no MC")
    return h.build({"work": [
        checkpoint("pod", load, stage="DELIVERED", needs={}, human=False, billing_ready=True),
        checkpoint("invoice-no-mc", load,
                   needs={"INVOICE_UNATTRIBUTED": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"INVOICE_UNATTRIBUTED": "CARRIER_NOT_STATED"},
                   actions={"INVOICE_UNATTRIBUTED": ["ASK_HUMAN_RESOLVE_IDENTITY"]},
                   human=True, posture="HUMAN_ATTENTION"),
        checkpoint("a-day-later", load,
                   needs={"INVOICE_UNATTRIBUTED": ("OPEN", "HUMAN_REQUIRED")}, human=True),
        # Placed, the invoice is finally COMPARED - and it does not match. New, correct work.
        checkpoint("attributed", load,
                   needs={"INVOICE_DISCREPANCY": ("OPEN", "HUMAN_REQUIRED")},
                   settled={"INVOICE_UNATTRIBUTED": "RESOLVED"}, human=True),
    ]})


def promise(due_by: str, kind: str = "status_update") -> dict[str, Any]:
    """A structured promise to follow up, saying what it is ABOUT. `kind` is what a reader would
    have reported: status_update, send_document, call_back, or other when the words do not say."""
    return {"type": "commitment", "commitment_kind": kind, "due_by": due_by,
            "in_quoted_text": False}


def _pings(h: HistoryBuilder, load: str, *times: tuple[str, int]) -> None:
    """In-transit position pings at `(clock, day)`, each inside the brokerage's cadence."""
    for clock, day in times:
        h.track(f"ping-{day}-{clock.replace(':', '')}", h.t(clock, day), "IN_TRANSIT",
                refs=(load_ref(load),), position="I-74")


# ============================================================ a load that needs nothing

def w02_clean_load() -> Any:
    """Booked, picked up, tracked inside the cadence, delivered, signed for, billed as agreed. At
    every moment the answer is a wait or nothing at all, and at the end it is nothing at all."""
    h = HistoryBuilder("W02", "Decatur to Fort Wayne: a load that never needs anyone", NORTHLINE,
                       day="2026-06-05", zone="America/Chicago",
                       hostile=("healthy_load_stays_quiet", "billing_ready_is_zero_work"))
    load, refs = "LD-49002", (load_ref("LD-49002"),)
    stops = _stops(h, pickup="Prairie Ag Decatur", delivery="Three Rivers Co-op",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   delivery_zone="America/Indiana/Indianapolis")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    customer, carrier = _covered(h, load=load, customer="prairie_ag", carrier="redbird",
                                 po="PO-2302", bol="BOL-56002", pro="PRO-60002", sell=188000,
                                 stops=stops, at=("07:30", "08:10"))
    _rate_con(h, "rate-con", h.t("08:30"), load=load, number="RC-49002", carrier="redbird",
              linehaul=150000, via=NORTHLINE_OPS)
    h.track("at-pickup", h.t("10:20"), "AT_PICKUP", refs=refs, stop_key="S1")
    h.track("loaded", h.t("11:05"), "LOADED", refs=refs, stop_key="S1")
    _pings(h, load, ("13:30", 0), ("16:45", 0), ("20:00", 0), ("23:30", 0), ("03:00", 1),
           ("06:30", 1))
    h.track("at-delivery", h.t("08:50", 1), "AT_DELIVERY", refs=refs, stop_key="S2")
    _delivered(h, "delivered", h.t("09:40", 1), load=load, customer=customer, carrier=carrier,
               po="PO-2302", bol="BOL-56002", pro="PRO-60002", sell=188000, stops=stops)
    _pod(h, "pod", h.t("10:00", 1), load=load, via=NORTHLINE_PODS)
    _invoice_as(h, "invoice", h.t("11:00", 1), load=load, number="RB-9002", carrier="redbird",
                linehaul=150000, via=NORTHLINE_OPS, mc=CARRIERS["redbird"]["mc"])
    h.clock("end", h.t("12:00", 2))
    return h.build({"work": [
        checkpoint("tender", load, stage="PLANNING", posture="WAIT", human=False),
        checkpoint("covered", load, stage="DISPATCHED", posture="WAIT", human=False,
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC")],
                   next_action="WAIT"),
        checkpoint("loaded", load, stage="IN_TRANSIT", posture="WAIT",
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("TRACKING_UPDATE_PENDING", "PENDING", "DETERMINISTIC")]),
        checkpoint("ping-1-0300", load, posture="WAIT", human=False),
        checkpoint("delivered", load, stage="DELIVERED", posture="NEYMA_CAN_ACT",
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")},
                   actions={"DOCUMENT_REQUIRED": ["REQUEST_POD"]}, billing_ready=False),
        checkpoint("pod", load, quiet=True, billing_ready=True),
        checkpoint("invoice", load, quiet=True, billing_ready=True, posture="QUIET",
                   next_action=None, housekeeping=0),
        checkpoint("end", load, quiet=True, billing_ready=True, stage="DELIVERED"),
    ]})


# ============================================================ a promise, through time

def w03_promise_through_time() -> Any:
    """ "I'll update you in an hour." Before the hour: WAIT. A minute after it, in silence, over a
    channel that was up: a follow-up Neyma could make. Then the update arrives and it is closed."""
    h = HistoryBuilder("W03", "Champaign to Evansville: a promise, an hour, and silence",
                       NORTHLINE, day="2026-06-09", zone="America/Chicago",
                       hostile=("promise_pending_is_a_wait", "promise_overdue_is_a_follow_up",
                                "promised_update_arrives", "duplicate_messages"))
    load, refs = "LD-49003", (load_ref("LD-49003"),)
    stops = _stops(h, pickup="Midwest Paper Champaign", delivery="Ohio Valley Print",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   pickup_window=("09:00", "11:00"))
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    _covered(h, load=load, customer="midwest_paper", carrier="redbird", po="PO-7801",
             bol="BOL-56003", pro="PRO-60003", sell=164000, stops=stops, at=("07:30", "08:05"))
    h.message("check-in", h.t("10:00"), channel="sms", source_system=NORTHLINE_SMS,
              sender=driver("redbird"), thread="sms-ray-dalton",
              body="checked in at the shipper, still waiting on a door. I'll update you in an "
                   "hour.", refs=refs,
              asserts=(says("AT_PICKUP", "S1"), promise(h.t("11:00"))),
              external_id="<sms-49003-checkin>")
    h.clock("a-minute-late", h.t("11:01"))
    h.redeliver("check-in-again", h.t("11:05"), of="check-in")
    h.message("update", h.t("11:20"), channel="sms", source_system=NORTHLINE_SMS,
              sender=driver("redbird"), thread="sms-ray-dalton", body="loaded and rolling",
              refs=refs, asserts=(says("LOADED", "S1"),))
    waiting = [("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
               ("CARRIER_UPDATE_PENDING", "PENDING", "WAIT")]
    return h.build({"work": [
        checkpoint("check-in", load, stage="AT_PICKUP", posture="WAIT", needs=waiting,
                   human=False, due={"CARRIER_UPDATE_PENDING": h.t("11:00")}),
        # Forty-five minutes on, asked again with nothing new: still a wait, and the same wait.
        checkpoint("check-in", load, at=h.t("10:45"), posture="WAIT", needs=waiting),
        # A minute past the hour, ASKED before the deadline machinery has ruled: not yet "late".
        checkpoint("check-in", load, at=h.t("11:01"), posture="WAIT",
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("CARRIER_STATUS_OVERDUE", "DUE", "DETERMINISTIC")],
                   reasons={"CARRIER_STATUS_OVERDUE": "PROMISED_UPDATE_DUE"}),
        checkpoint("a-minute-late", load, posture="NEYMA_CAN_ACT", human=False,
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("CARRIER_STATUS_OVERDUE", "OVERDUE", "NEYMA_ACTION_CANDIDATE")],
                   reasons={"CARRIER_STATUS_OVERDUE": "PROMISED_UPDATE_OVERDUE"},
                   actions={"CARRIER_STATUS_OVERDUE": ["REQUEST_CARRIER_STATUS"]}),
        checkpoint("check-in-again", load, posture="NEYMA_CAN_ACT",
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("CARRIER_STATUS_OVERDUE", "OVERDUE", "NEYMA_ACTION_CANDIDATE")]),
        checkpoint("update", load, stage="IN_TRANSIT", posture="WAIT", human=False,
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("TRACKING_UPDATE_PENDING", "PENDING", "DETERMINISTIC")],
                   settled={"CARRIER_STATUS_OVERDUE": "SATISFIED",
                            "CARRIER_UPDATE_PENDING": "SATISFIED"}, housekeeping=1),
    ]})


# ============================================================ tracking goes quiet, and comes back

def w04_tracking_goes_quiet() -> Any:
    """A moving truck, a cadence the brokerage chose, and two silences. The first ends when the
    pings resume; the second ends when the driver says he delivered — which is a claim, so the work
    that follows is the paper that proves it."""
    h = HistoryBuilder("W04", "Bloomington to Toledo: tracking goes quiet twice", NORTHLINE,
                       day="2026-06-13", zone="America/Chicago",
                       hostile=("stale_tracking", "tracking_resumes",
                                "delivery_reported_while_tracking_is_stale"))
    load, refs = "LD-49004", (load_ref("LD-49004"),)
    stops = _stops(h, pickup="Great Lakes Beverage Bloomington", delivery="Maumee Distributing",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    _covered(h, load=load, customer="great_lakes_bev", carrier="summit", po="PO-4501",
             bol="BOL-56004", pro="PRO-60004", sell=172000, stops=stops, at=("07:30", "08:00"))
    h.track("loaded", h.t("11:00"), "LOADED", refs=refs, stop_key="S1")
    h.track("ping-noon", h.t("12:00"), "IN_TRANSIT", refs=refs, position="I-74 E")
    h.clock("first-silence", h.t("16:05"))
    h.track("ping-resumes", h.t("17:00"), "IN_TRANSIT", refs=refs, position="US-24 E")
    h.clock("second-silence", h.t("21:10"))
    h.message("driver-delivered", h.t("07:30", 1), channel="sms", source_system=NORTHLINE_SMS,
              sender=driver("summit"), thread="sms-dwayne-pruitt", body="delivered, empty",
              refs=refs, asserts=(says("DELIVERED", "S2"),))
    _pod(h, "pod", h.t("08:10", 1), load=load, via=NORTHLINE_PODS)
    stale = [("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
             ("CARRIER_STATUS_OVERDUE", "OVERDUE", "NEYMA_ACTION_CANDIDATE")]
    return h.build({"work": [
        checkpoint("ping-noon", load, stage="IN_TRANSIT", posture="WAIT",
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("TRACKING_UPDATE_PENDING", "PENDING", "DETERMINISTIC")],
                   due={"TRACKING_UPDATE_PENDING": h.t("16:00")}),
        checkpoint("first-silence", load, posture="NEYMA_CAN_ACT", human=False, needs=stale,
                   reasons={"CARRIER_STATUS_OVERDUE": "TRACKING_OVERDUE"},
                   actions={"CARRIER_STATUS_OVERDUE": ["REQUEST_CARRIER_STATUS"]}),
        checkpoint("ping-resumes", load, posture="WAIT",
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("TRACKING_UPDATE_PENDING", "PENDING", "DETERMINISTIC")],
                   settled={"CARRIER_STATUS_OVERDUE": "SATISFIED"},
                   due={"TRACKING_UPDATE_PENDING": h.t("21:00")}),
        checkpoint("second-silence", load, posture="NEYMA_CAN_ACT", needs=stale),
        checkpoint("driver-delivered", load, stage="DELIVERED", posture="NEYMA_CAN_ACT",
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")},
                   human=False, billing_ready=False),
        checkpoint("pod", load, quiet=True, billing_ready=True),
    ]})


def w05_blind_is_not_late() -> Any:
    """The cadence passes while the tracking channel is DOWN. Neyma cannot say the carrier went
    quiet over a channel it was not watching: the follow-up is offered, and it is not called late."""
    h = HistoryBuilder("W05", "Kankakee to Dayton: the tracking feed is down", NORTHLINE,
                       day="2026-06-17", zone="America/Chicago",
                       hostile=("tracking_unavailable", "blind_is_not_late"))
    load, refs = "LD-49005", (load_ref("LD-49005"),)
    stops = _stops(h, pickup="Prairie Ag Kankakee", delivery="Miami Valley Feed",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS)
    _cover(h, TRACKING, health="DOWN", minute=5)
    _covered(h, load=load, customer="prairie_ag", carrier="bluegrass", po="PO-2305",
             bol="BOL-56005", pro="PRO-60005", sell=169000, stops=stops, at=("07:30", "08:00"))
    h.message("driver-loaded", h.t("11:00"), channel="sms", source_system=NORTHLINE_SMS,
              sender=driver("bluegrass"), thread="sms-hank-rollins", body="loaded, on the way",
              refs=refs, asserts=(says("LOADED", "S1"),))
    h.clock("cadence-passes", h.t("15:10"))
    return h.build({"work": [
        checkpoint("cadence-passes", load, posture="NEYMA_CAN_ACT", human=False,
                   needs=[("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                          ("CARRIER_STATUS_OVERDUE", "UNVERIFIED", "NEYMA_ACTION_CANDIDATE")],
                   reasons={"CARRIER_STATUS_OVERDUE": "TRACKING_UNVERIFIED"}),
    ]})


# ============================================================ appointments

def w06_appointments() -> Any:
    """An unconfirmed pickup, two systems that disagree about the delivery window, a human who
    decides, and then a carrier who says the receiver moved it again."""
    h = HistoryBuilder("W06", "Rockford to Louisville: whose appointment is it", NORTHLINE,
                       day="2026-06-21", zone="America/Chicago",
                       hostile=("appointment_not_confirmed", "contradictory_appointment_times",
                                "conflict_resolved_by_a_human", "receiver_moved_the_appointment"))
    load, refs = "LD-49006", (load_ref("LD-49006"),)
    zone = "America/Kentucky/Louisville"
    stops = _stops(h, pickup="Midwest Paper Rockford", delivery="Derby City Cold Storage",
                   delivery_status="CONFIRMED", delivery_zone=zone,
                   delivery_window=("13:00", "15:00"))
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    _covered(h, load=load, customer="midwest_paper", carrier="ironwood", po="PO-7806",
             bol="BOL-56006", pro="PRO-60006", sell=176000, stops=stops, at=("07:30", "08:00"))
    h.appointment("pickup-confirmed", h.t("08:30"), "S1", h.local("10:00"), h.local("12:00"),
                  "America/Chicago", refs=refs)
    h.appointment("portal-says-morning", h.t("09:00"), "S2", h.local("09:00", 1),
                  h.local("11:00", 1), zone, refs=refs)
    h.human("dana-decides", h.t("09:40"), "dana.ortiz", "confirm_appointment", refs=refs,
            stop_key="S2", window_start_local=h.local("09:00", 1),
            window_end_local=h.local("11:00", 1), timezone=zone,
            note="called the receiver: 9 to 11 is right, the TMS was never updated")
    h.track("at-pickup", h.t("10:30"), "AT_PICKUP", refs=refs, stop_key="S1")
    h.track("loaded", h.t("11:15"), "LOADED", refs=refs, stop_key="S1")
    h.track("ping", h.t("14:00"), "IN_TRANSIT", refs=refs, position="I-65 S")
    h.message("receiver-pushed", h.t("15:00"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("ironwood"), thread="re-load-49006", subject="RE: LD-49006",
              body="Receiver pushed us to 2 tomorrow.", refs=refs,
              asserts=(states_appointment("S2", h.local("14:00", 1), h.local("14:00", 1), zone),))
    h.human("dana-decides-again", h.t("15:30"), "dana.ortiz", "confirm_appointment", refs=refs,
            stop_key="S2", window_start_local=h.local("14:00", 1),
            window_end_local=h.local("16:00", 1), timezone=zone,
            note="receiver confirmed by phone: 2 to 4")
    conflict = ("EVIDENCE_CONFLICT", "OPEN", "HUMAN_REQUIRED")
    watching = [("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
                ("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC")]
    rolling = [("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC"),
               ("TRACKING_UPDATE_PENDING", "PENDING", "DETERMINISTIC")]
    return h.build({"work": [
        checkpoint("covered", load, posture="NEYMA_CAN_ACT", human=False,
                   needs=[("APPOINTMENT_UNCONFIRMED", "OPEN", "NEYMA_ACTION_CANDIDATE"),
                          ("ARRIVAL_PENDING", "PENDING", "DETERMINISTIC")],
                   reasons={"APPOINTMENT_UNCONFIRMED": "APPOINTMENT_NOT_CONFIRMED:S1"},
                   actions={"APPOINTMENT_UNCONFIRMED": ["VERIFY_APPOINTMENT"]}),
        checkpoint("pickup-confirmed", load, posture="WAIT", needs=watching),
        checkpoint("portal-says-morning", load, posture="HUMAN_ATTENTION", human=True,
                   needs=[conflict, *watching],
                   reasons={"EVIDENCE_CONFLICT": "APPOINTMENT_WINDOW"},
                   actions={"EVIDENCE_CONFLICT": ["ASK_HUMAN_RESOLVE_CONFLICT",
                                                  "VERIFY_APPOINTMENT"]},
                   next_action="ASK_HUMAN_RESOLVE_CONFLICT"),
        # Her decision MOVES the watch: the delivery deadline is now the end of the window she
        # confirmed, in the receiver's own timezone, not the one the TMS still shows.
        checkpoint("dana-decides", load, posture="WAIT", human=False, needs=watching,
                   settled={"EVIDENCE_CONFLICT": "RESOLVED"},
                   due={"ARRIVAL_PENDING": [h.t("12:00"), h.t("11:00", 1, zone)]}),
        # A statement made AFTER she decided is a new dispute. Hers is preserved; she is asked.
        checkpoint("receiver-pushed", load, posture="HUMAN_ATTENTION", human=True,
                   needs=[conflict, *rolling],
                   reasons={"EVIDENCE_CONFLICT": "APPOINTMENT_WINDOW"}),
        checkpoint("dana-decides-again", load, posture="WAIT", human=False, needs=rolling,
                   settled={"EVIDENCE_CONFLICT": "RESOLVED"},
                   due={"ARRIVAL_PENDING": h.t("16:00", 1, zone)}),
    ]})


# ============================================================ the paper that proves delivery

def w07_documents() -> Any:
    """Delivered with no POD; the configured day passes; a POD nobody signed arrives; then a signed
    one; then the same signed one twice more. One need the whole way, and then none."""
    h = HistoryBuilder("W07", "Aurora to Columbus: the POD, late, unusable, then twice", NORTHLINE,
                       day="2026-06-25", zone="America/Chicago",
                       hostile=("tms_delivered_pod_absent", "document_overdue",
                                "incomplete_documents", "duplicate_messages"))
    load, refs = "LD-49007", (load_ref("LD-49007"),)
    stops = _stops(h, pickup="Great Lakes Beverage Aurora", delivery="Scioto Farm Supply",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    customer, carrier = _covered(h, load=load, customer="great_lakes_bev", carrier="bluegrass",
                                 po="PO-4507", bol="BOL-56007", pro="PRO-60007", sell=199000,
                                 stops=stops, at=("07:30", "08:00"))
    _rate_con(h, "rate-con", h.t("08:20"), load=load, number="RC-49007", carrier="bluegrass",
              linehaul=161000, via=NORTHLINE_OPS)
    h.track("loaded", h.t("11:00"), "LOADED", refs=refs, stop_key="S1")
    h.track("at-delivery", h.t("14:30"), "AT_DELIVERY", refs=refs, stop_key="S2")
    _delivered(h, "delivered", h.t("15:00"), load=load, customer=customer, carrier=carrier,
               po="PO-4507", bol="BOL-56007", pro="PRO-60007", sell=199000, stops=stops)
    h.clock("a-day-passes", h.t("15:05", 1))
    _pod(h, "pod-unsigned", h.t("16:00", 1), load=load, via=NORTHLINE_PODS, signed=False,
         note="(driver copy)")
    _pod(h, "pod-signed", h.t("18:00", 1), load=load, via=NORTHLINE_PODS)
    h.redeliver("pod-signed-again", h.t("18:05", 1))
    h.document("pod-forwarded", h.t("18:10", 1), "POD",
               f"PROOF OF DELIVERY | load {load} | received in good order ", refs=refs,
               via=NORTHLINE_OPS, signed=True)
    return h.build({"work": [
        checkpoint("delivered", load, posture="NEYMA_CAN_ACT", human=False, billing_ready=False,
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")},
                   reasons={"DOCUMENT_REQUIRED": "DOCUMENT_NOT_RECEIVED"},
                   due={"DOCUMENT_REQUIRED": h.t("15:00", 1)}),
        checkpoint("a-day-passes", load, human=False,
                   needs={"DOCUMENT_REQUIRED": ("OVERDUE", "NEYMA_ACTION_CANDIDATE")}),
        checkpoint("pod-unsigned", load, human=False, billing_ready=False,
                   needs={"DOCUMENT_REQUIRED": ("OVERDUE", "NEYMA_ACTION_CANDIDATE")},
                   reasons={"DOCUMENT_REQUIRED": "DOCUMENT_RECEIVED_UNUSABLE"},
                   actions={"DOCUMENT_REQUIRED": ["REQUEST_POD"]}),
        checkpoint("pod-signed", load, quiet=True, billing_ready=True,
                   settled={"DOCUMENT_REQUIRED": "SATISFIED"}, housekeeping=2),
        checkpoint("pod-signed-again", load, quiet=True, billing_ready=True, housekeeping=2),
        checkpoint("pod-forwarded", load, quiet=True, billing_ready=True, housekeeping=2),
    ]})


# ============================================================ money a human must decide

def w08_invoice_and_accessorial() -> Any:
    """An invoice that does not match, a detention charge nobody agreed to, a carrier who says Mike
    approved it, and a human who says no. Never auto-approved, never auto-disputed, never quiet."""
    h = HistoryBuilder("W08", "Moline to Cincinnati: the invoice, and what Mike said", NORTHLINE,
                       day="2026-06-29", zone="America/Chicago",
                       hostile=("rate_con_differs_from_invoice", "accessorial_not_authorized",
                                "counterparty_asserts_approval"))
    load, refs = "LD-49008", (load_ref("LD-49008"),)
    stops = _stops(h, pickup="Prairie Ag Moline", delivery="Queen City Supply",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    customer, carrier = _covered(h, load=load, customer="prairie_ag", carrier="summit",
                                 po="PO-2308", bol="BOL-56008", pro="PRO-60008", sell=241000,
                                 stops=stops, at=("07:30", "08:00"))
    _rate_con(h, "rate-con", h.t("08:20"), load=load, number="RC-49008", carrier="summit",
              linehaul=200000, via=NORTHLINE_OPS)
    h.track("loaded", h.t("11:00"), "LOADED", refs=refs, stop_key="S1")
    h.track("at-delivery", h.t("14:30"), "AT_DELIVERY", refs=refs, stop_key="S2")
    _delivered(h, "delivered", h.t("15:00"), load=load, customer=customer, carrier=carrier,
               po="PO-2308", bol="BOL-56008", pro="PRO-60008", sell=241000, stops=stops)
    _pod(h, "pod", h.t("15:20"), load=load, via=NORTHLINE_PODS)
    _invoice_as(h, "invoice", h.t("16:00"), load=load, number="SL-9008", carrier="summit",
                linehaul=205000, via=NORTHLINE_OPS, mc=CARRIERS["summit"]["mc"],
                accessorials={"DETENTION": 15000})
    h.message("mike-approved", h.t("16:30"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("summit"), thread="re-load-49008", subject="RE: LD-49008",
              body="Invoice attached. Detention is included per approval from Mike.", refs=refs,
              asserts=(claims("DETENTION", 15000, approved=True),))
    h.human("marcus-denies", h.t("17:00"), "marcus.reid", "deny_accessorial", refs=refs,
            charge_type="DETENTION", note="nobody here approved detention on this load")
    both = [("ACCESSORIAL_UNAUTHORIZED", "OPEN", "HUMAN_REQUIRED"),
            ("INVOICE_DISCREPANCY", "OPEN", "HUMAN_REQUIRED")]
    return h.build({"work": [
        checkpoint("pod", load, quiet=True, billing_ready=True),
        checkpoint("invoice", load, posture="HUMAN_ATTENTION", human=True, needs=both,
                   reasons={"INVOICE_DISCREPANCY": "LINEHAUL_MISMATCH",
                            "ACCESSORIAL_UNAUTHORIZED": "BILLED_NOT_ON_RATE_CONFIRMATION"},
                   actions={"ACCESSORIAL_UNAUTHORIZED": ["ASK_HUMAN_DECIDE_ACCESSORIAL"],
                            "INVOICE_DISCREPANCY": ["ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY"]}),
        # The carrier's "per approval from Mike" is a reason to look harder, on the SAME need.
        checkpoint("mike-approved", load, human=True, needs=both,
                   reasons={"ACCESSORIAL_UNAUTHORIZED": ["BILLED_NOT_ON_RATE_CONFIRMATION",
                                                         "COUNTERPARTY_CLAIMS_APPROVAL"]}),
        checkpoint("marcus-denies", load, human=True,
                   needs={"INVOICE_DISCREPANCY": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"INVOICE_DISCREPANCY": ["LINEHAUL_MISMATCH",
                                                    "ACCESSORIAL_DENIED_BUT_BILLED:DETENTION"]},
                   settled={"ACCESSORIAL_UNAUTHORIZED": "RESOLVED"}),
    ]})


def w09_accessorial_authorized() -> Any:
    """A detention claim made in a text, before any invoice. A named human authorizes it up to a
    cap; the invoice then bills exactly that, and the load is quiet."""
    h = HistoryBuilder("W09", "Peoria to Indianapolis: detention, asked for and authorized",
                       NORTHLINE, day="2026-07-03", zone="America/Chicago",
                       hostile=("accessorial_not_authorized", "human_authorization"))
    load, refs = "LD-49009", (load_ref("LD-49009"),)
    stops = _stops(h, pickup="Midwest Paper Peoria", delivery="Hoosier Distributing",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   delivery_zone="America/Indiana/Indianapolis")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    customer, carrier = _covered(h, load=load, customer="midwest_paper", carrier="redbird",
                                 po="PO-7809", bol="BOL-56009", pro="PRO-60009", sell=158000,
                                 stops=stops, at=("07:30", "08:00"))
    _rate_con(h, "rate-con", h.t("08:20"), load=load, number="RC-49009", carrier="redbird",
              linehaul=124000, via=NORTHLINE_OPS)
    h.track("loaded", h.t("11:00"), "LOADED", refs=refs, stop_key="S1")
    h.message("detention-claim", h.t("13:00"), channel="sms", source_system=NORTHLINE_SMS,
              sender=dispatcher("redbird"), thread="sms-redbird-dispatch",
              body="shipper held him 3 hrs, we'll need detention 175", refs=refs,
              asserts=(claims("DETENTION", 17500),))
    h.human("dana-authorizes", h.t("13:30"), "dana.ortiz", "authorize_accessorial", refs=refs,
            charge_type="DETENTION", amount_cap_minor=17500, currency="USD",
            note="shipper confirmed the hold")
    h.track("at-delivery", h.t("14:30"), "AT_DELIVERY", refs=refs, stop_key="S2")
    _delivered(h, "delivered", h.t("15:00"), load=load, customer=customer, carrier=carrier,
               po="PO-7809", bol="BOL-56009", pro="PRO-60009", sell=158000, stops=stops)
    _pod(h, "pod", h.t("15:20"), load=load, via=NORTHLINE_PODS)
    _invoice_as(h, "invoice", h.t("16:00"), load=load, number="RB-9009", carrier="redbird",
                linehaul=124000, via=NORTHLINE_OPS, mc=CARRIERS["redbird"]["mc"],
                accessorials={"DETENTION": 17500})
    return h.build({"work": [
        checkpoint("detention-claim", load, posture="HUMAN_ATTENTION", human=True,
                   reasons={"ACCESSORIAL_UNAUTHORIZED": "CLAIMED_NOT_AUTHORIZED"},
                   actions={"ACCESSORIAL_UNAUTHORIZED": ["ASK_HUMAN_DECIDE_ACCESSORIAL"]}),
        checkpoint("dana-authorizes", load, human=False,
                   settled={"ACCESSORIAL_UNAUTHORIZED": "RESOLVED"}),
        checkpoint("invoice", load, quiet=True, billing_ready=True),
    ]})


# ============================================================ P9-D23, the other ways in and out

def w10_mc_written_another_way() -> Any:
    """The invoice prints "MC-77120". The TMS holds "MC-771203". One digit short is a DIFFERENT
    number: Neyma matches an MC on its exact digits and never on a prefix of them, so it does not
    decide this is the same carrier. A human places the invoice. (A benign re-spelling of the SAME
    digits - "MC 771203" - does resolve by itself; that is tested where it can be varied, in
    `test_p9_load_work.py`, not here.)"""
    h = HistoryBuilder("W10", "Normal to Lima: an MC printed one digit short", NORTHLINE,
                       day="2026-07-07", zone="America/Chicago",
                       hostile=("invoice_unattributed", "carrier_mc_truncated",
                                "attribution_corrected_by_human"))
    load = "LD-49010"
    stops = _stops(h, pickup="Prairie Ag Normal", delivery="Allen County Feed",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    customer, carrier = _covered(h, load=load, customer="prairie_ag", carrier="ironwood",
                                 po="PO-2310", bol="BOL-56010", pro="PRO-60010", sell=181000,
                                 stops=stops, at=("07:30", "08:00"))
    _rate_con(h, "rate-con", h.t("08:20"), load=load, number="RC-49010", carrier="ironwood",
              linehaul=143000, via=NORTHLINE_OPS)
    _delivered(h, "delivered", h.t("15:00"), load=load, customer=customer, carrier=carrier,
               po="PO-2310", bol="BOL-56010", pro="PRO-60010", sell=181000, stops=stops)
    _pod(h, "pod", h.t("15:20"), load=load, via=NORTHLINE_PODS)
    invoice = _invoice_as(h, "invoice-other-spelling", h.t("16:00"), load=load, number="IW-9010",
                          carrier="ironwood", linehaul=143000, via=NORTHLINE_OPS, mc="MC-77120")
    h.human("attributed", h.t("16:30"), "marcus.reid", "attribute_carrier_invoice",
            refs=(load_ref(load),), movement_key="M1",
            target={"source_system": NORTHLINE_OPS, "external_id": invoice},
            note="same carrier - their new template cuts the last digit off")
    return h.build({"work": [
        checkpoint("invoice-other-spelling", load, posture="HUMAN_ATTENTION", human=True,
                   needs={"INVOICE_UNATTRIBUTED": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"INVOICE_UNATTRIBUTED": "CARRIER_UNRECOGNIZED"}),
        checkpoint("attributed", load, quiet=True, billing_ready=True,
                   settled={"INVOICE_UNATTRIBUTED": "RESOLVED"}, housekeeping=1),
    ]})


def w11_system_of_record_corrects_the_carrier() -> Any:
    """The TMS row names the wrong carrier. The right carrier's invoice arrives and fits no movement
    of the load. Then the system of record is corrected — and that, not a guess and not a human's
    act, is what places the invoice."""
    h = HistoryBuilder("W11", "Pekin to Akron: the TMS named the wrong carrier", NORTHLINE,
                       day="2026-07-11", zone="America/Chicago",
                       hostile=("invoice_unattributed", "carrier_not_on_load",
                                "attribution_corrected_by_system_of_record"))
    load = "LD-49011"
    stops = _stops(h, pickup="Great Lakes Beverage Pekin", delivery="Summit County Beverage",
                   delivery_zone="America/New_York")
    customer = CUSTOMERS["great_lakes_bev"]
    wrong, right = CARRIERS["redbird"], CARRIERS["ironwood"]
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    h.tms("tender", h.t("07:30"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-4511", bol="BOL-56011", sell=charges(203000), stops=stops)
    h.tms("covered-wrong-carrier", h.t("08:00"), load=load, status="COVERED", version=2,
          customer=customer, po="PO-4511", bol="BOL-56011", sell=charges(203000), stops=stops,
          movements=(movement("M1", wrong),))
    _rate_con(h, "rate-con", h.t("08:20"), load=load, number="RC-49011", carrier="ironwood",
              linehaul=166000, via=NORTHLINE_OPS)
    h.tms("delivered", h.t("15:00"), load=load, status="DELIVERED", version=3, customer=customer,
          po="PO-4511", bol="BOL-56011", sell=charges(203000), stops=stops,
          movements=(movement("M1", wrong, status="DELIVERED"),))
    _pod(h, "pod", h.t("15:20"), load=load, via=NORTHLINE_PODS)
    _invoice_as(h, "invoice", h.t("16:00"), load=load, number="IW-9011", carrier="ironwood",
                linehaul=166000, via=NORTHLINE_OPS, mc=right["mc"])
    h.tms("carrier-corrected", h.t("17:00"), load=load, status="DELIVERED", version=4,
          customer=customer, po="PO-4511", bol="BOL-56011", sell=charges(203000), stops=stops,
          movements=(movement("M1", right, status="DELIVERED"),))
    return h.build({"work": [
        checkpoint("invoice", load, posture="HUMAN_ATTENTION", human=True,
                   needs={"INVOICE_UNATTRIBUTED": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"INVOICE_UNATTRIBUTED": "CARRIER_NOT_ON_LOAD"}),
        checkpoint("carrier-corrected", load, quiet=True, billing_ready=True, human=False,
                   settled={"INVOICE_UNATTRIBUTED": "SATISFIED"}, housekeeping=1),
    ]})


def w12_one_carrier_two_movements() -> Any:
    """One carrier ran both movements of the load. Its MC is exactly right and still does not say
    WHICH movement the invoice bills. Neyma does not pick the first."""
    h = HistoryBuilder("W12", "Galesburg to Erie: one carrier, two movements, one invoice",
                       NORTHLINE, day="2026-07-15", zone="America/Chicago",
                       hostile=("invoice_unattributed", "carrier_ambiguous",
                                "one_load_two_movements"))
    load = "LD-49012"
    stops = _stops(h, pickup="Midwest Paper Galesburg", delivery="Lakeshore Print",
                   delivery_zone="America/New_York")
    customer, carrier = CUSTOMERS["midwest_paper"], CARRIERS["bluegrass"]
    both = (movement("M1", carrier, status="DELIVERED"), movement("M2", carrier,
                                                                  status="DELIVERED"))
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    h.tms("tender", h.t("07:30"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-7812", bol="BOL-56012", sell=charges(254000), stops=stops)
    h.tms("covered", h.t("08:00"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-7812", bol="BOL-56012", sell=charges(254000), stops=stops,
          movements=(movement("M1", carrier), movement("M2", carrier)))
    _rate_con(h, "rate-con-m1", h.t("08:20"), load=load, number="RC-49012-A",
              carrier="bluegrass", linehaul=90000, via=NORTHLINE_OPS, movement_key="M1")
    _rate_con(h, "rate-con-m2", h.t("08:25"), load=load, number="RC-49012-B",
              carrier="bluegrass", linehaul=110000, via=NORTHLINE_OPS, movement_key="M2")
    h.tms("delivered", h.t("15:00"), load=load, status="DELIVERED", version=3, customer=customer,
          po="PO-7812", bol="BOL-56012", sell=charges(254000), stops=stops, movements=both)
    _pod(h, "pod", h.t("15:20"), load=load, via=NORTHLINE_PODS)
    invoice = _invoice_as(h, "invoice", h.t("16:00"), load=load, number="BG-9012",
                          carrier="bluegrass", linehaul=110000, via=NORTHLINE_OPS,
                          mc=carrier["mc"])
    h.human("attributed", h.t("16:30"), "marcus.reid", "attribute_carrier_invoice",
            refs=(load_ref(load),), movement_key="M2",
            target={"source_system": NORTHLINE_OPS, "external_id": invoice},
            note="this is the second leg")
    return h.build({"work": [
        checkpoint("invoice", load, posture="HUMAN_ATTENTION", human=True,
                   needs={"INVOICE_UNATTRIBUTED": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"INVOICE_UNATTRIBUTED": "CARRIER_AMBIGUOUS"}),
        checkpoint("attributed", load, quiet=True, human=False,
                   settled={"INVOICE_UNATTRIBUTED": "RESOLVED"}),
    ]})


def _twin(h: HistoryBuilder, *, load: str, ops: str, pods: str, mc: str | None) -> str:
    """The same load number, PO, BOL, carrier, invoice number and message id, at whichever
    brokerage `h` is. Only the printed MC differs."""
    stops = _stops(h, pickup="Ozark Building Supply", delivery="Bluff City Lumber")
    customer, carrier = CUSTOMERS["cedar_building"], CARRIERS["ironwood"]
    _cover(h, *dict.fromkeys((ops, pods)))
    h.tms("tender", h.t("07:30"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-9050", bol="BOL-56050", sell=charges(210000), stops=stops)
    h.tms("covered", h.t("08:00"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-9050", bol="BOL-56050", sell=charges(210000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-60050"),))
    _rate_con(h, "rate-con", h.t("08:20"), load=load, number="RC-49050", carrier="ironwood",
              linehaul=170000, via=ops)
    h.tms("delivered", h.t("15:00"), load=load, status="DELIVERED", version=3, customer=customer,
          po="PO-9050", bol="BOL-56050", sell=charges(210000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-60050", status="DELIVERED"),))
    _pod(h, "pod", h.t("15:20"), load=load, via=pods)
    return _invoice_as(h, "invoice", h.t("16:00"), load=load, number="IW-9050",
                       carrier="ironwood", linehaul=170000, via=ops, mc=mc)


def w13_the_same_invoice_at_another_brokerage() -> Any:
    """Cedar Ridge's copy of load LD-49050 gets an invoice with no MC. It is Cedar Ridge's to place
    and nobody else's."""
    h = HistoryBuilder("W13", "Cedar Ridge LD-49050: an invoice with no MC", CEDAR,
                       day="2026-07-19", zone="America/Chicago",
                       hostile=("invoice_unattributed", "same_external_id_under_two_tenants"))
    load = "LD-49050"
    _twin(h, load=load, ops=CEDAR_OPS, pods=CEDAR_OPS, mc=None)
    h.clock("end", h.t("12:00", 1))
    return h.build({"work": [
        checkpoint("invoice", load, posture="HUMAN_ATTENTION", human=True,
                   needs={"INVOICE_UNATTRIBUTED": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"INVOICE_UNATTRIBUTED": "CARRIER_NOT_STATED"}),
        checkpoint("end", load, human=True,
                   needs={"INVOICE_UNATTRIBUTED": ("OPEN", "HUMAN_REQUIRED")}),
    ]})


def w14_the_twin_at_northline() -> Any:
    """Northline's load with the SAME number, PO, BOL, carrier and invoice number — and an invoice
    that prints its MC. It reconciles. A Northline human then attributes "the" invoice by the very
    message id Cedar Ridge's unplaced one carries; it can reach only Northline's."""
    h = HistoryBuilder("W14", "Northline LD-49050: the twin that reconciles", NORTHLINE,
                       day="2026-07-19", zone="America/Chicago",
                       hostile=("same_external_id_under_two_tenants",
                                "cross_tenant_attribution_trap"))
    load = "LD-49050"
    invoice = _twin(h, load=load, ops=NORTHLINE_OPS, pods=NORTHLINE_PODS,
                    mc=CARRIERS["ironwood"]["mc"])
    h.human("attributed", h.t("16:30"), "marcus.reid", "attribute_carrier_invoice",
            refs=(load_ref(load),), movement_key="M1",
            target={"source_system": CEDAR_OPS, "external_id": invoice},
            note="trying to place the Cedar Ridge copy from here")
    h.clock("end", h.t("12:00", 1))
    return h.build({"work": [
        checkpoint("invoice", load, quiet=True, billing_ready=True),
        # The act names a record Northline does not hold. It is refused to a human, and it places
        # nothing anywhere.
        checkpoint("attributed", load, human=True, billing_ready=True,
                   needs={"IDENTITY_UNRESOLVED": ("OPEN", "HUMAN_REQUIRED")},
                   reasons={"IDENTITY_UNRESOLVED": "HUMAN_ACT_NAMES_NOTHING"}),
    ]})


# ============================================================ act now, or wait for the promise?

def w15_a_promise_and_an_open_need() -> Any:
    """Delivered, no POD. The dispatcher promises to "get back to you by 3" — about what, the
    record cannot say. Then he promises the POD itself by 2. Then 2 passes."""
    h = HistoryBuilder("W15", "Sterling to Canton: a POD owed, and two promises", NORTHLINE,
                       day="2026-07-23", zone="America/Chicago",
                       hostile=("pending_promise_of_unsettled_scope",
                                "promise_covers_the_missing_document", "promise_never_arrives"))
    load, refs = "LD-49015", (load_ref("LD-49015"),)
    stops = _stops(h, pickup="Prairie Ag Sterling", delivery="Stark County Feed",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    customer, carrier = _covered(h, load=load, customer="prairie_ag", carrier="summit",
                                 po="PO-2315", bol="BOL-56015", pro="PRO-60015", sell=193000,
                                 stops=stops, at=("07:30", "08:00"))
    h.track("loaded", h.t("09:30"), "LOADED", refs=refs, stop_key="S1")
    h.track("at-delivery", h.t("09:45"), "AT_DELIVERY", refs=refs, stop_key="S2")
    _delivered(h, "delivered", h.t("10:00"), load=load, customer=customer, carrier=carrier,
               po="PO-2315", bol="BOL-56015", pro="PRO-60015", sell=193000, stops=stops)
    h.message("get-back-to-you", h.t("10:30"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("summit"), thread="re-load-49015", subject="RE: LD-49015",
              body="Dwayne is back at the yard around two. I'll get back to you by 3.",
              refs=refs, asserts=(promise(h.t("15:00"), "other"),))
    h.message("pod-by-two", h.t("11:00"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("summit"), thread="re-load-49015", subject="RE: LD-49015",
              body="Found the paperwork. I'll send the POD by 2.", refs=refs,
              asserts=(promise(h.t("14:00"), "send_document"),))
    h.clock("two-passes", h.t("14:05"))
    return h.build({"work": [
        checkpoint("delivered", load, posture="NEYMA_CAN_ACT", human=False,
                   needs={"DOCUMENT_REQUIRED": ("OPEN", "NEYMA_ACTION_CANDIDATE")}),
        checkpoint("get-back-to-you", load, human=False,
                   needs=[("CARRIER_UPDATE_PENDING", "PENDING", "WAIT"),
                          ("DOCUMENT_REQUIRED", "OPEN", "MODEL_REASONING")],
                   reasons={"DOCUMENT_REQUIRED": "PENDING_PROMISE_OF_UNSETTLED_SCOPE"},
                   actions={"DOCUMENT_REQUIRED": ["REQUEST_POD", "WAIT"]}),
        checkpoint("pod-by-two", load, posture="WAIT", human=False,
                   needs=[("CARRIER_UPDATE_PENDING", "PENDING", "WAIT"),
                          ("DOCUMENT_REQUIRED", "OPEN", "WAIT")],
                   reasons={"DOCUMENT_REQUIRED": "COVERED_BY_PENDING_PROMISE"},
                   due={"DOCUMENT_REQUIRED": h.t("14:00")}),
        checkpoint("two-passes", load, posture="NEYMA_CAN_ACT", human=False,
                   needs=[("CARRIER_STATUS_OVERDUE", "OVERDUE", "NEYMA_ACTION_CANDIDATE"),
                          ("DOCUMENT_REQUIRED", "OPEN", "NEYMA_ACTION_CANDIDATE")],
                   together=[2]),
    ]})


WORK_HISTORY_FACTORIES = (
    w01_invoice_without_a_carrier, w02_clean_load, w03_promise_through_time,
    w04_tracking_goes_quiet, w05_blind_is_not_late, w06_appointments, w07_documents,
    w08_invoice_and_accessorial, w09_accessorial_authorized, w10_mc_written_another_way,
    w11_system_of_record_corrects_the_carrier, w12_one_carrier_two_movements,
    w13_the_same_invoice_at_another_brokerage, w14_the_twin_at_northline,
    w15_a_promise_and_an_open_need,
)


def build_work_histories() -> list[Any]:
    """Each history built fresh. Within a brokerage the order is chronological."""
    return [factory() for factory in WORK_HISTORY_FACTORIES]


__all__ = ["TRACKING_CADENCE_MINUTES", "WORK_HISTORY_FACTORIES", "WORK_SETUPS",
           "build_work_histories", "checkpoint", "promise"]
