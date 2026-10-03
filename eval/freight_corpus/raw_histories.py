"""Nine raw-language load histories: freight said the way people say it.

Where the twenty hostile histories were authored structured-first and then un-read (`raw.py`), these
are authored as language from the start — a driver's text, a dispatcher's reply, a forwarded thread, a
correction, an invoice note that claims an approval. Each carries labeled expected outcomes exactly as
the twenty do, plus the reading a careful reader would give each message (`READINGS`), which is what a
scripted gateway replies with in tests.

They run in their OWN database, never alongside the twenty: the deterministic harness and its 262
labeled checks are unchanged by anything here.

    R01  a check-in and a promise, then silence            promise -> Expectation -> OVERDUE
    R02  a promise, kept, then quoted in a forward         no second obligation
    R03  "that was the wrong load number"                  a claim; only a human re-binds
    R04  three messages nothing exact can place            model candidates never bind
    R05  the same load number at another brokerage         candidates never cross tenants
    R06  a quoted rate, and "approved by Mike"             neither is authority
    R07  the receiver moved the appointment                Conflict, not overwrite
    R08  two parties, one inbox, two appointment times     neither supersedes the other
    R09  "we delivered" while tracking says otherwise      Conflict, not a verdict

SYNTHETIC. Every company, person, number and sentence here is invented development input. Nothing in
this file is a design-partner observation and no freight rule is validated by it.
"""

from __future__ import annotations

from typing import Any

from .builders import HistoryBuilder, charges, load_ref, movement, stop
from .histories import TRACKING, _cover, _pod, _stops
from .parties import (
    CARRIERS,
    CEDAR,
    CEDAR_OPS,
    CUSTOMERS,
    NORTHLINE,
    NORTHLINE_OPS,
    NORTHLINE_PODS,
    NORTHLINE_SMS,
    customer_contact,
    dispatcher,
    driver,
)
from .raw import Task, document_text
from .reading import (
    appointment,
    charge,
    correction,
    delay,
    message,
    paper,
    pick,
    promise,
    rate,
    reference,
    status,
)

#: body text -> the reading of it.
READINGS: dict[str, dict[str, Any]] = {}
#: document text -> the reading of it.
DOCUMENT_READINGS: dict[str, dict[str, Any]] = {}
#: candidate-request text -> a responder that proposes from the SUPPLIED options.
CANDIDATE_READINGS: dict[str, Any] = {}


def _say(body: str, reading: dict[str, Any]) -> str:
    READINGS[body] = reading
    return body


CHECK_IN = _say(
    "Checked in at the shipper 12:42, still waiting on a door. I'll update you in an hour.",
    message(category="STATUS_UPDATE",
            statuses=[status("ARRIVED", "PICKUP", "Checked in at the shipper 12:42")],
            commitments=[promise("I'll update you in an hour", minutes=60, text="in an hour")]))

PROMISE = _say(
    "Luis is loaded. I'll update you by 5 with an ETA.",
    message(category="STATUS_UPDATE", statuses=[status("LOADED", "PICKUP", "Luis is loaded")],
            commitments=[promise("I'll update you by 5 with an ETA", clock="17:00", day=0,
                                 text="by 5")]))
ETA = _say("ETA is 0700 tomorrow at the receiver.", message(category="STATUS_UPDATE"))
FORWARD = _say(
    "FYI, see the carrier's note below.\n\n"
    "---------- Forwarded message ---------\n"
    "From: Pete Vogel <pete@ironwoodhauling.example>\n"
    "Date: Fri, Jun 5, 2026 at 3:00 PM\n"
    "Subject: RE: LD-51002\n\n"
    "Luis is loaded. I'll update you by 5 with an ETA.\n",
    message(category="OTHER",
            statuses=[status("LOADED", "PICKUP", "Luis is loaded", quoted=True)],
            commitments=[promise("I'll update you by 5 with an ETA", clock="17:00", day=0,
                                 text="by 5", actor="CARRIER", quoted=True)]))

DELIVERED_WRONG_THREAD = _say(
    "Dwayne delivered at the receiver, POD to follow.",
    message(category="STATUS_UPDATE",
            statuses=[status("DELIVERED", "DELIVERY", "Dwayne delivered at the receiver")],
            commitments=[promise("POD to follow", action="SEND_DOCUMENT")],
            documents=[paper("POD", "PROMISED", "POD to follow")]))
