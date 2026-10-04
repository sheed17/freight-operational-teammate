"""P9 — the freight-history input contract: what one inbound record looks like before Neyma has
decided anything about it.

A freight history is one brokerage's load over time, as the ordered sequence of things outside
systems and people SAID: TMS snapshots, tracking signals, appointment readings, documents, emails and
texts, and the authenticated acts of the brokerage's own staff. It is DEVELOPMENT INPUT. Nothing in a
history is evidence of customer validation, and no rule is validated by appearing in one.

### THE RECORD NEVER SAYS HOW MUCH IT CAN BEAR. A record names the CHANNEL it arrived on and its
KIND. The runtime derives the `Acquisition` from those two facts and the provenance class from the
acquisition (R-P1). A record carrying `provenance_class` anywhere in its content is refused.

### STRUCTURED OR RAW. A message's `asserts` list and a document's `extracted` block are what its
text SAYS, as structure. A record may arrive with them already supplied — a fixture, written so the
deterministic mechanism can be exercised with no model at all — or without them, as raw language. A
raw record is read by a model through `interpretation.py`, which produces these same structures, each
item carrying an evidence span, and nothing downstream moves. Either way what the text says is a
READING of an artifact (`MODEL_EXTRACTED`): it may evidence a field and can never choose one.

### AN UNREADABLE RECORD IS NOT DROPPED. `parse_record` raises `UnparseableRecord`; intake turns that
into an UNPARSEABLE Observation owned by a named human.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .entity_mapping import ExternalReference
from .foundation import Acquisition, format_instant
from .model import DOC_TYPES, TRACKING_PROGRESSION, TRACKING_SIGNALS

#: Kinds that become an Observation. Each is something a source SAID.
OBSERVATION_KINDS: tuple[str, ...] = (
    "tms_load", "tracking_event", "appointment", "document", "message", "human_assertion",
)
#: Kinds that are not statements about freight: a channel-health reading and the passage of time.
CONTROL_KINDS: tuple[str, ...] = ("channel_coverage", "clock")

CHANNELS: tuple[str, ...] = ("tms", "tracking_provider", "portal", "email", "sms", "console",
                             "probe", "clock")

#: Which channels may carry which kind. A record outside this table is unparseable — a text message
#: claiming to be a TMS snapshot is not a TMS snapshot.
LEGAL_CHANNELS: dict[str, tuple[str, ...]] = {
    "tms_load": ("tms",),
    "tracking_event": ("tracking_provider", "tms"),
    "appointment": ("portal", "tms"),
    "document": ("email", "sms", "portal"),
    "message": ("email", "sms"),
    "human_assertion": ("console",),
    "channel_coverage": ("probe",),
    "clock": ("clock",),
}

HUMAN_ACTS: tuple[str, ...] = (
    "bind_observation", "correct_binding", "authorize_accessorial", "deny_accessorial",
    "correct_reference", "attribute_carrier_invoice", "confirm_appointment",
)
ASSERT_TYPES: tuple[str, ...] = (
    "status", "commitment", "appointment", "accessorial_claim", "rate", "delay",
)
MESSAGE_DIRECTIONS: tuple[str, ...] = ("inbound", "outbound")
SENDER_ROLES: tuple[str, ...] = (
    "carrier_contact", "driver", "customer_contact", "facility_contact", "broker_user",
)
#: Sender roles on the carrier's side of a movement — whose follow-up answers a carrier's promise.
CARRIER_SIDE_ROLES: tuple[str, ...] = ("carrier_contact", "driver")
APPOINTMENT_STATUSES: tuple[str, ...] = ("REQUESTED", "CONFIRMED", "RESCHEDULED", "CANCELLED")
COVERAGE_HEALTH: tuple[str, ...] = ("HEALTHY", "DOWN", "UNKNOWN", "PARTIAL")


class UnparseableRecord(ValueError):
    """The record cannot be read as its declared kind. Intake files it UNPARSEABLE, human-owned."""


class MalformedHistory(ValueError):
    """The history itself is not a history — a fixture defect, raised before any record is read."""


def acquisition_for(channel: str, kind: str) -> Acquisition:
    """HOW the record was obtained — the only input to its provenance (R-P1).

    A system of record is imported. An authenticated human act is asserted. Everything read off a
    document or out of a message is a READING of an artifact: it may evidence a field and can never
    choose one, whichever channel carried it."""
    if kind == "human_assertion":
        return Acquisition.AUTHENTICATED_HUMAN_ACT
    if kind in ("document", "message"):
        return Acquisition.MODEL_READ_FROM_ARTIFACT
    return Acquisition.EXTERNAL_SYSTEM_OF_RECORD


def to_utc(instant: str, *, what: str) -> str:
    """An offset-carrying ISO-8601 instant to the canonical UTC form. A naive instant is refused: a
    time with no offset is a time nobody can order against another clock."""
    try:
        parsed = datetime.fromisoformat(str(instant).replace("Z", "+00:00"))
    except ValueError as exc:
        raise UnparseableRecord(f"{what} {instant!r} is not an ISO-8601 instant") from exc
    if parsed.tzinfo is None:
        raise UnparseableRecord(f"{what} {instant!r} carries no UTC offset")
    return format_instant(parsed.astimezone(timezone.utc))


def require_zone(name: object, *, what: str) -> str:
    try:
        ZoneInfo(str(name))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise UnparseableRecord(f"{what} {name!r} is not an IANA timezone") from exc
    return str(name)


def local_wall(value: object, *, what: str) -> str:
    """A facility-local wall-clock reading (`2026-03-09T08:00`). It must be NAIVE: the facility's
    zone, not an offset baked into the string, is what honours a DST boundary."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise UnparseableRecord(f"{what} {value!r} is not a local wall-clock time") from exc
    if parsed.tzinfo is not None:
        raise UnparseableRecord(f"{what} {value!r} must be facility-local, without an offset")
    return parsed.isoformat(timespec="minutes")


