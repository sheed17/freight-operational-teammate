"""The hostile freight corpus: twenty synthetic load histories for small and midsize brokerages.

### THIS IS DEVELOPMENT INPUT, NOT EVIDENCE. Every company, person, number and document here is
invented. Nothing in this file validates a freight rule, and nothing here is a design-partner
observation. The corpus exists to be thrown at the freight-domain spine so that what breaks can be
seen, classified and fixed.

Each history is one load (occasionally with a sibling load, where the hostility needs two) written in
the order things ARRIVED. `expected` carries LABELED outcomes — what Neyma should have concluded —
and only what is labeled is asserted.

The histories are spaced four days apart per brokerage so that one brokerage's clock only ever moves
forward across the whole corpus, the way a real inbox does.
"""

from __future__ import annotations

from typing import Any

from .builders import (
    TMS,
    HistoryBuilder,
    bare_ref,
    bol_ref,
    charges,
    claims,
    commit,
    load_ref,
    movement,
    po_ref,
    quotes_rate,
    says,
    states_appointment,
    stop,
)
from .parties import (
    CARRIERS,
    CEDAR,
    CEDAR_OPS,
    CUSTOMERS,
    HARBOR,
    HARBOR_OPS,
    NORTHLINE,
    NORTHLINE_OPS,
    NORTHLINE_PODS,
    NORTHLINE_SMS,
    customer_contact,
    dispatcher,
    driver,
)

TRACKING = "tracking:macropoint"
HARBOR_TMS = "tms:haulerdesk"


def _cover(h: HistoryBuilder, *channels: str, health: str = "HEALTHY", minute: int = 0) -> None:
    """A channel-health reading for this history's window: day 0 through day 3."""
    for index, channel in enumerate(channels, start=minute):
        h.coverage(f"coverage-{channel}", h.t(f"05:{index:02d}"), channel, h.t("00:00"),
                   h.t("23:59", 3), health=health)


def _stops(h: HistoryBuilder, *, pickup: str, delivery: str, pickup_status: str = "REQUESTED",
           delivery_status: str = "REQUESTED", pickup_zone: str = "America/Chicago",
           delivery_zone: str = "America/Chicago",
           pickup_window: tuple[str, str] = ("10:00", "12:00"),
           delivery_window: tuple[str, str] = ("09:00", "11:00")) -> tuple[dict[str, Any], ...]:
    return (
        stop("S1", "PICKUP", 1, pickup, pickup_zone,
             appointment=(h.local(pickup_window[0]), h.local(pickup_window[1]), pickup_status)),
        stop("S2", "DELIVERY", 2, delivery, delivery_zone,
             appointment=(h.local(delivery_window[0], 1), h.local(delivery_window[1], 1),
                          delivery_status)),
    )


def _rate_con(h: HistoryBuilder, label: str, at: str, *, load: str, number: str, carrier: str,
              linehaul: int, via: str, signed: bool = True, movement_key: str | None = None,
              refs: tuple[dict[str, Any], ...] | None = None) -> None:
    mc = CARRIERS[carrier]["mc"]
    h.document(label, at, "RATE_CON",
               f"RATE CONFIRMATION {number} | {CARRIERS[carrier]['name']} {mc} | load {load} | "
               f"linehaul {linehaul} | signed={signed}",
               refs=refs if refs is not None else (load_ref(load),), via=via, signed=signed,
               extracted={"ratecon_number": number, "carrier_mc": mc,
                          "movement_key": movement_key, **charges(linehaul)})


def _invoice(h: HistoryBuilder, label: str, at: str, *, load: str, number: str, carrier: str,
             linehaul: int, via: str, accessorials: dict[str, int] | None = None,
             rendition: str = "a", refs: tuple[dict[str, Any], ...] | None = None) -> None:
    mc = CARRIERS[carrier]["mc"]
    total = linehaul + sum((accessorials or {}).values())
    h.document(label, at, "CARRIER_INVOICE",
               f"INVOICE {number} rendition {rendition} | {CARRIERS[carrier]['name']} {mc} | "
               f"load {load} | linehaul {linehaul} | {accessorials or {}} | total {total}",
               refs=refs if refs is not None else (load_ref(load),), via=via,
               extracted={"invoice_number": number, "carrier_mc": mc,
                          **charges(linehaul, 0, accessorials, total=total)})


def _pod(h: HistoryBuilder, label: str, at: str, *, load: str, via: str,
         refs: tuple[dict[str, Any], ...] | None = None, signed: bool = True,
         legible: bool = True, pages: tuple[int, int] = (1, 1), channel: str = "email",
         note: str = "") -> None:
    h.document(label, at, "POD", f"PROOF OF DELIVERY | load {load} | received in good order {note}",
               refs=refs if refs is not None else (load_ref(load),), via=via, signed=signed,
               legible=legible, pages=pages, channel=channel)


# ======================================================================================= Northline

def n01_baseline_detention() -> Any:
    h = HistoryBuilder(
        "N01", "Chicago to Detroit: a late update, then detention nobody authorized", NORTHLINE,
        day="2026-03-09", zone="America/Chicago",
        hostile=("promised_follow_up_late", "accessorial_not_authorized",
                 "rate_con_differs_from_invoice"))
    load, refs = "LD-48219", (load_ref("LD-48219"),)
    customer, carrier = CUSTOMERS["midwest_paper"], CARRIERS["redbird"]
    stops = _stops(h, pickup="Midwest Paper DC", delivery="Lakeshore Print",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   pickup_window=("12:00", "14:00"), delivery_zone="America/Detroit")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    h.tms("tender", h.t("08:14"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-7731", bol="BOL-55120", sell=charges(285000), stops=stops)
    h.tms("covered", h.t("09:03"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-7731", bol="BOL-55120", sell=charges(285000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-99812"),))
    _rate_con(h, "rate-con", h.t("09:20"), load=load, number="RC-48219", carrier="redbird",
              linehaul=240000, via=NORTHLINE_OPS)
    h.message("driver-arrived", h.t("12:44"), channel="sms", source_system=NORTHLINE_SMS,
              sender=driver("redbird"), thread="sms-ray-dalton", body="at the dock, checked in",
              refs=refs, asserts=(says("AT_PICKUP", "S1"),))
    h.message("driver-loaded", h.t("13:31"), channel="sms", source_system=NORTHLINE_SMS,
              sender=driver("redbird"), thread="sms-ray-dalton", body="loaded and rolling",
              refs=refs, asserts=(says("LOADED", "S1"),))
    h.track("ping-transit", h.t("17:12"), "IN_TRANSIT", refs=refs, position="I-94 E near mm 142")
    h.message("carrier-promise", h.t("18:05"), channel="sms", source_system=NORTHLINE_SMS,
              sender=dispatcher("redbird"), thread="sms-redbird-dispatch",
              body="checking with Ray, will update you by 8", refs=refs,
              asserts=(commit(h.t("20:00")),))
    h.message("carrier-delay", h.t("20:17"), channel="sms", source_system=NORTHLINE_SMS,
              sender=dispatcher("redbird"), thread="sms-redbird-dispatch",
              body="shipper held him 3 hrs this afternoon, we'll need detention 175", refs=refs,
              asserts=({"type": "delay", "reason": "held at the shipper"},
                       claims("DETENTION", 17500)))
    h.message("driver-delivered", h.t("09:48", 1), channel="sms", source_system=NORTHLINE_SMS,
              sender=driver("redbird"), thread="sms-ray-dalton", body="delivered, empty",
              refs=refs, asserts=(says("DELIVERED", "S2"),))
    _pod(h, "pod", h.t("10:03", 1), load=load, via=NORTHLINE_PODS)
    _invoice(h, "carrier-invoice", h.t("10:05", 1), load=load, number="RB-2291",
             carrier="redbird", linehaul=240000, accessorials={"DETENTION": 17500},
             via=NORTHLINE_OPS)
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "records": {"tender": {"disposition": "CREATED_LOAD", "load": load},
                    "pod": {"disposition": "BOUND", "load": load},
                    "carrier-invoice": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "movements": 1, "delivered_claimed": True,
            "documents": {"RATE_CON": 1, "POD": 1, "CARRIER_INVOICE": 1}, "payables": 1,
            "requirements": {"POD": "SATISFIED"},
            "expectations": {"arrival:S1": "DISCHARGED", "arrival:S2": "DISCHARGED",
                             "counterparty_update": "DISCHARGED", "document:POD": "DISCHARGED"},
            "conflict_fields": [], "reconciliation": ["DISCREPANT"],
            "discrepancy_codes": ["ACCESSORIAL_NOT_ON_RATE_CONFIRMATION"],
            "exception_types": ["accessorial_authorization_unresolved", "expectation_unmet"],
            "accessorials": {"DETENTION": "CLAIMED"}, "authorizations": 0,
            "invoice_eligible": True, "needs_human": True,
            "timeline_kinds": ["carrier_assignment", "expectation_overdue",
                               "expectation_discharged", "financial_reconciliation"]}},
        "unbound": [],
    })