WRONG_NUMBER = _say(
    "That was the wrong load number in my last email — this is for 51004.",
    message(category="CORRECTION",
            references=[reference("LOAD_NUMBER", "51004", "this is for 51004",
                                  role="CORRECTED_TO")],
            corrections=[correction("LOAD_REFERENCE",
                                    "That was the wrong load number in my last email")]))

POD_BARE = _say(
    "POD attached for 51005.",
    message(category="DOCUMENT_DELIVERY", documents=[paper("POD", "ATTACHED", "POD attached")],
            references=[reference("LOAD_NUMBER", "51005", "51005")]))
LATE_LAKESHORE = _say(
    "running about an hour late to Lakeshore Print",
    message(category="STATUS_UPDATE",
            delays=[delay("running about an hour late", stop="DELIVERY")]))
UNKNOWN_LOAD = _say(
    "Need the rate con for load 99731 resent, we never got it.",
    message(category="REQUEST", response_requested=True,
            documents=[paper("RATE_CON", "REQUESTED", "Need the rate con for load 99731 resent")],
            references=[reference("LOAD_NUMBER", "99731", "load 99731")]))
CANDIDATE_READINGS["POD\n" + POD_BARE] = pick("LD-51005 (load_ref)", evidence="51005")
CANDIDATE_READINGS[LATE_LAKESHORE] = pick("Lakeshore Print Annex", support="PARTIAL",
                                          evidence="Lakeshore Print")

RATE_TALK = _say("Per our call we are at 2150 all in on this one.",
                 message(category="RATE", rates=[rate("2150", "we are at 2150 all in")]))
APPROVED_BY_MIKE = _say(
    "Invoice attached. Detention is included per approval from Mike.",
    message(category="ACCESSORIAL_OR_BILLING",
            documents=[paper("CARRIER_INVOICE", "ATTACHED", "Invoice attached")],
            accessorials=[charge("DETENTION", "Detention is included per approval from Mike",
                                 approved=True, approver="Mike")]))

PUSHED = _say(
    "Receiver pushed us to 10 tomorrow. Customer told us today so can you verify?",
    message(category="APPOINTMENT", response_requested=True,
            appointments=[appointment("DELIVERY", "Receiver pushed us to 10 tomorrow", day=1,
                                      start="10:00", state="RESCHEDULED")]))
STILL_TODAY = _say(
    "We still have the delivery appointment today at 3pm, please confirm the driver will make it.",
    message(category="APPOINTMENT", response_requested=True,
            appointments=[appointment("DELIVERY", "the delivery appointment today at 3pm", day=0,
                                      start="15:00")]))

SET_FOR_0900 = _say(
    "Confirming we are set for 0900 delivery tomorrow.",
    message(category="APPOINTMENT",
            appointments=[appointment("DELIVERY", "we are set for 0900 delivery tomorrow", day=1,
                                      start="09:00")]))
RECEIVER_SAYS_1300 = _say(
    "Receiver has the delivery appointment at 1300 tomorrow.",
    message(category="APPOINTMENT",
            appointments=[appointment("DELIVERY", "the delivery appointment at 1300 tomorrow",
                                      day=1, start="13:00")]))
CORRECTED_TO_1000 = _say(
    "Correction - delivery appt is 1000 tomorrow, not 0900.",
    message(category="CORRECTION",
            appointments=[appointment("DELIVERY", "delivery appt is 1000 tomorrow", day=1,
                                      start="10:00")],
            corrections=[correction("APPOINTMENT", "Correction - delivery appt is 1000 tomorrow")]))

DELIVERED_BUT_TRACKING = _say(
    "We delivered about 45 minutes ago but tracking still shows us at the receiver.",
    message(category="STATUS_UPDATE",
            statuses=[status("DELIVERED", "DELIVERY", "We delivered about 45 minutes ago")]))


def _paper(h: HistoryBuilder, label: str, at: str, doc_type: str, block: dict[str, Any], *,
           load: str, carrier: str, via: str, signed: bool | None = None) -> None:
    text, reading = document_text(doc_type, {"carrier_mc": CARRIERS[carrier]["mc"], **block},
                                  load=load, carrier_name=CARRIERS[carrier]["name"])
    DOCUMENT_READINGS[text] = reading
    h.raw_document(label, at, doc_type, text, refs=(load_ref(load),), via=via, signed=signed)


