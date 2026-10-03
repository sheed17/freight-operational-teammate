"""P9 — Operational Timeline Entry (domain entity #39): the "what happened, when, why" view of one load.

### DERIVED, NEVER AUTHORITATIVE. Every entry is computed from a canonical record that already exists
— a bound Observation, an Expectation, a Conflict, an Exception, a binding decision, a mapping change,
a reconciliation result — and pins the record it came from in `source_refs`. Nothing reads the
timeline to decide anything, and it is rebuilt from scratch on every projection.

### NO PROSE IS WRITTEN FOR A FIXTURE. Each sentence is assembled from the record's own kind and
fields by the small set of templates below. A history the corpus has never seen renders through the
same templates.

### IT KEEPS THE BELIEFS OF THE DAY. A statement that was later superseded, corrected or contradicted
stays on the timeline at the instant it was made, flagged, rather than being rewritten to what is
believed now.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .financial import blocking_discrepancies
from .foundation import stable_id
from .model import DirectedMoney, OperationalTimelineEntry, carrier_owed
from .projection import (
    LoadView,
    resolve_appointment_claim,
    resolve_claim_money,
    resolve_stop_key,
)

SIGNAL_LABELS: dict[str, str] = {
    "tracking_provider_position": "tracking provider",
    "driver_assertion": "driver",
    "carrier_assertion": "carrier",
    "tms_status": "TMS",
}
ROLE_LABELS: dict[str, str] = {
    "carrier_contact": "carrier", "driver": "driver", "customer_contact": "customer",
    "facility_contact": "facility", "broker_user": "broker",
}


def _money(amount_minor: int, currency: str) -> str:
    return carrier_owed(amount_minor, currency).display()


def _total(block: dict[str, Any]) -> int:
    return (block["linehaul_minor"] + block["fuel_minor"]
            + sum(a["amount_minor"] for a in block["accessorials"]))


def _local(instant_utc: str, zone: str) -> str:
    moment = datetime.fromisoformat(instant_utc.replace("Z", "+00:00")).astimezone(ZoneInfo(zone))
    return moment.strftime("%H:%M")


def _stop_label(view: LoadView, stop_key: str | None) -> str:
    stop = view.stops.get(stop_key or "")
    if stop is None:
        return ""
    kind = str(stop.value("stop_type") or "").lower()
    name = stop.value("facility_name") or stop_key
    return f" at {kind} ({name})"


class _Builder:
    def __init__(self, view: LoadView) -> None:
        self.view = view
        self.entries: list[OperationalTimelineEntry] = []

    def add(self, *, at: str, zone: str, kind: str, summary: str, provenance: str | None,
            sources: tuple[str, ...], received_at: str | None = None,
            flags: tuple[str, ...] = ()) -> None:
        tenant = self.view.load.tenant_id
        self.entries.append(OperationalTimelineEntry(
            timeline_entry_id=stable_id("tle", tenant, self.view.load_id, kind, at, *sources,
                                        summary),
            tenant_id=tenant, load_id=self.view.load_id, at=at, originating_timezone=zone,
            kind=kind, summary=summary, provenance_class=provenance, source_refs=sources,
            received_at=received_at, flags=flags))


def _observation_entries(builder: _Builder) -> None:
    view = builder.view
    previous_status: str | None = None
    seen_movements: set[str] = set()
    fallen_off: set[str] = set()
    duplicates = set(view.duplicate_evidence_arrivals)
    duplicate_invoices = {oid for p in view.payables.values() for oid in p.duplicate_observation_ids}
    # A record that ARRIVED after one carrying a later `as_of` is late news. It is told where it
    # belongs in business time — the timeline is the order things happened — and flagged.
    out_of_order: set[str] = set()
    latest_as_of = ""
    for observation in view.observations:
        if observation["as_of"] < latest_as_of:
            out_of_order.add(observation["observation_id"])
        latest_as_of = max(latest_as_of, observation["as_of"])
    in_business_time = sorted(view.observations,
                              key=lambda o: (o["as_of"], o["received_at"], o["observation_id"]))
    for observation in in_business_time:
        parsed = observation["parsed"]
        payload = parsed["payload"]
        zone = parsed["timezone"]
        oid = observation["observation_id"]
        flags: list[str] = ["arrived_out_of_order"] if oid in out_of_order else []
        base = {"at": observation["as_of"], "zone": zone, "sources": (f"observation:{oid}",),
                "received_at": observation["received_at"]}
        provenance = _provenance_label(parsed)
        kind = parsed["kind"]

        if kind == "tms_load":
            status = payload["status"]
            if previous_status is None:
                builder.add(kind="load_data", provenance=provenance, flags=tuple(flags),
                            summary=f"customer tender / load data observed in TMS "
                                    f"(load {payload['load_ref']}, status {status})", **base)
            elif status != previous_status:
                builder.add(kind="tms_status", provenance=provenance, flags=tuple(flags),
                            summary=f"TMS status {previous_status} -> {status}", **base)
            if payload.get("previous_load_ref"):
                builder.add(kind="reference_change", provenance=provenance, flags=tuple(flags),
                            summary=f"TMS renumbered the load {payload['previous_load_ref']} -> "
                                    f"{payload['load_ref']}", **base)
            previous_status = status
            for movement in payload.get("movements", ()):
                key = movement["movement_key"]
                carrier = movement.get("carrier") or {}
                if key not in seen_movements and carrier.get("legal_name"):
                    seen_movements.add(key)
                    builder.add(kind="carrier_assignment", provenance=provenance,
                                flags=tuple(flags),
                                summary=f"carrier assignment observed: {carrier['legal_name']} "
                                        f"({carrier.get('mc_number', 'MC unknown')})", **base)
                if movement.get("status") == "FELL_OFF" and key not in fallen_off:
                    fallen_off.add(key)
                    builder.add(kind="carrier_fell_off", provenance=provenance, flags=tuple(flags),
                                summary=f"carrier fell off: {carrier.get('legal_name', key)}",
                                **base)
        elif kind == "tracking_event":
            builder.add(kind="tracking", provenance=provenance, flags=tuple(flags),
                        summary=f"{SIGNAL_LABELS[payload['signal']]} reports {payload['status']}"
                                f"{_stop_label(view, payload.get('stop_key'))}", **base)
        elif kind == "appointment":
            builder.add(kind="appointment", provenance=provenance, flags=tuple(flags),
                        summary=f"appointment{_stop_label(view, payload['stop_key'])} reported "
                                f"{payload['status']}: {payload['start_local']}.."
                                f"{payload['end_local']} {payload['timezone']}", **base)
        elif kind == "document":
            builder.add(kind="document", provenance=provenance,
                        flags=tuple(flags + _document_flags(payload, oid, duplicates,
                                                            duplicate_invoices)),
                        summary=_document_summary(payload, oid, duplicates, duplicate_invoices),
                        **base)
        elif kind == "message":
            for summary, extra in _message_summaries(view, payload, zone):
                builder.add(kind="communication", provenance=provenance,
                            flags=tuple(flags + extra), summary=summary, **base)
        elif kind == "human_assertion":
            builder.add(kind="human_act", provenance=provenance, flags=tuple(flags),
                        summary=_human_summary(payload), **base)


def _provenance_label(parsed: dict[str, Any]) -> str:
    from .foundation import Acquisition, assign_at_runtime
    return assign_at_runtime(Acquisition(parsed["acquisition"])).value


def _document_flags(payload: dict[str, Any], oid: str, duplicates: set[str],
                    duplicate_invoices: set[str]) -> list[str]:
    flags: list[str] = []
    if oid in duplicates or oid in duplicate_invoices:
        flags.append("duplicate_recognized")
    if not payload["legible"]:
        flags.append("illegible")
    if payload["pages_present"] < payload["pages_expected"]:
        flags.append("incomplete")
    return flags


def _document_summary(payload: dict[str, Any], oid: str, duplicates: set[str],
                      duplicate_invoices: set[str]) -> str:
    doc_type = payload["doc_type"]
    extracted = payload.get("extracted") or {}
    if oid in duplicates:
        return f"{doc_type} received again (identical bytes) - recognized as a duplicate"
    if oid in duplicate_invoices:
        return (f"carrier invoice {extracted.get('invoice_number')} received again - recognized "
                f"as a duplicate, no second payable")
    notes: list[str] = []
    if payload["signed"] is False:
        notes.append("unsigned")
    if not payload["legible"]:
        notes.append("illegible")
    if payload["pages_present"] < payload["pages_expected"]:
        notes.append(f"{payload['pages_present']} of {payload['pages_expected']} pages")
    suffix = f" ({', '.join(notes)})" if notes else ""
    if doc_type == "RATE_CON" and extracted:
        return (f"rate confirmation {extracted['ratecon_number']} received: buy "
                f"{_money(_total(extracted), extracted['currency'])} OUT{suffix}")
    if doc_type == "CARRIER_INVOICE" and extracted:
        return (f"carrier invoice {extracted['invoice_number']} received: "
                f"{_money(_total(extracted), extracted['currency'])} OUT{suffix}")
    return f"{doc_type} received{suffix}"


def _message_summaries(view: LoadView, payload: dict[str, Any],
                       zone: str) -> list[tuple[str, list[str]]]:
    who = ROLE_LABELS[payload["sender"]["role"]]
    out: list[tuple[str, list[str]]] = []
    base_flags = ["forwarded"] if payload["forwarded"] else []
    for item in payload["asserts"]:
        kind = item["type"]
        if kind == "status":
            out.append((f"{who} reports {item['status']}"
                        f"{_stop_label(view, resolve_stop_key(view, item))}", list(base_flags)))
        elif kind == "commitment":
            flags = list(base_flags)
            if item["in_quoted_text"]:
                flags.append("quoted_not_a_new_commitment")
                out.append((f"{who} message quotes an earlier promise to update by "
                            f"{_local(item['due_by'], zone)} - not a new commitment", flags))
            else:
                out.append((f"{who} promises another update by {_local(item['due_by'], zone)}",
                            flags))
        elif kind == "appointment":
            placed = resolve_appointment_claim(view, item)
            if placed is None:
                out.append((f"{who} states an appointment that names no single stop of this load "
                            f"- retained, not applied", list(base_flags) + ["not_placed"]))
            else:
                out.append((f"{who} states appointment{_stop_label(view, placed['stop_key'])}: "
                            f"{placed['start_local']}..{placed['end_local']} "
                            f"{placed['timezone']}", list(base_flags)))
        elif kind == "accessorial_claim":
            flags = list(base_flags)
            money, weakened = resolve_claim_money(view, item)
            claim = f"{who} claims {item['charge_type']}"
            if money is not None:
                claim += f" {money.display()} OUT"
            if weakened is not None:
                flags.append("currency_assumed_not_stated")
            if item["claims_authorization"]:
                flags.append("counterparty_asserted_authorization")
                claim += " and asserts it was approved - an assertion, not an authorization"
            out.append((claim, flags))
        elif kind == "rate":
            money, _ = resolve_claim_money(view, item)
            stated = f" of {money.display()} OUT" if money is not None else ""
            out.append((f"{who} states a rate{stated} in conversation - retained as an "
                        f"observation, not the buy rate",
                        list(base_flags) + ["not_authoritative"]))
        elif kind == "reference_correction":
            stated = item.get("stated_reference")
            out.append((f"{who} says an earlier message named the wrong load"
                        + (f" and now names {stated}" if stated else "")
                        + " - a claim; nothing was re-bound", list(base_flags)))
        elif kind == "delay":
            out.append((f"{who} reports a delay"
                        + (f": {item['reason']}" if item["reason"] else ""), list(base_flags)))
    if not out:
        label = payload["subject"] or payload["body"][:60]
        direction = "to" if payload["direction"] == "outbound" else "from"
        out.append((f"message {direction} {who}: {label}", list(base_flags)))
    return out


def _human_summary(payload: dict[str, Any]) -> str:
    who = payload["human_id"]
    act = payload["act"]
    if act == "authorize_accessorial":
        cap = DirectedMoney(payload["amount_cap_minor"], payload["currency"], payload["direction"],
                            "owed_to_carrier" if payload["direction"] == "OUT"
                            else "owed_by_customer")
        return f"{who} authorized {payload['charge_type']} up to {cap.display()} {cap.direction}"
    if act == "deny_accessorial":
        return f"{who} denied {payload['charge_type']}"
    if act == "bind_observation":
        return f"{who} bound an unbound inbound record to this load"
    if act == "correct_binding":
        return f"{who} corrected a binding: a record bound elsewhere belongs to this load"
    return f"{who} corrected an external reference"


def _foundation_entries(builder: _Builder) -> None:
    view = builder.view
    zone = _load_zone(view)
    for expectation in view.expectations:
        eid = f"expectation:{expectation['expectation_id']}"
        label = _expectation_label(expectation["expected_type"])
        still_owed = expectation["state"] in ("OVERDUE", "INDETERMINATE")
        # The deadline is shown AT the deadline, as it was believed then — whether or not the thing
        # arrived afterwards. `overdue_at` is set by M8 on both verdicts; which one it was is read
        # from the coverage the verdict recorded.
        if expectation["overdue_at"] is not None and expectation["coverage_gap"] is None:
            builder.add(at=expectation["deadline_utc"],
                        zone=expectation["originating_timezone"], kind="expectation_overdue",
                        summary=f"{label} overdue - the channel was demonstrably healthy and "
                                f"nothing arrived",
                        provenance=None, sources=(eid,),
                        flags=("needs_human",) if still_owed else ())
        elif expectation["overdue_at"] is not None:
            builder.add(at=expectation["deadline_utc"],
                        zone=expectation["originating_timezone"], kind="expectation_indeterminate",
                        summary=f"{label} deadline passed and the channel was not provably "
                                f"healthy ({expectation['coverage_gap']}) - indeterminate, not "
                                f"late",
                        provenance=None, sources=(eid,),
                        flags=("needs_human",) if still_owed else ())
        if expectation["state"] == "DISCHARGED" and expectation["late"]:
            builder.add(at=expectation["updated_at"],
                        zone=expectation["originating_timezone"], kind="expectation_discharged",
                        summary=f"{label} arrived late and was accepted",
                        provenance=None, sources=(eid,))
    for conflict in view.conflicts:
        stated = " vs ".join(str(p["stated_value"]) for p in conflict["parties"])
        builder.add(at=conflict["created_at"], zone=zone, kind="conflict",
                    summary=f"conflict on {conflict['field'].replace('_', ' ')}: {stated} - "
                            f"owned by {conflict['owner_id']}, not resolved by Neyma",
                    provenance=None,
                    sources=(f"conflict:{conflict['conflict_id']}",), flags=("needs_human",))
    for exception in view.exceptions:
        if exception["source_kind"] == "expectation":
            continue                                # already on the timeline as the missed deadline
        builder.add(at=exception["created_at"], zone=zone, kind="exception",
                    summary=f"exception ({exception['type'].replace('_', ' ')}): "
                            f"{exception['summary']}",
                    provenance=None,
                    sources=(f"exception:{exception['type']}:{exception['source_ref']}",),
                    flags=("needs_human",))
    for mapping in view.mappings:
        if mapping.state == "ACTIVE" or mapping.retired_at is None:
            continue
        verb = "superseded" if mapping.state == "SUPERSEDED" else "corrected as wrong"
        builder.add(at=mapping.retired_at, zone=zone, kind="reference_change",
                    summary=f"external reference {mapping.external_id_kind} "
                            f"{mapping.external_id} {verb} - the prior mapping is retained",
                    provenance=mapping.provenance_class,
                    sources=(f"mapping:{mapping.mapping_id}",))
    for item in view.binding_history:
        if item["state"] != "CORRECTED":
            continue
        builder.add(at=item["updated_at"], zone=zone, kind="binding_correction",
                    summary="a record previously bound to this load was corrected away from it - "
                            "the prior binding is retained",
                    provenance=item["provenance_class"],
                    sources=(f"observation:{item['subject_ref']}",))
    for item in view.ambiguous_candidates:
        others = len(item.candidate_load_ids) - 1
        if item.model_proposed:
            summary = (f"an inbound {item.kind} named no load exactly; a model proposed this load"
                       + (f" and {others} other(s)" if others else "")
                       + " as a candidate - held for a human, not bound")
        elif others:
            summary = (f"an inbound {item.kind} may belong to this load or to {others} other(s) - "
                       f"held for a human, not bound")
        else:
            summary = (f"an inbound {item.kind} reaches this load only through a retired or "
                       f"unqualified reference - held for a human, not bound")
        builder.add(at=item.as_of, zone=zone, kind="ambiguous_binding", summary=summary,
                    provenance=None, sources=(f"observation:{item.observation_id}",),
                    flags=("needs_human",))
    bound_here = {o["observation_id"] for o in view.observations}
    for item in view.binding_history:
        if item["state"] == "REJECTED" and item["source"] is not None \
                and item["subject_ref"] not in bound_here:
            builder.add(at=item["source"]["as_of"], zone=zone, kind="ambiguous_binding",
                        summary=f"an inbound {item['source']['parsed']['kind']} was held as a "
                                f"possible match for this load and was bound elsewhere",
                        provenance=None, sources=(f"observation:{item['subject_ref']}",))
    latest = max((o["received_at"] for o in view.observations), default=None)
    for result in view.reconciliations:
        blocking = blocking_discrepancies(result)
        if result.actual is None:
            continue                               # nothing has been billed; nothing to report
        if result.status == "RECONCILED":
            summary = "financial reconciliation: invoice matches the signed rate confirmation"
        elif result.status == "DISCREPANT":
            parts = []
            for d in blocking:
                amount = (f" {'+' if (d.delta_minor or 0) > 0 else ''}"
                          f"{_money(d.delta_minor, (d.actual or d.expected).currency)}"
                          if d.delta_minor is not None else "")
                note = "" if d.authorization == "n/a" else f", authorization {d.authorization}"
                parts.append(f"{d.line.lower()}{amount}{note}")
            summary = "financial discrepancy: " + "; ".join(parts)
        elif any(d.code == "EXPECTED_BUY_UNESTABLISHED" for d in blocking):
            summary = ("financial reconciliation not concluded: no rate confirmation is on file to "
                       "reconcile the invoice against")
        elif result.expected_condition == "conflicting" or result.actual_condition == "conflicting":
            summary = "financial reconciliation not concluded: one side is in conflict"
        else:
            summary = (f"financial reconciliation not concluded: the invoice matches, but the "
                       f"basis is {result.expected_basis} and only a SIGNED rate confirmation "
                       f"concludes it")
        builder.add(at=latest or view.load.field_of("load_ref").facts[0].as_of, zone=zone,
                    kind="financial_reconciliation", summary=summary, provenance=None,
                    sources=(f"reconciliation:{result.reconciliation_id}",),
                    flags=() if result.status == "RECONCILED" else ("needs_human",))


def _expectation_label(expected_type: str) -> str:
    if expected_type == "counterparty_update":
        return "expected response"
    if expected_type.startswith("document:"):
        return f"expected {expected_type.split(':', 1)[1]}"
    if expected_type.startswith("arrival:"):
        return f"expected arrival at stop {expected_type.split(':', 1)[1]}"
    return expected_type


def _load_zone(view: LoadView) -> str:
    for observation in view.observations:
        return observation["parsed"]["timezone"]
    return "UTC"


def build_timeline(view: LoadView) -> list[OperationalTimelineEntry]:
    """The ordered operational timeline of one load, from its canonical records."""
    builder = _Builder(view)
    _observation_entries(builder)
    _foundation_entries(builder)
    # At one instant, what a source SAID comes before what Neyma concluded from it.
    return sorted(builder.entries,
                  key=lambda e: (e.at, 0 if e.received_at is not None else 1,
                                 e.received_at or e.at, e.kind, e.timeline_entry_id))


def render_timeline(view: LoadView) -> str:
    """A human-readable rendering: local clock time in each entry's originating timezone, with the
    day marked when it changes."""
    load_ref = view.load.value("load_ref") or view.load_id
    lines = [f"LOAD {load_ref}  [{view.load.tenant_id}]"]
    current_day: str | None = None
    for entry in view.timeline:
        moment = datetime.fromisoformat(entry.at.replace("Z", "+00:00")).astimezone(
            ZoneInfo(entry.originating_timezone))
        day = moment.strftime("%Y-%m-%d")
        if day != current_day:
            lines.append(f"  -- {moment.strftime('%a %Y-%m-%d')} --")
            current_day = day
        marks = "".join(f" [{flag}]" for flag in entry.flags)
        lines.append(f"  {moment.strftime('%H:%M')} {entry.summary}{marks}")
    return "\n".join(lines)