def n02_duplicates() -> Any:
    h = HistoryBuilder(
        "N02", "Milwaukee to Indianapolis: everything arrives twice", NORTHLINE,
        day="2026-03-13", zone="America/Chicago",
        hostile=("duplicate_messages", "forwarded_repeated_email", "duplicate_invoice",
                 "quoted_commitment"))
    load, refs = "LD-48233", (load_ref("LD-48233"),)
    customer, carrier = CUSTOMERS["great_lakes_bev"], CARRIERS["ironwood"]
    stops = _stops(h, pickup="Great Lakes Beverage Plant 2", delivery="Hoosier Distributing",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED",
                   delivery_zone="America/Indiana/Indianapolis")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    h.tms("tender", h.t("07:40"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-4410", bol="BOL-55390", sell=charges(198000), stops=stops)
    h.redeliver("tender-redelivered", h.t("07:41"))
    h.tms("covered", h.t("08:30"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-4410", bol="BOL-55390", sell=charges(198000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-31077"),))
    _rate_con(h, "rate-con", h.t("08:52"), load=load, number="RC-48233", carrier="ironwood",
              linehaul=162000, via=NORTHLINE_OPS)
    h.redeliver("rate-con-redelivered", h.t("08:55"))
    h.track("ping-pickup", h.t("10:35"), "AT_PICKUP", refs=refs, stop_key="S1")
    h.track("ping-loaded", h.t("11:20"), "LOADED", refs=refs, stop_key="S1")
    h.message("carrier-promise", h.t("15:00"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("ironwood"), thread="re-load-48233", subject="RE: LD-48233",
              body="Luis delivers in the morning, I will send the POD by 11 tomorrow.", refs=refs,
              asserts=(commit(h.t("11:00", 1)),), external_id="<msg-48233-promise@ironwood>")
    h.track("ping-delivery", h.t("08:40", 1), "AT_DELIVERY", refs=refs, stop_key="S2")
    h.tms("delivered", h.t("09:55", 1), load=load, status="DELIVERED", version=3,
          customer=customer, po="PO-4410", bol="BOL-55390", sell=charges(198000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-31077", status="DELIVERED"),))
    h.message("carrier-pod-note", h.t("10:20", 1), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("ironwood"), thread="re-load-48233", subject="RE: LD-48233",
              body="POD attached, thanks.", refs=refs, external_id="<msg-48233-pod@ironwood>")
    _pod(h, "pod", h.t("10:21", 1), load=load, via=NORTHLINE_PODS)
    h.message("customer-forward", h.t("12:10", 1), channel="email", source_system=NORTHLINE_OPS,
              sender=customer_contact("great_lakes_bev"), thread="fwd-load-48233",
              subject="FW: RE: LD-48233",
              body="FYI, forwarding the carrier's note. > I will send the POD by 11 tomorrow.",
              refs=refs, forwarded=True, quoted=("<msg-48233-promise@ironwood>",),
              asserts=(commit(h.t("11:00", 1), quoted=True),))
    h.document("pod-forwarded", h.t("12:11", 1), "POD",
               f"PROOF OF DELIVERY | load {load} | received in good order ", refs=refs,
               via=NORTHLINE_OPS, signed=True, attached_to="customer-forward")
    _invoice(h, "carrier-invoice", h.t("13:00", 1), load=load, number="IW-7718",
             carrier="ironwood", linehaul=162000, via=NORTHLINE_OPS)
    _invoice(h, "carrier-invoice-resent", h.t("16:45", 1), load=load, number="IW-7718",
             carrier="ironwood", linehaul=162000, via=NORTHLINE_OPS, rendition="b")
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "records": {"tender-redelivered": {"disposition": "DUPLICATE"},
                    "rate-con-redelivered": {"disposition": "DUPLICATE"},
                    "pod-forwarded": {"disposition": "BOUND", "load": load},
                    "carrier-invoice-resent": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "documents": {"RATE_CON": 1, "POD": 1, "CARRIER_INVOICE": 2}, "payables": 1,
            "duplicate_invoices": 1, "duplicate_evidence": 1,
            "requirements": {"POD": "SATISFIED"},
            "expectations": {"arrival:S1": "DISCHARGED", "arrival:S2": "DISCHARGED",
                             "counterparty_update": "DISCHARGED", "document:POD": "DISCHARGED"},
            "conflict_fields": [], "exception_types": [], "reconciliation": ["RECONCILED"],
            "discrepancy_codes": [], "invoice_eligible": True, "needs_human": False}},
        "unbound": [],
    })


def n03_delivered_no_pod() -> Any:
    h = HistoryBuilder(
        "N03", "Joliet to Columbus: the TMS says delivered and the POD never comes", NORTHLINE,
        day="2026-03-17", zone="America/Chicago",
        hostile=("tms_delivered_pod_absent", "document_overdue"))
    load, refs = "LD-48260", (load_ref("LD-48260"),)
    customer, carrier = CUSTOMERS["prairie_ag"], CARRIERS["bluegrass"]
    stops = _stops(h, pickup="Prairie Ag Joliet", delivery="Scioto Farm Supply",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS, TRACKING)
    h.tms("tender", h.t("08:00"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-2207", bol="BOL-55612", sell=charges(221000), stops=stops)
    h.tms("covered", h.t("08:45"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-2207", bol="BOL-55612", sell=charges(221000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-40218"),))
    _rate_con(h, "rate-con", h.t("09:05"), load=load, number="RC-48260", carrier="bluegrass",
              linehaul=184000, via=NORTHLINE_OPS)
    h.track("ping-loaded", h.t("11:10"), "LOADED", refs=refs, stop_key="S1")
    h.track("ping-transit", h.t("16:00"), "IN_TRANSIT", refs=refs, position="I-70 E near mm 88")
    h.tms("delivered", h.t("10:40", 1), load=load, status="DELIVERED", version=3,
          customer=customer, po="PO-2207", bol="BOL-55612", sell=charges(221000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-40218", status="DELIVERED"),))
    _invoice(h, "carrier-invoice", h.t("14:00", 1), load=load, number="BG-1190",
             carrier="bluegrass", linehaul=184000, via=NORTHLINE_OPS)
    h.clock("a-day-later", h.t("12:00", 2))
    return h.build({
        "loads": {load: {
            "reported_status": "DELIVERED", "delivered_claimed": True,
            "documents": {"RATE_CON": 1, "CARRIER_INVOICE": 1},
            "requirements": {"POD": "OUTSTANDING"},
            "expectations": {"document:POD": "OVERDUE"},
            "exception_types": ["expectation_unmet"], "reconciliation": ["RECONCILED"],
            "invoice_eligible": False, "needs_human": True,
            "timeline_kinds": ["expectation_overdue"]}},
        "unbound": [],
    })


def n04_pod_before_delivered() -> Any:
    h = HistoryBuilder(
        "N04", "Rockford to St. Louis: the POD arrives before the TMS says delivered", NORTHLINE,
        day="2026-03-21", zone="America/Chicago",
        hostile=("pod_before_tms_delivered",))
    load, refs = "LD-48277", (load_ref("LD-48277"),)
    customer, carrier = CUSTOMERS["midwest_paper"], CARRIERS["summit"]
    stops = _stops(h, pickup="Midwest Paper Rockford", delivery="Gateway Packaging")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS)
    h.tms("tender", h.t("07:55"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-7745", bol="BOL-55701", sell=charges(142000), stops=stops)
    h.tms("covered", h.t("08:40"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-7745", bol="BOL-55701", sell=charges(142000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-52090"),))
    _rate_con(h, "rate-con", h.t("09:00"), load=load, number="RC-48277", carrier="summit",
              linehaul=118000, via=NORTHLINE_OPS)
    h.tms("in-transit", h.t("15:00"), load=load, status="IN_TRANSIT", version=3,
          customer=customer, po="PO-7745", bol="BOL-55701", sell=charges(142000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-52090", status="PICKED_UP"),))
    _pod(h, "pod", h.t("08:50", 1), load=load, via=NORTHLINE_PODS)
    h.tms("delivered", h.t("13:30", 1), load=load, status="DELIVERED", version=4,
          customer=customer, po="PO-7745", bol="BOL-55701", sell=charges(142000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-52090", status="DELIVERED"),))
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "records": {"pod": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "reported_status": "DELIVERED", "delivered_claimed": True,
            "documents": {"RATE_CON": 1, "POD": 1}, "requirements": {"POD": "SATISFIED"},
            "expectations": {}, "exception_types": [], "reconciliation": ["COMPUTED"],
            "invoice_eligible": True, "needs_human": False}},
        "unbound": [],
    })


def n05_contradictory_appointment() -> Any:
    h = HistoryBuilder(
        "N05", "Gary to Louisville: three sources, two delivery appointments", NORTHLINE,
        day="2026-03-25", zone="America/Chicago",
        hostile=("contradictory_appointment_times",))
    load, refs = "LD-48305", (load_ref("LD-48305"),)
    customer, carrier = CUSTOMERS["great_lakes_bev"], CARRIERS["redbird"]
    zone = "America/Kentucky/Louisville"
    stops = _stops(h, pickup="Great Lakes Beverage Gary", delivery="Derby City Cold Storage",
                   pickup_status="CONFIRMED", delivery_zone=zone)
    _cover(h, NORTHLINE_OPS, TRACKING)
    h.tms("tender", h.t("08:05"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-4455", bol="BOL-55820", sell=charges(176000), stops=stops)
    h.tms("covered", h.t("08:50"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-4455", bol="BOL-55820", sell=charges(176000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-99901"),))
    h.track("ping-pickup", h.t("10:50"), "AT_PICKUP", refs=refs, stop_key="S1")
    h.appointment("portal-appointment", h.t("11:30"), "S2", h.local("13:00", 1),
                  h.local("15:00", 1), zone, refs=refs)
    h.message("carrier-appointment", h.t("12:15"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("redbird"), thread="re-load-48305", subject="RE: LD-48305 appt",
              body="Confirming we are set for 0900 delivery tomorrow.", refs=refs,
              asserts=(states_appointment("S2", h.local("09:00", 1), h.local("11:00", 1), zone),))
    h.clock("end", h.t("18:00"))
    return h.build({
        "loads": {load: {
            "conflict_fields": ["window"],
            "appointment_conditions": {"S1": "consistent", "S2": "conflicting"},
            "expectations": {"arrival:S1": "DISCHARGED"}, "needs_human": True,
            "invoice_eligible": False, "timeline_kinds": ["conflict", "appointment"]}},
        "unbound": [],
    })


def n06_rate_con_vs_invoice() -> Any:
    h = HistoryBuilder(
        "N06", "Peoria to Memphis: the invoice bills the phone number, not the rate con",
        NORTHLINE, day="2026-03-29", zone="America/Chicago",
        hostile=("rate_con_differs_from_invoice", "conversational_rate_is_not_authority"))
    load, refs = "LD-48340", (load_ref("LD-48340"),)
    customer, carrier = CUSTOMERS["prairie_ag"], CARRIERS["ironwood"]
    stops = _stops(h, pickup="Prairie Ag Peoria", delivery="Delta Crop Services")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS)
    h.tms("tender", h.t("07:30"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-2251", bol="BOL-56010", sell=charges(248000), stops=stops)
    h.tms("covered", h.t("08:20"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-2251", bol="BOL-56010", sell=charges(248000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-31200"),))
    h.message("carrier-rate-talk", h.t("09:10"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("ironwood"), thread="re-load-48340", subject="RE: LD-48340",
              body="Per our call we are at 2150 all in on this one.", refs=refs,
              asserts=(quotes_rate(215000),))
    _rate_con(h, "rate-con", h.t("09:40"), load=load, number="RC-48340", carrier="ironwood",
              linehaul=195000, via=NORTHLINE_OPS)
    h.tms("delivered", h.t("11:15", 1), load=load, status="DELIVERED", version=3,
          customer=customer, po="PO-2251", bol="BOL-56010", sell=charges(248000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-31200", status="DELIVERED"),))
    _pod(h, "pod", h.t("11:40", 1), load=load, via=NORTHLINE_PODS)
    _invoice(h, "carrier-invoice", h.t("15:20", 1), load=load, number="IW-7790",
             carrier="ironwood", linehaul=215000, via=NORTHLINE_OPS)
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "loads": {load: {
            "payables": 1, "reconciliation": ["DISCREPANT"],
            "discrepancy_codes": ["LINEHAUL_MISMATCH"],
            "conflict_fields": ["owed_to_carrier.linehaul"], "exception_types": [],
            "requirements": {"POD": "SATISFIED"}, "invoice_eligible": True, "needs_human": True}},
        "unbound": [],
    })


def n07_wrong_load_document_candidate() -> Any:
    h = HistoryBuilder(
        "N07", "Two Kenosha loads: a POD carrying one load's number and the other's BOL",
        NORTHLINE, day="2026-04-02", zone="America/Chicago",
        hostile=("wrong_load_document_candidate", "human_binding"))
    customer, carrier = CUSTOMERS["great_lakes_bev"], CARRIERS["bluegrass"]
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS)
    for load, po, bol, pro, at in (("LD-48301", "PO-4470", "BOL-60301", "PRO-40301", "07:20"),
                                   ("LD-48302", "PO-4471", "BOL-60302", "PRO-40302", "07:25")):
        stops = _stops(h, pickup="Great Lakes Beverage Kenosha", delivery=f"Consignee {load[-1]}")
        h.tms(f"tender-{load}", h.t(at), load=load, status="COVERED", version=1,
              customer=customer, po=po, bol=bol, sell=charges(131000), stops=stops,
              movements=(movement("M1", carrier, pro=pro),))
    for load, po, bol, pro, at in (("LD-48301", "PO-4470", "BOL-60301", "PRO-40301", "09:30"),
                                   ("LD-48302", "PO-4471", "BOL-60302", "PRO-40302", "09:45")):
        stops = _stops(h, pickup="Great Lakes Beverage Kenosha", delivery=f"Consignee {load[-1]}")
        h.tms(f"delivered-{load}", h.t(at, 1), load=load, status="DELIVERED", version=2,
              customer=customer, po=po, bol=bol, sell=charges(131000), stops=stops,
              movements=(movement("M1", carrier, pro=pro, status="DELIVERED"),))
    _pod(h, "pod", h.t("10:30", 1), load="LD-48301", via=NORTHLINE_PODS,
         refs=(load_ref("LD-48301"), bol_ref("BOL-60302")), note="BOL-60302")
    h.human("triage-binds-pod", h.t("14:00", 1), "priya.nair", "bind_observation",
            refs=(load_ref("LD-48302"),),
            target={"source_system": NORTHLINE_PODS, "external_id": h.records[-1].external_id},
            note="BOL-60302 is on the paper; the load number was typed wrong by the carrier")
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "records": {
            "pod": {"disposition": "AMBIGUOUS", "candidates": ["LD-48301", "LD-48302"],
                    "ambiguity": "references_name_different_loads"},
            "triage-binds-pod": {"disposition": "BOUND", "load": "LD-48302"}},
        "loads": {
            "LD-48302": {"documents": {"POD": 1}, "requirements": {"POD": "SATISFIED"},
                         "expectations": {"document:POD": "DISCHARGED"},
                         "invoice_eligible": True},
            "LD-48301": {"documents": {}, "requirements": {"POD": "OUTSTANDING"},
                         "expectations": {"document:POD": "OVERDUE"},
                         "invoice_eligible": False, "needs_human": True}},
        "unbound": [],
    })


def n08_two_plausible_loads() -> Any:
    h = HistoryBuilder(
        "N08", "One order, two loads, one PO: a message that could mean either", NORTHLINE,
        day="2026-04-06", zone="America/Chicago",
        hostile=("two_plausible_loads", "ambiguous_reference_stays_ambiguous",
                 "unqualified_reference", "order_split_across_loads"))
    customer, carrier = CUSTOMERS["prairie_ag"], CARRIERS["summit"]
    _cover(h, NORTHLINE_OPS, NORTHLINE_SMS)
    for load, bol, pro, at in (("LD-48410", "BOL-60410", "PRO-52410", "07:10"),
                               ("LD-48411", "BOL-60411", "PRO-52411", "07:12")):
        stops = _stops(h, pickup="Prairie Ag Decatur", delivery="Wabash Valley Co-op")
        h.tms(f"tender-{load}", h.t(at), load=load, status="COVERED", version=1,
              customer=customer, po="PO-8850", bol=bol, order_id="ORD-5521",
              sell=charges(119000), stops=stops, movements=(movement("M1", carrier, pro=pro),))
    po = po_ref(customer["id"], "PO-8850")
    h.message("customer-po-only", h.t("10:05"), channel="email", source_system=NORTHLINE_OPS,
              sender=customer_contact("prairie_ag"), thread="po-8850-delivery",
              subject="PO-8850 delivery", body="Please push delivery on PO-8850 to Thursday.",
              refs=(po,))
    h.message("text-bare-number", h.t("10:40"), channel="sms", source_system=NORTHLINE_SMS,
              sender=("driver", "unknown", "+1-555-0100"), thread="sms-unknown-0100",
              body="48410 running 2 hrs behind", refs=(bare_ref("48410"),))
    h.message("customer-po-and-load", h.t("11:15"), channel="email", source_system=NORTHLINE_OPS,
              sender=customer_contact("prairie_ag"), thread="po-8850-delivery",
              subject="RE: PO-8850 delivery",
              body="To be clear I mean the second truck, LD-48411.",
              refs=(po, load_ref("LD-48411")))
    h.clock("end", h.t("18:00"))
    return h.build({
        "records": {
            "customer-po-only": {"disposition": "AMBIGUOUS",
                                 "candidates": ["LD-48410", "LD-48411"],
                                 "ambiguity": "one_reference_names_several_loads"},
            "text-bare-number": {"disposition": "UNBOUND"},
            "customer-po-and-load": {"disposition": "BOUND", "load": "LD-48411"}},
        "loads": {"LD-48410": {"needs_human": True}, "LD-48411": {"needs_human": True}},
        "unbound": ["customer-po-only", "text-bare-number"],
    })


def n09_silence_and_blind_tracking() -> Any:
    h = HistoryBuilder(
        "N09", "Elgin to Des Moines: a silent carrier, and a tracking feed that was down",
        NORTHLINE, day="2026-04-10", zone="America/Chicago",
        hostile=("carrier_silence", "promise_never_arrives", "tracking_unavailable"))
    load, refs = "LD-48455", (load_ref("LD-48455"),)
    customer, carrier = CUSTOMERS["midwest_paper"], CARRIERS["redbird"]
    stops = _stops(h, pickup="Midwest Paper Elgin", delivery="Hawkeye Print Works",
                   pickup_status="CONFIRMED")
    _cover(h, NORTHLINE_SMS, NORTHLINE_OPS)
    _cover(h, TRACKING, health="DOWN", minute=10)
    h.tms("tender", h.t("07:00"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-7780", bol="BOL-56190", sell=charges(164000), stops=stops)
    h.tms("covered", h.t("07:50"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-7780", bol="BOL-56190", sell=charges(164000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-99955"),))
    h.message("carrier-promise", h.t("09:20"), channel="sms", source_system=NORTHLINE_SMS,
              sender=dispatcher("redbird"), thread="sms-redbird-dispatch",
              body="Ray is about 30 out, I'll text you by 11 once he's checked in", refs=refs,
              asserts=(commit(h.t("11:00")),))
    h.clock("midday", h.t("12:30"))
    return h.build({
        "loads": {load: {
            "delivered_claimed": False,
            "expectations": {"arrival:S1": "INDETERMINATE", "counterparty_update": "OVERDUE"},
            "exception_types": ["expectation_unmet"], "needs_human": True,
            "timeline_kinds": ["expectation_overdue", "expectation_indeterminate"]}},
        "unbound": [],
    })


def n10_corrected_reference() -> Any:
    h = HistoryBuilder(
        "N10", "Aurora to Toledo: the TMS renumbers the load, and a PO was keyed wrong",
        NORTHLINE, day="2026-04-14", zone="America/Chicago",
        hostile=("corrected_load_number", "stale_reference", "corrected_reference_by_human"))
    customer, carrier = CUSTOMERS["great_lakes_bev"], CARRIERS["ironwood"]
    stops = _stops(h, pickup="Great Lakes Beverage Aurora", delivery="Maumee Bottling",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_OPS)
    h.tms("tender", h.t("07:45"), load="LD-48519", status="TENDERED", version=1,
          customer=customer, po="PO-4504", bol="BOL-56300", sell=charges(187000), stops=stops)
    h.tms("covered", h.t("08:30"), load="LD-48519", status="COVERED", version=2,
          customer=customer, po="PO-4504", bol="BOL-56300", sell=charges(187000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-31519"),))
    h.message("carrier-old-number", h.t("09:00"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("ironwood"), thread="re-load-48519", subject="RE: LD-48519",
              body="Driver assigned, Luis will be there at 10.", refs=(load_ref("LD-48519"),))
    h.tms("renumbered", h.t("10:10"), load="LD-48591", status="COVERED", version=3,
          previous_load_ref="LD-48519", customer=customer, po="PO-4504", bol="BOL-56300",
          sell=charges(187000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-31519"),))
    h.message("carrier-new-number", h.t("11:00"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("ironwood"), thread="re-load-48591", subject="RE: LD-48591",
              body="Loaded, on the way.", refs=(load_ref("LD-48591"),),
              asserts=(says("LOADED", "S1"),))
    h.message("carrier-stale-number", h.t("13:20"), channel="email", source_system=NORTHLINE_OPS,
              sender=dispatcher("ironwood"), thread="re-load-48519", subject="RE: LD-48519",
              body="ETA 9am tomorrow on this one.", refs=(load_ref("LD-48519"),))
    h.human("ops-corrects-po", h.t("14:00"), "dana.ortiz", "correct_reference",
            refs=(load_ref("LD-48591"),),
            wrong_reference=po_ref(customer["id"], "PO-4504"),
            right_reference=po_ref(customer["id"], "PO-4540"),
            note="the PO was keyed as 4504; the customer's order says 4540")
    h.message("customer-right-po", h.t("15:30"), channel="email", source_system=NORTHLINE_OPS,
              sender=customer_contact("great_lakes_bev"), thread="po-4540",
              subject="PO-4540 status", body="Any update on PO-4540?",
              refs=(po_ref(customer["id"], "PO-4540"),))
    h.clock("end", h.t("18:00"))
    return h.build({
        "records": {
            "carrier-old-number": {"disposition": "BOUND", "load": "LD-48591"},
            "renumbered": {"disposition": "BOUND", "load": "LD-48591"},
            "carrier-new-number": {"disposition": "BOUND", "load": "LD-48591"},
            "carrier-stale-number": {"disposition": "AMBIGUOUS", "candidates": ["LD-48591"],
                                     "ambiguity": "single_weak"},
            "customer-right-po": {"disposition": "BOUND", "load": "LD-48591"}},
        "loads": {"LD-48591": {"retired_references": ["LD-48519", "PO-4504"],
                               "needs_human": True,
                               "timeline_kinds": ["reference_change", "ambiguous_binding"]}},
        "unbound": ["carrier-stale-number"],
    })


def n11_incomplete_documents() -> Any:
    h = HistoryBuilder(
        "N11", "Kankakee to Evansville: three documents arrive and none of them is a POD",
        NORTHLINE, day="2026-04-18", zone="America/Chicago",
        hostile=("incomplete_documents", "unsigned_bol_is_not_a_pod", "illegible_document"))
    load, refs = "LD-48620", (load_ref("LD-48620"),)
    customer, carrier = CUSTOMERS["prairie_ag"], CARRIERS["bluegrass"]
    stops = _stops(h, pickup="Prairie Ag Kankakee", delivery="Ohio Valley Seed")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS, NORTHLINE_SMS)
    h.tms("tender", h.t("07:35"), load=load, status="COVERED", version=1, customer=customer,
          po="PO-2290", bol="BOL-56440", sell=charges(153000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-40620"),))
    h.tms("delivered", h.t("09:30", 1), load=load, status="DELIVERED", version=2,
          customer=customer, po="PO-2290", bol="BOL-56440", sell=charges(153000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-40620", status="DELIVERED"),))
    _pod(h, "pod-page-one-only", h.t("10:00", 1), load=load, via=NORTHLINE_PODS, pages=(1, 2),
         note="page 1 of 2")
    h.document("bol-unsigned", h.t("10:20", 1), "BOL",
               f"BILL OF LADING BOL-56440 | load {load} | consignee signature: (blank)",
               refs=refs, via=NORTHLINE_PODS, signed=False)
    _pod(h, "pod-photo-illegible", h.t("11:00", 1), load=load, via=NORTHLINE_SMS, channel="sms",
         legible=False, note="phone photo, glare")
    h.clock("a-day-later", h.t("12:00", 2))
    return h.build({
        "records": {"pod-page-one-only": {"disposition": "BOUND", "load": load},
                    "bol-unsigned": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "documents": {"POD": 2, "BOL": 1}, "requirements": {"POD": "OUTSTANDING"},
            "expectations": {"document:POD": "OVERDUE"},
            "exception_types": ["document_unusable", "expectation_unmet"],
            "invoice_eligible": False, "needs_human": True}},
        "unbound": [],
    })


def n12_accessorial_authorization() -> Any:
    h = HistoryBuilder(
        "N12", "Bloomington to Nashville: a carrier says it was approved; one charge was",
        NORTHLINE, day="2026-04-22", zone="America/Chicago",
        hostile=("accessorial_not_authorized", "counterparty_asserts_approval",
                 "human_authorization"))
    load, refs = "LD-48702", (load_ref("LD-48702"),)
    customer, carrier = CUSTOMERS["midwest_paper"], CARRIERS["summit"]
    stops = _stops(h, pickup="Midwest Paper Bloomington", delivery="Cumberland Press")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS, NORTHLINE_SMS)
    h.tms("tender", h.t("07:15"), load=load, status="COVERED", version=1, customer=customer,
          po="PO-7799", bol="BOL-56555", sell=charges(212000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-52702"),))
    _rate_con(h, "rate-con", h.t("07:40"), load=load, number="RC-48702", carrier="summit",
              linehaul=180000, via=NORTHLINE_OPS)
    h.message("carrier-lumper-claim", h.t("16:00"), channel="sms", source_system=NORTHLINE_SMS,
              sender=dispatcher("summit"), thread="sms-summit-dispatch",
              body="lumper was 240 at the receiver, your guy already approved it on the phone",
              refs=refs, asserts=(claims("LUMPER", 24000, approved=True),))
    h.human("ap-authorizes-lumper", h.t("16:30"), "marcus.reid", "authorize_accessorial",
            refs=refs, charge_type="LUMPER", amount_cap_minor=24000, currency="USD",
            direction="OUT", note="confirmed with the receiver; lumper receipt requested")
    h.tms("delivered", h.t("10:00", 1), load=load, status="DELIVERED", version=2,
          customer=customer, po="PO-7799", bol="BOL-56555", sell=charges(212000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-52702", status="DELIVERED"),))
    _pod(h, "pod", h.t("10:30", 1), load=load, via=NORTHLINE_PODS)
    _invoice(h, "carrier-invoice", h.t("14:10", 1), load=load, number="SL-3302",
             carrier="summit", linehaul=180000,
             accessorials={"LUMPER": 24000, "DETENTION": 15000}, via=NORTHLINE_OPS)
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "records": {"ap-authorizes-lumper": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "accessorials": {"LUMPER": "AUTHORIZED", "DETENTION": "CLAIMED"},
            "authorizations": 1, "reconciliation": ["DISCREPANT"],
            "discrepancy_codes": ["ACCESSORIAL_NOT_ON_RATE_CONFIRMATION"],
            "exception_types": ["accessorial_authorization_unresolved",
                                "counterparty_self_authorization"],
            "invoice_eligible": True, "needs_human": True}},
        "unbound": [],
    })


def n13_conflicting_tracking() -> Any:
    h = HistoryBuilder(
        "N13", "Naperville to Grand Rapids: the driver says delivered, the truck says otherwise",
        NORTHLINE, day="2026-04-26", zone="America/Chicago",
        hostile=("conflicting_tracking_sources", "driver_assertion_is_not_delivery_proof"))
    load, refs = "LD-48760", (load_ref("LD-48760"),)
    customer, carrier = CUSTOMERS["great_lakes_bev"], CARRIERS["redbird"]
    stops = _stops(h, pickup="Great Lakes Beverage Naperville", delivery="Furniture City Bev",
                   pickup_status="CONFIRMED", pickup_window=("06:00", "08:00"),
                   delivery_zone="America/Detroit")
    _cover(h, NORTHLINE_SMS, NORTHLINE_PODS, TRACKING)
    h.tms("tender", h.t("05:30"), load=load, status="COVERED", version=1, customer=customer,
          po="PO-4530", bol="BOL-56680", sell=charges(139000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-99760"),))
    h.track("ping-pickup", h.t("06:40"), "AT_PICKUP", refs=refs, stop_key="S1")
    h.track("ping-transit", h.t("11:00"), "IN_TRANSIT", refs=refs, position="I-196 N near mm 20")
    h.message("driver-delivered", h.t("14:05"), channel="sms", source_system=NORTHLINE_SMS,
              sender=driver("redbird"), thread="sms-ray-dalton", body="delivered", refs=refs,
              asserts=(says("DELIVERED", "S2"),))
    h.track("ping-still-moving", h.t("14:40"), "IN_TRANSIT", refs=refs,
            position="38 mi west of the consignee, moving")
    h.clock("end", h.t("18:00"))
    return h.build({
        "loads": {load: {
            "delivered_claimed": True, "conflict_fields": ["tracking_status"],
            "requirements": {"POD": "OUTSTANDING"},
            # Labeled as of the END OF THE CORPUS: this brokerage's clock keeps moving through its
            # later histories, the configured deadline passes, and no POD ever comes.
            "expectations": {"arrival:S1": "DISCHARGED", "document:POD": "OVERDUE"},
            "invoice_eligible": False, "needs_human": True, "timeline_kinds": ["conflict"]}},
        "unbound": [],
    })


def n14_late_and_stale() -> Any:
    h = HistoryBuilder(
        "N14", "Waukegan to Fort Wayne: paper before the load exists, and news out of order",
        NORTHLINE, day="2026-04-30", zone="America/Chicago",
        hostile=("late_arriving_information", "stale_information", "record_before_load_exists"))
    load, refs = "LD-48801", (load_ref("LD-48801"),)
    customer, carrier = CUSTOMERS["prairie_ag"], CARRIERS["ironwood"]
    stops = _stops(h, pickup="Prairie Ag Waukegan", delivery="Three Rivers Feed",
                   delivery_zone="America/Indiana/Indianapolis")
    _cover(h, NORTHLINE_OPS, TRACKING)
    _rate_con(h, "rate-con-early", h.t("07:30"), load=load, number="RC-48801", carrier="ironwood",
              linehaul=127000, via=NORTHLINE_OPS)
    h.tms("tender", h.t("08:10"), load=load, status="COVERED", version=1, customer=customer,
          po="PO-2310", bol="BOL-56790", sell=charges(151000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-31801"),))
    h.track("ping-pickup", h.t("11:52"), "AT_PICKUP", refs=refs, stop_key="S1",
            as_of=h.t("11:50"))
    h.tms("in-transit", h.t("13:02"), load=load, status="IN_TRANSIT", version=3,
          customer=customer, po="PO-2310", bol="BOL-56790", sell=charges(151000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-31801", status="PICKED_UP"),),
          as_of=h.t("13:00"))
    h.track("ping-transit", h.t("14:31"), "IN_TRANSIT", refs=refs, position="US-30 E near mm 64",
            as_of=h.t("14:30"))
    h.track("ping-loaded-late", h.t("15:10"), "LOADED", refs=refs, stop_key="S1",
            as_of=h.t("12:40"))
    h.tms("dispatched-stale", h.t("15:30"), load=load, status="DISPATCHED", version=2,
          customer=customer, po="PO-2310", bol="BOL-56790", sell=charges(151000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-31801"),), as_of=h.t("12:00"))
    h.clock("end", h.t("18:00"))
    return h.build({
        "records": {"rate-con-early": {"disposition": "UNBOUND"},
                    "dispatched-stale": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "reported_status": "IN_TRANSIT", "documents": {"RATE_CON": 1},
            "conflict_fields": [], "reconciliation": ["COMPUTED"], "needs_human": False}},
        "unbound": [],
    })


def n15_repower() -> Any:
    h = HistoryBuilder(
        "N15", "Champaign to Lexington: the first carrier falls off and the load is re-covered",
        NORTHLINE, day="2026-05-04", zone="America/Chicago",
        hostile=("carrier_falls_off", "one_load_two_movements"))
    load = "LD-48890"
    customer = CUSTOMERS["midwest_paper"]
    first, second = CARRIERS["ironwood"], CARRIERS["bluegrass"]
    stops = _stops(h, pickup="Midwest Paper Champaign", delivery="Bluegrass Printing Co",
                   delivery_zone="America/New_York")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS)
    h.tms("tender", h.t("07:00"), load=load, status="COVERED", version=1, customer=customer,
          po="PO-7811", bol="BOL-56900", sell=charges(263000), stops=stops,
          movements=(movement("M1", first, pro="PRO-31890"),))
    _rate_con(h, "rate-con-first", h.t("07:25"), load=load, number="RC-48890-A",
              carrier="ironwood", linehaul=210000, via=NORTHLINE_OPS, movement_key="M1")
    h.tms("recovered", h.t("11:40"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-7811", bol="BOL-56900", sell=charges(263000), stops=stops,
          movements=(movement("M1", first, pro="PRO-31890", status="FELL_OFF"),
                     movement("M2", second, pro="PRO-40890")))
    _rate_con(h, "rate-con-second", h.t("12:05"), load=load, number="RC-48890-B",
              carrier="bluegrass", linehaul=235000, via=NORTHLINE_OPS, movement_key="M2")
    h.tms("delivered", h.t("12:30", 1), load=load, status="DELIVERED", version=3,
          customer=customer, po="PO-7811", bol="BOL-56900", sell=charges(263000), stops=stops,
          movements=(movement("M1", first, pro="PRO-31890", status="FELL_OFF"),
                     movement("M2", second, pro="PRO-40890", status="DELIVERED")))
    _pod(h, "pod", h.t("13:00", 1), load=load, via=NORTHLINE_PODS)
    _invoice(h, "carrier-invoice", h.t("15:00", 1), load=load, number="BG-1244",
             carrier="bluegrass", linehaul=235000, via=NORTHLINE_OPS)
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "loads": {load: {
            "movements": 2, "payables": 1,
            "documents": {"RATE_CON": 2, "POD": 1, "CARRIER_INVOICE": 1},
            "reconciliation": ["COMPUTED", "RECONCILED"], "requirements": {"POD": "SATISFIED"},
            "conflict_fields": [], "invoice_eligible": True, "needs_human": False,
            "timeline_kinds": ["carrier_fell_off", "carrier_assignment"]}},
        "unbound": [],
    })


def n16_wrong_load_corrected() -> Any:
    h = HistoryBuilder(
        "N16", "Two Springfield loads: a POD bound by its number to the wrong one, then corrected",
        NORTHLINE, day="2026-05-08", zone="America/Chicago",
        hostile=("wrong_load_document_bound", "correction_supersedes_without_deleting"))
    customer, carrier = CUSTOMERS["midwest_paper"], CARRIERS["summit"]
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS)
    loads = (("LD-48720", "PO-7760", "BOL-57020", "PRO-52720"),
             ("LD-48721", "PO-7761", "BOL-57021", "PRO-52721"))
    for index, (load, po, bol, pro) in enumerate(loads):
        stops = _stops(h, pickup="Midwest Paper Springfield", delivery=f"Capitol Print {index}")
        h.tms(f"tender-{load}", h.t(f"07:1{index}"), load=load, status="COVERED", version=1,
              customer=customer, po=po, bol=bol, sell=charges(128000), stops=stops,
              movements=(movement("M1", carrier, pro=pro),))
    for index, (load, po, bol, pro) in enumerate(loads):
        stops = _stops(h, pickup="Midwest Paper Springfield", delivery=f"Capitol Print {index}")
        h.tms(f"delivered-{load}", h.t(f"10:0{index}", 1), load=load, status="DELIVERED",
              version=2, customer=customer, po=po, bol=bol, sell=charges(128000), stops=stops,
              movements=(movement("M1", carrier, pro=pro, status="DELIVERED"),))
    _pod(h, "pod", h.t("11:00", 1), load="LD-48720", via=NORTHLINE_PODS,
         note="consignee stamp Capitol Print 1")
    h.human("triage-corrects-pod", h.t("15:00", 1), "priya.nair", "correct_binding",
            refs=(load_ref("LD-48721"),),
            target={"source_system": NORTHLINE_PODS, "external_id": h.records[-1].external_id},
            note="the consignee stamp is Capitol Print 1, which is LD-48721")
    h.clock("two-days-later", h.t("12:00", 3))
    return h.build({
        "records": {"pod": {"disposition": "BOUND", "load": "LD-48720"},
                    "triage-corrects-pod": {"disposition": "BOUND", "load": "LD-48721"}},
        "loads": {
            "LD-48721": {"documents": {"POD": 1}, "requirements": {"POD": "SATISFIED"},
                         "expectations": {"document:POD": "DISCHARGED"},
                         "invoice_eligible": True},
            "LD-48720": {"documents": {}, "requirements": {"POD": "OUTSTANDING"},
                         "expectations": {"document:POD": "OVERDUE"},
                         "invoice_eligible": False, "needs_human": True,
                         "timeline_kinds": ["binding_correction"]}},
        "unbound": [],
    })


# ======================================================================================= Cedar Ridge

def c01_same_identifiers_other_tenant() -> Any:
    h = HistoryBuilder(
        "C01", "Cedar Ridge's own LD-48219: every identifier Northline also uses", CEDAR,
        day="2026-03-09", zone="America/Chicago",
        hostile=("same_external_id_under_two_tenants", "tms_delivered_pod_absent",
                 "no_configured_deadline"))
    load, refs = "LD-48219", (load_ref("LD-48219"),)
    customer, carrier = CUSTOMERS["cedar_building"], CARRIERS["redbird"]
    stops = _stops(h, pickup="Ozark Building Products", delivery="Little Rock Lumber Yard")
    _cover(h, CEDAR_OPS)
    h.tms("tender", h.t("08:20"), load=load, status="TENDERED", version=1, customer=customer,
          po="PO-7731", bol="BOL-55120", sell=charges(268000), stops=stops)
    h.tms("covered", h.t("09:10"), load=load, status="COVERED", version=2, customer=customer,
          po="PO-7731", bol="BOL-55120", sell=charges(268000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-99812"),))
    _rate_con(h, "rate-con", h.t("09:30"), load=load, number="RC-48219", carrier="redbird",
              linehaul=230000, via=CEDAR_OPS)
    h.track("ping-transit", h.t("16:20"), "IN_TRANSIT", refs=refs, position="I-40 W near mm 201")
    h.tms("delivered", h.t("11:00", 1), load=load, status="DELIVERED", version=3,
          customer=customer, po="PO-7731", bol="BOL-55120", sell=charges(268000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-99812", status="DELIVERED"),))
    _invoice(h, "carrier-invoice", h.t("13:30", 1), load=load, number="RB-2291",
             carrier="redbird", linehaul=230000, via=CEDAR_OPS)
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "records": {"tender": {"disposition": "CREATED_LOAD", "load": load},
                    "rate-con": {"disposition": "BOUND", "load": load},
                    "carrier-invoice": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "documents": {"RATE_CON": 1, "CARRIER_INVOICE": 1}, "payables": 1,
            "requirements": {"POD": "OUTSTANDING"}, "expectations": {},
            "exception_types": [], "reconciliation": ["RECONCILED"],
            "invoice_eligible": False, "needs_human": True}},
        "unbound": [],
    })


def c02_no_rate_confirmation() -> Any:
    h = HistoryBuilder(
        "C02", "Fayetteville to Tulsa: an invoice arrives and there was never a rate con", CEDAR,
        day="2026-03-13", zone="America/Chicago",
        hostile=("no_rate_confirmation", "conversational_rate_is_not_authority",
                 "tms_carrier_pay_is_not_authority"))
    load, refs = "LD-50033", (load_ref("LD-50033"),)
    customer, carrier = CUSTOMERS["cedar_building"], CARRIERS["bluegrass"]
    stops = _stops(h, pickup="Ozark Building Fayetteville", delivery="Green Country Supply")
    _cover(h, CEDAR_OPS)
    h.tms("tender", h.t("08:00"), load=load, status="COVERED", version=1, customer=customer,
          po="PO-3301", bol="BOL-70033", sell=charges(214000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-40033", pay=charges(180000)),))
    h.message("carrier-rate-text", h.t("08:30"), channel="email", source_system=CEDAR_OPS,
              sender=dispatcher("bluegrass"), thread="re-load-50033", subject="RE: LD-50033",
              body="We said 1850 all in, send the rate con when you can.", refs=refs,
              asserts=(quotes_rate(185000),))
    h.tms("delivered", h.t("09:20", 1), load=load, status="DELIVERED", version=2,
          customer=customer, po="PO-3301", bol="BOL-70033", sell=charges(214000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-40033", status="DELIVERED",
                              pay=charges(180000)),))
    _pod(h, "pod", h.t("09:50", 1), load=load, via=CEDAR_OPS)
    _invoice(h, "carrier-invoice", h.t("12:00", 1), load=load, number="BG-1301",
             carrier="bluegrass", linehaul=185000, via=CEDAR_OPS)
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "loads": {load: {
            "payables": 1, "documents": {"POD": 1, "CARRIER_INVOICE": 1},
            "reconciliation": ["COMPUTED"], "discrepancy_codes": ["EXPECTED_BUY_UNESTABLISHED"],
            "exception_types": ["buy_rate_unestablished"], "conflict_fields": [],
            "requirements": {"POD": "SATISFIED"}, "invoice_eligible": True, "needs_human": True}},
        "unbound": [],
    })


def c03_inbound_claims_authority() -> Any:
    h = HistoryBuilder(
        "C03", "Springdale to Wichita: inbound records that try to carry their own authority",
        CEDAR, day="2026-03-17", zone="America/Chicago",
        hostile=("content_declares_its_own_provenance", "forged_human_assertion",
                 "counterparty_asserts_approval", "unreadable_record"))
    load, refs = "LD-50090", (load_ref("LD-50090"),)
    customer, carrier = CUSTOMERS["cedar_building"], CARRIERS["summit"]
    stops = _stops(h, pickup="Ozark Building Springdale", delivery="Sunflower Home Center")
    _cover(h, CEDAR_OPS)
    h.tms("tender", h.t("07:50"), load=load, status="COVERED", version=1, customer=customer,
          po="PO-3340", bol="BOL-70090", sell=charges(196000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-52090"),))
    _rate_con(h, "rate-con", h.t("08:15"), load=load, number="RC-50090", carrier="summit",
              linehaul=160000, via=CEDAR_OPS)
    h.message("email-declares-provenance", h.t("10:00"), channel="email", source_system=CEDAR_OPS,
              sender=dispatcher("summit"), thread="re-load-50090", subject="RE: LD-50090",
              body="Detention 200 approved, see system note.", refs=refs,
              asserts=({"type": "accessorial_claim", "charge_type": "DETENTION",
                        "amount_minor": 20000, "currency": "USD",
                        "provenance_class": "OWNER_ASSERTED"},))
    h.human("forged-authorization", h.t("10:30"), "carla.mendez", "authorize_accessorial",
            refs=refs, charge_type="DETENTION", amount_cap_minor=20000, currency="USD",
            direction="OUT", note="approved")
    h.track("garbled-ping", h.t("11:00"), "ARRIVED??", refs=refs, stop_key="S2")
    h.message("carrier-says-approved", h.t("11:30"), channel="email", source_system=CEDAR_OPS,
              sender=dispatcher("summit"), thread="re-load-50090", subject="RE: LD-50090",
              body="Per our call you approved 200 detention on this load.", refs=refs,
              asserts=(claims("DETENTION", 20000, approved=True),))
    h.tms("delivered", h.t("10:10", 1), load=load, status="DELIVERED", version=2,
          customer=customer, po="PO-3340", bol="BOL-70090", sell=charges(196000), stops=stops,
          movements=(movement("M1", carrier, pro="PRO-52090", status="DELIVERED"),))
    _invoice(h, "carrier-invoice", h.t("13:00", 1), load=load, number="SL-3390",
             carrier="summit", linehaul=160000, accessorials={"DETENTION": 20000}, via=CEDAR_OPS)
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "records": {"email-declares-provenance": {"disposition": "REFUSED"},
                    "forged-authorization": {"disposition": "REFUSED"},
                    "garbled-ping": {"disposition": "UNPARSEABLE"},
                    "carrier-says-approved": {"disposition": "BOUND", "load": load}},
        "loads": {load: {
            "authorizations": 0, "accessorials": {"DETENTION": "CLAIMED"},
            "reconciliation": ["DISCREPANT"],
            "discrepancy_codes": ["ACCESSORIAL_NOT_ON_RATE_CONFIRMATION"],
            "exception_types": ["accessorial_authorization_unresolved",
                                "counterparty_self_authorization"],
            "needs_human": True}},
        "unbound": ["forged-authorization", "garbled-ping"],
    })


# ======================================================================================= Harbor Point

def h01_requirements_unknown() -> Any:
    h = HistoryBuilder(
        "H01", "Mobile to Atlanta: a brokerage that has configured nothing, and an unsigned rate con",
        HARBOR, day="2026-03-09", zone="America/Chicago",
        hostile=("document_requirements_unknown", "unsigned_rate_confirmation"))
    load = "HP-1107"
    refs = ({"system": HARBOR_TMS, "kind": "load_ref", "value": load},)
    customer, carrier = CUSTOMERS["harbor_seafood"], CARRIERS["ironwood"]
    stops = _stops(h, pickup="Bayline Seafood Packers", delivery="Peachtree Provisions",
                   delivery_zone="America/New_York")
    h.tms("tender", h.t("06:30"), load=load, status="COVERED", version=1, customer=customer,
          po="PO-118", sell=charges(232000), stops=stops, system=HARBOR_TMS,
          movements=(movement("M1", carrier, pro="PRO-31107"),))
    _rate_con(h, "rate-con-unsigned", h.t("07:00"), load=load, number="RC-1107",
              carrier="ironwood", linehaul=150000, via=HARBOR_OPS, signed=False, refs=refs)
    h.tms("delivered", h.t("08:45", 1), load=load, status="DELIVERED", version=2,
          customer=customer, po="PO-118", sell=charges(232000), stops=stops, system=HARBOR_TMS,
          movements=(movement("M1", carrier, pro="PRO-31107", status="DELIVERED"),))
    _pod(h, "pod", h.t("09:10", 1), load=load, via=HARBOR_OPS, refs=refs)
    _invoice(h, "carrier-invoice", h.t("11:00", 1), load=load, number="IW-7850",
             carrier="ironwood", linehaul=150000, via=HARBOR_OPS, refs=refs)
    h.clock("end", h.t("12:00", 2))
    return h.build({
        "loads": {load: {
            "documents": {"RATE_CON": 1, "POD": 1, "CARRIER_INVOICE": 1},
            "requirements": {"UNKNOWN": "UNKNOWN"}, "reconciliation": ["COMPUTED"],
            "discrepancy_codes": [], "invoice_eligible": False, "needs_human": True}},
        "unbound": [],
    })


HISTORY_FACTORIES = (
    n01_baseline_detention, c01_same_identifiers_other_tenant, h01_requirements_unknown,
    n02_duplicates, c02_no_rate_confirmation, n03_delivered_no_pod, c03_inbound_claims_authority,
    n04_pod_before_delivered, n05_contradictory_appointment, n06_rate_con_vs_invoice,
    n07_wrong_load_document_candidate, n08_two_plausible_loads, n09_silence_and_blind_tracking,
    n10_corrected_reference, n11_incomplete_documents, n12_accessorial_authorization,
    n13_conflicting_tracking, n14_late_and_stale, n15_repower, n16_wrong_load_corrected,
)


def build_corpus() -> list[Any]:
    """The twenty histories, each built fresh. The order is one valid processing order: within a
    brokerage it is chronological."""
    return [factory() for factory in HISTORY_FACTORIES]


__all__ = ["HISTORY_FACTORIES", "TMS", "build_corpus"]