def r01_promise_then_silence() -> Any:
    h = HistoryBuilder("R01", "Rockford to Dayton: a check-in, a promise, and then silence",
                       NORTHLINE, day="2026-06-01", zone="America/Chicago",
                       hostile=("raw_language", "promise_never_arrives"))
    load, refs = "LD-51001", (load_ref("LD-51001"),)
    stops = _stops(h, pickup="Midwest Paper Rockford", delivery="Miami Valley Print",
                   pickup_status="CONFIRMED", pickup_window=("12:00", "14:00"),
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_SMS, TRACKING)
    h.tms("covered", h.t("08:10"), load=load, status="COVERED", version=1,
          customer=CUSTOMERS["midwest_paper"], po="PO-9001", bol="BOL-71001",
          sell=charges(190000), stops=stops,
          movements=(movement("M1", CARRIERS["redbird"], pro="PRO-71001"),))
    # Sent 12:44, received three minutes later: the promise runs from when it was SAID.
    h.raw_message("driver-checkin", h.t("12:47"), channel="sms", source_system=NORTHLINE_SMS,
                  sender=driver("redbird"), thread="sms-ray-dalton", body=CHECK_IN, refs=refs,
                  as_of=h.t("12:44"))
    h.clock("afternoon", h.t("14:30"))
    return h.build({
        "records": {"driver-checkin": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "expectations": {"arrival:S1": "DISCHARGED", "counterparty_update": "OVERDUE"},
            "exception_types": ["expectation_unmet"], "conflict_fields": [],
            "needs_human": True, "timeline_kinds": ["expectation_overdue"]}},
        "unbound": [],
    })


def r02_quoted_promise() -> Any:
    h = HistoryBuilder("R02", "Madison to Indianapolis: a promise, kept, then quoted in a forward",
                       NORTHLINE, day="2026-06-05", zone="America/Chicago",
                       hostile=("raw_language", "quoted_commitment", "forwarded_repeated_email"))
    load, refs = "LD-51002", (load_ref("LD-51002"),)
    stops = _stops(h, pickup="Great Lakes Beverage Madison", delivery="Hoosier Distributing",
                   delivery_zone="America/Indiana/Indianapolis")
    _cover(h, NORTHLINE_OPS)
    h.tms("covered", h.t("08:00"), load=load, status="COVERED", version=1,
          customer=CUSTOMERS["great_lakes_bev"], po="PO-9002", bol="BOL-71002",
          sell=charges(201000), stops=stops,
          movements=(movement("M1", CARRIERS["ironwood"], pro="PRO-71002"),))
    h.raw_message("carrier-promise", h.t("15:00"), channel="email", source_system=NORTHLINE_OPS,
                  sender=dispatcher("ironwood"), thread="re-load-51002", subject="RE: LD-51002",
                  body=PROMISE, refs=refs, external_id="<msg-51002-promise@ironwood>")
    h.raw_message("carrier-eta", h.t("16:40"), channel="email", source_system=NORTHLINE_OPS,
                  sender=dispatcher("ironwood"), thread="re-load-51002", subject="RE: LD-51002",
                  body=ETA, refs=refs)
    # Forwarded BEFORE the quoted deadline, after the promise was already kept: the one moment a
    # quoted promise read as new would raise a second obligation and then call it overdue.
    h.raw_message("customer-forward", h.t("16:50"), channel="email", source_system=NORTHLINE_OPS,
                  sender=customer_contact("great_lakes_bev"), thread="fwd-load-51002",
                  subject="FW: RE: LD-51002", body=FORWARD, refs=refs, forwarded=True,
                  quoted=("<msg-51002-promise@ironwood>",))
    h.clock("next-day", h.t("12:00", 1))
    return h.build({
        "records": {"customer-forward": {"disposition": "BOUND", "load": load}},
        "loads": {load: {"expectations": {"counterparty_update": "DISCHARGED"},
                         "exception_types": [], "conflict_fields": [], "needs_human": False}},
        "unbound": [],
    })


