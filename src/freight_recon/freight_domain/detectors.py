"""P9 — what the freight picture OWES: pure detectors over a `LoadView`.

A detector reads the canonical projection of one load and returns INTENTS — a Conflict that should
exist, an Expectation that should be raised or discharged, an Exception a human must own. It writes
nothing. Intake hands the intents to the foundational machines, which decide whether each is new, a
coalescing duplicate, or illegal.

### NO SECOND CONFLICT OR EXPECTATION SYSTEM. An intent is a request to M7, M8 or M9. The rules that
matter live there: a Conflict has at least two parties and exactly one open row per field; OVERDUE
needs proven channel coverage and INDETERMINATE is what a blind window is; an Exception has one named
owner. Nothing here resolves, closes, ranks or picks a winner.

### EVERY THRESHOLD IS CONFIGURATION OR IT IS ABSENT. How long after delivery a POD is due, and which
channel it is expected on, come from the brokerage's own setup. Where the setup is silent the detector
raises no deadline — the requirement stays visibly OUTSTANDING without an invented clock on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .financial import blocking_discrepancies
from .foundation import facility_local_deadline, format_instant, stable_id
from .history import CARRIER_SIDE_ROLES, TenantSetup, utc_datetime
from .model import OWNER_CONFIRMATION, TRACKING_PROGRESSION, DirectedMoney, Fact
from .projection import (
    OPEN_CONFLICT_STATES,
    OWED_STATES,
    LoadView,
    commitment_expectation_id,
    explain_unattributed_invoice,
    sender_identity,
)

#: Signals that report where a truck IS. A system of record that simply has not been updated yet is
#: not evidence against a later status, so `tms_status` never plays the regressing party.
CURRENT_STATE_SIGNALS: tuple[str, ...] = (
    "tracking_provider_position", "driver_assertion", "carrier_assertion",
)
ARRIVAL_STATUSES: tuple[str, ...] = ("AT_PICKUP", "AT_DELIVERY", "LOADED", "DELIVERED")
#: The movement stages that can only be reported once the truck has been to a stop of that kind.
STAGES_PAST_STOP: dict[str, tuple[str, ...]] = {
    "PICKUP": ("LOADED", "IN_TRANSIT", "AT_DELIVERY", "DELIVERED"),
    "DELIVERY": ("AT_DELIVERY", "DELIVERED"),
}
#: The M8 expected-type of "this moving truck should be heard from again".
TRACKING_UPDATE = "tracking_update"
#: Statuses that say the freight is on the truck and has not been delivered.
UNDER_WAY_STATUSES: tuple[str, ...] = ("LOADED", "IN_TRANSIT", "AT_DELIVERY")
LINE_MISMATCH_CODES: dict[str, str] = {
    "LINEHAUL_MISMATCH": "linehaul", "FUEL_MISMATCH": "fuel",
    "ACCESSORIAL_AMOUNT_MISMATCH": "accessorials", "ACCESSORIAL_NOT_BILLED": "accessorials",
    "CURRENCY_MISMATCH": "linehaul",
}
ACCESSORIAL_UNRESOLVED: tuple[str, ...] = ("UNRESOLVED", "EXCEEDS_AUTHORIZATION", "DENIED")


@dataclass(frozen=True)
class RaiseConflict:
    conflict_id: str
    kind: str
    entity_ref: str
    field: str
    parties: tuple[tuple[str, str, str], ...]       # (observation_id, provenance_class, stated)
    owner_id: str


@dataclass(frozen=True)
class RaiseExpectation:
    expectation_id: str
    subject_ref: str
    expected_type: str
    expected_source: str
    owner_id: str
    originating_timezone: str
    deadline_utc: str | None = None
    appointment_local: datetime | None = None


@dataclass(frozen=True)
class DischargeExpectation:
    expectation_id: str
    observation_ids: tuple[str, ...]                # tried in order; the first M8 accepts discharges


@dataclass(frozen=True)
class AmendExpectation:
    expectation_id: str
    deadline_utc: str


@dataclass(frozen=True)
class CancelExpectation:
    expectation_id: str
    reason: str


@dataclass(frozen=True)
class RaiseException:
    exception_id: str
    type: str
    severity: str
    source_ref: str
    source_kind: str
    owner_id: str
    summary: str
    entity_ref: str
    specific_question: str


Intent = (RaiseConflict | RaiseExpectation | DischargeExpectation | AmendExpectation
          | CancelExpectation | RaiseException)


def _stated(value: Any) -> str:
    if isinstance(value, DirectedMoney):
        return f"{value.display()} {value.direction}"
    if isinstance(value, dict) and {"start_local", "end_local", "timezone"} <= set(value):
        return f"{value['start_local']}..{value['end_local']} {value['timezone']}"
    return str(value)


def _conflict_kind(provenances: list[str]) -> str:
    """Which of M7's six kinds a disagreement is — read off the parties' provenance, not chosen."""
    if "OWNER_ASSERTED" in provenances:
        return "INFERRER_VS_OWNER"
    if all(p == "SYSTEM_IMPORTED" for p in provenances):
        return "SYSTEM_VS_SYSTEM"
    if "SYSTEM_IMPORTED" in provenances:
        return "CLAIM_VS_OBSERVATION"
    return "CLAIM_VS_CLAIM"


def _parties(facts: list[Fact]) -> tuple[tuple[str, str, str], ...]:
    seen: dict[str, tuple[str, str, str]] = {}
    for fact in facts:
        seen.setdefault(fact.observation_id,
                        (fact.observation_id, fact.provenance_class, _stated(fact.value)))
    return tuple(seen.values())


def detect(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """Everything this load's current picture owes, as intents. Discharges come first so that a
    record which both answers one promise and makes another is handled in that order."""
    intents: list[Intent] = []
    intents.extend(_discharges(view, setup))
    intents.extend(_field_conflicts(view, setup))
    intents.extend(_tracking_conflicts(view, setup))
    intents.extend(_commitment_expectations(view, setup))
    intents.extend(_document_expectations(view, setup))
    intents.extend(_arrival_expectations(view, setup))
    intents.extend(_tracking_expectations(view, setup))
    intents.extend(_financial_obligations(view, setup))
    intents.extend(_document_exceptions(view, setup))
    intents.extend(_reference_correction_exceptions(view, setup))
    return intents


# --------------------------------------------------------------------------------- conflicts

def _field_conflicts(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """Two sources' latest statements about one contested field disagree. Neyma does not flatten
    them into one guessed value: the field becomes `conflicting` and a human owns the decision."""
    out: list[Intent] = []
    for entity in view.entities():
        for name in entity.CONTESTED:
            facts = entity.field_of(name).disagreement()
            parties = _parties(facts)
            if len(parties) < 2:
                continue
            # A field a human has already decided can be disputed AGAIN, by a statement made after
            # her decision. That is a new Conflict, not the resolved one reopened: the settled
            # dispute keeps its own row and its own parties, and the new one counts on from it.
            settled = len([c for c in view.conflicts
                           if c["entity_ref"] == entity.ref and c["field"] == name
                           and c["state"] not in OPEN_CONFLICT_STATES])
            out.append(RaiseConflict(
                conflict_id=stable_id("conf", view.load.tenant_id, entity.ref, name,
                                      *((settled,) if settled else ())),
                kind=_conflict_kind([p[1] for p in parties]), entity_ref=entity.ref, field=name,
                parties=parties, owner_id=setup.load_owner))
    return out


def _tracking_conflicts(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """One source reports a LATER stage and another source, at a LATER instant, reports an EARLIER
    one — a truck said to be delivered that a tracking provider then places in transit. That is a
    contradiction a human looks at. It is never resolved here by recency or by source."""
    staged = [t for t in view.tracking if t.value("status") in TRACKING_PROGRESSION]
    staged.sort(key=lambda t: (t.field_of("status").facts[0].as_of, t.entity_id))
    # ### A HUMAN'S DECISION SETTLES WHAT WAS SAID BEFORE IT, AND ONLY THAT. Once a recorded human
    # has said where the load is (`confirm_movement_status`), a contradiction between statements
    # made up to that instant is HERS, decided, and is not detected again. A statement made AFTER
    # she decided that contradicts an earlier one - hers included - is a NEW dispute with its own
    # row; the settled one keeps its row and its parties.
    decided_at = max((t.field_of("status").facts[0].as_of for t in staged
                      if t.value("signal") == OWNER_CONFIRMATION), default="")
    settled = len([c for c in view.conflicts
                   if c["entity_ref"] == view.ref and c["field"] == "tracking_status"
                   and c["state"] not in OPEN_CONFLICT_STATES])
    for later in staged:
        later_fact = later.field_of("status").facts[0]
        if later.value("signal") not in CURRENT_STATE_SIGNALS:
            continue
        if later_fact.as_of <= decided_at:
            continue
        for earlier in staged:
            earlier_fact = earlier.field_of("status").facts[0]
            if earlier_fact.as_of >= later_fact.as_of or earlier.overruled_by is not None:
                continue
            if earlier_fact.source_system == later_fact.source_system:
                continue
            if earlier_fact.observation_id == later_fact.observation_id:
                continue
            if (TRACKING_PROGRESSION.index(later_fact.value)
                    < TRACKING_PROGRESSION.index(earlier_fact.value)):
                parties = _parties([earlier_fact, later_fact])
                return [RaiseConflict(
                    conflict_id=stable_id("conf", view.load.tenant_id, view.ref,
                                          "tracking_status", *((settled,) if settled else ())),
                    kind=_conflict_kind([p[1] for p in parties]), entity_ref=view.ref,
                    field="tracking_status", parties=parties, owner_id=setup.load_owner)]
    return []


# --------------------------------------------------------------------------------- expectations

def _has_owed(view: LoadView, expected_type: str) -> list[dict[str, Any]]:
    return [e for e in view.expectations
            if e["expected_type"] == expected_type and e["state"] in OWED_STATES]


def _commitment_expectations(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """A counterparty said they would follow up by a time. That is an Expectation: if nothing arrives
    the silence becomes visible instead of being nobody's job. A commitment that sits inside QUOTED
    or forwarded text is not a new promise and raises nothing."""
    out: list[Intent] = []
    for commitment in view.commitments:
        if commitment["in_quoted_text"]:
            continue
        out.append(RaiseExpectation(
            expectation_id=commitment_expectation_id(view.load.tenant_id, view.ref, commitment),
            subject_ref=view.ref, expected_type="counterparty_update",
            expected_source=commitment["channel"], owner_id=setup.load_owner,
            originating_timezone=commitment["timezone"], deadline_utc=commitment["due_by"]))
    return out


def _document_expectations(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """Delivery was reported and a required document is not on file: that document is now EXPECTED,
    by the brokerage's own configured deadline, on its configured channel. Delivered does not imply
    the POD arrived (CD-8) — this is the mechanism that keeps the difference visible."""
    out: list[Intent] = []
    claims = view.delivered_claims()
    # A document was expected BECAUSE delivery was reported. If that report has since been moved
    # off this load — a human corrected the binding it rested on — the reason is gone, and the
    # Expectation is cancelled with it (M8 EX-6), retained as CANCELLED. Left owed, it would call a
    # carrier late for paper on a load nobody says was delivered. M8 has no such exit from
    # INDETERMINATE: that one stays owed, and the work engine keeps it in front of a human.
    pending = {r.required_doc_type for r in view.requirements if r.state == "PENDING"}
    for expectation in view.expectations:
        kind, _, doc_type = expectation["expected_type"].partition(":")
        if kind == "document" and doc_type in pending \
                and expectation["state"] in ("RAISED", "OVERDUE"):
            out.append(CancelExpectation(
                expectation["expectation_id"],
                f"delivery is no longer reported on this load, so no {doc_type} is owed"))
    if not claims:
        return out
    first = min((c.field_of("status").facts[0] for c in claims), key=lambda f: f.as_of)
    configs = {c.required_doc_type: c for c in setup.document_requirements}
    for requirement in view.requirements:
        config = configs.get(requirement.required_doc_type)
        if config is None or requirement.state != "OUTSTANDING":
            continue
        if config.expected_channel is None or config.expected_within_hours is None:
            continue                               # no configured deadline: none is invented
        expected_type = f"document:{requirement.required_doc_type}"
        if _has_owed(view, expected_type):
            continue
        generation = len([e for e in view.expectations if e["expected_type"] == expected_type])
        deadline = utc_datetime(first.as_of) + timedelta(hours=config.expected_within_hours)
        out.append(RaiseExpectation(
            expectation_id=stable_id("exp", view.load.tenant_id, view.ref, expected_type,
                                     generation),
            subject_ref=view.ref, expected_type=expected_type,
            expected_source=config.expected_channel, owner_id=setup.load_owner,
            originating_timezone=first.originating_timezone,
            deadline_utc=format_instant(deadline)))
    return out


def _arrival_expectations(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """A CONFIRMED appointment expects an arrival by the end of its window, in the FACILITY's local
    time. The deadline is evaluated against the tracking channel's recorded coverage, so a blind
    channel yields INDETERMINATE and never "late" (CD-14). A REQUESTED appointment, or one whose
    window is in conflict, raises nothing: neither is a time anyone agreed to."""
    if setup.arrival_tracking_channel is None:
        return []
    out: list[Intent] = []
    for stop_key, appointment in view.appointments.items():
        if appointment.value("status") != "CONFIRMED":
            continue
        window = appointment.value("window")
        if window is None:
            continue
        expected_type = f"arrival:{stop_key}"
        # An appointment that MOVED moves its deadline with it. Without this the watch keeps the
        # window nobody holds any more: a truck is called late against a time that was rescheduled,
        # or is never called late against the time that replaced it.
        deadline = format_instant(facility_local_deadline(
            datetime.fromisoformat(window["end_local"]), window["timezone"]))
        stale = [e for e in view.expectations if e["expected_type"] == expected_type
                 and e["state"] in ("RAISED", "OVERDUE") and e["deadline_utc"] != deadline]
        if stale:
            for expectation in stale:
                out.append(AmendExpectation(expectation["expectation_id"], deadline)
                           if expectation["state"] == "RAISED"
                           else CancelExpectation(expectation["expectation_id"],
                                                  f"the appointment at {stop_key} was moved"))
            continue
        # ### THE OBLIGATION IS LOGICAL; A ROW IS ONE GENERATION OF IT. A truck's arrival at a stop
        # is ONE obligation however often the appointment moves, and M8 may hold several rows
        # about it: a watch that followed the appointment by amendment (and so still carries the
        # id of the window it was first raised for), watches cancelled when the appointment moved
        # away, a watch a since-overruled claim answered. What is owed is therefore asked of the
        # obligation, never of an id.
        #
        # A live watch on the deadline that now stands IS the watch, whichever row it is. Asked by
        # id, a moved appointment that was then missed got a second watch beside it.
        if any(e["expected_type"] == expected_type and e["state"] in OWED_STATES
               and e["deadline_utc"] == deadline for e in view.expectations):
            continue
        # A watch here that a STANDING record answered: the truck has been to this stop and the
        # record of that is kept. Nothing is owed, whatever window that row was raised for.
        evidence = arrival_evidence(view, stop_key)
        if any(e["expected_type"] == expected_type and e["state"] == "DISCHARGED"
               and e["discharge_observation_id"] in evidence for e in view.expectations):
            continue
        watch = (expected_type, window["end_local"], window["timezone"])
        out.append(RaiseExpectation(
            # Raised under its own id - unless nothing STANDING says the truck reached this stop
            # (the record that answered the watch was overruled or moved to another load, or the
            # appointment has come back to a window whose watch is history), in which case the
            # watch is owed again (`_owed_again_id`).
            expectation_id=(stable_id("exp", view.load.tenant_id, view.ref, *watch)
                            if evidence
                            else _owed_again_id(view, *watch)),
            subject_ref=view.ref, expected_type=expected_type,
            expected_source=setup.arrival_tracking_channel, owner_id=setup.load_owner,
            originating_timezone=window["timezone"],
            appointment_local=datetime.fromisoformat(window["end_local"])))
    return out


def arrival_evidence(view: LoadView, stop_key: str) -> list[str]:
    """The records that STAND as evidence the truck has been to this stop, as observation ids.

    A tracking signal at that stop is one. So is a signal that names NO stop, when the load has
    exactly one stop of that kind: "loaded" was at the only pickup, "delivered" at the only
    delivery — the same rule that places a stop named only by kind. Without it a system of
    record's bare DELIVERED never answers the arrival it implies, and a delivered load goes on
    asking where the truck is. With two pickups nothing is assumed about which.

    ### A CLAIM A RECORDED HUMAN OVERRULED IS NOT AMONG THEM. It is still on the load as what its
    source said. It does not say the truck arrived."""
    standing = view.standing_tracking()
    arrivals = [t.origin_observation_id for t in standing
                if t.stop_key == stop_key and t.value("status") in ARRIVAL_STATUSES]
    stop = view.stops.get(stop_key)
    kind = stop.value("stop_type") if stop is not None else None
    if kind in STAGES_PAST_STOP and len(
            [s for s in view.stops.values() if s.value("stop_type") == kind]) == 1:
        arrivals += [t.origin_observation_id for t in standing
                     if t.stop_key is None and t.value("status") in STAGES_PAST_STOP[kind]]
    return list(dict.fromkeys(arrivals))


def _owed_again_id(view: LoadView, *watch: object) -> str:
    """The id a watch is raised under when NOTHING STANDING answers it.

    ### AN OVERRULED CLAIM CANNOT GO ON DISCHARGING AN EXPECTATION. M8's DISCHARGED is terminal, and
    it should be: that row is the record that this watch WAS answered, by that record, at that
    time, and nothing here rewrites it. But a claim a recorded human has since overruled answers
    nothing — nor does a record she has moved to another load — so when it was the only answer the
    watch is OWED AGAIN: raised as the next generation of the same id, the way a required document
    is (`_document_expectations`).

    ### A WATCH THAT IS HISTORY NEVER STANDS IN FOR ONE THAT IS OWED. The obligation is the
    logical thing — this truck, this stop, this window; a generation is one row M8 kept about it.
    DISCHARGED, CANCELLED and EXPIRED are all terminal: the row says the watch was answered, or
    withdrawn because the appointment moved away, or aged out. None of them says anybody is
    waiting NOW. So when the obligation is current again — the appointment came back to the window
    that row was raised for — it is watched by the next generation, and the dead row is left
    exactly as it was. Stopping at a CANCELLED generation, as this once did, left a confirmed
    appointment with no watch at all.

    The first generation is the id the watch always had, so nothing ever raised is renamed. A
    generation that is still OWED is returned as itself: a watch already owed is not raised twice.
    No row is ever reused or reopened. Only a caller that has established that nothing standing
    answers the watch may ask."""
    states = {e["expectation_id"]: e["state"] for e in view.expectations}
    generation = 0
    while True:
        expectation_id = stable_id("exp", view.load.tenant_id, view.ref, *watch,
                                   *((generation,) if generation else ()))
        if states.get(expectation_id) in (None, *OWED_STATES):
            return expectation_id
        generation += 1


def movement_signals(view: LoadView) -> list[Any]:
    """Every movement signal on this load, oldest first by the instant it is ABOUT. A late-arriving
    report of an earlier moment sorts where it happened, so stale news never looks like fresh news."""
    return sorted(view.tracking,
                  key=lambda t: (t.field_of("status").facts[0].as_of, t.entity_id))


def tracking_expectation_id(view: LoadView, anchor: Any) -> str:
    """The watch this signal started: its own id, or the generation of it that is owed again when
    what once answered it no longer stands (`_owed_again_id`)."""
    return _owed_again_id(view, TRACKING_UPDATE, anchor.origin_observation_id)


def _tracking_expectations(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """A truck that is UNDER WAY is expected to be heard from again within the brokerage's own
    tracking cadence, counted from the last movement signal. With no cadence configured there is no
    clock — a cadence nobody chose would be a freight rule nobody chose. The deadline is M8's, and it
    is evaluated against the tracking channel's recorded coverage, so a blind channel yields
    INDETERMINATE and never "the carrier went quiet" (CD-14).

    ### PROVISIONAL — NEEDS VALIDATION (P9-D32). WHEN the clock starts (the first under-way signal),
    WHAT resets it (any movement signal, from any source) and WHEN it stops (a delivery report) are
    this build's SYNTHETIC choices, made so the corpus can be run. They are not validated freight
    rules and not a universal one: how a brokerage wants a moving truck watched is TENANT POLICY.
    They raise an Expectation and, at most, a shadow candidate — never authority for anything."""
    cadence = setup.tracking_update_cadence_minutes
    if cadence is None or setup.arrival_tracking_channel is None:
        return []
    signals = movement_signals(view)
    # Under way is where the truck has BEEN, so it is read from the claims that stand: a "loaded"
    # a recorded human overruled starts no clock.
    if view.delivered_claims() or not any(t.value("status") in UNDER_WAY_STATUSES
                                          for t in view.standing_tracking()):
        return []
    if _has_owed(view, TRACKING_UPDATE):
        return []
    anchor = signals[-1]
    fact = anchor.field_of("status").facts[0]
    # Nothing is owed, no delivery report stands and no signal is later than this one - so if M8
    # holds the watch this signal started as DISCHARGED, what discharged it no longer stands (a
    # delivery report a human has since overruled). The truck is still to be heard from.
    return [RaiseExpectation(
        expectation_id=tracking_expectation_id(view, anchor), subject_ref=view.ref,
        expected_type=TRACKING_UPDATE, expected_source=setup.arrival_tracking_channel,
        owner_id=setup.load_owner, originating_timezone=fact.originating_timezone,
        deadline_utc=format_instant(utc_datetime(fact.as_of) + timedelta(minutes=cadence)))]


def _discharges(view: LoadView, setup: TenantSetup) -> list[Intent]:
    out: list[Intent] = []
    owed = [e for e in view.expectations if e["state"] in OWED_STATES]
    if not owed:
        return out
    by_id = {e["expectation_id"]: e for e in owed}

    # A tracking update is owed since ONE movement signal; any signal about a later moment answers
    # it, and so does a report of delivery whenever it is about — nothing is moving after that, so
    # no later signal would ever come to close it.
    signals = movement_signals(view)
    delivered = {t.entity_id for t in view.delivered_claims()}
    for anchor in signals:
        expectation = by_id.get(tracking_expectation_id(view, anchor))
        if expectation is None:
            continue
        since = anchor.field_of("status").facts[0].as_of
        answers = [t.origin_observation_id for t in signals
                   if t is not anchor and (t.field_of("status").facts[0].as_of > since
                                           or t.entity_id in delivered)]
        if answers:
            out.append(DischargeExpectation(expectation["expectation_id"],
                                            tuple(dict.fromkeys(answers))))

    # A promise is answered by the next inbound word, on this load, FROM THE SENDER WHO MADE IT.
    for commitment in view.commitments:
        expectation = by_id.get(
            commitment_expectation_id(view.load.tenant_id, view.ref, commitment))
        if expectation is None:
            continue
        # A ROLE IS NOT A PARTY. The receiver's dock is not the shipper's, a colleague is not the
        # contact who promised, the driver is not the dispatcher, and on a two-carrier load one
        # carrier's driver is not the other's. A word answers a promise only when it comes from
        # the exact sender identity the promise's own record carries; no organisation, facility,
        # carrier or customer is inferred from a role. A promise whose record carries no address
        # has no identity and is matched to nothing: it stays owed and goes overdue to a named
        # human rather than being kept by whoever wrote next.
        promiser = commitment["sender_identity"]
        side = (CARRIER_SIDE_ROLES if commitment["sender_role"] in CARRIER_SIDE_ROLES
                else (commitment["sender_role"],))
        answers = [
            o["observation_id"] for o in view.observations
            if o["received_at"] > commitment["received_at"]
            and o["parsed"]["kind"] == "message"
            and o["parsed"]["payload"]["direction"] == "inbound"
            and o["parsed"]["payload"]["sender"]["role"] in side
            and promiser is not None and sender_identity(o["parsed"]["payload"]) == promiser]
        if commitment["commitment_kind"] == "send_document" \
                and commitment["sender_role"] in CARRIER_SIDE_ROLES:
            # A CARRIER's promise to send paper is kept by the PAPER, not only by another message:
            # a required document that arrived after the promise and satisfies its requirement
            # answers it. Without this a carrier who did exactly what they said is called late for
            # it. The carrier side's promise ONLY: a document records no sender, and the required
            # paper is the carrier's to send (the only side whose promise the work engine lets
            # cover it) - so it never keeps a customer's or a facility's promise for them.
            received = {o["observation_id"]: o["received_at"] for o in view.observations}
            for requirement in view.requirements:
                if requirement.state != "SATISFIED" or requirement.satisfied_by_document_id is None:
                    continue
                document = next(d for d in view.documents.values()
                                if d.entity_id == requirement.satisfied_by_document_id)
                answers += [oid for oid in document.arrivals
                            if received.get(oid, "") > commitment["received_at"]]
        if answers:
            out.append(DischargeExpectation(expectation["expectation_id"],
                                            tuple(dict.fromkeys(answers))))

    # A required document is discharged by the document itself — or, when a human moved it onto
    # this load, by the human's act, because M5 has no re-bind and the document's own row still
    # names the load it was first bound to.
    for requirement in view.requirements:
        if requirement.state != "SATISFIED" or requirement.satisfied_by_document_id is None:
            continue
        expected_type = f"document:{requirement.required_doc_type}"
        document = next(d for d in view.documents.values()
                        if d.entity_id == requirement.satisfied_by_document_id)
        human_acts = [h["source"]["observation_id"] for h in view.binding_history
                      if h["source"] is not None and h["state"] == "CONFIRMED"]
        placing_acts = [
            o["observation_id"] for o in view.observations
            if o["parsed"]["kind"] == "human_assertion"
            and o["parsed"]["payload"]["act"] in ("bind_observation", "correct_binding")]
        candidates = tuple(dict.fromkeys([*document.arrivals, *placing_acts, *human_acts]))
        for expectation in owed:
            if expectation["expected_type"] == expected_type:
                out.append(DischargeExpectation(expectation["expectation_id"], candidates))

    # An appointment's arrival is discharged by a STANDING tracking signal at that stop.
    for expectation in owed:
        if not expectation["expected_type"].startswith("arrival:"):
            continue
        arrivals = arrival_evidence(view, expectation["expected_type"].split(":", 1)[1])
        if arrivals:
            out.append(DischargeExpectation(expectation["expectation_id"], tuple(arrivals)))
    return out


# --------------------------------------------------------------------------------- money, documents

def _financial_obligations(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """A reconciliation mismatch is never adjusted away. A billed line that disagrees with the rate
    confirmation is a Conflict on what is owed to the carrier; an accessorial with no recorded human
    authorization, and an invoice with nothing to be reconciled against, are Exceptions — never
    auto-approved and never auto-disputed (V-15, V-17)."""
    out: list[Intent] = []
    tenant = view.load.tenant_id
    movements = {m.entity_id: m for m in view.movements.values()}
    for result in view.reconciliations:
        movement = movements[result.movement_id]
        ratecon = view.rate_confirmations.get(movement.entity_id)
        payable = next((p for p in view.payables.values()
                        if p.movement_id == movement.entity_id), None)
        unresolved: list[str] = []
        for discrepancy in blocking_discrepancies(result):
            line = LINE_MISMATCH_CODES.get(discrepancy.code)
            if line is not None and ratecon is not None and payable is not None:
                facts = [ratecon.field_of(line).current, payable.field_of(line).current]
                parties = _parties([f for f in facts if f is not None])
                if len(parties) >= 2:
                    out.append(RaiseConflict(
                        conflict_id=stable_id("conf", tenant, movement.ref, "owed", line),
                        kind=_conflict_kind([p[1] for p in parties]), entity_ref=movement.ref,
                        field=f"owed_to_carrier.{line}", parties=parties,
                        owner_id=setup.load_owner))
            elif discrepancy.code == "ACCESSORIAL_NOT_ON_RATE_CONFIRMATION" \
                    and discrepancy.authorization in ACCESSORIAL_UNRESOLVED:
                unresolved.append(f"{discrepancy.line} ({discrepancy.authorization})")
            elif discrepancy.code == "INVOICE_ARITHMETIC" and payable is not None:
                out.append(RaiseException(
                    exception_id=stable_id("exc", tenant, payable.ref, "invoice_arithmetic"),
                    type="carrier_invoice_arithmetic", severity="SEV2",
                    source_ref=payable.origin_observation_id, source_kind="observation",
                    owner_id=setup.load_owner, entity_ref=view.ref,
                    summary="A carrier invoice's stated total is not the sum of its own lines.",
                    specific_question="Which figure does the carrier mean to bill?"))
            elif discrepancy.code == "EXPECTED_BUY_UNESTABLISHED" and payable is not None:
                out.append(RaiseException(
                    exception_id=stable_id("exc", tenant, payable.ref, "buy_unestablished"),
                    type="buy_rate_unestablished", severity="SEV2",
                    source_ref=payable.origin_observation_id, source_kind="observation",
                    owner_id=setup.load_owner, entity_ref=view.ref,
                    summary=("A carrier invoice is on file with no rate confirmation to reconcile "
                             "it against. The rate confirmation is the only authoritative buy rate "
                             "(V-14, unvalidated); an earlier conversational figure is not one."),
                    specific_question="What buy rate was agreed for this movement, and where is "
                                      "it recorded?"))
        if unresolved and payable is not None:
            out.append(RaiseException(
                exception_id=stable_id("exc", tenant, payable.ref, "accessorial_authorization"),
                type="accessorial_authorization_unresolved", severity="SEV2",
                source_ref=payable.origin_observation_id, source_kind="observation",
                owner_id=setup.load_owner, entity_ref=view.ref,
                summary=("The carrier billed accessorial(s) that are not on the rate confirmation "
                         "and have no recorded human authorization: " + ", ".join(unresolved)
                         + "."),
                specific_question="Did a named person at this brokerage authorize each of these "
                                  "charges? Authorize or deny each one."))

    # An invoice bound to the load that no movement claims was compared against NOTHING: no
    # reconciliation above saw it. That is not "no discrepancy" — it is a silent stall, and it is
    # raised to a named human with everything needed to place it (P9-D23). Nothing is guessed: not
    # the sole movement of a one-carrier load, and not a "close enough" spelling of an MC.
    for payable in view.payables.values():
        if payable.movement_id is not None:
            continue
        explained = explain_unattributed_invoice(view, payable)
        out.append(RaiseException(
            exception_id=stable_id("exc", tenant, payable.ref, "unattributed"),
            type="carrier_invoice_unattributed", severity="SEV2",
            source_ref=payable.origin_observation_id, source_kind="observation",
            owner_id=setup.load_owner, entity_ref=view.ref,
            summary=explained["summary"], specific_question=explained["question"]))

    for charge in view.accessorials.values():
        if charge.counterparty_asserted_authorization and charge.lifecycle_state != "AUTHORIZED":
            out.append(RaiseException(
                exception_id=stable_id("exc", tenant, charge.ref, "self_authorization"),
                type="counterparty_self_authorization", severity="SEV1",
                source_ref=charge.claim_observation_ids[0], source_kind="observation",
                owner_id=setup.load_owner, entity_ref=view.ref,
                summary=(f"A counterparty asserted that the {charge.value('charge_type')} "
                         f"accessorial was already approved. No recorded human authorization "
                         f"exists. A counterparty's claim of approval is not an approval."),
                specific_question="Did a named person at this brokerage approve this charge?"))
    return out


def _document_exceptions(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """A REQUIRED document arrived and cannot be used — illegible, missing pages, or a POD nobody
    signed. It does not count, and a human is told why rather than left to find out at billing."""
    required = {c.required_doc_type for c in setup.document_requirements}
    out: list[Intent] = []
    for document in view.documents.values():
        doc_type = document.value("doc_type")
        if doc_type not in required:
            continue
        pages = document.value("pages") or {}
        problems: list[str] = []
        if document.lifecycle_state == "ILLEGIBLE":
            problems.append("it is illegible")
        if pages.get("present", 0) < pages.get("expected", 1):
            problems.append(f"{pages.get('present', 0)} of {pages.get('expected', 1)} pages arrived")
        if doc_type == "POD" and document.value("signed") is not True:
            problems.append("it carries no signature")
        if not problems:
            continue
        out.append(RaiseException(
            exception_id=stable_id("exc", view.load.tenant_id, document.ref, "unusable"),
            type="document_unusable", severity="SEV2",
            source_ref=document.origin_observation_id, source_kind="observation",
            owner_id=setup.load_owner, entity_ref=view.ref,
            summary=f"A {doc_type} arrived and cannot satisfy the requirement: "
                    + "; ".join(problems) + ".",
            specific_question=f"Can a usable {doc_type} be obtained from the carrier?"))
    return out


def _reference_correction_exceptions(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """A counterparty says an earlier message named the WRONG load. That is a claim about where
    records belong, and a counterparty's claim re-binds nothing: only a named human corrects a
    binding (M6 IB-7), which retains the binding it replaces. So nothing moves here — the person who
    owns inbound triage is asked, with the reference the sender now states."""
    out: list[Intent] = []
    for correction in view.reference_corrections:
        stated = correction["stated_reference"]
        out.append(RaiseException(
            exception_id=stable_id("exc", view.load.tenant_id, correction["observation_id"],
                                   "reference_correction", correction["index"]),
            type="counterparty_reference_correction", severity="SEV2",
            source_ref=correction["observation_id"], source_kind="observation",
            owner_id=setup.intake_owner, entity_ref=view.ref,
            summary=("A counterparty says an earlier message named the wrong load"
                     + (f" and now names {stated!r}" if stated else "")
                     + ". Nothing was re-bound: a correction to a binding is a human's act."),
            specific_question="Which load do the earlier message and this one belong to?"))
    return out
