"""A deterministic hostile mutation layer for the operational work engine.

Each mutant is one of the through-time histories with ONE thing done to it that an inbox really does:
a record arrives twice, arrives late, arrives out of order, never arrives; a promise is repeated; the
process restarts in the middle; the very same load turns up at another brokerage. No randomness: the
same mutants, in the same order, every run. No model is called.

### THE ORACLE DOES NOT ASK THE WORK ENGINE WHAT THE WORK IS. `audit_state` reads the canonical
`LoadView` itself — its Expectations, Conflicts, Exceptions, requirements, payables and held records —
and checks the engine's answer against it:

    silent stall        every live signal a human or Neyma should know about is behind some need
    stale work          every need is behind a signal that is still live
    false quiet         a load with a live signal is never reported as having no work
    false escalation    a need that is a human's is one of the kinds a human must decide
    duplicate work      one need id appears once; one cause is one need
    billing readiness   reported ready if and only if the canonical guard says so, and never while a
                        document is owed, the sell rate is unsettled or a billing conflict is open
    tenant              every need, origin and evidence id is the brokerage's own
    authority           no human's need offers WAIT; nothing carries money

A finding is a product defect to be FIXED. The fixtures are not tuned around one.

SYNTHETIC development input. Nothing here is a design-partner observation.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from freight_recon.freight_domain.corpus_run import cross_tenant_violations
from freight_recon.freight_domain.financial import blocking_discrepancies
from freight_recon.freight_domain.history import (
    OBSERVATION_KINDS,
    FreightHistory,
    InboundRecord,
    TenantSetup,
)
from freight_recon.freight_domain.intake import FreightIntake
from freight_recon.freight_domain.load_work import (
    Handling,
    LoadWorkState,
    NeedKind,
    ShadowAction,
    evaluate_load_work,
)
from freight_recon.freight_domain.projection import LoadView

from .parties import CEDAR, NORTHLINE
from .work_histories import WORK_SETUPS, build_work_histories

#: Kinds only a named human may settle. A need of one of these that is NOT human-required, or a
#: human-required need of any other kind, is a finding.
HUMAN_KINDS: frozenset[NeedKind] = frozenset({
    NeedKind.EVIDENCE_CONFLICT, NeedKind.IDENTITY_UNRESOLVED, NeedKind.DOCUMENT_NEEDS_READING,
    NeedKind.INVOICE_UNATTRIBUTED, NeedKind.INVOICE_DISCREPANCY,
    NeedKind.ACCESSORIAL_UNAUTHORIZED, NeedKind.RECONCILIATION_BLOCKED, NeedKind.BILLING_BLOCKED,
    NeedKind.BILLING_REQUIREMENTS_UNKNOWN, NeedKind.UNCLASSIFIED_EXCEPTION,
})
#: Exception types whose liveness this oracle reads from the cause, not from the row.
_JUDGED_BY_CAUSE: frozenset[str] = frozenset({
    "carrier_invoice_unattributed", "accessorial_authorization_unresolved",
    "counterparty_self_authorization", "carrier_invoice_arithmetic", "buy_rate_unestablished",
    "document_unusable", "expectation_unmet", "counterparty_reference_correction",
})
_MONEY = re.compile(r"\bUSD\b|\$\s?\d|amount_minor|\d,\d{3}\.\d{2}")
#: Every table a canonical row can be written to. Evaluating work must leave all of them alone.
CANONICAL_TABLES: tuple[str, ...] = (
    "observations", "identity_binding_claims", "external_entity_mappings", "conflicts",
    "conflict_parties", "expectations", "exceptions", "evidence", "evidence_spans", "work_items",
    "event_outbox",
)


@dataclass(frozen=True)
class Mutant:
    mutant_id: str
    operator: str
    base: str
    histories: tuple[FreightHistory, ...]
    restart_after: str | None = None          # a record label: the intake is rebuilt just after it
    same_final_work_as_base: bool = False


@dataclass
class MutantResult:
    mutant: Mutant
    steps: int = 0
    evaluations: int = 0
    findings: list[str] = field(default_factory=list)
    final: dict[str, tuple[tuple[str, str, str, str], ...]] = field(default_factory=dict)


def row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
            for t in CANONICAL_TABLES}


# ============================================================ the oracle

def live_signals(view: LoadView) -> dict[str, str]:
    """Every canonical signal on this load that somebody should know about, read from the view
    itself and keyed the way a need names its origins. The value says what kind of thing it is."""
    signals: dict[str, str] = {}
    for expectation in view.owed_expectations():
        signals[f"expectation:{expectation['expectation_id']}"] = "expectation"
    for conflict in view.open_conflicts():
        signals[f"conflict:{conflict['conflict_id']}"] = "conflict"
    delivered = bool(view.delivered_claims())
    for requirement in view.requirements:
        if requirement.state == "OUTSTANDING" or (requirement.state == "UNKNOWN" and delivered):
            signals[f"requirement:{requirement.requirement_id}"] = "requirement"
    for payable in view.payables.values():
        if payable.movement_id is None:
            signals[f"payable:{payable.entity_id}"] = "unattributed_invoice"
    payables = {p.entity_id for p in view.payables.values()}
    for result in view.reconciliations:
        if result.payable_id not in payables:
            continue                                  # nothing has been billed against it
        blocking = blocking_discrepancies(result)
        undecided = [d for d in blocking if d.code == "ACCESSORIAL_NOT_ON_RATE_CONFIRMATION"
                     and d.authorization != "DENIED"]
        if [d for d in blocking if d not in undecided] or (
                result.status == "COMPUTED" and result.actual is not None and not blocking):
            signals[f"reconciliation:{result.reconciliation_id}"] = "reconciliation"
        for discrepancy in undecided:
            charge = view.accessorials.get(discrepancy.line)
            if charge is not None:
                signals[f"accessorial:{charge.entity_id}"] = "undecided_accessorial"
    for charge in view.accessorials.values():
        if charge.counterparty_asserted_authorization \
                and charge.lifecycle_state not in ("AUTHORIZED", "DENIED"):
            signals[f"accessorial:{charge.entity_id}"] = "claimed_approval"
    for item in view.ambiguous_candidates:
        signals[f"observation:{item.observation_id}"] = "held_record"
    for exception in view.open_exceptions():
        # An Exception whose cause the record can show cured is judged by that cause, above. Every
        # other open Exception is a question somebody still has to answer.
        if exception["type"] not in _JUDGED_BY_CAUSE:
            signals[f"exception:{exception['type']}@{exception['source_ref']}"] = "open_exception"
    return signals


def _origin_is_live(origin: str, view: LoadView, signals: dict[str, str]) -> bool:
    kind, _, ident = origin.partition(":")
    if origin in signals:
        return True
    if kind == "exception":
        return any(f"{x['type']}@{x['source_ref']}" == ident for x in view.open_exceptions())
    if kind == "document":
        return any(d.entity_id == ident for d in view.documents.values())
    if kind == "accessorial":
        return any(c.entity_id == ident and c.lifecycle_state not in ("AUTHORIZED", "DENIED")
                   for c in view.accessorials.values())
    if kind in ("appointment", "stop"):
        return origin in {a.ref for a in view.appointments.values()} | {
            s.ref for s in view.stops.values()}
    if kind == "field":
        return True
    if kind == "reconciliation":
        return any(r.reconciliation_id == ident for r in view.reconciliations)
    return False


def audit_state(state: LoadWorkState, view: LoadView, *, tenant: str) -> list[str]:
    """Everything wrong with one evaluation, as findings. An empty list is a clean answer."""
    findings: list[str] = []
    where = f"{tenant}/{state.load_number}@{state.as_of}"
    signals = live_signals(view)
    origins = {origin for need in state.needs for origin in need.origins}

    ids = [n.need_id for n in state.needs]
    if len(ids) != len(set(ids)):
        findings.append(f"{where}: DUPLICATE WORK - a need id appears more than once")
    for signal, kind in signals.items():
        if signal not in origins:
            findings.append(f"{where}: SILENT STALL - live {kind} {signal} is behind no need")
    if state.routine_work_is_zero and signals:
        findings.append(f"{where}: FALSE QUIET - {len(signals)} live signal(s) and no work")
    for need in state.needs:
        if not need.origins:
            findings.append(f"{where}: {need.kind.value} names no origin")
        if not any(_origin_is_live(o, view, signals) for o in need.origins):
            findings.append(f"{where}: STALE WORK - {need.kind.value} rests on nothing live "
                            f"({list(need.origins)})")
        if need.tenant_id != tenant or need.load_id != state.load_id:
            findings.append(f"{where}: TENANT - a need belongs to {need.tenant_id}")
        if need.human_required != (need.kind in HUMAN_KINDS) and not (
                need.kind is NeedKind.DOCUMENT_REQUIRED and need.human_required):
            findings.append(f"{where}: {'FALSE ESCALATION' if need.human_required else 'A HUMAN NEED DOWNGRADED'}"
                            f" - {need.kind.value} human_required={need.human_required}")
        if need.human_required and (need.handling is not Handling.HUMAN_REQUIRED
                                    or ShadowAction.WAIT in need.actions):
            findings.append(f"{where}: AUTHORITY - a human's need ({need.kind.value}) can be "
                            f"waited away")
        if need.handling is Handling.MODEL_REASONING and len(need.actions) < 2:
            findings.append(f"{where}: {need.kind.value} is undecided with nothing to choose")
        if not need.owner_id:
            findings.append(f"{where}: {need.kind.value} has no accountable owner")
    counts = [k for k in (NeedKind.CARRIER_STATUS_OVERDUE, NeedKind.APPOINTMENT_UNCONFIRMED)
              if len([n for n in state.needs if n.kind is k]) > 1]
    if counts:
        findings.append(f"{where}: DUPLICATE WORK - more than one {counts[0].value}")

    # Billing readiness, recomputed from the view rather than read back from the state.
    eligible = view.invoice is not None and view.invoice.lifecycle_state == "ELIGIBLE"
    if state.billing_ready != eligible:
        findings.append(f"{where}: BILLING - reported {state.billing_ready}, the guard says "
                        f"{eligible}")
    if state.billing_ready:
        if not view.delivered_claims():
            findings.append(f"{where}: BILLING - ready with no delivery reported")
        if any(r.state != "SATISFIED" for r in view.requirements):
            findings.append(f"{where}: BILLING - ready with a document requirement unmet")
        if view.load.condition("sell") != "consistent":
            findings.append(f"{where}: BILLING - ready with the sell rate "
                            f"{view.load.condition('sell')}")
        if any(c["field"] in ("sell", "tracking_status") for c in view.open_conflicts()):
            findings.append(f"{where}: BILLING - ready with a billing conflict open")

    document = json.dumps(state.as_document(), sort_keys=True, default=str)
    if _MONEY.search(document):
        findings.append(f"{where}: MONEY - an amount appears in the work state")
    return findings


def signature(state: LoadWorkState) -> tuple[tuple[str, str, str, str], ...]:
    """What the work IS, without when it was asked: comparable across a mutant and its base."""
    return tuple(sorted((n.need_id, n.kind.value, n.status.value, n.handling.value)
                        for n in state.needs))


# ============================================================ mutation operators

def _relabel(record: InboundRecord, suffix: str, **changes: Any) -> InboundRecord:
    return replace(record, label=f"{record.label}~{suffix}", **changes)


def _history(base: FreightHistory, records: Sequence[InboundRecord]) -> FreightHistory:
    return FreightHistory(history_id=base.history_id, title=base.title, tenant=base.tenant,
                          hostile=base.hostile, records=tuple(records), expected={})


def _retime(records: Sequence[InboundRecord], slots: Sequence[str]) -> list[InboundRecord]:
    """The same records in a NEW order, each arriving in the slot that order gives it. What a record
    is ABOUT (`as_of`) is untouched: only when it arrived moves."""
    return [replace(record, received_at=slot) for record, slot in zip(records, slots)]


def duplicate_every_record(base: FreightHistory) -> FreightHistory:
    """Every observation arrives twice, the copy at the same instant as the original."""
    out: list[InboundRecord] = []
    for record in base.records:
        out.append(record)
        if record.kind in OBSERVATION_KINDS:
            out.append(_relabel(record, "dup"))
    return _history(base, out)


def redeliver_first_at_the_end(base: FreightHistory) -> FreightHistory | None:
    """The first message or document is re-delivered after everything else has happened."""
    first = next((r for r in base.records if r.kind in ("message", "document")), None)
    if first is None:
        return None
    return _history(base, [*base.records,
                           _relabel(first, "again", received_at=base.records[-1].received_at)])


def drop(base: FreightHistory, label: str) -> FreightHistory:
    return _history(base, [r for r in base.records if r.label != label])


def swap_with_next(base: FreightHistory, index: int) -> FreightHistory:
    """Two neighbouring records arrive in the opposite order."""
    records = list(base.records)
    slots = [r.received_at for r in records]
    records[index], records[index + 1] = records[index + 1], records[index]
    return _history(base, _retime(records, slots))


def delay_to_the_end(base: FreightHistory, label: str) -> FreightHistory:
    """One record arrives after everything else — still saying what it said about the earlier
    moment it describes."""
    moved = next(r for r in base.records if r.label == label)
    rest = [r for r in base.records if r.label != label]
    return _history(base, [*rest, replace(moved, received_at=rest[-1].received_at)])


def repeat_the_promise(base: FreightHistory) -> FreightHistory | None:
    """A counterparty says the same thing again a minute later, as a NEW message."""
    for index, record in enumerate(base.records):
        asserts = record.payload.get("asserts") if record.kind == "message" else None
        if asserts and any(a.get("type") == "commitment" for a in asserts):
            copy = _relabel(record, "said-again", external_id=f"{record.external_id}-again")
            return _history(base, [*base.records[:index + 1], copy, *base.records[index + 1:]])
    return None


def at_another_brokerage(base: FreightHistory) -> FreightHistory:
    """The same records — same load number, PO, BOL, carrier, invoice number and message ids — as
    another brokerage's own freight."""
    return FreightHistory(history_id=f"{base.history_id}@cedar", title=base.title, tenant=CEDAR,
                          hostile=base.hostile, records=base.records, expected={})