def r03_wrong_load_number() -> Any:
    h = HistoryBuilder("R03", "Two Peoria loads: 'that was the wrong load number'", NORTHLINE,
                       day="2026-06-09", zone="America/Chicago",
                       hostile=("raw_language", "counterparty_correction",
                                "correction_supersedes_without_deleting"))
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS)
    for index, (load, po, bol, pro) in enumerate((("LD-51003", "PO-9003", "BOL-71003",
                                                   "PRO-71003"),
                                                  ("LD-51004", "PO-9004", "BOL-71004",
                                                   "PRO-71004"))):
        stops = _stops(h, pickup="Prairie Ag Peoria", delivery=f"River Bend Co-op {index}")
        h.tms(f"covered-{load}", h.t(f"07:1{index}"), load=load, status="COVERED", version=1,
              customer=CUSTOMERS["prairie_ag"], po=po, bol=bol, sell=charges(133000),
              stops=stops, movements=(movement("M1", CARRIERS["summit"], pro=pro),))
    h.raw_message("carrier-delivered", h.t("10:00"), channel="email",
                  source_system=NORTHLINE_OPS, sender=dispatcher("summit"),
                  thread="re-load-51003", subject="RE: LD-51003", body=DELIVERED_WRONG_THREAD,
                  refs=(load_ref("LD-51003"),))
    first = h.records[-1].external_id
    h.raw_message("carrier-correction", h.t("10:20"), channel="email",
                  source_system=NORTHLINE_OPS, sender=dispatcher("summit"),
                  thread="re-load-51003", subject="RE: LD-51003", body=WRONG_NUMBER,
                  refs=(load_ref("LD-51003"),))
    h.human("triage-corrects", h.t("11:00"), "priya.nair", "correct_binding",
            refs=(load_ref("LD-51004"),),
            target={"source_system": NORTHLINE_OPS, "external_id": first},
            note="the carrier says the delivery report was for 51004")
    h.clock("end", h.t("12:00"))
    return h.build({
        "records": {"carrier-delivered": {"disposition": "BOUND", "load": "LD-51003"},
                    "carrier-correction": {"disposition": "BOUND", "load": "LD-51003"},
                    "triage-corrects": {"disposition": "BOUND", "load": "LD-51004"}},
        # LD-51003 also ends with an unmet POD expectation: it was raised while the delivery
        # report was (wrongly) on this load, and nothing withdraws an Expectation when the binding
        # it rested on is corrected (debt P9-D2). It is owned and visible, which is the safe side.
        "loads": {"LD-51003": {"delivered_claimed": False,
                               "exception_types": ["counterparty_reference_correction",
                                                   "expectation_unmet"],
                               "needs_human": True,
                               "timeline_kinds": ["binding_correction"]},
                  "LD-51004": {"delivered_claimed": True}},
        "unbound": [],
    })


def r04_nothing_exact() -> Any:
    h = HistoryBuilder("R04", "Three messages nothing exact can place", NORTHLINE,
                       day="2026-06-13", zone="America/Chicago",
                       hostile=("raw_language", "unqualified_reference", "two_plausible_loads",
                                "unknown_load_reference"))
    _cover(h, NORTHLINE_OPS, NORTHLINE_SMS)
    for load, carrier, pickup, po, bol, pro, at in (
            ("LD-51005", "redbird", "Midwest Paper Peoria", "PO-9005", "BOL-71005", "PRO-71005",
             "07:05"),
            ("LD-51006", "bluegrass", "Midwest Paper Joliet", "PO-9006", "BOL-71006",
             "PRO-71006", "07:10")):
        stops = _stops(h, pickup=pickup, delivery="Lakeshore Print Annex",
                       delivery_zone="America/Detroit")
        h.tms(f"covered-{load}", h.t(at), load=load, status="COVERED", version=1,
              customer=CUSTOMERS["midwest_paper"], po=po, bol=bol, sell=charges(150000),
              stops=stops, movements=(movement("M1", CARRIERS[carrier], pro=pro),))
    h.raw_message("pod-note-bare", h.t("10:00"), channel="email", source_system=NORTHLINE_OPS,
                  sender=dispatcher("redbird"), thread="misc-pod", subject="POD", body=POD_BARE)
    h.raw_message("late-lakeshore", h.t("10:30"), channel="sms", source_system=NORTHLINE_SMS,
                  sender=("driver", "unknown", "+1-555-0199"), thread="sms-unknown-0199",
                  body=LATE_LAKESHORE)
    h.raw_message("unknown-load", h.t("11:00"), channel="email", source_system=NORTHLINE_OPS,
                  sender=dispatcher("summit"), thread="misc-ratecon", subject="",
                  body=UNKNOWN_LOAD)
    h.clock("end", h.t("12:00"))
    return h.build({
        "records": {
            "pod-note-bare": {"disposition": "AMBIGUOUS", "candidates": ["LD-51005"],
                              "ambiguity": "model_inferred"},
            "late-lakeshore": {"disposition": "AMBIGUOUS",
                               "candidates": ["LD-51005", "LD-51006"],
                               "ambiguity": "model_inferred"},
            "unknown-load": {"disposition": "UNBOUND"}},
        "loads": {"LD-51005": {"needs_human": True}, "LD-51006": {"needs_human": True}},
        "unbound": ["late-lakeshore", "pod-note-bare", "unknown-load"],
    })


