"""Builders for the hostile freight corpus: the small vocabulary a history is written in.

A history is authored as the ordered list of things that ARRIVED at a brokerage. These helpers only
shorten the writing — they add no behaviour, decide nothing, and produce exactly the `InboundRecord`s
the freight-domain intake reads. Nothing here sets a provenance class: a record names its channel and
kind, and the runtime decides what it can bear.

SYNTHETIC. Every company, person, number and document below is invented for development.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from freight_recon.freight_domain.history import FreightHistory, InboundRecord  # noqa: E402

#: The TMS product both corpus brokerages happen to run. Two tenants, one outside system name — which
#: is exactly why an external id is trusted only within a tenant.
TMS = "tms:loadmaster"
FMCSA = "fmcsa"
TRACKING = "tracking:macropoint"
PORTAL = "portal:opendock"
CONSOLE = "console:neyma"


def load_ref(value: str) -> dict[str, Any]:
    """The brokerage's own TMS load number."""
    return {"system": TMS, "kind": "load_ref", "value": value}


def bare_ref(value: str) -> dict[str, Any]:
    """A number someone typed without saying whose numbering it is. It can never resolve exactly."""
    return {"system": None, "kind": "load_ref", "value": value}


def po_ref(customer_id: str, value: str) -> dict[str, Any]:
    """A customer's PO number — meaningful only within that customer's numbering."""
    return {"system": f"customer:{customer_id}", "kind": "po_number", "value": value}


def pro_ref(mc_number: str, value: str) -> dict[str, Any]:
    """A carrier's PRO number — meaningful only within that carrier's numbering."""
    return {"system": f"carrier:{mc_number}", "kind": "pro_number", "value": value}


def bol_ref(value: str) -> dict[str, Any]:
    """The BOL number as the TMS recorded it."""
    return {"system": TMS, "kind": "bol_number", "value": value}


def charges(linehaul: int, fuel: int = 0, accessorials: dict[str, int] | None = None, *,
            currency: str = "USD", total: int | None = None) -> dict[str, Any]:
    """Integer minor units. `total` is what the DOCUMENT states, when it states one."""
    block: dict[str, Any] = {
        "currency": currency, "linehaul_minor": linehaul, "fuel_minor": fuel,
        "accessorials": [{"charge_type": k, "amount_minor": v}
                         for k, v in (accessorials or {}).items()],
    }
    if total is not None:
        block["total_minor"] = total
    return block


def stop(key: str, stop_type: str, sequence: int, facility: str, zone: str, *,
         appointment: tuple[str, str, str] | None = None) -> dict[str, Any]:
    """A stop. `appointment` is `(start_local, end_local, status)` in the FACILITY's wall time."""
    block: dict[str, Any] = {"stop_key": key, "stop_type": stop_type, "sequence": sequence,
                             "facility_name": facility, "facility_timezone": zone}
    if appointment is not None:
        block["appointment"] = {"window_start_local": appointment[0],
                                "window_end_local": appointment[1], "status": appointment[2]}
    return block


def movement(key: str, carrier: dict[str, Any], *, status: str = "BOOKED", pro: str | None = None,
             pay: dict[str, Any] | None = None,
             stops: tuple[str, ...] = ("S1", "S2")) -> dict[str, Any]:
    block: dict[str, Any] = {
        "movement_key": key, "status": status,
        "carrier": {"mc_number": carrier["mc"], "dot_number": carrier.get("dot"),
                    "legal_name": carrier["name"], "contacts": [carrier["dispatcher"]]},
        "driver": carrier.get("driver", {}), "carrier_pro": pro,
        "legs": [{"leg_key": "L1", "stop_keys": list(stops)}],
    }
    if pay is not None:
        block["carrier_pay"] = pay
    return block