def _require(payload: Mapping[str, Any], key: str, *, what: str) -> Any:
    if key not in payload or payload[key] in (None, ""):
        raise UnparseableRecord(f"{what} is missing required {key!r}")
    return payload[key]


def _minor(value: object, *, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UnparseableRecord(
            f"{what} must be integer minor units, got {type(value).__name__} {value!r}: a float "
            f"amount is two different payments waiting to happen")
    return value


def _currency(value: object, *, what: str) -> str:
    text = str(value or "")
    if len(text) != 3 or not text.isalpha() or not text.isupper():
        raise UnparseableRecord(f"{what} {value!r} is not an ISO-4217 code")
    return text


def _references(raw: Sequence[Any] | None, *, what: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw or ():
        if not isinstance(item, Mapping):
            raise UnparseableRecord(f"{what}: a reference must be a mapping")
        out.append({"system": item.get("system"), "kind": str(_require(item, "kind", what=what)),
                    "value": str(_require(item, "value", what=what)),
                    "entity": item.get("entity", "brokerage_load")})
    return out


def _money_lines(block: Mapping[str, Any], *, what: str) -> dict[str, Any]:
    currency = _currency(_require(block, "currency", what=what), what=f"{what} currency")
    accessorials = []
    for line in block.get("accessorials", ()):
        accessorials.append({
            "charge_type": str(_require(line, "charge_type", what=what)).upper(),
            "amount_minor": _minor(_require(line, "amount_minor", what=what), what=what),
        })
    parsed: dict[str, Any] = {
        "currency": currency,
        "linehaul_minor": _minor(_require(block, "linehaul_minor", what=what), what=what),
        "fuel_minor": _minor(block.get("fuel_minor", 0), what=what),
        "accessorials": accessorials,
    }
    if "total_minor" in block and block["total_minor"] is not None:
        parsed["total_minor"] = _minor(block["total_minor"], what=what)
    return parsed


def _parse_window(block: Mapping[str, Any], *, what: str) -> dict[str, Any]:
    return {
        "start_local": local_wall(_require(block, "window_start_local", what=what), what=what),
        "end_local": local_wall(_require(block, "window_end_local", what=what), what=what),
        "timezone": require_zone(_require(block, "timezone", what=what), what=f"{what} timezone"),
    }


def _parse_tms_load(payload: Mapping[str, Any]) -> dict[str, Any]:
    what = "tms_load"
    parsed: dict[str, Any] = {
        "load_ref": str(_require(payload, "load_ref", what=what)),
        "status": str(_require(payload, "status", what=what)).upper(),
        "previous_load_ref": payload.get("previous_load_ref"),
        "references": _references(payload.get("references"), what=what),
        "order": dict(payload.get("order") or {}),
        "customer": dict(payload.get("customer") or {}),
        "movements": [],
        "stops": [],
    }
    if payload.get("sell") is not None:
        parsed["sell"] = _money_lines(payload["sell"], what="tms_load sell")
    for movement in payload.get("movements", ()):
        item: dict[str, Any] = {
            "movement_key": str(_require(movement, "movement_key", what="tms_load movement")),
            "status": str(movement.get("status", "BOOKED")).upper(),
            "carrier": dict(movement.get("carrier") or {}),
            "driver": dict(movement.get("driver") or {}),
            "carrier_pro": movement.get("carrier_pro"),
            "legs": [{"leg_key": str(leg["leg_key"]), "stop_keys": [str(s) for s in leg["stop_keys"]]}
                     for leg in movement.get("legs", ())],
        }
        if movement.get("carrier_pay") is not None:
            item["carrier_pay"] = _money_lines(movement["carrier_pay"],
                                               what="tms_load carrier_pay")
        parsed["movements"].append(item)
    for stop in payload.get("stops", ()):
        entry: dict[str, Any] = {
            "stop_key": str(_require(stop, "stop_key", what="tms_load stop")),
            "stop_type": str(_require(stop, "stop_type", what="tms_load stop")).upper(),
            "sequence": int(stop.get("sequence", 0)),
            "facility_name": str(stop.get("facility_name", "")),
            "facility_timezone": require_zone(
                _require(stop, "facility_timezone", what="tms_load stop"),
                what="facility timezone"),
        }
        if entry["stop_type"] not in ("PICKUP", "DELIVERY"):
            raise UnparseableRecord(f"stop_type {entry['stop_type']!r} is not PICKUP or DELIVERY")
        if stop.get("appointment"):
            appointment = dict(stop["appointment"])
            appointment.setdefault("timezone", entry["facility_timezone"])
            status = str(appointment.get("status", "REQUESTED")).upper()
            if status not in APPOINTMENT_STATUSES:
                raise UnparseableRecord(f"appointment status {status!r} is not canonical")
            entry["appointment"] = {**_parse_window(appointment, what="tms_load appointment"),
                                    "status": status}
        parsed["stops"].append(entry)
    return parsed


def _parse_tracking(payload: Mapping[str, Any]) -> dict[str, Any]:
    what = "tracking_event"
    signal = str(_require(payload, "signal", what=what))
    if signal not in TRACKING_SIGNALS:
        raise UnparseableRecord(
            f"tracking signal {signal!r} is not one of {list(TRACKING_SIGNALS)}. A model-derived ETA "
            f"is a Claim, not an Observation, and has no route in through this door.")
    status = str(_require(payload, "status", what=what)).upper()
    if status not in (*TRACKING_PROGRESSION, "DELAYED"):
        raise UnparseableRecord(f"tracking status {status!r} is not canonical")
    return {"signal": signal, "status": status, "stop_key": payload.get("stop_key"),
            "movement_key": payload.get("movement_key"), "position": payload.get("position")}


def _parse_appointment(payload: Mapping[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status", "CONFIRMED")).upper()
    if status not in APPOINTMENT_STATUSES:
        raise UnparseableRecord(f"appointment status {status!r} is not canonical")
    return {"stop_key": str(_require(payload, "stop_key", what="appointment")), "status": status,
            **_parse_window(payload, what="appointment")}


def _parse_document(payload: Mapping[str, Any]) -> dict[str, Any]:
    what = "document"
    doc_type = str(_require(payload, "doc_type", what=what)).upper()
    if doc_type not in DOC_TYPES:
        raise UnparseableRecord(f"doc_type {doc_type!r} is not one of {list(DOC_TYPES)}")
    content = _require(payload, "content", what=what)
    if not isinstance(content, str):
        raise UnparseableRecord("document content must be text standing in for the artifact bytes")
    parsed: dict[str, Any] = {
        "doc_type": doc_type,
        "content": content,
        "media_type": str(payload.get("media_type", "application/pdf")),
        "signed": payload.get("signed"),
        "legible": bool(payload.get("legible", True)),
        "pages_expected": int(payload.get("pages_expected", 1)),
        "pages_present": int(payload.get("pages_present", payload.get("pages_expected", 1))),
        "attached_to": payload.get("attached_to"),
        "extracted": {},
    }
    extracted = dict(payload.get("extracted") or {})
    if doc_type in ("RATE_CON", "CARRIER_INVOICE") and extracted:
        charges = _money_lines(extracted, what=f"{doc_type} charges")
        number_key = "ratecon_number" if doc_type == "RATE_CON" else "invoice_number"
        parsed["extracted"] = {
            number_key: str(_require(extracted, number_key, what=doc_type)),
            "carrier_mc": extracted.get("carrier_mc"),
            "movement_key": extracted.get("movement_key"),
            "status": str(extracted.get("status", "")).upper() or None,
            **charges,
        }
    return parsed


def _parse_assert(item: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(_require(item, "type", what="message assert"))
    if kind not in ASSERT_TYPES:
        raise UnparseableRecord(f"message assert type {kind!r} is not one of {list(ASSERT_TYPES)}")
    if kind == "status":
        status = str(_require(item, "status", what="status assert")).upper()
        if status not in (*TRACKING_PROGRESSION, "DELAYED"):
            raise UnparseableRecord(f"asserted status {status!r} is not canonical")
        return {"type": kind, "status": status, "stop_key": item.get("stop_key"),
                "movement_key": item.get("movement_key")}
    if kind == "commitment":
        return {"type": kind,
                "commitment_kind": str(item.get("commitment_kind", "status_update")),
                "due_by": to_utc(_require(item, "due_by", what="commitment"), what="due_by"),
                "in_quoted_text": bool(item.get("in_quoted_text", False))}
    if kind == "appointment":
        status = str(item.get("status", "CONFIRMED")).upper()
        return {"type": kind, "stop_key": str(_require(item, "stop_key", what="appointment assert")),
                "status": status, **_parse_window(item, what="appointment assert")}
    if kind == "accessorial_claim":
        return {"type": kind,
                "charge_type": str(_require(item, "charge_type", what="accessorial")).upper(),
                "amount_minor": _minor(_require(item, "amount_minor", what="accessorial"),
                                       what="accessorial amount"),
                "currency": _currency(_require(item, "currency", what="accessorial"),
                                      what="accessorial currency"),
                "movement_key": item.get("movement_key"),
                "claims_authorization": bool(item.get("claims_authorization", False))}
    if kind == "rate":
        return {"type": kind,
                "amount_minor": _minor(_require(item, "amount_minor", what="rate"),
                                       what="rate amount"),
                "currency": _currency(_require(item, "currency", what="rate"), what="rate currency"),
                "movement_key": item.get("movement_key")}
    return {"type": kind, "reason": str(item.get("reason", "")),
            "stop_key": item.get("stop_key")}


def _parse_message(payload: Mapping[str, Any]) -> dict[str, Any]:
    what = "message"
    direction = str(_require(payload, "direction", what=what))
    if direction not in MESSAGE_DIRECTIONS:
        raise UnparseableRecord(f"message direction {direction!r} is not inbound or outbound")
    sender = dict(_require(payload, "sender", what=what))
    role = str(_require(sender, "role", what="message sender"))
    if role not in SENDER_ROLES:
        raise UnparseableRecord(f"sender role {role!r} is not one of {list(SENDER_ROLES)}")
    return {
        "direction": direction,
        "thread_key": str(_require(payload, "thread_key", what=what)),
        "sender": {"role": role, "name": str(sender.get("name", "")),
                   "address": str(sender.get("address", ""))},
        "subject": str(payload.get("subject", "")),
        "body": str(_require(payload, "body", what=what)),
        "quoted_external_ids": [str(x) for x in payload.get("quoted_external_ids", ())],
        "forwarded": bool(payload.get("forwarded", False)),
        "asserts": [_parse_assert(a) for a in payload.get("asserts", ())],
    }


def _parse_human_assertion(payload: Mapping[str, Any]) -> dict[str, Any]:
    what = "human_assertion"
    act = str(_require(payload, "act", what=what))
    if act not in HUMAN_ACTS:
        raise UnparseableRecord(f"human act {act!r} is not one of {list(HUMAN_ACTS)}")
    parsed: dict[str, Any] = {"act": act, "human_id": str(_require(payload, "human_id", what=what)),
                              "note": str(payload.get("note", ""))}
    if act in ("bind_observation", "correct_binding", "attribute_carrier_invoice"):
        target = dict(_require(payload, "target", what=act))
        parsed["target"] = {"source_system": str(_require(target, "source_system", what=act)),
                            "external_id": str(_require(target, "external_id", what=act))}
        if act == "attribute_carrier_invoice":
            # WHICH movement of the load the invoice bills. The human names the movement; the
            # carrier follows from it. Nothing here names a payee or an amount.
            parsed["movement_key"] = str(_require(payload, "movement_key", what=act))
    elif act == "confirm_appointment":
        # A recorded human states the appointment at one stop, in the FACILITY's wall time. It is
        # the only thing that settles a disputed window; a counterparty's sentence cannot.
        parsed["stop_key"] = str(_require(payload, "stop_key", what=act))
        parsed.update(_parse_window(payload, what=act))
    elif act in ("authorize_accessorial", "deny_accessorial"):
        parsed["charge_type"] = str(_require(payload, "charge_type", what=act)).upper()
        if act == "authorize_accessorial":
            parsed["amount_cap_minor"] = _minor(_require(payload, "amount_cap_minor", what=act),
                                                what="authorization cap")
            parsed["currency"] = _currency(_require(payload, "currency", what=act),
                                           what="authorization currency")
            parsed["direction"] = str(payload.get("direction", "OUT"))
    else:
        wrong = dict(_require(payload, "wrong_reference", what=act))
        parsed["wrong_reference"] = {"system": wrong.get("system"),
                                     "kind": str(_require(wrong, "kind", what=act)),
                                     "value": str(_require(wrong, "value", what=act))}
        right = payload.get("right_reference")
        parsed["right_reference"] = (
            {"system": right.get("system"), "kind": str(right["kind"]), "value": str(right["value"])}
            if right else None)
    return parsed


_PARSERS = {
    "tms_load": _parse_tms_load,
    "tracking_event": _parse_tracking,
    "appointment": _parse_appointment,
    "document": _parse_document,
    "message": _parse_message,
    "human_assertion": _parse_human_assertion,
}


@dataclass(frozen=True)
class InboundRecord:
    """One record of a history, as authored. `label` is the corpus's own handle for asserting an
    expected outcome; the domain never reads it."""

    label: str
    channel: str
    kind: str
    source_system: str
    external_id: str
    received_at: str
    as_of: str
    timezone: str
    refs: tuple[Mapping[str, Any], ...]
    payload: Mapping[str, Any]

    @property
    def is_observation(self) -> bool:
        return self.kind in OBSERVATION_KINDS

    def content(self) -> dict[str, Any]:
        """The immutable CONTENT a source said: the natural-key digest is computed over exactly this.
        Arrival time is not content, so the same email received twice is one Observation."""
        return {"kind": self.kind, "channel": self.channel, "timezone": self.timezone,
                "as_of_local": self.as_of, "refs": [dict(r) for r in self.refs],
                "payload": _plain(self.payload)}

    def references(self) -> list[ExternalReference]:
        return [ExternalReference(r.get("system"), str(r["kind"]), str(r["value"]))
                for r in self.refs]


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def parse_record(record: InboundRecord) -> dict[str, Any]:
    """The deterministic parse: validate the record against its declared kind and normalize it. The
    result is what M5 stores as `parsed_value`, and it records HOW the record was acquired so the
    provenance of every fact later read from it is re-derived from that, never from the row's
    binding."""
    if record.kind not in OBSERVATION_KINDS:
        raise UnparseableRecord(f"kind {record.kind!r} is not an observation kind")
    if record.channel not in LEGAL_CHANNELS[record.kind]:
        raise UnparseableRecord(
            f"a {record.kind!r} cannot arrive on channel {record.channel!r}; it arrives on "
            f"{list(LEGAL_CHANNELS[record.kind])}")
    if not isinstance(record.payload, Mapping):
        raise UnparseableRecord("the record payload is not a mapping")
    return {
        "kind": record.kind,
        "channel": record.channel,
        "acquisition": acquisition_for(record.channel, record.kind).value,
        "timezone": require_zone(record.timezone, what="record timezone"),
        "as_of_local": record.as_of,
        "refs": _references(record.refs, what="record refs"),
        "payload": _PARSERS[record.kind](record.payload),
    }


@dataclass(frozen=True)
class DocumentRequirementConfig:
    """A brokerage's own statement of what a load needs before an action. CONFIGURATION, never a
    constant: per-customer requirement sets are NEEDS VALIDATION."""

    gate: str
    required_doc_type: str
    expected_channel: str | None = None
    expected_within_hours: int | None = None


@dataclass(frozen=True)
class TenantSetup:
    """E1 — the brokerage, its named humans, and its own configuration. Everything a history would
    otherwise have to assume about a brokerage is stated here or is `unknown`."""

    tenant: str
    legal_name: str
    humans: tuple[Mapping[str, str], ...]
    load_owner: str
    intake_owner: str
    recorded_by: str
    document_requirements: tuple[DocumentRequirementConfig, ...] = ()
    arrival_tracking_channel: str | None = None
    # How often a MOVING truck is expected to be heard from, on `arrival_tracking_channel`. The
    # brokerage's own cadence, or None: with none configured there is no staleness clock, because a
    # cadence nobody chose would be a freight rule nobody chose (NEEDS VALIDATION).
    tracking_update_cadence_minutes: int | None = None

    def __post_init__(self) -> None:
        if self.tracking_update_cadence_minutes is not None and (
                isinstance(self.tracking_update_cadence_minutes, bool)
                or not isinstance(self.tracking_update_cadence_minutes, int)
                or self.tracking_update_cadence_minutes <= 0):
            raise MalformedHistory(
                f"{self.tenant}: tracking_update_cadence_minutes must be a positive whole number "
                f"of minutes or None, got {self.tracking_update_cadence_minutes!r}")
        known = {h["human_id"] for h in self.humans}
        for role, owner in (("load_owner", self.load_owner), ("intake_owner", self.intake_owner)):
            if owner not in known:
                raise MalformedHistory(
                    f"{self.tenant}: {role} {owner!r} is not one of the tenant's named humans "
                    f"{sorted(known)}. Ownership of an obligation is never ambiguous and never "
                    f"defaulted.")


@dataclass(frozen=True)
class FreightHistory:
    history_id: str
    title: str
    tenant: str
    hostile: tuple[str, ...]
    records: tuple[InboundRecord, ...]
    expected: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        labels = [r.label for r in self.records]
        if len(set(labels)) != len(labels):
            raise MalformedHistory(f"{self.history_id}: record labels are not unique")
        received = [to_utc(r.received_at, what="received_at") for r in self.records]
        if received != sorted(received):
            raise MalformedHistory(
                f"{self.history_id}: records are not in arrival order. A history is the order "
                f"things ARRIVED; what they are ABOUT is `as_of` and may be earlier or later.")
        for record in self.records:
            if record.kind not in (*OBSERVATION_KINDS, *CONTROL_KINDS):
                raise MalformedHistory(f"{self.history_id}: unknown record kind {record.kind!r}")

    def as_document(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id, "title": self.title, "tenant": self.tenant,
            "hostile": list(self.hostile),
            "records": [{"label": r.label, "channel": r.channel, "kind": r.kind,
                         "source_system": r.source_system, "external_id": r.external_id,
                         "received_at": r.received_at, "as_of": r.as_of, "timezone": r.timezone,
                         "refs": [dict(x) for x in r.refs], "payload": _plain(r.payload)}
                        for r in self.records],
            "expected": _plain(self.expected),
        }


def utc_datetime(instant_utc: str) -> datetime:
    return datetime.fromisoformat(instant_utc.replace("Z", "+00:00"))


def sequence_of(items: Sequence[Any] | None) -> tuple[Any, ...]:
    return tuple(items or ())