def r05_same_number_other_tenant() -> Any:
    h = HistoryBuilder("R05", "Cedar Ridge's own LD-51005, and a POD note with a bare number",
                       CEDAR, day="2026-06-13", zone="America/Chicago",
                       hostile=("raw_language", "same_external_id_under_two_tenants",
                                "unqualified_reference"))
    load = "LD-51005"
    stops = _stops(h, pickup="Ozark Building Products", delivery="Little Rock Lumber Yard")
    _cover(h, CEDAR_OPS)
    h.tms("covered", h.t("07:30"), load=load, status="COVERED", version=1,
          customer=CUSTOMERS["cedar_building"], po="PO-9005", bol="BOL-71005",
          sell=charges(171000), stops=stops,
          movements=(movement("M1", CARRIERS["redbird"], pro="PRO-71005"),))
    h.raw_message("pod-note-bare", h.t("10:05"), channel="email", source_system=CEDAR_OPS,
                  sender=dispatcher("redbird"), thread="misc-pod", subject="POD", body=POD_BARE)
    h.clock("end", h.t("12:00"))
    return h.build({
        "records": {"pod-note-bare": {"disposition": "AMBIGUOUS", "candidates": [load],
                                      "ambiguity": "model_inferred"}},
        "loads": {load: {"needs_human": True}},
        "unbound": ["pod-note-bare"],
    })


