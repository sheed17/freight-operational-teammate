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
from .foundation import format_instant, stable_id
from .history import CARRIER_SIDE_ROLES, TenantSetup, utc_datetime
from .model import TRACKING_PROGRESSION, DirectedMoney, Fact
from .projection import OWED_STATES, LoadView, commitment_expectation_id

#: Signals that report where a truck IS. A system of record that simply has not been updated yet is
#: not evidence against a later status, so `tms_status` never plays the regressing party.
CURRENT_STATE_SIGNALS: tuple[str, ...] = (
    "tracking_provider_position", "driver_assertion", "carrier_assertion",
)
ARRIVAL_STATUSES: tuple[str, ...] = ("AT_PICKUP", "AT_DELIVERY", "LOADED", "DELIVERED")
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


Intent = RaiseConflict | RaiseExpectation | DischargeExpectation | RaiseException


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
            out.append(RaiseConflict(
                conflict_id=stable_id("conf", view.load.tenant_id, entity.ref, name),
                kind=_conflict_kind([p[1] for p in parties]), entity_ref=entity.ref, field=name,
                parties=parties, owner_id=setup.load_owner))
    return out


def _tracking_conflicts(view: LoadView, setup: TenantSetup) -> list[Intent]:
    """One source reports a LATER stage and another source, at a LATER instant, reports an EARLIER
    one — a truck said to be delivered that a tracking provider then places in transit. That is a
    contradiction a human looks at. It is never resolved here by recency or by source."""
    staged = [t for t in view.tracking if t.value("status") in TRACKING_PROGRESSION]
    staged.sort(key=lambda t: (t.field_of("status").facts[0].as_of, t.entity_id))
    for later in staged:
        later_fact = later.field_of("status").facts[0]
        if later.value("signal") not in CURRENT_STATE_SIGNALS:
            continue
        for earlier in staged:
            earlier_fact = earlier.field_of("status").facts[0]
            if earlier_fact.as_of >= later_fact.as_of:
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
                                          "tracking_status"),
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
        out.append(RaiseExpectation(
            expectation_id=stable_id("exp", view.load.tenant_id, view.ref, expected_type,
                                     window["end_local"], window["timezone"]),
            subject_ref=view.ref, expected_type=expected_type,
            expected_source=setup.arrival_tracking_channel, owner_id=setup.load_owner,
            originating_timezone=window["timezone"],
            appointment_local=datetime.fromisoformat(window["end_local"])))
    return out


def _discharges(view: LoadView, setup: TenantSetup) -> list[Intent]:
    out: list[Intent] = []
    owed = [e for e in view.expectations if e["state"] in OWED_STATES]
    if not owed:
        return out
    by_id = {e["expectation_id"]: e for e in owed}

    # A carrier's promise is answered by the carrier's next inbound word on this load.
    for commitment in view.commitments:
        expectation = by_id.get(
            commitment_expectation_id(view.load.tenant_id, view.ref, commitment))
        if expectation is None:
            continue
        # A dispatcher's promise is kept by the driver's text as much as by the dispatcher's own.
        side = (CARRIER_SIDE_ROLES if commitment["sender_role"] in CARRIER_SIDE_ROLES
                else (commitment["sender_role"],))
        answers = [
            o["observation_id"] for o in view.observations
            if o["received_at"] > commitment["received_at"]
            and o["parsed"]["kind"] == "message"
            and o["parsed"]["payload"]["direction"] == "inbound"
            and o["parsed"]["payload"]["sender"]["role"] in side]
        if answers:
            out.append(DischargeExpectation(expectation["expectation_id"], tuple(answers)))

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

    # An appointment's arrival is discharged by a tracking signal at that stop.
    for expectation in owed:
        if not expectation["expected_type"].startswith("arrival:"):
            continue
        stop_key = expectation["expected_type"].split(":", 1)[1]
        arrivals = [t.origin_observation_id for t in view.tracking
                    if t.stop_key == stop_key and t.value("status") in ARRIVAL_STATUSES]
        if arrivals:
            out.append(DischargeExpectation(expectation["expectation_id"],
                                            tuple(dict.fromkeys(arrivals))))
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
