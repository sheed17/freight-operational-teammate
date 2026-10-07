"""P9 deep-end 3 — the operational work projection: WHAT WORK REMAINS ON THIS LOAD, RIGHT NOW?

    evaluate_load_work(view, setup=..., as_of=...) -> LoadWorkState

### IT IS A READ MODEL, AND IT IS NOT A SECOND SOURCE OF TRUTH. `LoadWorkState` is a pure function of
one load's canonical projection (`LoadView`) and the instant it is asked about. It writes nothing,
calls no machine transition, no adapter and no model. Asking twice creates no Work Item, no
Expectation, no Exception and no row of any kind — there is nothing here that could.

### WORK IS READ OFF THE CAUSE, NOT OFF THE PAPERWORK ABOUT IT. A need exists because of something in
the canonical record: a required document is not on file, an invoice is on no movement, two sources
disagree, a deadline passed in silence. The Expectation, Conflict and Exception rows raised for that
cause are its ORIGINS — they name the owner and the question — and they are grouped under the one
need they all describe. So one missing POD is one piece of work, however many rows describe it; and
when the cause is cured the need is gone, whatever state those rows are left in.

### M9 CLOSES ONLY BY A HUMAN'S DECISION, AND NOTHING HERE PRETENDS OTHERWISE. An Exception whose
cause has been cured stays open in M9 until a recorded human closes it (the `resolve_exception` act,
through M9's own transition). It is reported as HOUSEKEEPING — retained, owned, and not a task —
never as attention, and never silently dropped. And the other way round: closing an Exception does
not finish the work it was raised for. A need read off a CAUSE stands while the cause does, whether
or not its Exception row is still open.

### A CLOSED VOCABULARY. Need kinds, handling classes, statuses and shadow actions are enums. There
is no free-form "todo", and a signal this module cannot classify becomes an `UNCLASSIFIED_EXCEPTION`
a human must look at rather than disappearing.

### WAITING AND QUIET ARE ANSWERS. A load that needs nothing has no needs. Nothing is manufactured so
that every load has a next action.

### NO MONEY. Nothing in a `LoadWorkState` carries an amount. A discrepancy is named by its code.

### A SHADOW ACTION IS A WORD, NOT A CAPABILITY. `ShadowAction` names what could be proposed. Nothing
in this package can perform one: there is no send, no write, no adapter and no effect grant behind
any of them. They are not `ProposedIntent`s either — the registered action classes carry no class
for a document request or an appointment check, and adding one is a policy decision (P12).
"""

from __future__ import annotations

import enum
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .detectors import ARRIVAL_STATUSES, STAGES_PAST_STOP, TRACKING_UPDATE, UNDER_WAY_STATUSES
from .financial import blocking_discrepancies
from .foundation import EvidenceCondition, stable_id
from .history import CARRIER_SIDE_ROLES, TenantSetup, utc_datetime
from .model import AccessorialCharge
from .projection import (
    OPEN_CONFLICT_STATES,
    FreightProjection,
    LoadView,
    commitment_expectation_id,
    exception_key,
    explain_unattributed_invoice,
    split_ref,
)

WORK_VERSION = "p9-load-work-1"


class NeedKind(str, enum.Enum):
    CARRIER_UPDATE_PENDING = "CARRIER_UPDATE_PENDING"        # a promised update, not yet due
    ARRIVAL_PENDING = "ARRIVAL_PENDING"                      # a confirmed window, not yet closed
    TRACKING_UPDATE_PENDING = "TRACKING_UPDATE_PENDING"      # within the brokerage's own cadence
    CARRIER_STATUS_OVERDUE = "CARRIER_STATUS_OVERDUE"        # one follow-up, however many reasons
    APPOINTMENT_UNCONFIRMED = "APPOINTMENT_UNCONFIRMED"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    DOCUMENT_REQUIRED = "DOCUMENT_REQUIRED"
    DOCUMENT_NEEDS_READING = "DOCUMENT_NEEDS_READING"
    INVOICE_UNATTRIBUTED = "INVOICE_UNATTRIBUTED"
    INVOICE_DISCREPANCY = "INVOICE_DISCREPANCY"
    ACCESSORIAL_UNAUTHORIZED = "ACCESSORIAL_UNAUTHORIZED"
    RECONCILIATION_BLOCKED = "RECONCILIATION_BLOCKED"
    BILLING_BLOCKED = "BILLING_BLOCKED"
    BILLING_REQUIREMENTS_UNKNOWN = "BILLING_REQUIREMENTS_UNKNOWN"
    UNCLASSIFIED_EXCEPTION = "UNCLASSIFIED_EXCEPTION"


class Handling(str, enum.Enum):
    """Who, or what, the next step belongs to."""

    WAIT = "WAIT"                                    # owed by an outside party; nothing to do yet
    DETERMINISTIC = "DETERMINISTIC"                  # Neyma's own clock is watching an exact time
    NEYMA_ACTION_CANDIDATE = "NEYMA_ACTION_CANDIDATE"  # one shadow action applies
    MODEL_REASONING = "MODEL_REASONING"              # act-or-wait is not settled by the record
    HUMAN_REQUIRED = "HUMAN_REQUIRED"                # a named human must decide


class NeedStatus(str, enum.Enum):
    PENDING = "PENDING"            # owed, with a deadline that has not passed
    DUE = "DUE"                    # the deadline passed on the ASKING clock; M8 has not ruled yet
    OPEN = "OPEN"                  # work that exists now, with no deadline or one not yet passed
    OVERDUE = "OVERDUE"            # the deadline passed over a channel proven to be up
    UNVERIFIED = "UNVERIFIED"      # the deadline passed and we were blind: not provably late


class ShadowAction(str, enum.Enum):
    WAIT = "WAIT"
    REQUEST_CARRIER_STATUS = "REQUEST_CARRIER_STATUS"
    REQUEST_POD = "REQUEST_POD"
    VERIFY_APPOINTMENT = "VERIFY_APPOINTMENT"
    ASK_HUMAN_RESOLVE_IDENTITY = "ASK_HUMAN_RESOLVE_IDENTITY"
    ASK_HUMAN_RESOLVE_CONFLICT = "ASK_HUMAN_RESOLVE_CONFLICT"
    ASK_HUMAN_REVIEW_DOCUMENT = "ASK_HUMAN_REVIEW_DOCUMENT"
    ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY = "ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY"
    ASK_HUMAN_DECIDE_ACCESSORIAL = "ASK_HUMAN_DECIDE_ACCESSORIAL"
    ASK_HUMAN_SET_DOCUMENT_REQUIREMENTS = "ASK_HUMAN_SET_DOCUMENT_REQUIREMENTS"


class Stage(str, enum.Enum):
    PLANNING = "PLANNING"              # no carrier is on the load
    DISPATCHED = "DISPATCHED"          # a carrier is on it; nothing has been picked up
    AT_PICKUP = "AT_PICKUP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"            # delivery has been REPORTED (a claim, CD-15)
    DISPUTED = "DISPUTED"              # the movement sources contradict each other


class Posture(str, enum.Enum):
    QUIET = "QUIET"                        # nothing is owed and nothing is waited for
    WAIT = "WAIT"                          # only waiting / watching
    NEYMA_CAN_ACT = "NEYMA_CAN_ACT"        # shadow candidates exist; no human is needed
    HUMAN_ATTENTION = "HUMAN_ATTENTION"    # at least one need is a human's


#: The handling classes in which nothing is asked of anyone yet.
PASSIVE: tuple[Handling, ...] = (Handling.WAIT, Handling.DETERMINISTIC)
#: The order needs are listed in: a human's first, then what Neyma could do, then what is waited on.
_HANDLING_ORDER: dict[Handling, int] = {
    Handling.HUMAN_REQUIRED: 0, Handling.MODEL_REASONING: 1, Handling.NEYMA_ACTION_CANDIDATE: 2,
    Handling.DETERMINISTIC: 3, Handling.WAIT: 4,
}
#: What a promise must have been ABOUT for it to cover an open need without anyone reading it.
_PROMISE_COVERS: dict[NeedKind, str] = {
    NeedKind.CARRIER_STATUS_OVERDUE: "status_update",
    NeedKind.DOCUMENT_REQUIRED: "send_document",
}
#: Promise kinds whose scope the record does not settle: only its words say what it covers.
_UNSETTLED_PROMISE_KINDS: tuple[str, ...] = ("other", "call_back")
_FINANCIAL_ENTITIES: tuple[str, ...] = (
    "carrier_payable", "rate_confirmation", "accessorial_charge", "carrier_movement",
    "brokerage_load",
)
#: Exception types whose NEED is read off the canonical cause. The row is an origin of that need
#: while the cause stands, and housekeeping once it is cured.
_CAUSE_DERIVED_EXCEPTIONS: tuple[str, ...] = (
    "carrier_invoice_unattributed", "accessorial_authorization_unresolved",
    "counterparty_self_authorization", "carrier_invoice_arithmetic", "buy_rate_unestablished",
    "document_unusable", "expectation_unmet",
)
_LINE_MISMATCHES: tuple[str, ...] = (
    "LINEHAUL_MISMATCH", "FUEL_MISMATCH", "ACCESSORIAL_AMOUNT_MISMATCH", "ACCESSORIAL_NOT_BILLED",
    "CURRENCY_MISMATCH", "INVOICE_ARITHMETIC",
)