class HistoryBuilder:
    """One load's history, written in arrival order."""

    def __init__(self, history_id: str, title: str, tenant: str, *, day: str, zone: str,
                 hostile: tuple[str, ...]) -> None:
        self.history_id = history_id
        self.title = title
        self.tenant = tenant
        self.day = date.fromisoformat(day)
        self.zone = zone
        self.hostile = hostile
        self.records: list[InboundRecord] = []
        self._serial = 0

    # ------------------------------------------------------------------ time

    def t(self, clock: str, day: int = 0, zone: str | None = None) -> str:
        """`"08:14"` on the history's day (plus `day` days), as an offset-carrying ISO instant."""
        hour, minute = (int(part) for part in clock.split(":"))
        moment = datetime.combine(self.day + timedelta(days=day), time(hour, minute),
                                  tzinfo=ZoneInfo(zone or self.zone))
        return moment.isoformat()

    def local(self, clock: str, day: int = 0) -> str:
        """A facility-local wall-clock reading, with no offset."""
        return f"{(self.day + timedelta(days=day)).isoformat()}T{clock}"

    # ------------------------------------------------------------------ records

    def _add(self, label: str, *, channel: str, kind: str, source_system: str, at: str,
             payload: dict[str, Any], refs: tuple[dict[str, Any], ...] = (),
             external_id: str | None = None, as_of: str | None = None,
             zone: str | None = None) -> None:
        self._serial += 1
        self.records.append(InboundRecord(
            label=label, channel=channel, kind=kind, source_system=source_system,
            external_id=external_id or f"{self.history_id}-{self._serial:03d}",
            received_at=at, as_of=as_of or at, timezone=zone or self.zone,
            refs=tuple(refs), payload=payload))

    def redeliver(self, label: str, at: str, *, of: str | None = None) -> None:
        """The SAME record arriving again: same source, same external id, same content — only the
        arrival time differs. This is what a re-sent email or a re-polled TMS row looks like."""
        original = (next(r for r in self.records if r.label == of) if of else self.records[-1])
        self.records.append(replace(original, label=label, received_at=at))

    def tms(self, label: str, at: str, *, load: str, status: str, version: int,
            customer: dict[str, Any] | None = None, po: str | None = None,
            sell: dict[str, Any] | None = None, movements: tuple[dict[str, Any], ...] = (),
            stops: tuple[dict[str, Any], ...] = (), bol: str | None = None,
            previous_load_ref: str | None = None, order_id: str | None = None,
            as_of: str | None = None, system: str = TMS) -> None:
        """A TMS snapshot of the load row. `version` makes each snapshot its own source record."""
        references: list[dict[str, Any]] = []
        order: dict[str, Any] = {}
        if po and customer:
            references.append(po_ref(customer["id"], po))
            order["customer_po"] = po
        if order_id:
            order["tms_order_id"] = order_id
        if bol:
            references.append(bol_ref(bol))
        for item in movements:
            if item.get("carrier_pro"):
                references.append({**pro_ref(item["carrier"]["mc_number"], item["carrier_pro"]),
                                   "entity": f"carrier_movement:{item['movement_key']}"})
        payload: dict[str, Any] = {
            "load_ref": load, "status": status, "references": references, "order": order,
            "movements": list(movements), "stops": list(stops),
        }
        if previous_load_ref:
            payload["previous_load_ref"] = previous_load_ref
        if customer:
            payload["customer"] = {"tms_customer_id": customer["id"],
                                   "legal_name": customer["name"],
                                   "contacts": list(customer.get("contacts", ()))}
        if sell is not None:
            payload["sell"] = sell
        self._add(label, channel="tms", kind="tms_load", source_system=system, at=at,
                  payload=payload, external_id=f"{load}@v{version}", as_of=as_of)

    def track(self, label: str, at: str, status: str, *, refs: tuple[dict[str, Any], ...],
              stop_key: str | None = None, position: str | None = None,
              provider: str = TRACKING, as_of: str | None = None,
              external_id: str | None = None) -> None:
        self._add(label, channel="tracking_provider", kind="tracking_event",
                  source_system=provider, at=at, refs=refs, as_of=as_of, external_id=external_id,
                  payload={"signal": "tracking_provider_position", "status": status,
                           "stop_key": stop_key,
                           "position": {"label": position} if position else None})

    def appointment(self, label: str, at: str, stop_key: str, start: str, end: str, zone: str, *,
                    refs: tuple[dict[str, Any], ...], status: str = "CONFIRMED",
                    source: str = PORTAL) -> None:
        self._add(label, channel="portal", kind="appointment", source_system=source, at=at,
                  refs=refs, payload={"stop_key": stop_key, "window_start_local": start,
                                      "window_end_local": end, "timezone": zone,
                                      "status": status})

    def message(self, label: str, at: str, *, channel: str, source_system: str,
                sender: tuple[str, str, str], thread: str, body: str,
                refs: tuple[dict[str, Any], ...], subject: str = "",
                asserts: tuple[dict[str, Any], ...] = (), direction: str = "inbound",
                quoted: tuple[str, ...] = (), forwarded: bool = False,
                external_id: str | None = None, as_of: str | None = None) -> None:
        self._add(label, channel=channel, kind="message", source_system=source_system, at=at,
                  refs=refs, external_id=external_id, as_of=as_of,
                  payload={"direction": direction, "thread_key": thread,
                           "sender": {"role": sender[0], "name": sender[1], "address": sender[2]},
                           "subject": subject, "body": body, "asserts": list(asserts),
                           "quoted_external_ids": list(quoted), "forwarded": forwarded})

    def raw_message(self, label: str, at: str, *, channel: str, source_system: str,
                    sender: tuple[str, str, str], thread: str, body: str,
                    refs: tuple[dict[str, Any], ...] = (), subject: str = "",
                    quoted: tuple[str, ...] = (), forwarded: bool = False,
                    external_id: str | None = None, as_of: str | None = None) -> None:
        """A message exactly as it was captured: text, and NO `asserts`. What it says is for a
        reader to work out. `refs` is only what the envelope itself carried — a thread or subject
        line with the brokerage's own load number — and is empty when the text is all there is."""
        self._add(label, channel=channel, kind="message", source_system=source_system, at=at,
                  refs=refs, external_id=external_id, as_of=as_of,
                  payload={"direction": "inbound", "thread_key": thread,
                           "sender": {"role": sender[0], "name": sender[1], "address": sender[2]},
                           "subject": subject, "body": body,
                           "quoted_external_ids": list(quoted), "forwarded": forwarded})

    def raw_document(self, label: str, at: str, doc_type: str, text: str, *,
                     refs: tuple[dict[str, Any], ...], via: str, signed: bool | None = None,
                     external_id: str | None = None) -> None:
        """A document as text, with NO `extracted` block."""
        self._add(label, channel="email", kind="document", source_system=via, at=at, refs=refs,
                  external_id=external_id,
                  payload={"doc_type": doc_type, "content": text, "signed": signed,
                           "legible": True, "pages_present": 1, "pages_expected": 1,
                           "attached_to": None})

    def document(self, label: str, at: str, doc_type: str, content: str, *,
                 refs: tuple[dict[str, Any], ...], via: str, channel: str = "email",
                 signed: bool | None = None, legible: bool = True, pages: tuple[int, int] = (1, 1),
                 extracted: dict[str, Any] | None = None, attached_to: str | None = None,
                 external_id: str | None = None, as_of: str | None = None) -> None:
        self._add(label, channel=channel, kind="document", source_system=via, at=at, refs=refs,
                  external_id=external_id, as_of=as_of,
                  payload={"doc_type": doc_type, "content": content, "signed": signed,
                           "legible": legible, "pages_present": pages[0],
                           "pages_expected": pages[1], "extracted": extracted or {},
                           "attached_to": attached_to})

    def human(self, label: str, at: str, human_id: str, act: str, *,
              refs: tuple[dict[str, Any], ...], **fields: Any) -> None:
        self._add(label, channel="console", kind="human_assertion", source_system=CONSOLE, at=at,
                  refs=refs, payload={"human_id": human_id, "act": act, **fields})

    def coverage(self, label: str, at: str, channel: str, start: str, end: str, *,
                 health: str = "HEALTHY") -> None:
        self._add(label, channel="probe", kind="channel_coverage",
                  source_system="probe:channel-health", at=at,
                  payload={"channel": channel, "window_start": start, "window_end": end,
                           "health": health})

    def clock(self, label: str, at: str) -> None:
        self._add(label, channel="clock", kind="clock", source_system="clock", at=at, payload={})

    # ------------------------------------------------------------------ result

    def build(self, expected: dict[str, Any]) -> FreightHistory:
        return FreightHistory(history_id=self.history_id, title=self.title, tenant=self.tenant,
                              hostile=self.hostile, records=tuple(self.records),
                              expected=expected)


def commit(due_by: str, *, quoted: bool = False) -> dict[str, Any]:
    """A structured commitment — "I'll update you by <time>" — standing in for model interpretation."""
    return {"type": "commitment", "commitment_kind": "status_update", "due_by": due_by,
            "in_quoted_text": quoted}


def says(status: str, stop_key: str | None = None) -> dict[str, Any]:
    return {"type": "status", "status": status, "stop_key": stop_key}


def claims(charge_type: str, amount: int, *, approved: bool = False) -> dict[str, Any]:
    return {"type": "accessorial_claim", "charge_type": charge_type, "amount_minor": amount,
            "currency": "USD", "claims_authorization": approved}


def quotes_rate(amount: int) -> dict[str, Any]:
    return {"type": "rate", "amount_minor": amount, "currency": "USD"}


def states_appointment(stop_key: str, start: str, end: str, zone: str) -> dict[str, Any]:
    return {"type": "appointment", "stop_key": stop_key, "window_start_local": start,
            "window_end_local": end, "timezone": zone, "status": "CONFIRMED"}