_DROPPABLE = ("document", "tracking_event", "message", "appointment", "human_assertion")


def build_mutants() -> list[Mutant]:
    """The whole deterministic battery, in a fixed order."""
    mutants: list[Mutant] = []

    def add(operator: str, base: FreightHistory, histories: Sequence[FreightHistory | None], *,
            tag: str = "", **kw: Any) -> None:
        if any(h is None for h in histories):
            return
        mutants.append(Mutant(
            mutant_id=f"{base.history_id}:{operator}" + (f":{tag}" if tag else ""),
            operator=operator, base=base.history_id,
            histories=tuple(h for h in histories if h is not None), **kw))

    bases = [h for h in build_work_histories() if h.tenant == NORTHLINE]
    for base in bases:
        add("duplicate_arrival", base, [duplicate_every_record(base)],
            same_final_work_as_base=True)
        add("late_redelivery", base, [redeliver_first_at_the_end(base)],
            same_final_work_as_base=True)
        middle = base.records[len(base.records) // 2].label
        add("restart", base, [_history(base, base.records)], restart_after=middle,
            same_final_work_as_base=True)
        # The neighbour runs FIRST, so its rows are already in the database when this brokerage's
        # identical load arrives.
        add("same_load_at_another_brokerage", base, [at_another_brokerage(base), base],
            same_final_work_as_base=True)
        add("repeated_promise", base, [repeat_the_promise(base)])
        for record in base.records:
            if record.kind in _DROPPABLE:
                add("never_arrives", base, [drop(base, record.label)], tag=record.label)
        movable = [i for i, r in enumerate(base.records[:-1])
                   if r.kind in _DROPPABLE and base.records[i + 1].kind in _DROPPABLE]
        for index in movable[:2]:
            add("reordered", base, [swap_with_next(base, index)],
                tag=base.records[index].label)
        late = next((r for r in base.records if r.kind in ("tracking_event", "message")), None)
        if late is not None and late is not base.records[-1]:
            add("arrives_late", base, [delay_to_the_end(base, late.label)], tag=late.label)
    return mutants


# ============================================================ running one

def run_mutant(conn: sqlite3.Connection, mutant: Mutant, *,
               setups: dict[str, TenantSetup] | None = None,
               intake_factory: Callable[..., FreightIntake] = FreightIntake) -> MutantResult:
    """Step a mutant through the real spine on its own database, auditing every load after every
    record: the oracle, idempotence, and that evaluating wrote nothing."""
    setups = setups or WORK_SETUPS
    result = MutantResult(mutant=mutant)
    intakes: dict[str, FreightIntake] = {}
    for history in mutant.histories:
        intake = intakes.get(history.tenant) or intake_factory(conn, setups[history.tenant])
        intakes[history.tenant] = intake
        for record in history.records:
            intake.ingest(record)
            result.steps += 1
            before = row_counts(conn)
            as_of = intake.foundation.now()
            projection = intake.projection()
            for view in projection.loads.values():
                state = evaluate_load_work(view, setup=intake.setup, as_of=as_of)
                again = evaluate_load_work(view, setup=intake.setup, as_of=as_of)
                result.evaluations += 1
                if state.digest() != again.digest():
                    result.findings.append(f"{mutant.mutant_id}: evaluating the same state twice "
                                           f"gave two answers")
                result.findings.extend(f"{mutant.mutant_id} after {record.label}: {finding}"
                                       for finding in audit_state(state, view,
                                                                  tenant=history.tenant))
                if history.tenant == NORTHLINE:
                    result.final[state.load_number or state.load_id] = signature(state)
            if row_counts(conn) != before:
                result.findings.append(f"{mutant.mutant_id} after {record.label}: evaluating "
                                       f"work WROTE canonical rows")
            if mutant.restart_after == record.label:
                # The process dies here. Everything it knew is gone; the database is not.
                intake = intake_factory(conn, setups[history.tenant])
                intakes[history.tenant] = intake
    violations = cross_tenant_violations(conn)
    if violations:
        result.findings.append(f"{mutant.mutant_id}: CROSS-TENANT {violations}")
    for tenant, intake in intakes.items():
        effects = sum(intake.foundation.effect_surface_counts().values())
        if effects:
            result.findings.append(f"{mutant.mutant_id}: {effects} external-effect row(s) for "
                                   f"{tenant}")
    return result


__all__ = ["CANONICAL_TABLES", "HUMAN_KINDS", "Mutant", "MutantResult", "audit_state",
           "build_mutants", "live_signals", "row_counts", "run_mutant", "signature"]
