"""P9 deep-end 4 — the continuous load loop: ONE LOAD'S OPERATING PICTURE, AT EVERY MOMENT OF ITS LIFE.

    booked -> pickup -> tracking / communications -> delivery -> POD / documents
           -> reconciliation -> customer billing-ready

`load_work.py` answers one question at one instant: what work remains on this load? This module runs
a load THROUGH TIME and keeps the picture an operator would want in front of them — after every
record that arrives, and at every deadline that passes with nothing arriving at all:

    what is happening            what evidence supports it          what changed since last time
    what work remains            what is overdue                    what we are waiting for
    what Neyma would do next     what needs a human, and why        is customer billing ready
    is carrier-side work open    is the load genuinely QUIET        how many human touches so far

### SHADOW ONLY. NOTHING HERE ACTS. A `Proposal` is a sentence about what could be done, and its
`draft` is text nobody sends. An `Escalation` is a question laid in front of a named human, and
nothing here answers it. There is no send, no write, no adapter, no gate and no grant behind any of
it: this module imports none, and the ships-dark guards prove the package cannot reach one.

### IT IS A READ MODEL OVER THE CANONICAL RECORD. Every picture is computed from one load's
`LoadView` and its `LoadWorkState`. It writes nothing. The same history replayed gives the same
pictures; a duplicate record changes none; a restart loses none, because nothing lived only in
memory. The one thing the runner remembers between moments is the PREVIOUS picture, and only to say
what changed.

### TIME PASSING IS AN EVENT. A deadline that passes in silence is the moment the work changes
hands — from waiting to something Neyma would do, or to a human. The runner therefore evaluates at
every deadline that falls before the next record arrives, by letting the clock pass (the same `clock`
record a history may carry). No deadline is invented: each tick is at a `due_by` the canonical record
already holds.

### NO MONEY. A picture names a discrepancy by its code. Timeline sentences are quoted with their
amounts withheld, because a picture is meant to be shown, logged and compared.

### QUIET IS AN ANSWER, AND IT IS NEVER A GUESS. A load is quiet when it has no needs at all. Open
Conflicts, owed Expectations and open Exceptions whose cause stands are needs (`load_work.py`), so a
load with any of them is not quiet — and an independent audit, handed in by the caller, re-derives
that from the canonical record at every moment.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from .corpus_run import cross_tenant_violations
from .foundation import format_instant
from .history import FreightHistory, InboundRecord, TenantSetup, to_utc, utc_datetime
from .intake import FreightIntake
from .interpretation import FreightInterpreter
from .load_work import (
    EvidenceRef,
    Handling,
    LoadWorkState,
    NeedKind,
    NeedStatus,
    OperationalNeed,
    ShadowAction,
    Stage,
    evaluate_load_work,
    evaluate_unplaced_work,
)
from .projection import LoadView
from .work_run import WorkHistoryResult, check_checkpoint

LOOP_VERSION = "p9-load-loop-1"

#: Work that concerns what the CARRIER is owed. It never gates customer billing readiness (P9-D41),
#: and a load with any of it is never quiet.
CARRIER_SIDE_KINDS: tuple[NeedKind, ...] = (
    NeedKind.INVOICE_UNATTRIBUTED, NeedKind.INVOICE_DISCREPANCY,
    NeedKind.ACCESSORIAL_UNAUTHORIZED, NeedKind.RECONCILIATION_BLOCKED,
)
#: A deadline has passed: provably late, late on the asking clock, or passed while we were blind.
LATE_STATUSES: tuple[NeedStatus, ...] = (NeedStatus.OVERDUE, NeedStatus.DUE, NeedStatus.UNVERIFIED)
#: How long after a deadline the loop looks again when nothing has arrived.
TICK_GRACE = timedelta(minutes=1)
#: How many of the load's most recent timeline entries are quoted as evidence for the picture.
EVIDENCE_ENTRIES = 5

_STAGE_SENTENCE: dict[Stage, str] = {
    Stage.PLANNING: "Tendered. No carrier is on the load yet: covering it is outside this loop.",
    Stage.DISPATCHED: "Booked with a carrier. Nothing has been picked up.",
    Stage.AT_PICKUP: "The truck is reported at the pickup.",
    Stage.IN_TRANSIT: "Picked up and reported in transit.",
    Stage.DELIVERED: "Delivery has been reported.",
    Stage.DISPUTED: "The sources contradict each other about where this load is.",
}
#: An amount as the timeline writes it: a currency code, a figure, and its direction.
_AMOUNT = re.compile(r"\b[A-Z]{3} -?[\d,]+\.\d{2}(?: (?:IN|OUT|QUOTED))?")
_BARE_AMOUNT = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?|\b\d{1,3}(?:,\d{3})+\.\d{2}\b")


def without_money(text: str) -> str:
    """A timeline sentence with every amount withheld. The sentence still says WHAT happened."""
    return _BARE_AMOUNT.sub("[amount withheld]", _AMOUNT.sub("[amount withheld]", text))


# ================================================================================= the picture

@dataclass(frozen=True)
class Proposal:
    """What Neyma WOULD do about one need. Words. Nothing executes and nothing is sent."""

    need_id: str
    kind: str
    action: str
    to: str | None
    why: str
    draft: str | None = None             # the message it would send, if the action is a message
    undecided: bool = False              # act-or-wait is not settled by the record

    def as_document(self) -> dict[str, Any]:
        return {"need_id": self.need_id, "kind": self.kind, "action": self.action, "to": self.to,
                "why": self.why, "draft": self.draft, "undecided": self.undecided,
                "sent": False}


@dataclass(frozen=True)
class Escalation:
    """Everything a named human needs in order to decide one thing: the question, why it is theirs,
    and the records it rests on. Nothing here decides it for them."""

    need_id: str
    kind: str
    owner_id: str | None
    question: str | None
    why: str
    reason_codes: tuple[str, ...]
    evidence: tuple[EvidenceRef, ...]
    status: str

    def as_document(self) -> dict[str, Any]:
        return {"need_id": self.need_id, "kind": self.kind, "owner_id": self.owner_id,
                "question": self.question, "why": self.why,
                "reason_codes": list(self.reason_codes), "status": self.status,
                "evidence": [e.as_document() for e in self.evidence]}


@dataclass(frozen=True)
class Change:
    """One thing that is different from the previous picture of this load."""

    what: str            # FIRST_SEEN STAGE STATUS OPENED CLOSED MOVED BILLING QUIET HUMAN_ACT HAPPENED
    subject: str
    detail: str

    def as_document(self) -> dict[str, str]:
        return {"what": self.what, "subject": self.subject, "detail": self.detail}

    def token(self) -> str:
        return f"{self.what}:{self.subject}"


@dataclass(frozen=True)
class HumanTouches:
    """How much of a human this load has cost, read from the canonical record.

    `acts` are decisions a human actually recorded on this load. `answered` are needs the record
    shows a human's decision settled. `open` are needs waiting on a human right now. A touch is
    counted when a human had to act: `total` is the acts made plus the ones still owed."""

    acts: int
    answered: int
    open: int

    @property
    def total(self) -> int:
        return self.acts + self.open

    def as_document(self) -> dict[str, int]:
        return {"acts": self.acts, "answered": self.answered, "open": self.open,
                "total": self.total}


@dataclass(frozen=True)
class LoadMoment:
    """One load, at one moment: the thirteen answers."""

    index: int
    history_id: str
    trigger: str                         # the record that arrived, or the deadline that passed
    trigger_kind: str
    disposition: str
    about_this_load: bool                # did the record that arrived concern THIS load
    state: LoadWorkState
    happening: str
    evidence: tuple[str, ...]
    changes: tuple[Change, ...]
    proposals: tuple[Proposal, ...]
    escalations: tuple[Escalation, ...]
    touches: HumanTouches
    timeline_ids: frozenset[str] = field(default_factory=frozenset, compare=False)

    # ------------------------------------------------------------------ the answers

    @property
    def as_of(self) -> str:
        return self.state.as_of

    @property
    def load_number(self) -> str | None:
        return self.state.load_number

    @property
    def work(self) -> tuple[OperationalNeed, ...]:
        return self.state.needs

    @property
    def overdue(self) -> tuple[OperationalNeed, ...]:
        return tuple(n for n in self.state.needs if n.status in LATE_STATUSES)

    @property
    def waiting(self) -> tuple[OperationalNeed, ...]:
        return self.state.waiting

    @property
    def carrier_side(self) -> tuple[OperationalNeed, ...]:
        return tuple(n for n in self.state.needs if n.kind in CARRIER_SIDE_KINDS)

    @property
    def billing_ready(self) -> bool:
        return self.state.billing_ready

    @property
    def booked(self) -> bool:
        """Whether a carrier is on the load. This loop begins at BOOKED: covering a tendered load
        is work, and it is not work this loop models."""
        return self.state.stage is not Stage.PLANNING

    @property
    def quiet(self) -> bool:
        """Nothing is owed and nothing is waited for - on a load that is in the loop. A tendered
        load with no carrier has no needs here only because finding it a carrier is outside this
        loop; it is reported NOT quiet, never as finished."""
        return self.state.routine_work_is_zero and self.booked

    @property
    def next_step(self) -> str:
        """What happens next, in one word-group: a human's question, Neyma's first proposal, a
        wait, or nothing."""
        if self.escalations:
            return f"HUMAN:{self.escalations[0].kind}"
        if self.proposals:
            return f"NEYMA:{self.proposals[0].action}"
        if self.state.needs:
            return "WAIT"
        return "NOTHING" if self.booked else "NOT_BOOKED"

    def as_document(self) -> dict[str, Any]:
        """The replay-stable shape of the picture. It carries no money."""
        return {
            "version": LOOP_VERSION, "tenant_id": self.state.tenant_id,
            "load_id": self.state.load_id, "load_number": self.state.load_number,
            "as_of": self.as_of, "trigger": self.trigger, "trigger_kind": self.trigger_kind,
            "happening": self.happening, "stage": self.state.stage.value,
            "status": self.state.known_status, "evidence": list(self.evidence),
            "changes": [c.as_document() for c in self.changes],
            "work": [n.as_document() for n in self.state.needs],
            "overdue": [n.need_id for n in self.overdue],
            "waiting": [n.need_id for n in self.waiting],
            "proposals": [p.as_document() for p in self.proposals],
            "escalations": [e.as_document() for e in self.escalations],
            "billing_ready": self.billing_ready,
            "billing_blockers": list(self.state.billing_blockers),
            "carrier_side": [n.need_id for n in self.carrier_side],
            "quiet": self.quiet, "posture": self.state.posture.value,
            "housekeeping": len(self.state.housekeeping), "next_step": self.next_step,
            "human_touches": self.touches.as_document(),
        }

    def digest(self) -> str:
        """What the picture IS. `changes` are left out: they describe the road to this moment, and
        a restarted process reaches the same place without remembering the road."""
        document = self.as_document()
        document.pop("changes")
        text = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def signature(state: LoadWorkState) -> tuple[Any, ...]:
    """What a load's work IS, without when it was asked. Two evaluations with the same signature are
    the same picture a moment apart."""
    return (state.stage.value, state.known_status, state.billing_ready,
            tuple(sorted(state.billing_blockers)), len(state.housekeeping),
            tuple(sorted((n.need_id, n.status.value, n.handling.value, n.due_by or "",
                          n.reason_codes) for n in state.needs)),
            tuple(sorted(s.need_id for s in state.settled)))


# ================================================================================= building one

def _carrier_name(view: LoadView) -> str | None:
    names = [c.value("legal_name") for c in view.carriers.values() if c.value("legal_name")]
    return names[0] if len(set(names)) == 1 else None


def _stop_for(view: LoadView, need: OperationalNeed) -> tuple[str | None, Any]:
    """The stop a need is about, when its reason codes or related refs name one."""
    for code in need.reason_codes:
        if ":" in code and code.rsplit(":", 1)[1] in view.stops:
            key = code.rsplit(":", 1)[1]
            return key, view.stops[key]
    return None, None


def _window(view: LoadView, stop_key: str | None) -> str | None:
    appointment = view.appointments.get(stop_key or "")
    window = appointment.value("window") if appointment is not None else None
    if not isinstance(window, Mapping):
        return None
    return (f"{window.get('start_local')} to {window.get('end_local')} "
            f"({window.get('timezone')})")


def _draft(view: LoadView, need: OperationalNeed, action: ShadowAction) -> str | None:
    """The message this action WOULD be, assembled from the canonical record. A draft is text: no
    channel is opened, no recipient is resolved to an address, and nothing is sent."""
    load = view.load.value("load_ref") or view.load_id
    if action is ShadowAction.REQUEST_CARRIER_STATUS:
        return (f"Load {load}: we have not had the update we expected. Where is the truck now, "
                f"and what is the current ETA to the next stop?")
    if action is ShadowAction.REQUEST_POD:
        delivered = next((s.value("facility_name") for s in view.stops.values()
                          if s.value("stop_type") == "DELIVERY"), None)
        where = f" at {delivered}" if delivered else ""
        return (f"Load {load} is reported delivered{where}. Please send the signed proof of "
                f"delivery, all pages, so the load can be closed out.")
    if action is ShadowAction.VERIFY_APPOINTMENT:
        key, stop = _stop_for(view, need)
        facility = stop.value("facility_name") if stop is not None else None
        window = _window(view, key)
        what = f" at {facility}" if facility else ""
        when = f" We have it as {window}." if window else ""
        return (f"Load {load}: please confirm the appointment{what}.{when} Reply with the "
                f"confirmed window or the new one.")
    return None


def _proposals(view: LoadView, state: LoadWorkState) -> tuple[Proposal, ...]:
    out: list[Proposal] = []
    carrier = _carrier_name(view)
    for need in state.candidates:
        undecided = need.handling is Handling.MODEL_REASONING
        for action in need.actions:
            if action is ShadowAction.WAIT:
                continue
            to = need.counterparty
            if to == "carrier" and carrier:
                to = f"carrier ({carrier})"
            out.append(Proposal(need_id=need.need_id, kind=need.kind.value, action=action.value,
                                to=to, why=need.why, draft=_draft(view, need, action),
                                undecided=undecided))
    return tuple(out)


def _escalations(state: LoadWorkState) -> tuple[Escalation, ...]:
    return tuple(Escalation(need_id=n.need_id, kind=n.kind.value, owner_id=n.owner_id,
                            question=n.question, why=n.why, reason_codes=n.reason_codes,
                            evidence=n.evidence, status=n.status.value)
                 for n in state.human_attention)


def _human_acts(view: LoadView) -> int:
    return len([o for o in view.observations
                if (o.get("parsed") or {}).get("kind") == "human_assertion"])


def _touches(view: LoadView, state: LoadWorkState) -> HumanTouches:
    return HumanTouches(acts=_human_acts(view),
                        answered=len([s for s in state.settled if s.how == "RESOLVED"]),
                        open=len(state.human_attention))


def _happening(view: LoadView, state: LoadWorkState) -> str:
    parts = [_STAGE_SENTENCE[state.stage]]
    carrier = _carrier_name(view)
    if carrier and state.stage is not Stage.PLANNING:
        parts.append(f"Carrier: {carrier}.")
    if state.known_status:
        parts.append(f"System of record says {state.known_status}.")
    if state.stage is Stage.DELIVERED:
        for doc_type, condition in sorted(state.requirements.items()):
            parts.append(f"{doc_type}: {condition}.")
    return " ".join(parts)


def _evidence(view: LoadView, as_of: str) -> tuple[str, ...]:
    entries = [e for e in view.timeline if e.at <= as_of][-EVIDENCE_ENTRIES:]
    return tuple(f"{e.at} {without_money(e.summary)}"
                 f" [{e.provenance_class or 'derived'}; {len(e.source_refs)} record(s)]"
                 + "".join(f" [{flag}]" for flag in e.flags) for e in entries)


def _need_line(need: OperationalNeed) -> str:
    return f"{need.status.value}/{need.handling.value}" + (f" due {need.due_by}" if need.due_by
                                                           else "")


def _changes(previous: LoadMoment | None, view: LoadView, state: LoadWorkState,
             touches: HumanTouches) -> tuple[Change, ...]:
    if previous is None:
        return (Change("FIRST_SEEN", state.load_number or state.load_id,
                       "the load is now known"),)
    before = previous.state
    out: list[Change] = []
    if before.stage is not state.stage:
        out.append(Change("STAGE", state.stage.value,
                          f"{before.stage.value} -> {state.stage.value}"))
    if before.known_status != state.known_status:
        out.append(Change("STATUS", str(state.known_status),
                          f"{before.known_status} -> {state.known_status}"))
    then = {n.need_id: n for n in before.needs}
    now = {n.need_id: n for n in state.needs}
    settled = {s.need_id: s for s in state.settled}
    for need_id, need in now.items():
        if need_id not in then:
            out.append(Change("OPENED", need.kind.value, _need_line(need)))
        elif _need_line(then[need_id]) != _need_line(need) \
                or then[need_id].reason_codes != need.reason_codes:
            out.append(Change("MOVED", need.kind.value,
                              f"{_need_line(then[need_id])} -> {_need_line(need)}"))
    for need_id, need in then.items():
        if need_id not in now:
            how = settled[need_id].how if need_id in settled else "CLOSED"
            if how == "CLOSED" and need.handling in (Handling.WAIT, Handling.DETERMINISTIC) \
                    and state.need(NeedKind.CARRIER_STATUS_OVERDUE) is not None:
                how = "ESCALATED"            # a wait whose deadline passed became the follow-up
            out.append(Change("CLOSED", need.kind.value, how))
    if before.billing_ready != state.billing_ready:
        out.append(Change("BILLING", "customer_billing_ready",
                          f"{before.billing_ready} -> {state.billing_ready}"))
    was_quiet = previous.quiet
    is_quiet = state.routine_work_is_zero and state.stage is not Stage.PLANNING
    if was_quiet != is_quiet:
        out.append(Change("QUIET", "quiet", f"{was_quiet} -> {is_quiet}"))
    if touches.acts != previous.touches.acts:
        out.append(Change("HUMAN_ACT", "human", f"{previous.touches.acts} -> {touches.acts}"))
    for entry in view.timeline:
        if entry.timeline_entry_id not in previous.timeline_ids and entry.at <= state.as_of:
            out.append(Change("HAPPENED", entry.kind, without_money(entry.summary)))
    return tuple(out)


def build_moment(view: LoadView, state: LoadWorkState, *, previous: LoadMoment | None,
                 index: int, history_id: str, trigger: str, trigger_kind: str,
                 disposition: str, about_this_load: bool) -> LoadMoment:
    """The picture of one load at one instant. A pure function of the canonical view, the work
    state, and the picture before it."""
    touches = _touches(view, state)
    return LoadMoment(
        index=index, history_id=history_id, trigger=trigger, trigger_kind=trigger_kind,
        disposition=disposition, about_this_load=about_this_load, state=state,
        happening=_happening(view, state), evidence=_evidence(view, state.as_of),
        changes=_changes(previous, view, state, touches),
        proposals=_proposals(view, state), escalations=_escalations(state), touches=touches,
        timeline_ids=frozenset(e.timeline_entry_id for e in view.timeline))


# ================================================================================= the run

Audit = Callable[[LoadWorkState, LoadView, str], Sequence[str]]


@dataclass
class LoadStory:
    """One load, through time: every moment its picture changed or a record about it arrived."""

    tenant_id: str
    load_id: str
    moments: list[LoadMoment] = field(default_factory=list)

    @property
    def load_number(self) -> str | None:
        return self.moments[-1].load_number if self.moments else None

    @property
    def last(self) -> LoadMoment:
        return self.moments[-1]

    def at(self, label: str) -> LoadMoment:
        """The picture just after the record labeled `label` arrived (the last such moment)."""
        found = [m for m in self.moments if m.trigger == label]
        if not found:
            raise KeyError(f"load {self.load_number!r} has no moment after {label!r}")
        # Loads run side by side, and two histories may each have a record called "pod". The one
        # that was ABOUT this load is the one meant.
        own = [m for m in found if m.about_this_load]
        return (own or found)[-1]

    def summary(self) -> dict[str, Any]:
        last = self.last
        ever_human = {e.need_id for m in self.moments for e in m.escalations}
        return {
            "tenant_id": self.tenant_id, "load_number": self.load_number,
            "moments": len(self.moments), "stage": last.state.stage.value,
            "posture": last.state.posture.value, "quiet": last.quiet,
            "billing_ready": last.billing_ready,
            "carrier_side_open": len(last.carrier_side), "overdue": len(last.overdue),
            "human_touches": last.touches.total, "human_acts": last.touches.acts,
            "human_questions_open": last.touches.open,
            "human_questions_ever": len(ever_human),
            "cured_exceptions_awaiting_closure": len(last.state.housekeeping),
            "proposals_made": len({(p.need_id, p.action) for m in self.moments
                                   for p in m.proposals}),
            "deadlines_passed_in_silence": len([m for m in self.moments
                                                if m.trigger_kind == "tick"]),
            "ever_quiet_then_not": _reopened_after_quiet(self.moments),
            "next_step": last.next_step,
        }


def _reopened_after_quiet(moments: Sequence[LoadMoment]) -> int:
    count, was_quiet = 0, False
    for moment in moments:
        if was_quiet and not moment.quiet:
            count += 1
        was_quiet = moment.quiet
    return count


@dataclass
class LoopRunResult:
    intakes: dict[str, FreightIntake]
    stories: dict[tuple[str, str], LoadStory]            # (tenant, load_id)
    histories: list[WorkHistoryResult]
    findings: list[str]
    report: dict[str, Any]
    #: Work that belongs to NO load, per brokerage: a record nothing could place, an Exception
    #: about no entity. No load's story would ever show it, so it is carried beside them - a board
    #: on which every load is quiet must not hide it.
    unplaced: dict[str, tuple[OperationalNeed, ...]] = field(default_factory=dict)

    def story(self, tenant: str, load_number: str) -> LoadStory:
        for (owner, _), story in self.stories.items():
            if owner == tenant and story.load_number == load_number:
                return story
        raise KeyError(f"{tenant} has no load numbered {load_number!r}")

    def find(self, load_number: str) -> list[LoadStory]:
        return [s for s in self.stories.values() if s.load_number == load_number]


def _tick(at: str, zone: str) -> InboundRecord:
    """Time passing, with nothing arriving: the same control record a history may carry."""
    return InboundRecord(label=f"deadline@{at}", channel="clock", kind="clock",
                         source_system="clock", external_id=f"deadline@{at}", received_at=at,
                         as_of=at, timezone=zone, refs=(), payload={})


def _deadlines_before(states: Mapping[str, LoadWorkState], after: str, before: str) -> list[str]:
    """Every deadline the open work holds that falls after `after` and whose look-again instant is
    strictly before `before`, in order. These are instants the canonical record already names."""
    instants: set[str] = set()
    for state in states.values():
        for need in state.needs:
            if not need.due_by or need.due_by <= after:
                continue
            look = format_instant(utc_datetime(need.due_by) + TICK_GRACE)
            if look < before:
                instants.add(look)
    return sorted(instants)


_LOOP_KEYS = ("touches", "acts", "overdue", "carrier_side", "proposes", "escalates", "changed",
              "next_step", "drafts")


def check_loop_checkpoint(result: WorkHistoryResult, checkpoint: Mapping[str, Any],
                          moment: LoadMoment) -> None:
    """The loop's own labels, beside the work labels `check_checkpoint` already asserts. Only what
    a checkpoint LABELS is checked."""
    where = f"{result.history.history_id}/{checkpoint['after']}/{checkpoint['load']}"

    def check(what: str, actual: Any, expected: Any) -> None:
        result.checks += 1
        if actual != expected:
            result.mismatches.append(f"{where} {what}: expected {expected!r}, got {actual!r}")

    if "touches" in checkpoint:
        check("human touches", moment.touches.total, checkpoint["touches"])
    if "acts" in checkpoint:
        check("human acts", moment.touches.acts, checkpoint["acts"])
    if "overdue" in checkpoint:
        check("overdue", sorted(n.kind.value for n in moment.overdue),
              sorted(checkpoint["overdue"]))
    if "carrier_side" in checkpoint:
        check("carrier-side work", sorted(n.kind.value for n in moment.carrier_side),
              sorted(checkpoint["carrier_side"]))
    if "proposes" in checkpoint:
        check("proposals", sorted({p.action for p in moment.proposals}),
              sorted(checkpoint["proposes"]))
    if "escalates" in checkpoint:
        check("escalations", sorted(e.kind for e in moment.escalations),
              sorted(checkpoint["escalates"]))
    if "next_step" in checkpoint:
        check("next step", moment.next_step, checkpoint["next_step"])
    if "drafts" in checkpoint:
        check("drafted messages", len([p for p in moment.proposals if p.draft]),
              checkpoint["drafts"])
    for token in checkpoint.get("changed") or ():
        have = {c.token() for c in moment.changes}
        check(f"changed {token}", token in have, True)


def run_load_loop(conn: sqlite3.Connection, setups: Mapping[str, TenantSetup],
                  histories: Sequence[FreightHistory], *,
                  interpreter: FreightInterpreter | None = None,
                  audit: Audit | None = None, tick_at_deadlines: bool = True,
                  interleave: bool = True,
                  intakes: dict[str, FreightIntake] | None = None,
                  restart_after: Mapping[str, str] | None = None) -> LoopRunResult:
    """Run every history through its brokerage's intake on one shared database, keeping each load's
    picture as it evolves.

    A moment is recorded for a load when a record about it arrives, or when its picture changes —
    including when a deadline passes with nothing arriving. `audit`, when given, is run on EVERY
    evaluation of every load, not only on recorded moments: a load must not go falsely quiet between
    the moments anyone looks at. With `interleave` (the default) the histories are ONE inbox:
    their records are taken in arrival order, so loads are in flight side by side; without it each
    history runs to its end before the next begins. `restart_after` names, per history id, a record
    after which the process is thrown away and a new intake is built over the same database."""
    intakes = intakes if intakes is not None else {}
    stories: dict[tuple[str, str], LoadStory] = {}
    last_signature: dict[tuple[str, str], tuple[Any, ...]] = {}
    results: list[WorkHistoryResult] = []
    findings: list[str] = []
    counters = {"records": 0, "ticks": 0, "evaluations": 0, "duplicates": 0}
    index = 0
    #: Per brokerage, the views and work states of the evaluation just made. They are the canonical
    #: picture as of that brokerage's clock, and nothing changes it until the next record: so the
    #: deadlines to look at next, and a labeled checkpoint, are read from it rather than projected
    #: again.
    latest: dict[str, dict[str, tuple[LoadView, LoadWorkState]]] = {}
    #: Per brokerage, the instant of that evaluation. The RUNNER remembers it, not the intake: an
    #: intake rebuilt after a restart has not been told the time yet, and a deadline that falls
    #: just after a restart is still a deadline.
    clock: dict[str, str] = {}

    def step(history: FreightHistory, intake: FreightIntake, record: InboundRecord,
             kind: str) -> dict[str, LoadMoment]:
        nonlocal index
        outcome = intake.ingest(record)
        if outcome.disposition == "DUPLICATE":
            counters["duplicates"] += 1
        as_of = intake.foundation.now()
        projection = intake.projection()
        seen: dict[str, LoadMoment] = {}
        evaluated: dict[str, tuple[LoadView, LoadWorkState]] = {}
        latest[history.tenant] = evaluated
        clock[history.tenant] = as_of
        for load_id, view in sorted(projection.loads.items()):
            state = evaluate_load_work(view, setup=intake.setup, as_of=as_of)
            evaluated[load_id] = (view, state)
            counters["evaluations"] += 1
            if audit is not None:
                findings.extend(f"{history.history_id} after {record.label}: {finding}"
                                for finding in audit(state, view, history.tenant))
            key = (history.tenant, load_id)
            about = outcome.load_id == load_id
            now = signature(state)
            if key in stories and not about and last_signature.get(key) == now:
                continue
            story = stories.setdefault(key, LoadStory(tenant_id=history.tenant, load_id=load_id))
            moment = build_moment(
                view, state, previous=story.moments[-1] if story.moments else None,
                index=index, history_id=history.history_id, trigger=record.label,
                trigger_kind=kind, disposition=outcome.disposition, about_this_load=about)
            story.moments.append(moment)
            last_signature[key] = now
            seen[load_id] = moment
        index += 1
        return seen

    by_history: dict[str, WorkHistoryResult] = {}
    checkpoints: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for history in histories:
        result = WorkHistoryResult(history=history)
        results.append(result)
        by_history[history.history_id] = result
        for checkpoint in history.expected.get("work") or ():
            checkpoints.setdefault((history.history_id, checkpoint["after"]), []).append(checkpoint)
        labels = {r.label for r in history.records}
        for (owner, label) in sorted(checkpoints):
            if owner == history.history_id and label not in labels:
                result.checks += 1
                result.mismatches.append(f"{history.history_id}: a checkpoint names record "
                                         f"{label!r}, which this history does not have")

    # A brokerage has ONE inbox and many loads in flight. Records are taken in the order they
    # ARRIVED, across every history, exactly as that inbox would hand them over.
    if interleave:
        stream = sorted(((to_utc(record.received_at, what="received_at"), h_index, r_index,
                          history, record)
                         for h_index, history in enumerate(histories)
                         for r_index, record in enumerate(history.records)),
                        key=lambda item: item[:3])
    else:
        stream = [("", h_index, r_index, history, record)
                  for h_index, history in enumerate(histories)
                  for r_index, record in enumerate(history.records)]

    for _, _, _, history, record in stream:
        intake = intakes.get(history.tenant)
        if intake is None:
            intake = FreightIntake(conn, setups[history.tenant], interpreter=interpreter)
            intakes[history.tenant] = intake
        result = by_history[history.history_id]
        arriving = to_utc(record.received_at, what="received_at")
        if tick_at_deadlines and history.tenant in latest:
            # A tick is itself an evaluation, and what it shows may hold a NEW deadline that also
            # falls before this record: look again after each one.
            while True:
                states = {load_id: pair[1] for load_id, pair in latest[history.tenant].items()}
                due = _deadlines_before(states, clock[history.tenant], arriving)
                if not due:
                    break
                step(history, intake, _tick(due[0], record.timezone), "tick")
                counters["ticks"] += 1
        step(history, intake, record, record.kind)
        counters["records"] += 1

        for checkpoint in checkpoints.get((history.history_id, record.label), ()):
            result.checks += 1
            story = next((s for (owner, _), s in stories.items()
                          if owner == history.tenant
                          and s.load_number == checkpoint["load"]), None)
            if story is None:
                result.mismatches.append(f"{history.history_id}/{record.label}: no load is "
                                         f"numbered {checkpoint['load']!r}")
                continue
            if "at" in checkpoint:
                # Asked at another instant with nothing new: the work, not a recorded moment.
                moment_at = to_utc(checkpoint["at"], what="checkpoint instant")
                view = latest[history.tenant][story.load_id][0]
                check_checkpoint(result, checkpoint,
                                 evaluate_load_work(view, setup=intake.setup, as_of=moment_at))
                continue
            moment = story.last
            check_checkpoint(result, checkpoint, moment.state)
            if any(k in checkpoint for k in _LOOP_KEYS):
                check_loop_checkpoint(result, checkpoint, moment)
            result.checkpoints.append({"after": record.label, "as_of": moment.as_of,
                                       "load": checkpoint["load"],
                                       "posture": moment.state.posture.value})
        if restart_after and restart_after.get(history.history_id) == record.label:
            # The process dies here. Everything it knew is gone; the database is not.
            intakes[history.tenant] = FreightIntake(conn, setups[history.tenant],
                                                    interpreter=interpreter)

    unplaced = {tenant: evaluate_unplaced_work(
        intake.projection(), setup=intake.setup, exceptions=intake.foundation.exceptions(),
        as_of=intake.foundation.now()) for tenant, intake in sorted(intakes.items())}
    report = build_loop_report(conn, intakes, stories=stories, results=results,
                               counters=counters, findings=findings, audited=audit is not None,
                               unplaced=unplaced)
    return LoopRunResult(intakes=intakes, stories=stories, histories=results,
                         findings=findings, report=report, unplaced=unplaced)


def build_loop_report(conn: sqlite3.Connection, intakes: Mapping[str, FreightIntake], *,
                      stories: Mapping[tuple[str, str], LoadStory],
                      results: Sequence[WorkHistoryResult], counters: Mapping[str, int],
                      findings: Sequence[str], audited: bool,
                      unplaced: Mapping[str, Sequence[OperationalNeed]]) -> dict[str, Any]:
    """Counts. Nothing here grades, nothing here carries money, and no labor time is claimed."""
    summaries = [story.summary() for _, story in sorted(stories.items())]
    loads = len(summaries)
    effects = {tenant: intake.foundation.effect_surface_counts()
               for tenant, intake in sorted(intakes.items())}
    touches = [s["human_touches"] for s in summaries]
    zero_touch = [s for s in summaries if s["human_touches"] == 0]
    metrics: dict[str, Any] = {
        "histories_processed": len(results),
        "loads": loads,
        "records_arrived": counters["records"],
        "duplicate_records_suppressed": counters["duplicates"],
        "deadlines_passed_in_silence": counters["ticks"],
        "evaluations": counters["evaluations"],
        "moments_recorded": sum(s["moments"] for s in summaries),
        "loads_billing_ready": len([s for s in summaries if s["billing_ready"]]),
        "loads_quiet": len([s for s in summaries if s["quiet"]]),
        "loads_billing_ready_and_quiet": len([s for s in summaries
                                              if s["billing_ready"] and s["quiet"]]),
        "loads_billing_ready_with_carrier_side_work": len(
            [s for s in summaries if s["billing_ready"] and s["carrier_side_open"]]),
        "loads_waiting_on_a_human": len([s for s in summaries if s["human_questions_open"]]),
        "loads_with_overdue_work": len([s for s in summaries if s["overdue"]]),
        "loads_reopened_after_quiet": len([s for s in summaries if s["ever_quiet_then_not"]]),
        "human_touches_total": sum(touches),
        "human_touches_per_load": round(sum(touches) / loads, 3) if loads else None,
        "human_touches_max_on_one_load": max(touches) if touches else 0,
        "loads_with_zero_human_touches": len(zero_touch),
        "human_acts_recorded": sum(s["human_acts"] for s in summaries),
        "human_questions_open": sum(s["human_questions_open"] for s in summaries),
        "human_questions_ever_raised": sum(s["human_questions_ever"] for s in summaries),
        "work_on_no_load_needing_a_human": sum(len(needs) for needs in unplaced.values()),
        # NOT counted as touches, and not nothing: each is an M9 Exception whose cause the record
        # shows cured, which stays open until a named human closes it.
        "cured_exceptions_awaiting_human_closure": sum(
            s["cured_exceptions_awaiting_closure"] for s in summaries),
        "loads_with_cured_exceptions_awaiting_closure": len(
            [s for s in summaries if s["cured_exceptions_awaiting_closure"]]),
        "neyma_proposals_made": sum(s["proposals_made"] for s in summaries),
        "wrong_cross_tenant_mappings": len(cross_tenant_violations(conn)),
        "external_effect_rows": sum(sum(c.values()) for c in effects.values()),
        "labeled_checkpoints": sum(len(r.checkpoints) for r in results),
        "labeled_checks": sum(r.checks for r in results),
        "labeled_checks_failed": sum(len(r.mismatches) for r in results),
        "audit_findings": len(findings) if audited else None,
    }
    return {
        "report_version": LOOP_VERSION,
        "note": ("Synthetic development corpus. Nothing here is design-partner evidence, no "
                 "freight rule is validated by appearing in it, and no labor time was measured. "
                 "A human touch is a decision a human recorded, or one still owed."),
        "metrics": metrics, "loads": summaries, "effect_surface_rows": effects,
        "work_on_no_load": {tenant: [n.as_document() for n in needs]
                            for tenant, needs in sorted(unplaced.items())},
        "histories": [{"history_id": r.history.history_id, "title": r.history.title,
                       "tenant": r.history.tenant, "records": len(r.history.records),
                       "checkpoints": len(r.checkpoints), "labeled_checks": r.checks,
                       "labeled_mismatches": list(r.mismatches)} for r in results],
        "audit_findings": list(findings),
    }


# ================================================================================= rendering

def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def render_moment(moment: LoadMoment, *, detail: bool = True) -> str:
    """One moment, as an operator would be told it: the thirteen answers, in order."""
    state = moment.state
    lines = [f"--- {moment.as_of}  after {moment.trigger}"
             + ("" if moment.about_this_load or moment.trigger_kind == "tick"
                else "  (nothing arrived for this load)")
             + ("  (a deadline passed; nothing arrived)" if moment.trigger_kind == "tick" else ""),
             f" 1 happening     {moment.happening}"]
    lines.append(" 2 evidence      " + ("; ".join(moment.evidence[-2:]) if not detail
                                        else ""))
    if detail:
        lines.extend(f"                 {item}" for item in moment.evidence or ("- none",))
    lines.append(" 3 changed       " + ("; ".join(f"{c.what} {c.subject} ({c.detail})"
                                                  for c in moment.changes
                                                  if c.what != "HAPPENED") or "nothing"))
    lines.append(" 4 work          " + (", ".join(
        f"{n.kind.value}[{n.status.value}/{n.handling.value}]" for n in state.needs) or "none"))
    lines.append(" 5 overdue       " + (", ".join(
        f"{n.kind.value} (due {n.due_by}, {n.status.value})" for n in moment.overdue) or "none"))
    lines.append(" 6 waiting for   " + (", ".join(
        f"{n.kind.value}" + (f" until {n.due_by}" if n.due_by else "")
        for n in moment.waiting) or "nothing"))
    if moment.proposals:
        lines.append(" 7 Neyma would   " + "; ".join(
            f"{p.action} -> {p.to or '?'}" + (" (act-or-wait undecided)" if p.undecided else "")
            for p in moment.proposals))
        if detail:
            lines.extend(f"                 DRAFT, NOT SENT: {p.draft}"
                         for p in moment.proposals if p.draft)
    else:
        lines.append(" 7 Neyma would   " + ("wait" if state.needs and not moment.escalations
                                             else "nothing"))
    lines.append(" 8 needs a human " + (", ".join(
        f"{e.kind} -> {e.owner_id}" for e in moment.escalations) or "no"))
    if moment.escalations:
        for item in moment.escalations:
            lines.append(f" 9 why           {item.kind}: {item.why}")
            if detail and item.question:
                lines.append(f"                 asks {item.owner_id}: {item.question}")
            if detail:
                lines.extend(f"                 evidence {e.evidence_id} {e.kind}: {e.note}"
                             for e in item.evidence)
    else:
        lines.append(" 9 why           -")
    lines.append(f"10 billing ready {_yes(moment.billing_ready)}"
                 + ("" if moment.billing_ready else " - " + "; ".join(state.billing_blockers)))
    lines.append("11 carrier side  " + (", ".join(
        f"{n.kind.value}[{n.status.value}]" for n in moment.carrier_side) or "nothing open"))
    lines.append(f"12 quiet         {_yes(moment.quiet)}"
                 + ("" if moment.booked else "  (not booked: no carrier is on the load)")
                 + (f"  ({len(state.housekeeping)} cured exception(s) await a human's closure: "
                    f"housekeeping, not work)" if state.housekeeping else ""))
    lines.append(f"13 human touches {moment.touches.total}  (decisions recorded "
                 f"{moment.touches.acts}, still owed {moment.touches.open})")
    return "\n".join(lines)


def render_story(story: LoadStory, *, detail: bool = False) -> str:
    """One load, through time."""
    head = f"LOAD {story.load_number or story.load_id}  [{story.tenant_id}]  " \
           f"{len(story.moments)} moment(s)"
    return "\n".join([head, *(render_moment(m, detail=detail) for m in story.moments)])


def render_trace(story: LoadStory) -> str:
    """One load, one line per moment: the shape of its life at a glance."""
    lines = [f"LOAD {story.load_number or story.load_id}  [{story.tenant_id}]"]
    for m in story.moments:
        needs = ", ".join(f"{n.kind.value}/{n.status.value}/{n.handling.value}"
                          for n in m.state.needs) or "-"
        mark = "~" if m.trigger_kind == "tick" else (" " if m.about_this_load else ".")
        lines.append(f" {mark}{m.as_of[5:16]} {m.trigger[:26]:26s} {m.state.stage.value:10s} "
                     f"{m.state.posture.value:15s} bill={_yes(m.billing_ready):3s} "
                     f"touch={m.touches.total} {m.next_step:28s} {needs}")
    return "\n".join(lines)


def render_board(result: LoopRunResult) -> str:
    """Every load, where it stands now: the board an operator would glance at."""
    lines = [f"{'LOAD':11s} {'BROKERAGE':24s} {'STAGE':10s} {'POSTURE':15s} {'BILL':5s} "
             f"{'QUIET':5s} {'TOUCH':5s} {'CLOSE':5s} NEXT"]
    for (_, _), story in sorted(result.stories.items(),
                                key=lambda item: (item[0][0], item[1].load_number or "")):
        s = story.summary()
        lines.append(f"{(s['load_number'] or '?'):11s} {s['tenant_id']:24s} {s['stage']:10s} "
                     f"{s['posture']:15s} {_yes(s['billing_ready']):5s} {_yes(s['quiet']):5s} "
                     f"{s['human_touches']!s:5s} "
                     f"{s['cured_exceptions_awaiting_closure']!s:5s} {s['next_step']}")
    for tenant, needs in sorted(result.unplaced.items()):
        for need in needs:
            lines.append(f"{'(no load)':11s} {tenant:24s} {'-':10s} {'HUMAN_ATTENTION':15s} "
                         f"{'-':5s} {'no':5s} {'1':5s} {'-':5s} HUMAN:{need.kind.value} "
                         f"[{', '.join(need.reason_codes)}] -> {need.owner_id}")
    return "\n".join(lines)


__all__ = [
    "CARRIER_SIDE_KINDS", "Change", "Escalation", "HumanTouches", "LATE_STATUSES", "LOOP_VERSION",
    "LoadMoment", "LoadStory", "LoopRunResult", "Proposal", "build_loop_report", "build_moment",
    "check_loop_checkpoint", "render_board", "render_moment", "render_story", "render_trace",
    "run_load_loop",
    "signature", "without_money",
]