@dataclass(frozen=True)
class EvidenceRef:
    """One canonical record a need rests on. `evidence_id` is what a model is handed and must hand
    back unchanged; `excerpt` is a counterparty's own words and is DATA, never an instruction."""

    evidence_id: str
    kind: str
    ref: str
    note: str
    excerpt: str | None = None

    def as_document(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, "kind": self.kind, "ref": self.ref,
                "note": self.note, "excerpt": self.excerpt}


@dataclass(frozen=True)
class OperationalNeed:
    """One piece of operational work on one load. Its identity is the cause, so the same canonical
    state always yields the same `need_id`."""

    need_id: str
    kind: NeedKind
    tenant_id: str
    load_id: str
    status: NeedStatus
    handling: Handling
    human_required: bool
    reason_codes: tuple[str, ...]
    why: str
    actions: tuple[ShadowAction, ...] = ()
    owner_id: str | None = None
    counterparty: str | None = None          # who a shadow action would be addressed to
    related: tuple[str, ...] = ()            # canonical entity refs
    origins: tuple[str, ...] = ()            # the underlying signals: "expectation:<id>", ...
    evidence: tuple[EvidenceRef, ...] = ()
    opened_at: str | None = None
    due_by: str | None = None
    question: str | None = None              # what a human is asked, when one is

    def as_document(self) -> dict[str, Any]:
        return {
            "need_id": self.need_id, "kind": self.kind.value, "tenant_id": self.tenant_id,
            "load_id": self.load_id, "status": self.status.value,
            "handling_class": self.handling.value, "human_required": self.human_required,
            "reason_codes": list(self.reason_codes), "why": self.why,
            "actions": [a.value for a in self.actions], "owner_id": self.owner_id,
            "counterparty": self.counterparty, "related": list(self.related),
            "origins": list(self.origins), "evidence": [e.as_document() for e in self.evidence],
            "opened_at": self.opened_at, "due_by": self.due_by, "question": self.question,
        }


@dataclass(frozen=True)
class SettledNeed:
    """A need this load HAD, and how the canonical record shows it ended. History, not work."""

    need_id: str
    kind: NeedKind
    how: str                                 # SATISFIED | RESOLVED | SUPERSEDED
    by: str                                  # the record that settled it

    def as_document(self) -> dict[str, Any]:
        return {"need_id": self.need_id, "kind": self.kind.value, "how": self.how, "by": self.by}