def r06_rate_and_claimed_approval() -> Any:
    h = HistoryBuilder("R06", "Decatur to Memphis: a quoted rate, and 'approved by Mike'",
                       NORTHLINE, day="2026-06-17", zone="America/Chicago",
                       hostile=("raw_language", "conversational_rate_is_not_authority",
                                "counterparty_asserts_approval", "rate_con_differs_from_invoice"))
    load, refs = "LD-51007", (load_ref("LD-51007"),)
    customer, carrier = CUSTOMERS["prairie_ag"], CARRIERS["ironwood"]
    stops = _stops(h, pickup="Prairie Ag Decatur", delivery="Delta Crop Services")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS)
    h.tms("covered", h.t("07:30"), load=load, status="COVERED", version=1, customer=customer,
          po="PO-9007", bol="BOL-71007", sell=charges(248000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-71007"),))
    h.raw_message("carrier-rate-talk", h.t("09:10"), channel="email",
                  source_system=NORTHLINE_OPS, sender=dispatcher("ironwood"),
                  thread="re-load-51007", subject="RE: LD-51007", body=RATE_TALK, refs=refs)
    _paper(h, "rate-con", h.t("09:40"), "RATE_CON",
           {"ratecon_number": "RC-51007", **charges(195000)}, load=load, carrier="ironwood",
           via=NORTHLINE_OPS, signed=True)
    h.tms("delivered", h.t("11:15", 1), load=load, status="DELIVERED", version=2,
          customer=customer, po="PO-9007", bol="BOL-71007", sell=charges(248000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-71007", status="DELIVERED"),))
    _pod(h, "pod", h.t("11:40", 1), load=load, via=NORTHLINE_PODS)
    h.raw_message("carrier-invoice-note", h.t("15:18", 1), channel="email",
                  source_system=NORTHLINE_OPS, sender=dispatcher("ironwood"),
                  thread="re-load-51007", subject="RE: LD-51007 invoice", body=APPROVED_BY_MIKE,
                  refs=refs)
    _paper(h, "carrier-invoice", h.t("15:20", 1), "CARRIER_INVOICE",
           {"invoice_number": "IW-9107",
            **charges(215000, 0, {"DETENTION": 17500}, total=232500)},
           load=load, carrier="ironwood", via=NORTHLINE_OPS)
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "records": {"rate-con": {"disposition": "BOUND", "load": load},
                    "carrier-invoice": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "documents": {"RATE_CON": 1, "POD": 1, "CARRIER_INVOICE": 1}, "payables": 1,
            "reconciliation": ["DISCREPANT"],
            "discrepancy_codes": ["ACCESSORIAL_NOT_ON_RATE_CONFIRMATION", "LINEHAUL_MISMATCH"],
            "conflict_fields": ["owed_to_carrier.linehaul"],
            "accessorials": {"DETENTION": "CLAIMED"}, "authorizations": 0,
            "exception_types": ["accessorial_authorization_unresolved",
                                "counterparty_self_authorization"],
            "requirements": {"POD": "SATISFIED"}, "needs_human": True}},
        "unbound": [],
    })


def r07_receiver_moved_the_appointment() -> Any:
    h = HistoryBuilder("R07", "Gary to Louisville: the receiver moved the appointment", NORTHLINE,
                       day="2026-06-21", zone="America/Chicago",
                       hostile=("raw_language", "contradictory_appointment_times"))
    load, refs = "LD-51008", (load_ref("LD-51008"),)
    zone = "America/Kentucky/Louisville"
    stops = (stop("S1", "PICKUP", 1, "Great Lakes Beverage Gary", "America/Chicago",
                  appointment=(h.local("06:00"), h.local("08:00"), "REQUESTED")),
             stop("S2", "DELIVERY", 2, "Derby City Cold Storage", zone,
                  appointment=(h.local("15:00"), h.local("17:00"), "CONFIRMED")))
    _cover(h, NORTHLINE_OPS, TRACKING)
    h.tms("covered", h.t("05:30"), load=load, status="COVERED", version=1,
          customer=CUSTOMERS["great_lakes_bev"], po="PO-9008", bol="BOL-71008",
          sell=charges(176000), stops=stops,
          movements=(movement("M1", CARRIERS["redbird"], pro="PRO-71008"),))
    h.raw_message("carrier-reschedule", h.t("11:20"), channel="email",
                  source_system=NORTHLINE_OPS, sender=dispatcher("redbird"),
                  thread="re-load-51008", subject="RE: LD-51008", body=PUSHED, refs=refs)
    h.raw_message("customer-appointment", h.t("11:50"), channel="email",
                  source_system=NORTHLINE_OPS, sender=customer_contact("great_lakes_bev"),
                  thread="re-load-51008-customer", subject="LD-51008 delivery today",
                  body=STILL_TODAY, refs=refs)
    h.clock("midday", h.t("12:30"))
    return h.build({
        "loads": {load: {
            "conflict_fields": ["window"],
            "appointment_conditions": {"S1": "consistent", "S2": "conflicting"},
            # Labeled as of the END of the run: this brokerage's clock keeps moving through its
            # later histories, the original window closes, and no arrival is ever reported.
            "expectations": {"arrival:S2": "OVERDUE"}, "needs_human": True,
            "invoice_eligible": False, "timeline_kinds": ["conflict"]}},
        "unbound": [],
    })


def r08_two_parties_one_inbox() -> Any:
    h = HistoryBuilder("R08", "Aurora to Toledo: two parties, one inbox, two appointment times",
                       NORTHLINE, day="2026-06-25", zone="America/Chicago",
                       hostile=("raw_language", "contradictory_appointment_times",
                                "correction_supersedes_without_deleting"))
    load, refs = "LD-51009", (load_ref("LD-51009"),)
    stops = (stop("S1", "PICKUP", 1, "Great Lakes Beverage Aurora", "America/Chicago"),
             stop("S2", "DELIVERY", 2, "Maumee Bottling", "America/New_York"))
    _cover(h, NORTHLINE_OPS)
    h.tms("covered", h.t("07:00"), load=load, status="COVERED", version=1,
          customer=CUSTOMERS["great_lakes_bev"], po="PO-9009", bol="BOL-71009",
          sell=charges(187000), stops=stops,
          movements=(movement("M1", CARRIERS["ironwood"], pro="PRO-71009"),))
    h.raw_message("carrier-appointment", h.t("09:00"), channel="email",
                  source_system=NORTHLINE_OPS, sender=dispatcher("ironwood"),
                  thread="re-load-51009", subject="RE: LD-51009 appt", body=SET_FOR_0900,
                  refs=refs)
    h.raw_message("customer-appointment", h.t("09:30"), channel="email",
                  source_system=NORTHLINE_OPS, sender=customer_contact("great_lakes_bev"),
                  thread="re-load-51009-customer", subject="LD-51009", body=RECEIVER_SAYS_1300,
                  refs=refs)
    h.raw_message("carrier-corrects-itself", h.t("10:15"), channel="email",
                  source_system=NORTHLINE_OPS, sender=dispatcher("ironwood"),
                  thread="re-load-51009", subject="RE: LD-51009 appt", body=CORRECTED_TO_1000,
                  refs=refs)
    h.clock("end", h.t("12:00"))
    return h.build({
        "loads": {load: {"conflict_fields": ["window"],
                         "appointment_conditions": {"S2": "conflicting"},
                         "expectations": {}, "needs_human": True, "invoice_eligible": False}},
        "unbound": [],
    })


def r09_delivered_but_tracking_disagrees() -> Any:
    h = HistoryBuilder("R09", "Naperville to Grand Rapids: 'we delivered' while tracking disagrees",
                       NORTHLINE, day="2026-06-29", zone="America/Chicago",
                       hostile=("raw_language", "conflicting_tracking_sources",
                                "driver_assertion_is_not_delivery_proof"))
    load, refs = "LD-51010", (load_ref("LD-51010"),)
    stops = _stops(h, pickup="Great Lakes Beverage Naperville", delivery="Furniture City Bev",
                   delivery_zone="America/Detroit")
    _cover(h, NORTHLINE_SMS, NORTHLINE_PODS, TRACKING)
    h.tms("covered", h.t("05:30"), load=load, status="COVERED", version=1,
          customer=CUSTOMERS["great_lakes_bev"], po="PO-9010", bol="BOL-71010",
          sell=charges(139000), stops=stops,
          movements=(movement("M1", CARRIERS["redbird"], pro="PRO-71010"),))
    h.track("ping-arrived", h.t("13:10"), "AT_DELIVERY", refs=refs, stop_key="S2")
    h.raw_message("driver-delivered", h.t("14:05"), channel="sms", source_system=NORTHLINE_SMS,
                  sender=driver("redbird"), thread="sms-ray-dalton",
                  body=DELIVERED_BUT_TRACKING, refs=refs)
    h.track("ping-still-there", h.t("14:20"), "AT_DELIVERY", refs=refs, stop_key="S2",
            position="at the consignee, stationary")
    h.clock("end", h.t("18:00"))
    return h.build({
        "loads": {load: {"delivered_claimed": True, "conflict_fields": ["tracking_status"],
                         "requirements": {"POD": "OUTSTANDING"}, "invoice_eligible": False,
                         "needs_human": True, "timeline_kinds": ["conflict"]}},
        "unbound": [],
    })


RAW_HISTORY_FACTORIES = (
    r01_promise_then_silence, r02_quoted_promise, r03_wrong_load_number, r04_nothing_exact,
    r05_same_number_other_tenant, r06_rate_and_claimed_approval,
    r07_receiver_moved_the_appointment, r08_two_parties_one_inbox,
    r09_delivered_but_tracking_disagrees,
)


def build_raw_histories() -> list[Any]:
    """The nine raw histories, each built fresh. Building them also fills the reading tables."""
    return [factory() for factory in RAW_HISTORY_FACTORIES]


def raw_history_responder(overrides: dict[tuple[Task, str], Any] | None = None) -> Any:
    """A responder that reads the nine histories correctly. `overrides` replaces the reply for one
    `(task, text)` — how a test hands the spine a WRONG or hostile reading."""
    overrides = overrides or {}

    def respond(task: Task, request: Any) -> Any:
        text = getattr(request, "body", None) or request.text
        if (task, text) in overrides:
            reply = overrides[(task, text)]
            return reply(request) if callable(reply) else reply
        if task is Task.INTERPRET_MESSAGE:
            return READINGS.get(text)
        if task is Task.INTERPRET_DOCUMENT_TEXT:
            return DOCUMENT_READINGS.get(text)
        if task is Task.PROPOSE_ENTITY_CANDIDATES:
            scripted = CANDIDATE_READINGS.get(text)
            return scripted(request) if scripted is not None else {"candidates": []}
        return None
    return respond