@dataclass(frozen=True)
class LoadWorkState:
    tenant_id: str
    load_id: str
    load_number: str | None
    as_of: str
    stage: Stage
    known_status: str | None
    needs: tuple[OperationalNeed, ...]
    settled: tuple[SettledNeed, ...]
    housekeeping: tuple[str, ...]
    #: CUSTOMER billing readiness — the W8-1 / L-Invoice ELIGIBLE predicate (delivered, sell rate
    #: consistent, required documents on file, no billing Conflict). It is NOT "financially closed"
    #: (P9-D41): a carrier invoice may still be unplaced, discrepant or unreconciled, or carry an
    #: unauthorized accessorial. That is carrier-side WORK, it is in `needs`, and a load with it is
    #: never quiet — whatever this flag says.
    billing_ready: bool
    billing_blockers: tuple[str, ...]
    reconciliation: tuple[str, ...]
    requirements: Mapping[str, str]
    work_item: Mapping[str, Any] | None
    together: tuple[tuple[str, ...], ...] = ()
    version: str = WORK_VERSION

    # ------------------------------------------------------------------ the answer

    @property
    def waiting(self) -> tuple[OperationalNeed, ...]:
        return tuple(n for n in self.needs if n.handling in PASSIVE)

    @property
    def candidates(self) -> tuple[OperationalNeed, ...]:
        """Needs Neyma could move with a shadow action, no human required."""
        return tuple(n for n in self.needs if not n.human_required
                     and n.handling in (Handling.NEYMA_ACTION_CANDIDATE,
                                        Handling.MODEL_REASONING))

    @property
    def human_attention(self) -> tuple[OperationalNeed, ...]:
        return tuple(n for n in self.needs if n.human_required)

    @property
    def open_work(self) -> tuple[OperationalNeed, ...]:
        """Everything that is not merely waited for."""
        return tuple(n for n in self.needs if n.handling not in PASSIVE)

    @property
    def posture(self) -> Posture:
        if self.human_attention:
            return Posture.HUMAN_ATTENTION
        if self.candidates:
            return Posture.NEYMA_CAN_ACT
        return Posture.WAIT if self.needs else Posture.QUIET

    @property
    def next_action(self) -> ShadowAction | None:
        """The first-listed need's first action; WAIT when everything is waited for; None when the
        load is quiet or the first need is a human's question with no named action."""
        if not self.needs:
            return None
        first = self.needs[0]
        if first.handling in PASSIVE:
            return ShadowAction.WAIT
        return first.actions[0] if first.actions else None

    @property
    def raw_signals(self) -> int:
        """How many underlying canonical signals the needs were assembled from."""
        return len({origin for need in self.needs for origin in need.origins})

    @property
    def routine_work_is_zero(self) -> bool:
        return not self.needs

    def need(self, kind: NeedKind | str) -> OperationalNeed | None:
        wanted = NeedKind(kind)
        return next((n for n in self.needs if n.kind is wanted), None)

    def as_document(self) -> dict[str, Any]:
        return {
            "version": self.version, "tenant_id": self.tenant_id, "load_id": self.load_id,
            "load_number": self.load_number, "as_of": self.as_of, "stage": self.stage.value,
            "known_status": self.known_status, "posture": self.posture.value,
            "next_action": self.next_action.value if self.next_action else None,
            "needs": [n.as_document() for n in self.needs],
            "settled": [s.as_document() for s in self.settled],
            "housekeeping": list(self.housekeeping), "billing_ready": self.billing_ready,
            "billing_blockers": list(self.billing_blockers),
            "reconciliation": list(self.reconciliation),
            "requirements": dict(self.requirements),
            "work_item": dict(self.work_item) if self.work_item else None,
            "together": [list(group) for group in self.together],
            "raw_signals": self.raw_signals,
        }

    def digest(self) -> str:
        text = json.dumps(self.as_document(), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ================================================================================= identity

def exception_origin(exception: Mapping[str, Any]) -> str:
    return f"exception:{exception_key(exception)}"


def need_id(tenant: str, kind: NeedKind, *anchor: object) -> str:
    """The identity of a need: the brokerage, the kind of work, and the CAUSE. The tenant is the
    first component, so the same load number at another brokerage is a different need."""
    if not str(tenant or "").strip():
        raise ValueError("an operational need without a tenant cannot exist (CD-19)")
    return stable_id("need", tenant, kind.value, *anchor)


def evidence_ref(tenant: str, kind: str, ref: str, note: str,
                 excerpt: str | None = None) -> EvidenceRef:
    return EvidenceRef(evidence_id=stable_id("ev", tenant, kind, ref, length=12), kind=kind,
                       ref=ref, note=note, excerpt=excerpt)


# ================================================================================= the projection

@dataclass
class _Build:
    """The working state of one evaluation."""

    view: LoadView
    setup: TenantSetup
    as_of: str
    needs: list[OperationalNeed] = field(default_factory=list)
    settled: list[SettledNeed] = field(default_factory=list)
    housekeeping: list[str] = field(default_factory=list)
    claimed_exceptions: set[str] = field(default_factory=set)
    #: need id -> (its OWN authoritative deadline, whether that deadline has already passed). "Own"
    #: is the brokerage's, the system's or the facility's: a required document's configured
    #: deadline, a confirmed appointment window, the tenant's tracking cadence. A counterparty's
    #: promise is never one of these.
    own_deadline: dict[str, tuple[str, bool]] = field(default_factory=dict)

    @property
    def tenant(self) -> str:
        return self.view.load.tenant_id

    @property
    def load_id(self) -> str:
        return self.view.load_id

    def ev(self, kind: str, ref: str, note: str, excerpt: str | None = None) -> EvidenceRef:
        return evidence_ref(self.tenant, kind, ref, note, excerpt)

    def open_exceptions(self, *, type_: str | None = None, source_ref: str | None = None,
                        source_kind: str | None = None) -> list[dict[str, Any]]:
        return [x for x in self.view.open_exceptions()
                if (type_ is None or x["type"] == type_)
                and (source_ref is None or x["source_ref"] == source_ref)
                and (source_kind is None or x["source_kind"] == source_kind)]

    def claim(self, exceptions: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
        """Mark Exception rows as origins of a need, so they are not listed a second time."""
        rows = list(exceptions)
        self.claimed_exceptions.update(x["exception_id"] for x in rows)
        return tuple(exception_origin(x) for x in rows)

    def add(self, kind: NeedKind, anchor: Sequence[object], *, status: NeedStatus,
            handling: Handling, reason_codes: Sequence[str], why: str,
            actions: Sequence[ShadowAction] = (), owner_id: str | None = None,
            counterparty: str | None = None, related: Sequence[str] = (),
            origins: Sequence[str] = (), evidence: Sequence[EvidenceRef] = (),
            opened_at: str | None = None, due_by: str | None = None,
            question: str | None = None, human_required: bool | None = None,
            scope: str = "load") -> OperationalNeed:
        required = handling is Handling.HUMAN_REQUIRED if human_required is None \
            else human_required
        if required and handling is not Handling.HUMAN_REQUIRED:
            raise ValueError("a need a human must decide is handled as HUMAN_REQUIRED")
        # A need about the LOAD is anchored on it. One that is the same work wherever it is seen —
        # a held record offered to two loads, a missing tenant setting — is anchored without it.
        parts = (self.load_id, *anchor) if scope == "load" else tuple(anchor)
        identity = need_id(self.tenant, kind, *parts)
        for index, existing in enumerate(self.needs):
            if existing.need_id == identity:
                # The same cause reached by a second signal: one need, with both behind it.
                merged = _replace(
                    existing, reason_codes=(*existing.reason_codes, *reason_codes),
                    origins=(*existing.origins, *origins),
                    evidence=(*existing.evidence,
                              *(e for e in evidence if e not in existing.evidence)),
                    related=tuple(dict.fromkeys((*existing.related, *related))))
                self.needs[index] = merged
                return merged
        need = OperationalNeed(
            need_id=identity, kind=kind, tenant_id=self.tenant,
            load_id=self.load_id, status=status, handling=handling, human_required=required,
            reason_codes=tuple(dict.fromkeys(reason_codes)), why=why, actions=tuple(actions),
            owner_id=owner_id or self.setup.load_owner, counterparty=counterparty,
            related=tuple(dict.fromkeys(related)), origins=tuple(dict.fromkeys(origins)),
            evidence=tuple(evidence), opened_at=opened_at, due_by=due_by, question=question)
        self.needs.append(need)
        return need


def evaluate_load_work(view: LoadView, *, setup: TenantSetup, as_of: str) -> LoadWorkState:
    """What work remains on this load at `as_of` (a canonical UTC instant).

    `as_of` is the clock the question is asked on. It decides how long a wait has left, and whether
    a deadline the record still shows as live has in fact passed — which is reported as DUE, awaiting
    the deadline machinery's verdict, because whether a silence is OVERDUE or merely unobserved is
    M8's ruling over recorded channel coverage and never this function's guess."""
    if setup.tenant != view.load.tenant_id:
        raise ValueError(
            f"a load of {view.load.tenant_id!r} was evaluated with the setup of {setup.tenant!r}. "
            f"A brokerage's work is read with its own configuration and no other's.")
    utc_datetime(as_of)
    build = _Build(view=view, setup=setup, as_of=as_of)
    pending_promises = _expectation_needs(build)
    _document_needs(build)
    _identity_needs(build)
    _financial_needs(build)
    _conflict_needs(build)
    _appointment_needs(build)
    _billing_needs(build)
    _exception_needs(build)
    _apply_pending_promises(build, pending_promises)
    _settlements(build)

    needs = tuple(sorted(build.needs, key=lambda n: (_HANDLING_ORDER[n.handling],
                                                    n.due_by or "9999", n.kind.value, n.need_id)))
    invoice = view.invoice
    return LoadWorkState(
        tenant_id=view.load.tenant_id, load_id=view.load_id,
        load_number=view.load.value("load_ref"), as_of=as_of, stage=_stage(view),
        known_status=view.load.value("reported_status"), needs=needs,
        settled=tuple(sorted(build.settled, key=lambda s: (s.kind.value, s.need_id))),
        housekeeping=tuple(sorted(set(build.housekeeping))),
        billing_ready=invoice is not None and invoice.lifecycle_state == "ELIGIBLE",
        billing_blockers=tuple(invoice.blockers) if invoice is not None else (),
        reconciliation=tuple(sorted(r.status for r in view.reconciliations)),
        requirements={r.required_doc_type: r.state for r in view.requirements},
        work_item=({"work_item_id": view.work_item["work_item_id"],
                    "state": view.work_item["state"], "owner_id": view.work_item["owner_id"]}
                   if view.work_item else None),
        together=_together(needs))


# --------------------------------------------------------------------------------- stage

def _stage(view: LoadView) -> Stage:
    if any(c["field"] == "tracking_status" for c in view.open_conflicts()):
        return Stage.DISPUTED
    if view.delivered_claims():
        return Stage.DELIVERED
    # Where the load IS is read from the claims that stand: one a human overruled puts it nowhere.
    statuses = {t.value("status") for t in view.standing_tracking()}
    if statuses & set(UNDER_WAY_STATUSES):
        return Stage.IN_TRANSIT
    if "AT_PICKUP" in statuses:
        return Stage.AT_PICKUP
    if any(m.carrier_id for m in view.movements.values()):
        return Stage.DISPATCHED
    return Stage.PLANNING


# --------------------------------------------------------------------------------- expectations

def _expectation_status(expectation: Mapping[str, Any], as_of: str) -> NeedStatus:
    state = expectation["state"]
    if state == "OVERDUE":
        return NeedStatus.OVERDUE
    if state == "INDETERMINATE":
        return NeedStatus.UNVERIFIED
    return NeedStatus.DUE if expectation["deadline_utc"] <= as_of else NeedStatus.PENDING


def _commitment_for(view: LoadView, expectation_id: str) -> dict[str, Any] | None:
    return next((c for c in view.commitments
                 if commitment_expectation_id(view.load.tenant_id, view.ref, c)
                 == expectation_id), None)


def _promise_words(view: LoadView, commitment: Mapping[str, Any]) -> str | None:
    """What was actually said, for a human — and, bounded, for a model asked what the promise
    covers. The reading's own evidence quote when there is one, else the message body."""
    observation = next((o for o in view.observations
                        if o["observation_id"] == commitment["observation_id"]), None)
    if observation is None:
        return None
    payload = observation["parsed"]["payload"]
    asserts = payload.get("asserts") or ()
    if commitment["index"] < len(asserts):
        quoted = (asserts[commitment["index"]].get("evidence") or {}).get("text")
        if quoted:
            return str(quoted)[:240]
    return str(payload.get("body") or "")[:240] or None


def _side(sender_role: str | None) -> str:
    """Whose side a promise came from. A follow-up Expectation is raised for ANY sender's promise -
    a carrier's, a customer's, a facility's. One with no commitment record behind it is read as
    the carrier's, so that it is chased rather than left to nobody."""
    if sender_role is None or sender_role in CARRIER_SIDE_ROLES:
        return "carrier"
    return str(sender_role)


def _late_reason(prefix: str, status: NeedStatus) -> str:
    return {NeedStatus.OVERDUE: f"{prefix}_OVERDUE", NeedStatus.UNVERIFIED: f"{prefix}_UNVERIFIED",
            NeedStatus.DUE: f"{prefix}_DUE"}[status]


def _expectation_needs(build: _Build) -> list[dict[str, Any]]:
    """Waits and watches, and the ONE carrier follow-up every missed one collapses into. Returns the
    promises still pending — a pending promise can make acting on something else premature."""
    view, as_of = build.view, build.as_of
    owed_ids = {e["expectation_id"] for e in view.owed_expectations()}
    late: list[tuple[dict[str, Any], NeedStatus, str]] = []
    pending_promises: list[dict[str, Any]] = []

    for expectation in view.owed_expectations():
        etype = expectation["expected_type"]
        if etype.startswith("document:"):
            continue                                  # read with the requirement it serves
        status = _expectation_status(expectation, as_of)
        origin = f"expectation:{expectation['expectation_id']}"
        raised = build.open_exceptions(source_ref=expectation["expectation_id"],
                                       source_kind="expectation")
        if etype == "counterparty_update":
            commitment = _commitment_for(view, expectation["expectation_id"]) or {}
            words = _promise_words(view, commitment) if commitment else None
            evidence = [build.ev("expectation", expectation["expectation_id"],
                                 f"an update was promised by {expectation['deadline_utc']}")]
            if commitment:
                evidence.append(build.ev(
                    "observation", commitment["observation_id"],
                    f"a {commitment['sender_role']} promised a follow-up "
                    f"({commitment['commitment_kind']})", words))
            if status is NeedStatus.PENDING:
                need = build.add(
                    NeedKind.CARRIER_UPDATE_PENDING, (expectation["expectation_id"],),
                    status=status, handling=Handling.WAIT, reason_codes=("PROMISED_UPDATE_PENDING",),
                    why="A counterparty promised to follow up, and the time they named has not "
                        "passed.",
                    actions=(ShadowAction.WAIT,),
                    counterparty=_side(commitment.get("sender_role")),
                    origins=(origin, *build.claim(raised)), evidence=evidence,
                    opened_at=expectation["created_at"], due_by=expectation["deadline_utc"],
                    scope="tenant")
                pending_promises.append({"need": need, "kind": commitment.get("commitment_kind"),
                                         "sender_role": commitment.get("sender_role"),
                                         "due_by": expectation["deadline_utc"]})
            elif _side(commitment.get("sender_role")) == "carrier":
                late.append((expectation, status, _late_reason("PROMISED_UPDATE", status)))
            else:
                # The vocabulary carries a follow-up to a CARRIER and to nobody else: a customer's
                # or a facility's broken promise is a human's to chase.
                build.add(
                    NeedKind.UNCLASSIFIED_EXCEPTION,
                    ("expectation", expectation["expectation_id"]), status=status,
                    handling=Handling.HUMAN_REQUIRED,
                    reason_codes=(_late_reason("PROMISED_UPDATE", status)
                                  + f":{commitment.get('sender_role')}",),
                    why="A counterparty that is not the carrier promised a follow-up and the "
                        "time they named has passed.",
                    origins=(origin, *build.claim(raised)), evidence=evidence,
                    opened_at=expectation["created_at"], due_by=expectation["deadline_utc"],
                    scope="tenant")
        elif etype == TRACKING_UPDATE:
            if status is NeedStatus.PENDING:
                build.add(
                    NeedKind.TRACKING_UPDATE_PENDING, (),
                    status=status, handling=Handling.DETERMINISTIC,
                    reason_codes=("TRACKING_WITHIN_CADENCE",),
                    why="The truck is under way and was last heard from within this brokerage's "
                        "tracking cadence.",
                    actions=(ShadowAction.WAIT,), origins=(origin,),
                    evidence=[build.ev("expectation", expectation["expectation_id"],
                                       f"the next tracking update is expected by "
                                       f"{expectation['deadline_utc']}")],
                    opened_at=expectation["created_at"], due_by=expectation["deadline_utc"])
            else:
                late.append((expectation, status, _late_reason("TRACKING", status)))
        elif etype.startswith("arrival:"):
            stop_key = etype.split(":", 1)[1]
            stop = view.stops.get(stop_key)
            if status is NeedStatus.PENDING:
                build.add(
                    NeedKind.ARRIVAL_PENDING, (stop_key,), status=status,
                    handling=Handling.DETERMINISTIC, reason_codes=(f"ARRIVAL_EXPECTED:{stop_key}",),
                    why=f"The appointment at stop {stop_key} is confirmed and its window has not "
                        f"closed.",
                    actions=(ShadowAction.WAIT,), related=(stop.ref,) if stop else (),
                    origins=(origin,),
                    evidence=[build.ev("expectation", expectation["expectation_id"],
                                       f"arrival at {stop_key} is expected by "
                                       f"{expectation['deadline_utc']}")],
                    opened_at=expectation["created_at"], due_by=expectation["deadline_utc"])
            else:
                late.append((expectation, status,
                             _late_reason(f"ARRIVAL:{stop_key}", status)))
        else:
            # An expected-type this projection has no name for is never dropped.
            build.add(
                NeedKind.UNCLASSIFIED_EXCEPTION, ("expectation", expectation["expectation_id"]),
                status=NeedStatus.OPEN, handling=Handling.HUMAN_REQUIRED,
                reason_codes=(f"EXPECTATION:{etype}",),
                why=f"Something of type {etype!r} is owed on this load and Neyma has no rule for "
                    f"what follows.",
                origins=(origin, *build.claim(raised)), due_by=expectation["deadline_utc"],
                opened_at=expectation["created_at"],
                evidence=[build.ev("expectation", expectation["expectation_id"], etype)])

    if late:
        origins: list[str] = []
        evidence: list[EvidenceRef] = []
        for expectation, status, reason in late:
            origins.append(f"expectation:{expectation['expectation_id']}")
            origins.extend(build.claim(build.open_exceptions(
                source_ref=expectation["expectation_id"], source_kind="expectation")))
            gap = f" ({expectation['coverage_gap']})" if expectation["coverage_gap"] else ""
            evidence.append(build.ev(
                "expectation", expectation["expectation_id"],
                f"{expectation['expected_type']} was due {expectation['deadline_utc']}: "
                f"{expectation['state']}{gap}"))
        statuses = [s for _, s, _ in late]
        # A deadline M8 has not ruled on yet is Neyma's own next step, not an outreach.
        only_due = all(s is NeedStatus.DUE for s in statuses)
        worst = (NeedStatus.OVERDUE if NeedStatus.OVERDUE in statuses
                 else NeedStatus.UNVERIFIED if NeedStatus.UNVERIFIED in statuses
                 else NeedStatus.DUE)
        follow_up = build.add(
            NeedKind.CARRIER_STATUS_OVERDUE, (), status=worst,
            handling=Handling.DETERMINISTIC if only_due else Handling.NEYMA_ACTION_CANDIDATE,
            reason_codes=[r for _, _, r in late],
            why=("A deadline passed on the asking clock and the deadline machinery has not ruled "
                 "on it yet." if only_due else
                 "Something expected from the carrier side by a known time has not been seen."),
            actions=(ShadowAction.WAIT,) if only_due else (ShadowAction.REQUEST_CARRIER_STATUS,),
            counterparty="carrier", origins=origins, evidence=evidence,
            opened_at=min(e["deadline_utc"] for e, _, _ in late),
            due_by=min(e["deadline_utc"] for e, _, _ in late))
        # A missed arrival window or tracking cadence is a deadline of OURS that has passed. A
        # promise that itself went unanswered is not: it was only ever the counterparty's word.
        ours = [e["deadline_utc"] for e, _, _ in late
                if e["expected_type"] != "counterparty_update"]
        if ours:
            build.own_deadline[follow_up.need_id] = (min(ours), True)

    # An Exception raised for a deadline that has since been met: retained, owned, and not a task.
    for exception in view.open_exceptions():
        if exception["source_kind"] == "expectation" and exception["source_ref"] not in owed_ids:
            build.housekeeping.append(f"cured_exception:{exception_key(exception)}")
            build.claimed_exceptions.add(exception["exception_id"])
    return pending_promises


# --------------------------------------------------------------------------------- documents

def _document_needs(build: _Build) -> None:
    """A required document that is not usably on file after delivery is ONE need — whether the
    record shows it as an outstanding requirement, an owed Expectation, a missed deadline's
    Exception, or a copy that arrived and cannot be used."""
    view = build.view
    for requirement in view.requirements:
        doc_type = requirement.required_doc_type
        if requirement.state != "OUTSTANDING":
            continue
        expected_type = f"document:{doc_type}"
        owed = [e for e in view.owed_expectations() if e["expected_type"] == expected_type]
        origins = [f"requirement:{requirement.requirement_id}"]
        evidence = [build.ev("requirement", requirement.requirement_id, requirement.reason)]
        status, due_by, opened_at = NeedStatus.OPEN, None, None
        reasons = ["DOCUMENT_NOT_RECEIVED"]
        for expectation in owed:
            origins.append(f"expectation:{expectation['expectation_id']}")
            origins.extend(build.claim(build.open_exceptions(
                source_ref=expectation["expectation_id"], source_kind="expectation")))
            found = _expectation_status(expectation, build.as_of)
            status = NeedStatus.OPEN if found is NeedStatus.PENDING else found
            due_by, opened_at = expectation["deadline_utc"], expectation["created_at"]
            if expectation["coverage_gap"]:
                reasons.append("DOCUMENT_CHANNEL_BLIND")
            evidence.append(build.ev(
                "expectation", expectation["expectation_id"],
                f"{doc_type} is expected by {expectation['deadline_utc']}: "
                f"{expectation['state']}"))
        for document in view.documents.values():
            if document.value("doc_type") != doc_type:
                continue
            reasons[0] = "DOCUMENT_RECEIVED_UNUSABLE"
            origins.append(f"document:{document.entity_id}")
            origins.extend(build.claim(build.open_exceptions(
                type_="document_unusable", source_ref=document.origin_observation_id)))
            evidence.append(build.ev("document", document.entity_id,
                                     f"a {doc_type} arrived and does not satisfy the requirement "
                                     f"({document.lifecycle_state.lower()})"))
        if doc_type == "POD":
            handling, actions = Handling.NEYMA_ACTION_CANDIDATE, (ShadowAction.REQUEST_POD,)
            question = None
        else:
            # The vocabulary carries a request for a POD and for nothing else: any other required
            # paper is a human's to chase.
            handling, actions = Handling.HUMAN_REQUIRED, (ShadowAction.ASK_HUMAN_REVIEW_DOCUMENT,)
            question = f"How should the missing {doc_type} be obtained?"
        required = build.add(
            NeedKind.DOCUMENT_REQUIRED, (doc_type,), status=status, handling=handling,
            reason_codes=reasons,
            why=f"Delivery has been reported and no usable {doc_type} is on file.",
            actions=actions, counterparty="carrier", origins=origins, evidence=evidence,
            opened_at=opened_at, due_by=due_by, question=question)
        if due_by is not None:
            build.own_deadline[required.need_id] = (due_by, status is not NeedStatus.OPEN)

    # A document still OWED in M8 that no outstanding requirement explains: the delivery report it
    # was raised for has been moved off this load, and M8 could not cancel it. It is not a request
    # Neyma could make — nothing says this load was delivered — and it is not dropped: a named
    # human is shown an obligation that has outlived its cause.
    explained = {r.required_doc_type for r in view.requirements if r.state == "OUTSTANDING"}
    for expectation in view.owed_expectations():
        kind, _, doc_type = expectation["expected_type"].partition(":")
        if kind != "document" or doc_type in explained:
            continue
        raised = build.open_exceptions(source_ref=expectation["expectation_id"],
                                       source_kind="expectation")
        build.add(
            NeedKind.UNCLASSIFIED_EXCEPTION, ("expectation", expectation["expectation_id"]),
            status=_expectation_status(expectation, build.as_of),
            handling=Handling.HUMAN_REQUIRED,
            reason_codes=(f"EXPECTATION_OUTLIVED_ITS_CAUSE:{expectation['expected_type']}",),
            why=f"A {doc_type} is still recorded as owed on this load, and nothing on the load "
                f"now says it was delivered.",
            origins=(f"expectation:{expectation['expectation_id']}", *build.claim(raised)),
            evidence=[build.ev("expectation", expectation["expectation_id"],
                               f"{expectation['expected_type']} due "
                               f"{expectation['deadline_utc']}: {expectation['state']}")],
            opened_at=expectation["created_at"], due_by=expectation["deadline_utc"],
            question=f"Is a {doc_type} owed on this load at all?", scope="tenant")


# --------------------------------------------------------------------------------- conflicts

def _conflict_needs(build: _Build) -> None:
    """An unresolved Conflict is a human's. Neyma does not pick the likelier party. The Conflict and
    any Exception raised FOR it are one need.

    ### EVERY OPEN CONFLICT IS BEHIND A NEED. A Conflict on what a movement is owed is read with the
    invoice it disputes — while an invoice on that movement is still in discrepancy, the two are one
    need. When none is (the invoice was placed on another movement, or one side of the comparison
    is itself now in dispute) the Conflict is still OPEN in M7, and nothing but a human or a
    registered rule resolves one: it is shown as its own need, never dropped. Runs after the
    financial needs, so it knows which Conflicts an invoice already carries."""
    carried = {origin for need in build.needs for origin in need.origins}
    view = build.view
    for conflict in view.open_conflicts():
        entity_kind = split_ref(conflict["entity_ref"])[0]
        outlived = conflict["field"].startswith("owed_to_carrier.")
        if outlived and f"conflict:{conflict['conflict_id']}" in carried:
            continue                                  # read with the invoice it disputes
        raised = build.open_exceptions(source_ref=conflict["conflict_id"],
                                       source_kind="conflict")
        evidence = [build.ev("conflict", conflict["conflict_id"],
                             f"{conflict['kind']} on {entity_kind}.{conflict['field']}")]
        financial = entity_kind in _FINANCIAL_ENTITIES and conflict["field"] != "tracking_status"
        for party in conflict["parties"]:
            # A party's stated value is shown — unless it is money, which is never copied here.
            stated = None if financial else party["stated_value"]
            evidence.append(build.ev(
                party["party_kind"], party["party_ref"],
                f"{party['provenance_class']} " + (f"says {stated}" if stated
                                                   else "states a different figure")))
        if entity_kind == "appointment" and conflict["field"] == "window":
            reason = "APPOINTMENT_WINDOW"
            actions = (ShadowAction.ASK_HUMAN_RESOLVE_CONFLICT, ShadowAction.VERIFY_APPOINTMENT)
            why = "Sources state different appointment windows for one stop."
        elif conflict["field"] == "tracking_status":
            reason, actions = "TRACKING_STATUS", (ShadowAction.ASK_HUMAN_RESOLVE_CONFLICT,)
            why = "Movement sources contradict each other about where the freight is."
        elif financial:
            reason = f"FINANCIAL:{entity_kind}.{conflict['field']}"
            actions = (ShadowAction.ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY,)
            why = f"Sources state different figures for {entity_kind}.{conflict['field']}."
            if outlived:
                why += (" No invoice on this movement is in discrepancy now, and the dispute is "
                        "still open: only a human closes it.")
        else:
            reason = f"FIELD:{entity_kind}.{conflict['field']}"
            actions = (ShadowAction.ASK_HUMAN_RESOLVE_CONFLICT,)
            why = f"Sources disagree about {entity_kind}.{conflict['field']}."
        reasons = (reason, "OWED_LINE_CONFLICT_OUTLIVED_ITS_DISCREPANCY") if outlived else (reason,)
        build.add(
            NeedKind.EVIDENCE_CONFLICT, (conflict["conflict_id"],), status=NeedStatus.OPEN,
            handling=Handling.HUMAN_REQUIRED, reason_codes=reasons, why=why, actions=actions,
            owner_id=conflict["owner_id"], related=(conflict["entity_ref"],),
            origins=(f"conflict:{conflict['conflict_id']}", *build.claim(raised)),
            evidence=evidence, opened_at=conflict["created_at"],
            question="Which statement is right?")


# --------------------------------------------------------------------------------- identity

def _identity_needs(build: _Build) -> None:
    """A record Neyma could not place, with this load among its candidates. The need is anchored on
    the RECORD, so it is one piece of work on every load it is offered to. A model-proposed
    candidate is exactly as unbound as any other: a human decides."""
    for item in build.view.ambiguous_candidates:
        reason = "MODEL_PROPOSED_CANDIDATES" if item.model_proposed else "AMBIGUOUS_BINDING"
        build.add(
            NeedKind.IDENTITY_UNRESOLVED, (item.observation_id,), status=NeedStatus.OPEN,
            handling=Handling.HUMAN_REQUIRED, reason_codes=(reason,),
            why=f"An inbound {item.kind or 'record'} names more than one load, or none exactly, "
                f"and was bound to none.",
            actions=(ShadowAction.ASK_HUMAN_RESOLVE_IDENTITY,),
            owner_id=item.owner_id or build.setup.intake_owner,
            related=tuple(f"brokerage_load:{c}" for c in item.candidate_load_ids),
            origins=(f"observation:{item.observation_id}",),
            evidence=[build.ev("observation", item.observation_id,
                               f"held {item.state.lower()} ({item.reason}); references: "
                               + (", ".join(item.references) or "none"))],
            opened_at=item.as_of, question="Which load does this record belong to?",
            scope="tenant")


# --------------------------------------------------------------------------------- money

def _billed_only_on_unplaced_paper(view: LoadView, charge: AccessorialCharge) -> bool:
    """Whether every claim of this charge sits on an invoice nobody has placed. Until that invoice
    is someone's, asking a human to rule on its lines is asking the second question first."""
    unplaced = {o for p in view.payables.values() if p.movement_id is None
                for o in (p.origin_observation_id, *p.duplicate_observation_ids)}
    return bool(charge.claim_observation_ids) and set(charge.claim_observation_ids) <= unplaced


def _financial_needs(build: _Build) -> None:
    view = build.view

    for payable in view.payables.values():
        if payable.movement_id is not None:
            continue
        explained = explain_unattributed_invoice(view, payable)
        raised = build.open_exceptions(type_="carrier_invoice_unattributed",
                                       source_ref=payable.origin_observation_id)
        evidence = [build.ev("observation", payable.origin_observation_id,
                             f"carrier invoice {explained['invoice_number']} as received")]
        if explained["document_ref"]:
            evidence.append(build.ev("document", explained["document_ref"],
                                     f"prints carrier MC {explained['stated_carrier_mc']!r}"))
        for candidate in explained["candidates"]:
            evidence.append(build.ev(
                "carrier_movement", candidate["movement_id"],
                f"movement {candidate['movement_key']}: "
                f"{candidate['carrier_name'] or 'carrier not recorded'} "
                f"({candidate['carrier_mc'] or 'no MC recorded'})"))
        build.add(
            NeedKind.INVOICE_UNATTRIBUTED, (payable.entity_id,), status=NeedStatus.OPEN,
            handling=Handling.HUMAN_REQUIRED,
            reason_codes=(payable.attribution_problem or "CARRIER_NOT_STATED",),
            why=explained["summary"] + " Clears when " + explained["clears_when"] + ".",
            actions=(ShadowAction.ASK_HUMAN_RESOLVE_IDENTITY,),
            owner_id=raised[0]["owner_id"] if raised else None, related=(payable.ref,),
            origins=(f"payable:{payable.entity_id}", *build.claim(raised)), evidence=evidence,
            opened_at=raised[0]["created_at"] if raised else None,
            question=explained["question"])

    undecided: dict[str, list[str]] = {}
    payables = {p.entity_id: p for p in view.payables.values()}
    for result in view.reconciliations:
        payable = payables.get(result.payable_id or "")
        if payable is None:
            continue                                  # nothing has been billed against it yet
        movement_ref = f"carrier_movement:{result.movement_id}"
        blocking = blocking_discrepancies(result)
        mismatches = [d for d in blocking if d.code in _LINE_MISMATCHES]
        denied = [d for d in blocking if d.code == "ACCESSORIAL_NOT_ON_RATE_CONFIRMATION"
                  and d.authorization == "DENIED"]
        for discrepancy in blocking:
            if discrepancy.code == "ACCESSORIAL_NOT_ON_RATE_CONFIRMATION" \
                    and discrepancy.authorization != "DENIED":
                undecided.setdefault(discrepancy.line, []).append(
                    "EXCEEDS_AUTHORIZATION" if discrepancy.authorization
                    == "EXCEEDS_AUTHORIZATION" else "BILLED_NOT_ON_RATE_CONFIRMATION")
        if mismatches or denied:
            conflicts = [c for c in view.open_conflicts() if c["entity_ref"] == movement_ref
                         and c["field"].startswith("owed_to_carrier.")]
            raised = build.open_exceptions(type_="carrier_invoice_arithmetic",
                                           source_ref=payable.origin_observation_id)
            if denied:
                raised += build.open_exceptions(type_="accessorial_authorization_unresolved",
                                                source_ref=payable.origin_observation_id)
            build.add(
                NeedKind.INVOICE_DISCREPANCY, (payable.entity_id,), status=NeedStatus.OPEN,
                handling=Handling.HUMAN_REQUIRED,
                reason_codes=[d.code for d in mismatches]
                + [f"ACCESSORIAL_DENIED_BUT_BILLED:{d.line}" for d in denied],
                why=f"Carrier invoice {payable.value('invoice_number')} does not match what was "
                    f"agreed: " + "; ".join(d.detail for d in (*mismatches, *denied)) + ".",
                actions=(ShadowAction.ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY,),
                owner_id=conflicts[0]["owner_id"] if conflicts else None,
                related=(payable.ref, movement_ref),
                origins=(f"reconciliation:{result.reconciliation_id}",
                         *(f"conflict:{c['conflict_id']}" for c in conflicts),
                         *build.claim(raised)),
                evidence=[build.ev("reconciliation", result.reconciliation_id,
                                   f"{result.status}: " + ", ".join(d.code for d in blocking)),
                          build.ev("observation", payable.origin_observation_id,
                                   "the carrier invoice as received")],
                question="Which figure is owed? Nothing is adjusted until a human says.")
        unestablished = [d for d in blocking if d.code == "EXPECTED_BUY_UNESTABLISHED"]
        blocked: list[str] = []
        if unestablished:
            blocked.append("BUY_RATE_UNESTABLISHED")
        elif result.status == "COMPUTED" and result.actual is not None and not blocking:
            blocked.append("RATE_CONFIRMATION_NOT_SIGNED"
                           if result.expected_basis.startswith("rate_confirmation:")
                           and not result.expected_basis.endswith(":SIGNED")
                           else "RECONCILIATION_NOT_COMPARABLE")
        if blocked:
            raised = build.open_exceptions(type_="buy_rate_unestablished",
                                           source_ref=payable.origin_observation_id)
            build.add(
                NeedKind.RECONCILIATION_BLOCKED, (payable.entity_id,), status=NeedStatus.OPEN,
                handling=Handling.HUMAN_REQUIRED, reason_codes=blocked,
                why=f"Carrier invoice {payable.value('invoice_number')} cannot be reconciled: "
                    f"expected side {result.expected_condition} ({result.expected_basis}).",
                actions=(ShadowAction.ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY,),
                related=(payable.ref, movement_ref),
                origins=(f"reconciliation:{result.reconciliation_id}", *build.claim(raised)),
                evidence=[build.ev("reconciliation", result.reconciliation_id,
                                   f"{result.status}; expected {result.expected_condition}, "
                                   f"actual {result.actual_condition}")],
                question="What buy rate was agreed, and where is it recorded?")

    on_rate_confirmation = {line["charge_type"] for r in view.rate_confirmations.values()
                            for line in (r.value("accessorials") or ())}
    messages = {m.origin_observation_id for m in view.messages}
    for charge_type, charge in sorted(view.accessorials.items()):
        if charge.lifecycle_state in ("AUTHORIZED", "DENIED"):
            continue
        if _billed_only_on_unplaced_paper(view, charge):
            continue
        reasons = list(undecided.get(charge_type, ()))
        claimed_in_message = bool(set(charge.claim_observation_ids) & messages)
        if claimed_in_message and charge_type not in on_rate_confirmation and not reasons:
            reasons.append("CLAIMED_NOT_AUTHORIZED")
        if charge.counterparty_asserted_authorization:
            # A counterparty saying it was approved is a fraud signal on the charge. It is never an
            # authorization, and it makes the human's decision more urgent, not unnecessary.
            reasons.append("COUNTERPARTY_CLAIMS_APPROVAL")
        if charge.lifecycle_state == "DISPUTED":
            reasons.append("AMOUNT_DISPUTED")
        if not reasons:
            continue
        raised = [x for x in view.open_exceptions()
                  if (x["type"] == "counterparty_self_authorization"
                      and x["source_ref"] in charge.claim_observation_ids)
                  or (x["type"] == "accessorial_authorization_unresolved"
                      and x["source_ref"] in charge.claim_observation_ids)]
        build.add(
            NeedKind.ACCESSORIAL_UNAUTHORIZED, (charge_type,), status=NeedStatus.OPEN,
            handling=Handling.HUMAN_REQUIRED, reason_codes=reasons,
            why=f"A {charge_type} accessorial has been claimed or billed and no recorded human "
                f"of this brokerage has authorized it.",
            actions=(ShadowAction.ASK_HUMAN_DECIDE_ACCESSORIAL,), related=(charge.ref,),
            origins=(f"accessorial:{charge.entity_id}", *build.claim(raised)),
            evidence=[build.ev("observation", oid, f"a {charge_type} claim")
                      for oid in dict.fromkeys(charge.claim_observation_ids)],
            question=f"Did a named person at this brokerage authorize {charge_type}? Authorize "
                     f"or deny it.")


# --------------------------------------------------------------------------------- appointments

def _stop_reached(view: LoadView, stop_key: str) -> bool:
    """Whether a STANDING claim puts the truck at this stop or past it. A stop's reported arrival
    and departure are the claims made AT it, and they are read here from the claims themselves:
    one a recorded human overruled is still on the stop as what was said, and reaches nothing."""
    stop = view.stops[stop_key]
    standing = view.standing_tracking()
    if any(t.stop_key == stop_key and t.value("status") in ARRIVAL_STATUSES for t in standing):
        return True
    statuses = {t.value("status") for t in standing}
    return bool(statuses & set(STAGES_PAST_STOP.get(stop.value("stop_type"), ())))


def _appointment_needs(build: _Build) -> None:
    """A stop the truck has not reached whose appointment nobody has CONFIRMED. A REQUESTED window
    is not a time anyone agreed to (CD-13), so Neyma is watching no deadline there: it could not
    tell a late truck from an on-time one. One need per load, naming the stops.

    ### PROVISIONAL — NEEDS VALIDATION (P9-D32). That an unconfirmed appointment is work from the
    moment a carrier is on the load until the stop is reached is this build's SYNTHETIC choice, made
    so the corpus can be run. It is not a validated freight rule and not a universal one: whether,
    when and by whom a brokerage wants an appointment verified is TENANT POLICY, and it is not yet
    tenant-configurable here. It yields a shadow candidate only — never authority for anything."""
    view = build.view
    if not any(m.carrier_id for m in view.movements.values()) or view.delivered_claims():
        return
    reasons: list[str] = []
    related: list[str] = []
    for stop_key in sorted(view.stops, key=lambda k: (view.stops[k].value("sequence") or 0, k)):
        if _stop_reached(view, stop_key):
            continue
        appointment = view.appointments.get(stop_key)
        if appointment is None:
            reasons.append(f"APPOINTMENT_ABSENT:{stop_key}")
            related.append(view.stops[stop_key].ref)
            continue
        if appointment.condition("window") == EvidenceCondition.CONFLICTING.value:
            continue                                  # the Conflict is the need
        if appointment.value("status") != "CONFIRMED":
            reasons.append(f"APPOINTMENT_NOT_CONFIRMED:{stop_key}")
            related.append(appointment.ref)
    if reasons:
        build.add(
            NeedKind.APPOINTMENT_UNCONFIRMED, (), status=NeedStatus.OPEN,
            handling=Handling.NEYMA_ACTION_CANDIDATE, reason_codes=reasons,
            why="A stop this truck has not reached has no confirmed appointment, so no arrival "
                "deadline is being watched there.",
            actions=(ShadowAction.VERIFY_APPOINTMENT,), counterparty="facility", related=related,
            origins=related,
            evidence=[build.ev(split_ref(r)[0], r, "no confirmed window on record")
                      for r in related])


# --------------------------------------------------------------------------------- billing

def _billing_needs(build: _Build) -> None:
    """What stands between a DELIVERED load and billing readiness that no other need already names.
    The readiness predicate itself is the projection's (`L-Invoice ELIGIBLE`); it is read here,
    never restated."""
    view = build.view
    if not view.delivered_claims():
        return
    if any(r.state == "UNKNOWN" for r in view.requirements):
        build.add(
            NeedKind.BILLING_REQUIREMENTS_UNKNOWN, (), status=NeedStatus.OPEN,
            handling=Handling.HUMAN_REQUIRED, reason_codes=("DOCUMENT_REQUIREMENTS_NOT_CONFIGURED",),
            why="This brokerage has configured no document requirement, so what a delivered load "
                "needs before it is billed is unknown. It is never assumed.",
            actions=(ShadowAction.ASK_HUMAN_SET_DOCUMENT_REQUIREMENTS,),
            origins=[f"requirement:{r.requirement_id}" for r in view.requirements
                     if r.state == "UNKNOWN"],
            question="Which documents does this brokerage require before it invoices a load?",
            scope="tenant")
    sell = view.load.condition("sell")
    if sell != EvidenceCondition.CONSISTENT.value and sell != EvidenceCondition.CONFLICTING.value:
        build.add(
            NeedKind.BILLING_BLOCKED, ("sell",), status=NeedStatus.OPEN,
            handling=Handling.HUMAN_REQUIRED, reason_codes=(f"SELL_RATE_{sell.upper()}",),
            why=f"The load is delivered and its sell rate is {sell}: there is nothing to bill.",
            actions=(ShadowAction.ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY,),
            related=(view.load.ref,), origins=(f"field:{view.load.ref}.sell",),
            question="What is the customer to be billed for this load?")


# --------------------------------------------------------------------------------- exceptions

_EXCEPTION_NEEDS: dict[str, tuple[NeedKind, str, ShadowAction]] = {
    "interpretation_unavailable": (NeedKind.DOCUMENT_NEEDS_READING, "CONTENT_NOT_READABLE",
                                   ShadowAction.ASK_HUMAN_REVIEW_DOCUMENT),
    "counterparty_reference_correction": (NeedKind.IDENTITY_UNRESOLVED,
                                          "REFERENCE_CORRECTION_CLAIMED",
                                          ShadowAction.ASK_HUMAN_RESOLVE_IDENTITY),
    "assertion_target_missing": (NeedKind.IDENTITY_UNRESOLVED, "HUMAN_ACT_NAMES_NOTHING",
                                 ShadowAction.ASK_HUMAN_RESOLVE_IDENTITY),
    "invoice_attribution_unusable": (NeedKind.IDENTITY_UNRESOLVED, "HUMAN_ACT_NAMES_NOTHING",
                                     ShadowAction.ASK_HUMAN_RESOLVE_IDENTITY),
}


def _exception_needs(build: _Build) -> None:
    """Every open Exception no other need has claimed. One whose cause the record shows cured is
    housekeeping; one this projection has a name for is that need; anything else is an
    UNCLASSIFIED_EXCEPTION a human must look at. None is dropped.

    ### A QUESTION PUT TO A HUMAN IS NOT DECLARED ANSWERED HERE. A counterparty says an earlier
    message named the wrong load; a human then moves a record. Whether that was the answer is hers
    to say, by resolving the Exception (`resolve_exception`, which M9 records as her decision).
    Until she does the need stays open, and that is reported, not hidden."""
    view = build.view
    for exception in view.open_exceptions():
        if exception["exception_id"] in build.claimed_exceptions:
            continue
        etype = exception["type"]
        if etype in _CAUSE_DERIVED_EXCEPTIONS:
            # Its cause is read from the canonical record, and no need above still names it.
            build.housekeeping.append(f"cured_exception:{exception_key(exception)}")
            continue
        kind, reason, action = _EXCEPTION_NEEDS.get(
            etype, (NeedKind.UNCLASSIFIED_EXCEPTION, etype.upper(), None))
        build.add(
            kind, ("exception", exception_key(exception)), status=NeedStatus.OPEN,
            handling=Handling.HUMAN_REQUIRED, reason_codes=(reason,), why=exception["summary"],
            actions=(action,) if action is not None else (), owner_id=exception["owner_id"],
            origins=build.claim([exception]),
            evidence=[build.ev(exception["source_kind"], exception["source_ref"],
                               f"{etype} ({exception['severity']})")],
            opened_at=exception["created_at"], question=exception["specific_question"],
            scope="tenant")


# --------------------------------------------------------------------------------- act, or wait?

def _apply_pending_promises(build: _Build, pending: Sequence[Mapping[str, Any]]) -> None:
    """A carrier-directed candidate while the carrier side has a promise still pending.

    If the promise is recorded as being ABOUT the very thing the need is missing, acting now would
    only nag: the need WAITS until the promise falls due. If it is recorded as about something
    else, it changes nothing. If the record does not settle what it was about — only its words do —
    then act-or-wait is not a deterministic question, and the need says so (MODEL_REASONING) with
    both answers on offer. A human's need is never touched by any of this.

    ### A COUNTERPARTY'S PROMISE NEVER EXTENDS A DEADLINE OF OURS (P9-D46). A promise can make the
    follow-up point EARLIER; it cannot postpone, replace or suppress the brokerage's, the system's
    or the facility's own deadline. With that deadline T1 and the promise's T2:

      * T1 already passed  -> the need is untouched. Overdue work stays open work: a promise made
                              after the fact does not turn it back into a wait, and no model is
                              asked whether it should.
      * T1 still ahead     -> the wait ends at the EARLIER of T1 and T2. Promised for later than
                              T1, the need is waited on only until T1.
      * no T1 at all       -> the promise is the only clock there is: wait until T2.

    Deterministic, and decided here: which deadline governs is never a question for a model."""
    carrier_side = [p for p in pending if _side(p["sender_role"]) == "carrier"]
    if not carrier_side:
        return
    for index, need in enumerate(build.needs):
        covers = _PROMISE_COVERS.get(need.kind)
        if covers is None or need.human_required \
                or need.handling is not Handling.NEYMA_ACTION_CANDIDATE:
            continue
        own_deadline, own_passed = build.own_deadline.get(need.need_id, (None, False))
        if own_passed:
            continue                                  # our deadline passed: nothing defers it
        exact = [p for p in carrier_side if p["kind"] == covers]
        unsettled = [p for p in carrier_side if p["kind"] in _UNSETTLED_PROMISE_KINDS]
        if exact:
            promise = min(exact, key=lambda p: p["due_by"])
            horizon = min(d for d in (own_deadline, promise["due_by"]) if d is not None)
            build.needs[index] = _replace(
                need, handling=Handling.WAIT, actions=(ShadowAction.WAIT,),
                due_by=horizon,
                reason_codes=(*need.reason_codes, "COVERED_BY_PENDING_PROMISE",
                              *(("OWN_DEADLINE_STILL_CONTROLS",)
                                if horizon != promise["due_by"] else ())),
                origins=(*need.origins, *promise["need"].origins[:1]),
                evidence=(*need.evidence, *promise["need"].evidence))
        elif unsettled:
            promise = min(unsettled, key=lambda p: p["due_by"])
            build.needs[index] = _replace(
                need, handling=Handling.MODEL_REASONING,
                actions=(*need.actions, ShadowAction.WAIT),
                reason_codes=(*need.reason_codes, "PENDING_PROMISE_OF_UNSETTLED_SCOPE"),
                evidence=(*need.evidence, *promise["need"].evidence))


def _replace(need: OperationalNeed, **changes: Any) -> OperationalNeed:
    values = {name: getattr(need, name) for name in need.__dataclass_fields__}
    values.update(changes)
    values["reason_codes"] = tuple(dict.fromkeys(values["reason_codes"]))
    values["origins"] = tuple(dict.fromkeys(values["origins"]))
    return OperationalNeed(**values)


def _together(needs: Sequence[OperationalNeed]) -> tuple[tuple[str, ...], ...]:
    """Candidates addressed to the SAME counterparty are one outreach, not several."""
    groups: dict[str, list[str]] = {}
    for need in needs:
        if need.human_required or need.counterparty is None \
                or need.handling is not Handling.NEYMA_ACTION_CANDIDATE:
            continue
        groups.setdefault(need.counterparty, []).append(need.need_id)
    return tuple(tuple(ids) for _, ids in sorted(groups.items()) if len(ids) > 1)


# --------------------------------------------------------------------------------- history

def _settlements(build: _Build) -> None:
    """Needs this load HAD, as the canonical record shows them ended. Nothing is deleted to make a
    need go away: the discharged Expectation, the resolved Conflict and the human's act are all
    still there, and this reads them."""
    view, tenant, load_id = build.view, build.tenant, build.load_id
    open_ids = {n.need_id for n in build.needs}

    def settle(kind: NeedKind, anchor: Sequence[object], how: str, by: str, *,
               scope: str = "load") -> None:
        parts = (load_id, *anchor) if scope == "load" else tuple(anchor)
        identity = need_id(tenant, kind, *parts)
        if identity not in open_ids:
            build.settled.append(SettledNeed(identity, kind, how, by))

    # A movement watch is SATISFIED by the record that answered it only while that record stands.
    # One a recorded human has since overruled satisfied nothing: the watch it answered ended by
    # HER decision, and - when nothing else answers it - is owed again as a need of its own.
    overruled = {t.origin_observation_id: t.overruled_by for t in view.tracking
                 if t.overruled_by is not None}
    standing = {t.origin_observation_id for t in view.standing_tracking()}
    late_types: set[str] = set()
    for expectation in view.expectations:
        etype, state = expectation["expected_type"], expectation["state"]
        if state not in ("DISCHARGED", "CANCELLED", "EXPIRED"):
            continue
        how = "SATISFIED" if state == "DISCHARGED" else "SUPERSEDED"
        by = (f"observation:{expectation['discharge_observation_id']}"
              if expectation["discharge_observation_id"]
              else f"expectation:{expectation['expectation_id']}")
        answer = expectation["discharge_observation_id"]
        if state == "DISCHARGED" and answer in overruled and answer not in standing \
                and (etype == TRACKING_UPDATE or etype.startswith("arrival:")):
            kind = (NeedKind.TRACKING_UPDATE_PENDING if etype == TRACKING_UPDATE
                    else NeedKind.ARRIVAL_PENDING)
            settle(kind, () if etype == TRACKING_UPDATE else (etype.split(":", 1)[1],),
                   "SUPERSEDED", f"observation:{overruled[answer]}")
            continue
        if etype == "counterparty_update":
            settle(NeedKind.CARRIER_UPDATE_PENDING, (expectation["expectation_id"],), how, by,
                   scope="tenant")
        elif etype.startswith("arrival:"):
            settle(NeedKind.ARRIVAL_PENDING, (etype.split(":", 1)[1],), how, by)
        elif etype == TRACKING_UPDATE:
            settle(NeedKind.TRACKING_UPDATE_PENDING, (), how, by)
        elif etype.startswith("document:") and state == "CANCELLED":
            # The delivery report it was owed for was moved off this load.
            settle(NeedKind.DOCUMENT_REQUIRED, (etype.split(":", 1)[1],), how, by)
        if expectation["late"] and not etype.startswith("document:"):
            late_types.add(by)
    for by in sorted(late_types):
        # Something was late and then arrived: the follow-up it called for is no longer owed.
        settle(NeedKind.CARRIER_STATUS_OVERDUE, (), "SATISFIED", by)

    for requirement in view.requirements:
        if requirement.state == "SATISFIED" and requirement.satisfied_by_document_id:
            settle(NeedKind.DOCUMENT_REQUIRED, (requirement.required_doc_type,), "SATISFIED",
                   f"document:{requirement.satisfied_by_document_id}")
    for conflict in view.conflicts:
        if conflict["state"] not in OPEN_CONFLICT_STATES \
                and not conflict["field"].startswith("owed_to_carrier."):
            settle(NeedKind.EVIDENCE_CONFLICT, (conflict["conflict_id"],), "RESOLVED",
                   conflict["decision_ref"] or f"rule:{conflict['rule_id']}")
    was_unplaced = {x["source_ref"] for x in view.exceptions
                    if x["type"] == "carrier_invoice_unattributed"}
    for payable in view.payables.values():
        if payable.movement_id is None:
            continue
        if payable.attribution_basis == "HUMAN_ASSERTION":
            settle(NeedKind.INVOICE_UNATTRIBUTED, (payable.entity_id,), "RESOLVED",
                   payable.attribution_decision_ref or f"human:{payable.attributed_by}")
        elif payable.origin_observation_id in was_unplaced:
            # Later authoritative evidence placed it: the system of record now names its carrier.
            settle(NeedKind.INVOICE_UNATTRIBUTED, (payable.entity_id,), "SATISFIED",
                   f"carrier_movement:{payable.movement_id}")
    for charge_type, charge in view.accessorials.items():
        if charge.lifecycle_state in ("AUTHORIZED", "DENIED"):
            settle(NeedKind.ACCESSORIAL_UNAUTHORIZED, (charge_type,), "RESOLVED",
                   charge.authorization_id or f"denied:{charge_type}")
    for exception in view.exceptions:
        # A question a named human closed, in M9, by her own decision. The row is retained.
        if exception["state"] == "RESOLVED" and exception["type"] not in _CAUSE_DERIVED_EXCEPTIONS:
            kind = _EXCEPTION_NEEDS.get(exception["type"],
                                        (NeedKind.UNCLASSIFIED_EXCEPTION, "", None))[0]
            settle(kind, ("exception", exception_key(exception)), "RESOLVED",
                   f"human:{exception['decision_human_id']}", scope="tenant")
    for entry in view.binding_history:
        if entry["state"] == "CORRECTED":
            # A record bound here by mistake was moved by a human; the prior binding is retained.
            settle(NeedKind.IDENTITY_UNRESOLVED, (entry["subject_ref"],), "SUPERSEDED",
                   entry["decision_ref"] or f"observation:{entry['subject_ref']}",
                   scope="tenant")
        elif entry["state"] == "CONFIRMED" and entry["match_method"] == "HUMAN" \
                and entry["source"] is not None \
                and entry["source"]["parsed"]["kind"] != "human_assertion":
            settle(NeedKind.IDENTITY_UNRESOLVED, (entry["subject_ref"],), "RESOLVED",
                   entry["decision_ref"] or f"observation:{entry['subject_ref']}",
                   scope="tenant")


# ================================================================================= beyond one load

def evaluate_unplaced_work(projection: FreightProjection, *, setup: TenantSetup,
                           exceptions: Sequence[Mapping[str, Any]],
                           as_of: str) -> tuple[OperationalNeed, ...]:
    """Work that belongs to NO load, so that no load's view would ever show it: an inbound record
    nothing could place and that names no candidate, and an Exception raised about no entity. They
    are a human's, and they are listed here so that "every load is quiet" never hides them."""
    utc_datetime(as_of)
    tenant = projection.tenant
    attached = {x["exception_id"] for view in projection.loads.values() for x in view.exceptions}
    # ### ONE CAUSE, ONE NEED - HERE TOO. A record that was REFUSED (an assertion in the name of
    # nobody the brokerage has recorded) is held unbound AND has an Exception raised about it. That
    # is one thing for a human to look at, not two: the Exception says what is wrong, and the held
    # record is the evidence behind it.
    explained = {x["source_ref"] for x in exceptions
                 if x["state"] != "RESOLVED" and x["exception_id"] not in attached
                 and x["source_kind"] == "observation"}
    held = {item.observation_id for item in projection.unbound if not item.candidate_load_ids}
    needs: list[OperationalNeed] = []
    for item in projection.unbound:
        if item.candidate_load_ids:
            continue                                  # shown on each candidate load
        if item.observation_id in explained:
            continue                                  # read with the Exception raised about it
        reason = "UNREADABLE_RECORD" if item.state == "UNPARSEABLE" else "NO_REFERENCE_RESOLVED"
        needs.append(OperationalNeed(
            need_id=need_id(tenant, NeedKind.IDENTITY_UNRESOLVED, item.observation_id),
            kind=NeedKind.IDENTITY_UNRESOLVED, tenant_id=tenant, load_id="",
            status=NeedStatus.OPEN, handling=Handling.HUMAN_REQUIRED, human_required=True,
            reason_codes=(reason,),
            why=f"An inbound {item.kind or 'record'} could not be placed on any load.",
            actions=(ShadowAction.ASK_HUMAN_RESOLVE_IDENTITY,),
            owner_id=item.owner_id or setup.intake_owner,
            origins=(f"observation:{item.observation_id}",),
            evidence=(evidence_ref(tenant, "observation", item.observation_id,
                                   f"held {item.state.lower()} ({item.reason})"),),
            opened_at=item.as_of, question="Which load, if any, does this record belong to?"))
    for exception in exceptions:
        if exception["state"] == "RESOLVED" or exception["exception_id"] in attached \
                or exception["source_kind"] == "expectation":
            continue
        needs.append(OperationalNeed(
            need_id=need_id(tenant, NeedKind.UNCLASSIFIED_EXCEPTION, "exception",
                            exception_key(exception)),
            kind=NeedKind.UNCLASSIFIED_EXCEPTION, tenant_id=tenant, load_id="",
            status=NeedStatus.OPEN, handling=Handling.HUMAN_REQUIRED, human_required=True,
            reason_codes=(exception["type"].upper(),), why=exception["summary"],
            owner_id=exception["owner_id"],
            origins=(exception_origin(exception),
                     *((f"observation:{exception['source_ref']}",)
                       if exception["source_kind"] == "observation"
                       and exception["source_ref"] in held else ())),
            evidence=(evidence_ref(tenant, exception["source_kind"], exception["source_ref"],
                                   f"{exception['type']} ({exception['severity']})"),),
            opened_at=exception["created_at"], question=exception["specific_question"]))
    return tuple(sorted(needs, key=lambda n: (n.kind.value, n.need_id)))


# ================================================================================= rendering

def _remaining(due_by: str, as_of: str) -> str:
    minutes = int((utc_datetime(due_by) - utc_datetime(as_of)).total_seconds() // 60)
    if minutes < 0:
        minutes = -minutes
        return f"{minutes // 60}h{minutes % 60:02d}m ago" if minutes >= 60 else f"{minutes}m ago"
    return (f"{minutes // 60}h{minutes % 60:02d}m remaining" if minutes >= 60
            else f"{minutes}m remaining")


def _line(need: OperationalNeed, as_of: str) -> str:
    text = f"{need.kind.value} [{', '.join(need.reason_codes)}]"
    if need.due_by:
        text += f" - due {need.due_by} ({_remaining(need.due_by, as_of)})"
    return text


def render_load_work(state: LoadWorkState) -> str:
    """The development surface: one load's work, as an operator would be told it."""
    lines = [f"LOAD {state.load_number or state.load_id}  [{state.tenant_id}]  as of {state.as_of}",
             f"Stage: {state.stage.value}", f"Status: {state.known_status or 'not reported'}", ""]

    def section(title: str, needs: Sequence[OperationalNeed], *, detail: bool = False) -> None:
        lines.append(f"{title}:")
        if not needs:
            lines.append("- none")
        for need in needs:
            lines.append(f"- {_line(need, state.as_of)}")
            if detail:
                lines.append(f"    {need.why}")
                if need.question:
                    lines.append(f"    asks {need.owner_id}: {need.question}")
                for item in need.evidence:
                    lines.append(f"    evidence {item.evidence_id} {item.kind}: {item.note}")
        lines.append("")

    section("Waiting", state.waiting)
    section("Open work", state.open_work)
    lines.append("Neyma candidates:")
    offered = [f"- {action.value}  (for {need.kind.value})" for need in state.candidates
               for action in need.actions]
    lines.extend(offered or ["- none"])
    for group in state.together:
        lines.append(f"  one outreach covers {len(group)} of these")
    lines.append("")
    section("Human attention", state.human_attention, detail=True)
    lines.append("Next posture:")
    lines.append(f"- {state.next_action.value if state.next_action else state.posture.value}"
                 + (f"  ({state.posture.value})" if state.next_action else ""))
    lines.append("")
    lines.append(f"Billing ready: {'yes' if state.billing_ready else 'no'}"
                 + ("" if state.billing_ready else " - " + "; ".join(state.billing_blockers)))
    if state.housekeeping:
        lines.append(f"Housekeeping (cured, awaiting a human's closure): "
                     f"{len(state.housekeeping)}")
    return "\n".join(lines)


__all__ = [
    "EvidenceRef", "Handling", "LoadWorkState", "NeedKind", "NeedStatus",
    "OperationalNeed", "Posture", "SettledNeed", "ShadowAction", "Stage", "WORK_VERSION",
    "evaluate_load_work", "evaluate_unplaced_work", "evidence_ref", "exception_key",
    "exception_origin", "need_id",
    "render_load_work",
]
