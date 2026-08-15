"""Machine M1 — the Work Item, and the mechanism that makes rule 13 true instead of written.

    **Every open operational obligation has one accountable human owner.** — CLAUDE.md rule 13

That sentence has been in this repository since P0. Until now it has been a sentence. This module is
the difference: a Work Item cannot be created without an owner, cannot lose one through any
transition, cannot be given to somebody Neyma never recorded, cannot be given to somebody who has
left, and cannot be closed by anything except an explicit decision that resolves.

### WHERE OWNERSHIP COMES FROM, AND WHERE IT DOES NOT.

Ownership comes from `tenant_humans` — a row somebody put there, attributed to the human who put it
there. It never comes from a string a caller happened to pass, from a Slack handle that appeared in a
message, from the actor of the triggering event, or from "whoever was working on this". Those are all
inference, and an inferred owner is an owner nobody agreed to be. The foreign key is what makes the
difference structural rather than careful: `owner_id` that names no recorded human is not a bad value,
it is an **unwritable** one.

### THE TRANSITION TABLE IS DATA, NOT CODE.

`TRANSITIONS` below is the fourteen rows of `state-machines/01-work-item.machine.md` §14, as data. It
is the thing `AC-MACH-000` enumerates and compares to the specification by EXACT SET EQUALITY of
transition identifiers — a count match with different members must fail, so a row silently renamed or
a row silently added fails the build. Nothing here reads the specification at runtime; the test reads
both and asserts the bijection.

WI-14 has no row of its own in the executable table, and that is what `DELEGATES_TO` means. It says
`ESCALATED` may still block, await, close and cancel **under the guards of WI-5/WI-6/WI-7/WI-3/WI-12,
resolved by TARGET STATE and never positionally**. So it is applied mechanically: WI-14's declared
targets get `ESCALATED` added to their from-states at table-build time, they keep their own guards,
and they keep their own `producer_transition_id` — because the events registry attributes those
events to WI-3/5/6/7/12, and an event whose producer id named WI-14 would be a fact about a
transition the registry does not have.

### GUARD FAILURE AND ILLEGAL TRANSITION ARE DIFFERENT THINGS, AND THE DIFFERENCE IS SECURITY-VISIBLE.

The registry's universal default (§2, "Failure result") is precise: a transition raises, state is
unchanged, and there is **no event — but `IllegalTransitionAttempted` if the trigger was not legal
here**. So:

    (state, trigger) is not in the table   ⇒ raise · persist nothing · emit IllegalTransitionAttempted
                                             into the outbox AND a row into `security_events`, in ONE
                                             commit                                          (GR-1, C-4)
    (state, trigger) is in the table but a
    guard is false                         ⇒ raise · persist nothing · emit NOTHING AT ALL

Collapsing the two would be the easy mistake, and it is the expensive one in both directions. Every
unmet guard becoming a security event trains an operator to ignore security events; every illegal
trigger being filed as an ordinary refusal loses the only signal that something is driving the
machine from a state it should not be able to reach.

### WHAT THIS MODULE DOES NOT DO.

It performs **no external effect** — a Work Item performs none by construction
(`entities/01-work-item.md` point 38), it holds no commit key, it mints no witness and no grant, and
it imports neither the effect boundary nor the checkpoint kernel. It does not duplicate event
transport, replay, audit, timers, persistence, idempotency or PostgreSQL machinery: the outbox is
`event_outbox.TransactionalOutbox`, idempotency for a consumed trigger is
`event_inbox.DedupInbox`, and the age timer is the P5 durable timer. This is the machine; the
plumbing is P5's and stays P5's.

### IT SHIPS DARK. Nothing in the repository calls it yet.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .event_contracts import CONTRACTS
from .event_envelope import EventEnvelope, format_instant
from .event_inbox import ConsumeResult, DedupInbox
from .event_outbox import DuplicateEmission, TransactionalOutbox
from .migrations.phase6_work_items import (
    AUTHORITY_ROLES,
    DECISION_REF_KINDS,
    HUMAN_STATES,
    TERMINAL_WORK_ITEM_STATES,
    WORK_ITEM_STATES,
)
from .persistence import integrity_errors
from .tenant import require_tenant

# The aggregate this machine owns. `work_item` is NOT in `STRICT_ORDER_AGGREGATE_TYPES`: F1 is
# order-tolerant per `events/registry.md` §8, and claiming strictness it does not have would park
# perfectly deliverable events behind a gap that never fills.
AGGREGATE_TYPE = "work_item"

# The component name that travels on every envelope this machine emits. `entities/01-work-item.md`
# point 5: the Work Service owns the Work Item.
PRODUCER_COMPONENT = "work_service"

# The one consumer identity M1 presents to the dedup inbox. Fixed, because the dedup key is
# `(tenant, consumer_id, event_id)` and a consumer that renamed itself would re-arm every duplicate
# it had already absorbed.
CONSUMER_ID = "m1-work-item"

# GR-1's producer id for `IllegalTransitionAttempted`. It is not a transition — `events/registry.md`
# §3 states this contract's producer as the RULE, "‡(any machine, GR-1)", which is why the contract
# itself carries an empty `producers` tuple. `GR-1` is the specification's own answer, not a
# transition id invented here to satisfy the envelope's format.
ILLEGAL_TRANSITION_PRODUCER = "GR-1"

# ### THE IDENTITY OF ONE REFUSED ATTEMPT — AND WHY IT IS NOT THE TRANSITION-NATURAL ONE.
#
# §4's transition-natural identity is `(tenant, aggregate, aggregate_version, transition, name)`,
# and it is exactly right for an event a transition EMITS: the transition advanced the version, so
# the next emission cannot collide with it. `IllegalTransitionAttempted` is the one contract this
# machine emits for something that did NOT happen — the version does not move, by definition — so
# every hostile attempt against one Work Item at one version claims one identity. The outbox's
# UNIQUE constraint then refuses the SECOND attempt as a `DuplicateEmission`, which meant only the
# first hostile attempt was ever recorded, later ones failed with a transport error instead of a
# refusal, and through `DedupInbox.consume` the failure rolled the inbox receipt back and turned
# redelivery into a poison loop.
#
# So this identity keeps §4's shape and adds ONE component: the identity of the ATTEMPT. It is
# `sn_v1`-style — an explicitly supplied identity, which §4 already provides for — rather than a
# new mechanism.
#
#     same attempt (the same hostile event redelivered) ⇒ same identity ⇒ recorded ONCE
#     different attempt against one Work Item version   ⇒ different identity ⇒ recorded SEPARATELY
#
# The attempt identity is never invented where a real one exists: on a consumed trigger it IS the
# incoming event's `event_id`, so redelivery of one hostile event is idempotent by construction and
# not by luck.
ILLEGAL_ATTEMPT_IDENTITY_PREFIX = "ita_v1"

# The timer kind WI-10 fires from. WI-10's trigger type is `T` and its guard says "durable timer, not
# a sweep" — so the guard resolves an actual `durable_timers` row rather than trusting the caller to
# have used one. A sweep cannot produce this evidence, which is the whole point.
AGE_THRESHOLD_TIMER_KIND = "work_item_age_threshold"

# The actor kinds that may drive this machine at all. `model` is absent, and absent everywhere: C-6
# and GR-7 give a model exactly one output, a `ProposedIntent`, which is inert data. A model may
# propose that work is needed; it may never create, own, advance, close or cancel an obligation.
PERMITTED_ACTOR_TYPES: frozenset[str] = frozenset({"human", "system", "detector"})

# `entities/00-conventions.md` K-1(a): the event types that record a HUMAN DECISION and can therefore
# be the referent of a `decision_ref`.
#
# ### K-1 NAMES SIX. FIVE ARE CANONICAL EVENTS AND ONE IS NOT — `HumanResolved` is not among the 118
# contracts, and `ExceptionResolved` (M9, EC-3/EC-6) is the canonical name for what looks like the
# same fact. This module does NOT quietly substitute one for the other: substituting would be this
# unit amending K-1, and M9 is a later unit that will have to decide it on its own surface. So the
# resolvable set is K-1's names INTERSECTED with the canonical registry, the intersection is asserted
# non-empty at import (a decision_ref rule over an empty set would refuse everything and look
# strict), and a `decision_ref` naming an `ExceptionResolved` refuses **today**. Refusing is the safe
# direction; recorded as debt P6-D1.
K1_HUMAN_DECISION_EVENT_NAMES: tuple[str, ...] = (
    "HumanDecided", "HumanResolved", "ApprovalGranted", "RealityEstablished",
    "CompensationApproved", "BrakeReleased",
)
HUMAN_DECISION_EVENTS: frozenset[str] = frozenset(
    name for name in K1_HUMAN_DECISION_EVENT_NAMES if name in CONTRACTS
)
K1_NAMES_NOT_YET_CANONICAL: tuple[str, ...] = tuple(
    name for name in K1_HUMAN_DECISION_EVENT_NAMES if name not in CONTRACTS
)
if not HUMAN_DECISION_EVENTS:
    raise RuntimeError(
        "no K-1 human-decision event name resolves to a canonical contract. A decision_ref rule "
        "over an empty set refuses every closure while looking rigorous — that is a vacuous "
        "negative assertion, and CLAUDE.md §9 exists because this repository has shipped one."
    )


class WorkItemError(RuntimeError):
    """This machine will not do what was asked. Never degraded into a partial transition."""


class UnknownWorkItem(WorkItemError):
    """No Work Item with this id exists FOR THIS TENANT.

    ### Deliberately indistinguishable from "it belongs to another tenant", because establishing the
    difference would require a read across the tenant boundary — and [C-1] says a cross-tenant
    question is rejected before any handler, not answered carefully. The reader loses nothing: a
    tenant that cannot see a row cannot act on it either way.
    """


class OwnershipRefused(WorkItemError):
    """The proposed owner is not a recorded, active human of this tenant. I1 / M-35.

    Raised for all four shapes: absent from `tenant_humans`, offboarded, a non-human identity, and
    blank. They are one refusal because they are one defect — an owner nobody agreed to be.
    """


class AuthorityRefused(WorkItemError):
    """The ACTOR driving this transition does not hold the authority the transition requires."""


class GuardNotSatisfied(WorkItemError):
    """The (state, trigger) pair IS legal here and a precondition is false.

    ### No event is emitted — not even a security one. The trigger was legal; the world was not
    ready. `entities/00-conventions.md` and the registry's §2 default both draw this line, and
    blurring it is how `IllegalTransitionAttempted` becomes noise.
    """


class IllegalTransition(WorkItemError):
    """The (state, trigger) pair is NOT in the table. GR-1 / [C-4].

    Raised AFTER `IllegalTransitionAttempted` has been committed to the outbox and to
    `security_events` — the record survives the refusal, which is the point of recording it.
    """


class VersionConflict(WorkItemError):
    """A stale `expected_version`: zero rows matched, so somebody else transitioned first. GR-3."""


class DecisionRefUnresolvable(WorkItemError):
    """A `decision_ref` that references nothing is not a `decision_ref`. K-1.

    *"This closes the 'closed with the string `done`' hole: the CHECK is not 'non-null' but
    'resolves to an authenticated human decision event or an active rule id'."*
    """


# --------------------------------------------------------------------------------- the state set

class WorkItemState(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class Trigger(str, Enum):
    """The closed trigger set of §14, by the names the machine file and spec §12.1 use.

    ### `CorrectionInvalidatedAnEffect` IS ABSENT, AND THAT IS A DECISION WITH A REASON.
    The machine file lists it under §33 "Events consumed", but §27 routes it out of band: a
    correction that invalidates a completed effect RAISES A COMPENSATION (M10) and, per
    `entities/01-work-item.md` point 32, "may raise a Compensation-bearing obligation" — i.e. it
    creates a NEW Work Item rather than transitioning an existing one. It therefore has no row in
    §14 and cannot be swept as a (state, trigger) pair. Putting it in this enum would make every
    legitimate delivery of it an `IllegalTransitionAttempted` — a false security event, which is
    strictly worse than a missing one because it teaches people to ignore the real ones. Recorded as
    debt P6-D2; it closes when M10 lands.
    """

    WORK_ITEM_CREATED = "WorkItemCreated"
    PIPELINE_STARTED = "PipelineStarted"
    PIPELINE_CLOSED = "PipelineClosed"
    PIPELINE_FAILED = "PipelineFailed"
    EVIDENCE_MISSING = "EvidenceMissing"
    CONFLICT_RAISED = "ConflictRaised"
    HUMAN_DECISION_REQUIRED = "HumanDecisionRequired"
    BLOCKER_CLEARED = "BlockerCleared"
    HUMAN_DECIDED = "HumanDecided"
    AGE_THRESHOLD_CROSSED = "AgeThresholdCrossed"
    OWNERSHIP_REASSIGNED = "OwnershipReassigned"
    CANCELLATION_REQUESTED = "CancellationRequested"
    REOPEN_REQUESTED = "ReopenRequested"


class OwnerAfter(str, Enum):
    """§14's "Owner after" column, as a closed set rather than as prose.

    Twelve of the fourteen rows say `unchanged`, and a test asserts that mechanically: ownership
    moves on exactly WI-1 (assignment), WI-11 (reassignment) and WI-13 (the reopening actor names an
    assignee). Any other transition that touched the owner would be moving accountability as a side
    effect of unrelated progress, which is how an obligation ends up owned by whoever happened to
    trigger it.
    """

    UNCHANGED = "unchanged"
    ASSIGNED_AT_CREATION = "assigned_at_creation"
    NEW_OWNER = "new_owner"
    REOPENING_ASSIGNEE = "reopening_assignee"


# `PipelineFailed` disposition — §14 WI-4 vs WI-5. Two rows, one trigger, discriminated by a
# TOTAL and MUTUALLY EXCLUSIVE guard pair rather than by precedence, which a test asserts.
class FailureDisposition(str, Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"


# --------------------------------------------------------------------------- the transition table

@dataclass(frozen=True)
class TransitionRow:
    """One row of §14. Data, so `AC-MACH-000` can enumerate it and compare it to the specification."""

    id: str
    from_states: tuple[WorkItemState, ...]
    to_state: WorkItemState | None          # None only for the creation row, whose from is "—"
    triggers: tuple[Trigger, ...]
    trigger_types: tuple[str, ...]          # H|S|X|T, the registry §1 codes
    event_name: str | None                  # None only for the DELEGATES_TO row
    owner_after: OwnerAfter
    delegates_to: tuple[str, ...] = ()
    creates: bool = False

    @property
    def is_delegation(self) -> bool:
        return bool(self.delegates_to)


_NON_TERMINAL = tuple(
    s for s in WorkItemState if s.value not in TERMINAL_WORK_ITEM_STATES
)

# ### THE FOURTEEN ROWS OF `state-machines/01-work-item.machine.md` §14, VERBATIM IN STRUCTURE.
# Order follows the specification so the two can be read side by side. `AC-MACH-000` asserts the
# identifier sets are EQUAL — not that the counts match.
_DECLARED_ROWS: tuple[TransitionRow, ...] = (
    TransitionRow(
        id="WI-1", from_states=(), to_state=WorkItemState.OPEN,
        triggers=(Trigger.WORK_ITEM_CREATED,), trigger_types=("H", "S"),
        event_name="WorkItemCreated", owner_after=OwnerAfter.ASSIGNED_AT_CREATION, creates=True,
    ),
    TransitionRow(
        id="WI-2", from_states=(WorkItemState.OPEN,), to_state=WorkItemState.IN_PROGRESS,
        triggers=(Trigger.PIPELINE_STARTED,), trigger_types=("S",),
        event_name="WorkStarted", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-3", from_states=(WorkItemState.IN_PROGRESS,), to_state=WorkItemState.CLOSED,
        triggers=(Trigger.PIPELINE_CLOSED,), trigger_types=("S",),
        event_name="WorkItemClosed", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-4", from_states=(WorkItemState.IN_PROGRESS,), to_state=WorkItemState.IN_PROGRESS,
        triggers=(Trigger.PIPELINE_FAILED,), trigger_types=("S",),
        event_name="AttemptFailed", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-5", from_states=(WorkItemState.IN_PROGRESS,), to_state=WorkItemState.BLOCKED,
        triggers=(Trigger.PIPELINE_FAILED,), trigger_types=("S",),
        event_name="WorkBlocked", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-6", from_states=(WorkItemState.OPEN, WorkItemState.IN_PROGRESS),
        to_state=WorkItemState.BLOCKED,
        triggers=(Trigger.EVIDENCE_MISSING, Trigger.CONFLICT_RAISED), trigger_types=("S", "X"),
        event_name="WorkBlocked", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-7", from_states=(WorkItemState.OPEN, WorkItemState.IN_PROGRESS),
        to_state=WorkItemState.AWAITING_HUMAN,
        triggers=(Trigger.HUMAN_DECISION_REQUIRED,), trigger_types=("S",),
        event_name="HumanRequested", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-8", from_states=(WorkItemState.BLOCKED,), to_state=WorkItemState.IN_PROGRESS,
        triggers=(Trigger.BLOCKER_CLEARED,), trigger_types=("S", "X"),
        event_name="WorkUnblocked", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-9", from_states=(WorkItemState.AWAITING_HUMAN,), to_state=WorkItemState.IN_PROGRESS,
        triggers=(Trigger.HUMAN_DECIDED,), trigger_types=("H",),
        event_name="HumanDecided", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-10",
        from_states=(WorkItemState.OPEN, WorkItemState.IN_PROGRESS, WorkItemState.BLOCKED,
                     WorkItemState.AWAITING_HUMAN),
        to_state=WorkItemState.ESCALATED,
        triggers=(Trigger.AGE_THRESHOLD_CROSSED,), trigger_types=("T",),
        event_name="WorkEscalated", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-11", from_states=(WorkItemState.ESCALATED,), to_state=WorkItemState.IN_PROGRESS,
        triggers=(Trigger.OWNERSHIP_REASSIGNED,), trigger_types=("H",),
        event_name="OwnershipTransferred", owner_after=OwnerAfter.NEW_OWNER,
    ),
    TransitionRow(
        id="WI-12", from_states=_NON_TERMINAL, to_state=WorkItemState.CANCELLED,
        triggers=(Trigger.CANCELLATION_REQUESTED,), trigger_types=("H",),
        event_name="WorkItemCancelled", owner_after=OwnerAfter.UNCHANGED,
    ),
    TransitionRow(
        id="WI-13", from_states=(WorkItemState.CLOSED,), to_state=WorkItemState.IN_PROGRESS,
        triggers=(Trigger.REOPEN_REQUESTED,), trigger_types=("H",),
        event_name="Reopened", owner_after=OwnerAfter.REOPENING_ASSIGNEE,
    ),
    # ### THE DELEGATION ROW. It has no event and no single target state: §14 resolves it "by TARGET
    # STATE (never positionally)". It is applied below by widening its targets, and it is kept in the
    # table because `AC-MACH-000` compares against the specification's FOURTEEN identifiers.
    TransitionRow(
        id="WI-14", from_states=(WorkItemState.ESCALATED,), to_state=None,
        triggers=(), trigger_types=("S", "H"), event_name=None,
        owner_after=OwnerAfter.UNCHANGED,
        delegates_to=("WI-5", "WI-6", "WI-7", "WI-3", "WI-12"),
    ),
)


def _apply_delegation(rows: Sequence[TransitionRow]) -> tuple[TransitionRow, ...]:
    """Widen each WI-14 target with `ESCALATED`. Mechanical, so the delegation cannot drift.

    Written as a derivation rather than by adding `ESCALATED` to five from-state tuples by hand,
    because a hand-copied delegation is a delegation that stops matching its own row the first time
    §14 changes — and nothing would notice, since both halves would still be internally consistent.
    """
    by_id = {row.id: row for row in rows}
    widened: dict[str, TransitionRow] = {}
    for row in rows:
        if not row.is_delegation:
            continue
        for target_id in row.delegates_to:
            target = by_id.get(target_id)
            if target is None:
                raise RuntimeError(
                    f"{row.id} delegates to {target_id!r}, which is not a declared transition. A "
                    f"delegation to a row that does not exist is a state reachable by nothing."
                )
            base = widened.get(target_id, target)
            if all(s in base.from_states for s in row.from_states):
                widened[target_id] = base
                continue
            widened[target_id] = TransitionRow(
                id=base.id,
                from_states=tuple(base.from_states) + tuple(
                    s for s in row.from_states if s not in base.from_states),
                to_state=base.to_state, triggers=base.triggers,
                trigger_types=base.trigger_types, event_name=base.event_name,
                owner_after=base.owner_after, delegates_to=base.delegates_to, creates=base.creates,
            )
    return tuple(widened.get(row.id, row) for row in rows)


TRANSITIONS: tuple[TransitionRow, ...] = _apply_delegation(_DECLARED_ROWS)
TRANSITIONS_BY_ID: Mapping[str, TransitionRow] = {row.id: row for row in TRANSITIONS}

# §16's precedence, as data. Consulted ONLY when more than one row survives its guards for the same
# (state, trigger) — which the WI-4/WI-5 pair is deliberately built never to do. It exists because
# the specification states it, and because a precedence rule that is never expressible is a rule
# nobody can test.
PRECEDENCE: tuple[str, ...] = ("WI-12", "WI-3", "WI-5", "WI-6", "WI-7", "WI-2", "WI-8", "WI-9",
                               "WI-4", "WI-10", "WI-11", "WI-13")


def legal_transitions(state: WorkItemState, trigger: Trigger) -> tuple[TransitionRow, ...]:
    """Every row whose (from-state, trigger) matches. Empty means ILLEGAL under GR-1."""
    return tuple(
        row for row in TRANSITIONS
        if not row.is_delegation and not row.creates
        and state in row.from_states and trigger in row.triggers
    )


def rows_for_trigger(trigger: Trigger) -> tuple[TransitionRow, ...]:
    """Every non-delegation row this trigger can fire, whatever the state. Data, so it can be swept."""
    return tuple(
        row for row in TRANSITIONS if not row.is_delegation and trigger in row.triggers
    )


def work_item_must_exist(trigger: Trigger) -> bool:
    """Is an existing Work Item a PREREQUISITE of this trigger, or is it the trigger's PRODUCT?

    ### THIS IS DERIVED FROM §14, NOT LISTED. A hand-kept list of "the creation triggers" is a list
    that is right on the day it is written; `creates` is already on the row because `AC-MACH-000`
    enumerates the table, so the question is answered by the specification itself and a fourteenth
    row added tomorrow answers it too.

    A trigger whose every row `creates` brings the Work Item into existence — WI-1 — and demanding
    that it pre-exist is demanding that it exist before it exists. Everything else is ABOUT a Work
    Item, and `HumanDecided` is the sharp case: it rides on `work_item:<id>` because that is its
    ordering key, yet the item it decides must already be there. That pair — own aggregate, genuine
    prerequisite — is what `DedupInbox.consume(requires_existing=...)` exists to state, and what
    silently evaporated before it did.

    A trigger with NO row at all answers True: the safe reading of an unmapped trigger is that it
    is about something, and parking a stranger is recoverable where skipping one is not.
    """
    rows = rows_for_trigger(trigger)
    return not (rows and all(row.creates for row in rows))


# ------------------------------------------------------------------------------- recorded authority

@dataclass(frozen=True)
class HumanAuthority:
    """One recorded, attributed act of admitting a human to a tenant."""

    tenant: str
    human_id: str
    display_name: str
    authority_role: str
    state: str
    recorded_at: str
    recorded_by: str
    recorded_by_kind: str
    offboarded_at: str | None = None

    @property
    def is_active(self) -> bool:
        return self.state == "ACTIVE"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_authority(row: Any) -> HumanAuthority:
    return HumanAuthority(
        tenant=row["tenant"], human_id=row["human_id"], display_name=row["display_name"],
        authority_role=row["authority_role"], state=row["state"],
        recorded_at=row["recorded_at"], recorded_by=row["recorded_by"],
        recorded_by_kind=row["recorded_by_kind"], offboarded_at=row["offboarded_at"],
    )


def record_human_authority(
    conn: sqlite3.Connection,
    *,
    tenant: str,
    human_id: str,
    display_name: str,
    authority_role: str,
    recorded_by: str,
    recorded_by_kind: str = "human",
    now: datetime | None = None,
) -> HumanAuthority:
    """Admit ONE named human to ONE tenant, attributed to the human who admitted them.

    ### `recorded_by_kind` DEFAULTS TO `human` AND THE DATABASE ACCEPTS NOTHING ELSE. The default is
    a convenience; the CHECK is the rule. If a model could record an authority, the model would be
    choosing who may own work, and rule 13 would be enforced against a roster the model wrote.

    This is not user administration — that is the web control plane's, and ADR-017 assigns it to P11.
    It is the durable referent `entities/01-work-item.md` point 18 requires and had nowhere to point.
    """
    tenant = require_tenant(tenant, context="record_human_authority")
    if authority_role not in AUTHORITY_ROLES:
        raise AuthorityRefused(
            f"{authority_role!r} is not one of §7's human roles {list(AUTHORITY_ROLES)}. "
            f"An automated detector and an agent/model are §7 rows too, and neither may hold work: "
            f"a detector may engage a brake and never release one, and a model may emit a "
            f"ProposedIntent and nothing else (C-6, GR-7)."
        )
    if recorded_by_kind != "human":
        raise AuthorityRefused(
            f"recorded_by_kind={recorded_by_kind!r}: admitting a human to a tenant is itself a human "
            f"act. A machine that could grant authority could grant itself an owner."
        )
    stamp = format_instant(now or _utc_now())
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """
            INSERT INTO tenant_humans (
                tenant, human_id, display_name, authority_role, state, recorded_at, recorded_by,
                recorded_by_kind, offboarded_at
            ) VALUES (?,?,?,?, 'ACTIVE', ?,?,?, NULL)
            """,
            (tenant, human_id, display_name, authority_role, stamp, recorded_by, recorded_by_kind),
        )
        conn.commit()
    except integrity_errors() as exc:
        conn.rollback()
        raise AuthorityRefused(
            f"cannot record {human_id!r} as an authority of {tenant!r}: {exc}. Either they are "
            f"already recorded, or the identity is not a human one — 'system', 'model', 'agent', "
            f"'detector' and their neighbours are refused by the database, not by review."
        ) from exc
    except BaseException:
        conn.rollback()
        raise
    found = human_authority(conn, tenant=tenant, human_id=human_id)
    assert found is not None
    return found


def human_authority(
    conn: sqlite3.Connection, *, tenant: str, human_id: str,
) -> HumanAuthority | None:
    """One recorded authority, or None. Tenant-scoped by construction — no cross-tenant read."""
    row = conn.execute(
        "SELECT * FROM tenant_humans WHERE tenant = ? AND human_id = ?",
        (require_tenant(tenant, context="human_authority"), human_id),
    ).fetchone()
    return _row_to_authority(row) if row is not None else None


def active_humans(conn: sqlite3.Connection, *, tenant: str) -> list[HumanAuthority]:
    return [
        _row_to_authority(r) for r in conn.execute(
            "SELECT * FROM tenant_humans WHERE tenant = ? AND state = 'ACTIVE' ORDER BY human_id",
            (require_tenant(tenant, context="active_humans"),),
        ).fetchall()
    ]


def open_work_owned_by(
    conn: sqlite3.Connection, *, tenant: str, owner_id: str,
) -> list[str]:
    """The non-terminal Work Items this human is accountable for. The offboarding refusal reads it."""
    placeholders = ",".join("?" for _ in TERMINAL_WORK_ITEM_STATES)
    return [
        r["work_item_id"] for r in conn.execute(
            f"SELECT work_item_id FROM work_items "
            f" WHERE tenant = ? AND owner_id = ? AND state NOT IN ({placeholders}) "
            f" ORDER BY work_item_id",
            (require_tenant(tenant, context="open_work_owned_by"), owner_id,
             *TERMINAL_WORK_ITEM_STATES),
        ).fetchall()
    ]


def offboard_human(
    conn: sqlite3.Connection,
    *,
    tenant: str,
    human_id: str,
    offboarded_by: str,
    now: datetime | None = None,
) -> HumanAuthority:
    """Retire an authority — and REFUSE while they still owe this tenant open work.

    ### THIS IS POINT 36'S FAIL-CLOSED HALF, BUILT AT THE ONLY MOMENT IT IS CHEAP. *"A Work Item
    that loses its owner (e.g. offboarding) does not silently continue."* The full behaviour raises
    an Exception (M9) and blocks consequential Pipelines (M2) — both later units. What this unit can
    do without inventing either is make the ownerless state **unreachable through the supported
    path**: the human cannot be retired while they own non-terminal work, and the refusal NAMES the
    items so the operator reassigns them through WI-11 rather than being told "no".

    The residual is honest and recorded (P6-D3): a row edited around this API by an operator with a
    connection could still offboard an owner, and the Sev-0 detection that notices is M9's.
    """
    tenant = require_tenant(tenant, context="offboard_human")
    existing = human_authority(conn, tenant=tenant, human_id=human_id)
    if existing is None:
        raise AuthorityRefused(
            f"{human_id!r} is not a recorded authority of {tenant!r}; there is nothing to retire."
        )
    outstanding = open_work_owned_by(conn, tenant=tenant, owner_id=human_id)
    if outstanding:
        raise OwnershipRefused(
            f"{human_id!r} is still accountable for {len(outstanding)} open Work Item(s): "
            f"{outstanding}. Retiring them would leave that work owned by somebody who has left, "
            f"which is exactly the silent continuation `entities/01-work-item.md` point 36 forbids. "
            f"Reassign each item through WI-11 (OwnershipReassigned) first — reassignment is a "
            f"recorded, attributed act, and dropping the owner is not."
        )
    stamp = format_instant(now or _utc_now())
    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            "UPDATE tenant_humans SET state = 'OFFBOARDED', offboarded_at = ? "
            " WHERE tenant = ? AND human_id = ? AND state = 'ACTIVE'",
            (stamp, tenant, human_id),
        )
        if cursor.rowcount != 1:
            raise AuthorityRefused(
                f"{human_id!r} is not ACTIVE in {tenant!r}; it is {existing.state!r}."
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    found = human_authority(conn, tenant=tenant, human_id=human_id)
    assert found is not None
    # `offboarded_by` is recorded on the event a caller emits around this act, not on the row: the
    # row's `recorded_by` is the ADMISSION act and is immutable by trigger. Conflating the two would
    # let a retirement overwrite the record of who admitted them.
    del offboarded_by
    return found


# ------------------------------------------------------------------------------ decision references

@dataclass(frozen=True)
class DecisionRef:
    """A `decision_ref` that has been RESOLVED — never one that has merely been supplied."""

    ref: str
    kind: str
    event_name: str | None = None
    actor_id: str | None = None


def resolve_decision_ref(
    conn: sqlite3.Connection, *, tenant: str, ref: str, kind: str,
) -> DecisionRef:
    """K-1, executed. A string that references nothing is not a `decision_ref`.

    (a) `AUDIT_EVENT` — resolves against the canonical event log. The Audit Event IS the event in the
        transactional outbox: `entities/17-audit-event.md` gives it identity `(tenant_id, event_id)`
        (points 8, 17) and says it is *"written into the transactional OUTBOX in the SAME transaction
        as the state change that emitted it"* (point 15). So there is no second audit store to build,
        and building one would be the second authority CLAUDE.md §5 rule 17 forbids in its own domain.
        The row must be a human-decision event type AND carry `actor_type='human'` — the type alone
        is not enough, because `ApprovalGranted` emitted by automation would be exactly the laundered
        authority ER-11 refuses.

    (b) `RULE` — ### REFUSES TODAY, AND SAYS WHY. K-1's other referent is an `ACTIVE` `rule_id`, and
        Rules are machine M12, a later P6 unit with no table yet. A stub that accepted any rule id
        would make "closed by an active rule" true of rules that do not exist, which is worse than a
        refusal by exactly the margin that matters. Recorded as debt P6-D4.
    """
    tenant = require_tenant(tenant, context="resolve_decision_ref")
    if kind not in DECISION_REF_KINDS:
        raise DecisionRefUnresolvable(
            f"decision_ref_kind {kind!r} is not one of {list(DECISION_REF_KINDS)} (K-1). A "
            f"polymorphic reference whose namespace is guessed from the shape of the string "
            f"resolves differently the day a rule id starts looking like a uuid."
        )
    text = str(ref or "").strip()
    if not text:
        raise DecisionRefUnresolvable(
            "a blank decision_ref is not a decision_ref. I11: closure is an emitted event, never an "
            "inference, and never the string 'done'."
        )
    if kind == "RULE":
        raise DecisionRefUnresolvable(
            f"decision_ref {text!r} claims kind RULE, and Rules (machine M12) are not implemented "
            f"yet — there is no `rules` table to resolve an ACTIVE rule_id against. Refused rather "
            f"than accepted on trust: accepting would make 'closed by an active rule' true of a rule "
            f"that does not exist. Use an AUDIT_EVENT reference, or wait for M12 (debt P6-D4)."
        )
    row = conn.execute(
        "SELECT event_name, envelope_json FROM event_outbox WHERE tenant = ? AND event_id = ?",
        (tenant, text),
    ).fetchone()
    if row is None:
        raise DecisionRefUnresolvable(
            f"decision_ref {text!r} resolves to no canonical event for tenant {tenant!r}. A string "
            f"that references nothing is not a decision_ref (K-1), and the transition is illegal."
        )
    event_name = row["event_name"]
    if event_name not in HUMAN_DECISION_EVENTS:
        raise DecisionRefUnresolvable(
            f"decision_ref {text!r} resolves to a {event_name!r}, which is not one of K-1's "
            f"human-decision event types {sorted(HUMAN_DECISION_EVENTS)}. A `PipelineClosed` is a "
            f"system fact about an attempt, not a human deciding the obligation is discharged — "
            f"letting it close a Work Item is closure by system convenience."
            + (f" (K-1 also names {list(K1_NAMES_NOT_YET_CANONICAL)}, which is not among the "
               f"canonical contracts; see debt P6-D1.)" if K1_NAMES_NOT_YET_CANONICAL else "")
        )
    envelope = EventEnvelope.from_json(row["envelope_json"])
    if envelope.actor_type != "human":
        raise DecisionRefUnresolvable(
            f"decision_ref {text!r} resolves to a {event_name!r} recorded with "
            f"actor_type={envelope.actor_type!r}. K-1 requires an AUTHENTICATED HUMAN actor: a "
            f"human-decision event TYPE emitted by automation is authority laundering, not a "
            f"decision (ER-11)."
        )
    return DecisionRef(ref=text, kind=kind, event_name=event_name, actor_id=envelope.actor_id)


# --------------------------------------------------------------------------------- the machine

@dataclass(frozen=True)
class WorkItem:
    """One Work Item row, as the machine reads it."""

    tenant: str
    work_item_id: str
    type: str
    state: WorkItemState
    version: int
    owner_id: str
    phase_seq: int
    created_at: str
    updated_at: str
    entity_ref: str | None = None
    reopens: str | None = None
    prior_closure_ref: str | None = None
    escalation_at: str | None = None
    blocker_ref: str | None = None
    exposure_amount_minor: int | None = None
    exposure_currency: str | None = None
    exposure_observation_ref: str | None = None
    closure_decision_ref: str | None = None
    closure_decision_ref_kind: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state.value in TERMINAL_WORK_ITEM_STATES


@dataclass(frozen=True)
class TransitionResult:
    """What one transition did. Every field is read back from the row, never from the intention."""

    transition_id: str
    work_item: WorkItem
    event_id: str
    event_name: str
    from_state: WorkItemState | None
    to_state: WorkItemState
    owner_before: str | None
    owner_after: str


@dataclass(frozen=True)
class IllegalAttemptRecord:
    """What recording ONE refused attempt did — including the case where it had already been done.

    `already_recorded` is the difference between *"this attempt is on both surfaces because this
    call put it there"* and *"this attempt is on both surfaces because an earlier delivery of the
    SAME attempt put it there"*. Both are correct outcomes and neither is a failure; conflating them
    is how a redelivery ends up counted as a second hostile attempt.
    """

    event_id: str
    idempotency_identity: str
    already_recorded: bool


@dataclass(frozen=True)
class ConsumedTransition:
    """What consuming one canonical trigger did — including the case where it did nothing.

    `consume.outcome` is P5's (APPLIED / DUPLICATE_NOOP / PARKED / …) and is about DELIVERY.
    `transition`, `refusal` and `refusal_kind` are about the MACHINE. Keeping them apart is what
    stops "the event was delivered" being read as "the Work Item moved".
    """

    consume: ConsumeResult
    transition: "TransitionResult | None" = None
    refusal: str | None = None
    refusal_kind: str | None = None
    # Present exactly when `refusal_kind == "ILLEGAL"`: which record this refusal is, and whether
    # this delivery wrote it or found the SAME attempt already recorded.
    illegal_record: "IllegalAttemptRecord | None" = None

    @property
    def moved(self) -> bool:
        return self.transition is not None


@dataclass
class _Facts:
    """The caller-supplied facts a guard may read. Deliberately explicit and deliberately dumb.

    ### NOTHING HERE IS INFERRED. `obligation_satisfied` is the clearest case: WI-3's guard is
    "obligation satisfied", and acceptance item (d) says a finishing Pipeline Instance does NOT
    auto-close the item — billed is not paid, and a loop that closes at cash does not close when the
    invoice goes out. So it is a fact the caller must state, not something this machine derives from
    a `PipelineClosed` arriving. A machine that derived it would close obligations early and be
    right most of the time, which is the worst possible failure profile for money.
    """

    obligation_satisfied: bool | None = None
    disposition: FailureDisposition | None = None
    retries_remain: int | None = None
    reason: str | None = None
    question: str | None = None
    evidence_condition: str | None = None
    open_conflict: bool | None = None
    decision_ref: str | None = None
    decision_ref_kind: str | None = None
    to_owner: str | None = None
    assignee: str | None = None
    timer_id: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


class WorkItemMachine:
    """M1, on an existing connection, bound to ONE tenant.

    Bound at construction rather than per call, for the reason `DedupInbox` is: a machine that could
    be re-pointed at another tenant per call would put [C-1] in the caller's hands.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        tenant: str,
        clock: Callable[[], datetime] | None = None,
        producer_component: str = PRODUCER_COMPONENT,
    ) -> None:
        if getattr(conn, "row_factory", None) is not sqlite3.Row:
            raise WorkItemError(
                "WorkItemMachine reads columns by name and requires `row_factory = sqlite3.Row` "
                "(WorkflowStore sets it; PostgresConnection reports it)."
            )
        self._conn = conn
        self._tenant = require_tenant(tenant, context="WorkItemMachine")
        self._clock = clock or _utc_now
        self._component = producer_component

    @property
    def tenant(self) -> str:
        return self._tenant

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # --- reads -----------------------------------------------------------------------------------

    def get(self, work_item_id: str) -> WorkItem | None:
        row = self._conn.execute(
            "SELECT * FROM work_items WHERE tenant = ? AND work_item_id = ?",
            (self._tenant, work_item_id),
        ).fetchone()
        return _row_to_work_item(row) if row is not None else None

    def require(self, work_item_id: str) -> WorkItem:
        item = self.get(work_item_id)
        if item is None:
            raise UnknownWorkItem(
                f"no Work Item {work_item_id!r} for tenant {self._tenant!r}. This machine does not "
                f"look outside its tenant to find out whether it exists elsewhere — [C-1] rejects a "
                f"cross-tenant question rather than answering it carefully."
            )
        return item

    def ownerless(self) -> list[str]:
        """The Sev-0 observability query. It should always return nothing; that is why it exists.

        ### A NEGATIVE ASSERTION NEEDS A PROVEN POPULATION (CLAUDE.md §9), so this returns the ids
        AND the caller is expected to assert against a non-empty item population. An ownerless
        detector run over an empty table is a green check that parsed nothing.
        """
        placeholders = ",".join("?" for _ in TERMINAL_WORK_ITEM_STATES)
        return [
            r["work_item_id"] for r in self._conn.execute(
                f"""
                SELECT w.work_item_id FROM work_items w
                 WHERE w.tenant = ? AND w.state NOT IN ({placeholders})
                   AND NOT EXISTS (SELECT 1 FROM tenant_humans h
                                    WHERE h.tenant = w.tenant AND h.human_id = w.owner_id
                                      AND h.state = 'ACTIVE')
                 ORDER BY w.work_item_id
                """,
                (self._tenant, *TERMINAL_WORK_ITEM_STATES),
            ).fetchall()
        ]

    # --- WI-1 ------------------------------------------------------------------------------------

    def create(
        self,
        *,
        work_item_id: str,
        type: str,
        owner_id: str,
        actor_type: str,
        actor_id: str,
        entity_ref: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        exposure_amount_minor: int | None = None,
        exposure_currency: str | None = None,
        exposure_observation_ref: str | None = None,
    ) -> TransitionResult:
        """WI-1. ### `owner_id` MUST be an ACTIVE recorded human — creation with anything else FAILS.

        No event is emitted on failure and no row is written: a refused creation is not an illegal
        transition (there is no state it was refused from) and it is not a fact about a Work Item,
        because no Work Item came into existence.
        """
        self._require_actor(actor_type)
        owner = self._require_active_human(
            owner_id, what="the accountable owner at creation (I1, M-35)")
        if exposure_amount_minor is not None and not exposure_observation_ref:
            # K-4: a money field on an operational record carries the observation it was READ from.
            # A remembered amount is the one thing §22 forbids outright.
            raise WorkItemError(
                "exposure was supplied without `exposure_observation_ref`. K-4 permits a money value "
                "on an operational record only when it is sourced from a live or verified "
                "authoritative read; an amount recalled from memory is forbidden outright."
            )
        now = format_instant(self._clock())
        row = TRANSITIONS_BY_ID["WI-1"]
        envelope = self._envelope(
            event_name="WorkItemCreated", transition_id="WI-1", work_item_id=work_item_id,
            aggregate_version=1, owner_id=owner.human_id, actor_type=actor_type, actor_id=actor_id,
            payload=_prune({"owner_id": owner.human_id, "type": type, "entity_ref": entity_ref}),
            correlation_id=correlation_id or work_item_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id, now=now,
        )
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            outbox = TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock)
            self._conn.execute(
                """
                INSERT INTO work_items (
                    tenant, work_item_id, type, state, version, owner_id, phase_seq, entity_ref,
                    reopens, prior_closure_ref, escalation_at, blocker_ref, exposure_amount_minor,
                    exposure_currency, exposure_observation_ref, closure_decision_ref,
                    closure_decision_ref_kind, created_at, updated_at
                ) VALUES (?,?,?, 'OPEN', 1, ?, 1, ?, NULL, NULL, NULL, NULL, ?,?,?, NULL, NULL, ?,?)
                """,
                (self._tenant, work_item_id, type, owner.human_id, entity_ref,
                 exposure_amount_minor, exposure_currency, exposure_observation_ref, now, now),
            )
            outbox.emit(envelope)
            self._conn.commit()
        except integrity_errors() as exc:
            self._conn.rollback()
            raise WorkItemError(
                f"cannot create Work Item {work_item_id!r} for {self._tenant!r}: {exc}"
            ) from exc
        except BaseException:
            self._conn.rollback()
            raise
        item = self.require(work_item_id)
        return TransitionResult(
            transition_id=row.id, work_item=item, event_id=envelope.event_id,
            event_name="WorkItemCreated", from_state=None, to_state=WorkItemState.OPEN,
            owner_before=None, owner_after=item.owner_id,
        )

    # --- WI-2 … WI-13 ----------------------------------------------------------------------------

    def apply(
        self,
        work_item_id: str,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        expected_version: int | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        **facts: Any,
    ) -> TransitionResult:
        """ONE transition, in ONE commit: the state row and the event it emits, or neither.

        ### `event_id` IS THE IDENTITY OF WHAT THIS CALL RECORDS, WHICHEVER OF THE TWO IT RECORDS.
        Supplied, it is the id of the emitted transition event — and, when the trigger turns out to
        be illegal here, of the `IllegalTransitionAttempted` that records the refusal instead. One
        call records one fact; which fact it is depends on the answer, so pinning the identity pins
        it either way, and a caller that retries ONE attempt gets ONE refusal record. Left unset, a
        fresh identity is minted per call, because on this API each call IS a distinct attempt:
        there is no delivery to be redelivered.
        """
        self._require_actor(actor_type)
        item = self.require(work_item_id)
        if expected_version is not None and expected_version != item.version:
            raise VersionConflict(
                f"expected_version {expected_version} but {work_item_id!r} is at "
                f"version {item.version}: somebody else transitioned it first. Reload and retry "
                f"(GR-3) — a lost update here is a transition that silently did not happen."
            )
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            result = self._apply_locked(
                item, trigger, actor_type=actor_type, actor_id=actor_id,
                correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                event_id=event_id, facts=_Facts(**_split_facts(facts)),
            )
            self._conn.commit()
        except IllegalTransition:
            # ### THE REFUSAL IS ROLLED BACK; THE RECORD OF IT IS NOT.
            #
            # GR-1 says an illegal transition "raises, persists nothing, and emits
            # `IllegalTransitionAttempted`" — and those two halves cannot share a transaction,
            # because the transaction is the thing being abandoned. The first version of this method
            # wrote the security record inside the failing transaction and then rolled it back with
            # everything else: the refusal worked, the evidence of it vanished, and
            # `security_events` was empty after a hostile attempt. That is a silent hole in exactly
            # the surface somebody is paged from, and it passed every test that only asserted the
            # raise.
            #
            # So: abandon the attempt first, THEN record the attempt in a commit of its own. There
            # is no state change for it to be atomic with — that is the definition of the case.
            self._conn.rollback()
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._record_illegal_locked(
                    item, trigger, actor_type=actor_type, actor_id=actor_id,
                    correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
                    attempt_id=event_id or str(uuid.uuid4()), event_id=event_id,
                )
                self._conn.commit()
            except BaseException:
                self._conn.rollback()
                raise
            raise
        except BaseException:
            self._conn.rollback()
            raise
        return result

    def _apply_locked(
        self,
        item: WorkItem,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        facts: _Facts,
    ) -> TransitionResult:
        """The transition itself. Requires a transaction to be open; never opens or commits one.

        Separated from `apply` so the SAME body serves a consumed trigger, where `DedupInbox` owns
        the transaction (M-24) and the handler must not begin, commit or roll back. Two copies of a
        transition body is how one of them quietly stops emitting an event.
        """
        candidates = legal_transitions(item.state, trigger)
        if not candidates:
            raise IllegalTransition(
                f"{trigger.value} is not legal for a Work Item in {item.state.value} "
                f"(GR-1, [C-4]). No state change was persisted; `IllegalTransitionAttempted` is "
                f"recorded to the audit backbone AND to `security_events`, atomically with each "
                f"other, in a commit of their own."
            )
        surviving: list[tuple[TransitionRow, str]] = []
        refusals: list[str] = []
        for row in candidates:
            problem = self._guard_problem(row, item, trigger, facts, actor_type, actor_id)
            if problem is None:
                surviving.append((row, ""))
            else:
                refusals.append(f"{row.id}: {problem}")
        if not surviving:
            # A LEGAL TRIGGER WHOSE PRECONDITIONS ARE FALSE. No event — not even a security one.
            raise GuardNotSatisfied(
                f"{trigger.value} is legal for {item.state.value} but no guard is satisfied. "
                + " · ".join(refusals)
            )
        if len(surviving) > 1:
            surviving.sort(key=lambda pair: PRECEDENCE.index(pair[0].id))
        row = surviving[0][0]
        return self._commit_transition_locked(
            row, item, trigger, actor_type=actor_type, actor_id=actor_id,
            correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,
            event_id=event_id, facts=facts,
        )

    # --- consumed triggers ----------------------------------------------------------------------

    def reference_resolver(self, aggregate_type: str, aggregate_id: str) -> bool:
        """Does this aggregate exist yet, FOR THIS TENANT? M-26's question, answered tenant-scoped.

        Only `work_item` is answerable here — this machine owns one aggregate and knows nothing
        about the others. An unknown aggregate TYPE resolves **False** rather than True: "we cannot
        confirm this exists" must park. Answering True would let an event referencing a machine
        nobody has built yet be applied as though its referent were fine, which is the optimistic
        direction and the wrong one.
        """
        if aggregate_type != AGGREGATE_TYPE:
            return False
        return self._conn.execute(
            "SELECT 1 FROM work_items WHERE tenant = ? AND work_item_id = ?",
            (self._tenant, aggregate_id),
        ).fetchone() is not None

    def consume(
        self,
        envelope: EventEnvelope,
        *,
        work_item_id: str,
        trigger: Trigger,
        inbox: DedupInbox | None = None,
        accountable_owner_id: str | None = None,
        **facts: Any,
    ) -> ConsumedTransition:
        """Drive ONE transition from a canonical event, idempotently, through P5's dedup inbox.

        ### AN EVENT FOR A WORK ITEM THAT DOES NOT EXIST YET IS **PARKED**, NOT LOOPED.
        This was a live defect in the first version of this method and it is worth naming: with no
        reference resolver the inbox had nothing to check, the handler raised `UnknownWorkItem`, the
        inbox rolled back its own row along with the failure, and the transport redelivered the same
        event forever. M-26 already has the answer — park it with its arrival order, its accountable
        human and a TTL, drain it when the referent appears, and make it a loud OWNED problem on
        expiry rather than a log line. So the resolver and the `requires` pair are supplied here
        rather than left to whichever caller remembered.

        ### AND THAT CLAIM WAS ONLY TRUE OF THE TRIGGERS SOMEBODY HAPPENED TO TEST. It was asserted
        with one `PipelineStarted`, whose event rides on `pipeline_instance` — so the Work Item was
        a reference to somebody ELSE's aggregate and parked correctly. `HumanDecided` rides on
        `work_item:<id>` itself, and the inbox skips a required reference equal to the incoming
        event's own aggregate, because a creation event must not be made to wait for itself. The
        pair was therefore DROPPED, silently, and the whole defect above came back for exactly the
        triggers carried on the Work Item: raise, roll back, redeliver, forever, with inbox=0
        parks=0 outbox=0 security=0 on every pass. The population is derived from §14 now instead
        of sampled — see `work_item_must_exist` — and the demand is stated through
        `requires_existing`, which the inbox resolves WITHOUT that skip.

        ### THE TWO SELF-CARRIED SHAPES ARE OPPOSITES, WHICH IS WHY ONE FLAG CANNOT SERVE BOTH.
        `HumanDecided` decides a Work Item that must already exist ⇒ prerequisite ⇒ park it.
        `WorkItemCreated` IS the Work Item arriving ⇒ product ⇒ it must never wait for itself, and
        it is not a transition this machine consumes at all (§33; `legal_transitions` excludes
        every `creates` row; WI-1 is originated through `create()`). Delivered here it is refused
        as an outcome — `refusal_kind == "NOT_CONSUMABLE"` — consumed exactly once, persisting
        nothing and emitting nothing.

        ### THE IDEMPOTENCY IS NOT REIMPLEMENTED HERE. GR-4's mechanism is
        `(tenant, consumer_id, event_id)` in `event_inbox`, and `DedupInbox.consume` already owns
        the one commit that carries both the handler's writes and the inbox row (M-24). So a
        redelivered `PipelineClosed` is a no-op because the inbox says so, not because this machine
        remembered — and the state digest is byte-identical across the redelivery, which is what
        makes "no-op" a measurement.

        ### A REFUSAL IS A CONSUMPTION, NOT A DELIVERY FAILURE, AND THIS IS THE LOAD-BEARING PART.
        If the handler raised on a refusal, the inbox would roll back its own row along with
        everything else and the transport would redeliver the same event forever — an unsatisfiable
        guard would become an infinite loop, and the loop would emit a duplicate security record on
        every pass. Both refusals are therefore *outcomes*:

            guard unsatisfied  ⇒ no state change, NO event. This is the ORDINARY case, not an error:
                                 acceptance (d) says a finishing Pipeline does not close the item,
                                 so a `PipelineClosed` for an unmet obligation is supposed to change
                                 nothing and is supposed to be consumed exactly once.
            illegal trigger    ⇒ no state change, and `IllegalTransitionAttempted` recorded INSIDE
                                 the inbox commit — here the record and the consumption genuinely
                                 are one act, so they are one commit.

        Both come back on the returned `ConsumedTransition` rather than as an exception, so the
        caller can see what happened without the transport being asked to retry a decision.

        ### AND NEITHER REFUSAL MAY POISON THE INBOX — WHICH IS A STRONGER CLAIM THAN "IS AN
        OUTCOME", AND THE FIRST VERSION OF THIS METHOD ONLY MADE THE WEAKER ONE. Recording the
        illegal attempt could itself fail: every hostile attempt against one Work Item at one
        unchanged version claimed §4's transition-natural identity, so the SECOND distinct hostile
        event hit the outbox's UNIQUE constraint, `DuplicateEmission` escaped the handler, the inbox
        rolled its own receipt back with it, and the transport redelivered the same event forever —
        recording nothing on every pass. The refusal was an outcome; the RECORDING of it was not.
        Both are now: see `_record_illegal_locked`.

        ### AN EVENT THAT WOULD PARK MUST NAME THE HUMAN IT PARKS ON. `accountable_owner_id` is
        resolved from authoritative state before anything is written, and a consumption that cannot
        establish an accountable human for a Work Item that does not exist yet is REFUSED rather
        than parked ownerless. See `_accountable_owner_for`.
        """
        box = inbox or DedupInbox(
            self._conn, tenant=self._tenant, consumer_id=CONSUMER_ID, clock=self._clock,
            reference_resolver=self.reference_resolver,
        )
        # ### THE OWNER IS THE HUMAN A PARK LANDS ON, SO IT IS ESTABLISHED ONLY WHERE A PARK CAN.
        # `_accountable_owner_for` REFUSES rather than invent one (F-02), and that refusal is a
        # raise. Demanded of a trigger that can never park, it would be a gate on nothing that
        # nonetheless left no receipt — the transport would redeliver into the same refusal
        # forever, which is the very loop this method was corrected to stop. WI-1 creates the
        # Work Item, so it names no `requires_existing` and cannot park; there is no obligation
        # to own yet, because there is not yet anything to be obliged about.
        owner = (
            self._accountable_owner_for(box, envelope, work_item_id, accountable_owner_id)
            if work_item_must_exist(trigger) else accountable_owner_id
        )
        parsed = _Facts(**_split_facts(facts))
        outcome: dict[str, Any] = {"transition": None, "refusal": None, "refusal_kind": None,
                                   "illegal_record": None}

        def handler(event: EventEnvelope) -> None:
            item = self.get(work_item_id)
            if item is None:
                # ### ONLY A CREATION TRIGGER REACHES THIS, BECAUSE EVERY OTHER ONE PARKED.
                # A trigger the Work Item is a prerequisite of named it in `requires_existing` and
                # the inbox held the event under M-26 before the handler was reachable. So a
                # missing item here means WI-1: the event whose whole job is to bring the item
                # into existence, arriving at the CONSUMING path. §33's "Events consumed" does not
                # list `WorkItemCreated`, `legal_transitions` excludes every `creates` row, and
                # `create()` is where WI-1 is ORIGINATED — so there is no transition to attempt.
                #
                # It is refused as an outcome, not raised: raising is what rolled the receipt back
                # and looped the event forever. And it is not recorded as an illegal ATTEMPT,
                # because `IllegalTransitionAttempted` must name the Work Item's state and version
                # (GR-1, [C-4]) and there is no Work Item to name — inventing one would be a
                # fabricated security record, which is worse than none.
                outcome["refusal"], outcome["refusal_kind"] = (
                    f"{trigger.value} does not transition a Work Item — WI-1 CREATES one, and a "
                    f"creation is originated through create(), never consumed. There is no "
                    f"{work_item_id!r} to move and this event does not make one. Consumed once, "
                    f"nothing persisted, nothing emitted.",
                    "NOT_CONSUMABLE",
                )
                return
            try:
                outcome["transition"] = self._apply_locked(
                    item, trigger, actor_type=event.actor_type, actor_id=event.actor_id,
                    correlation_id=event.correlation_id, causation_id=event.event_id,
                    trace_id=event.trace_id, event_id=None, facts=parsed,
                )
            except IllegalTransition as exc:
                # ### THE ATTEMPT IDENTITY IS THE HOSTILE EVENT'S OWN `event_id`, NOT A NEW ONE.
                # That is what makes the two halves of the invariant true at once: redelivering ONE
                # hostile event records ONE refusal (and the inbox stops it before the handler
                # anyway), while a SECOND, DIFFERENT hostile event against the same Work Item at the
                # same unchanged version is a different attempt and gets its own evidence.
                record = self._record_illegal_locked(
                    item, trigger, actor_type=event.actor_type, actor_id=event.actor_id,
                    correlation_id=event.correlation_id, causation_id=event.event_id,
                    trace_id=event.trace_id, attempt_id=event.event_id,
                )
                outcome["refusal"], outcome["refusal_kind"] = str(exc), "ILLEGAL"
                outcome["illegal_record"] = record
            except GuardNotSatisfied as exc:
                outcome["refusal"], outcome["refusal_kind"] = str(exc), "GUARD"

        result = box.consume(
            envelope, handler,
            # ### STATED AS AN EXPLICIT PREREQUISITE, WHICH IS WHY IT NOW SURVIVES THE INBOX.
            # Through `requires` this pair was DROPPED for every trigger carried on the Work Item
            # itself — `HumanDecided` above all — because the inbox skips a required reference
            # equal to the incoming event's own aggregate. The handler then raised `UnknownWorkItem`
            # inside the inbox's one transaction, the receipt rolled back with it, and the event
            # redelivered forever: no receipt, no park, no owner, no security record, no outcome.
            # `requires_existing` is the affordance that says "must already exist" for exactly that
            # shape, and the empty tuple for WI-1 is the same sentence read the other way — a
            # creation does not wait for what it creates.
            requires=((AGGREGATE_TYPE, work_item_id),),
            requires_existing=(
                ((AGGREGATE_TYPE, work_item_id),) if work_item_must_exist(trigger) else ()
            ),
            accountable_owner_id=owner,
        )
        return ConsumedTransition(
            consume=result, transition=outcome["transition"], refusal=outcome["refusal"],
            refusal_kind=outcome["refusal_kind"], illegal_record=outcome["illegal_record"],
        )

    def _accountable_owner_for(
        self,
        box: DedupInbox,
        envelope: EventEnvelope,
        work_item_id: str,
        accountable_owner_id: str | None,
    ) -> str | None:
        """The human this consumption would park work on — resolved, or the call refuses.

        ### AN OWNERLESS PARK IS AN OBLIGATION NOBODY OWES, AND IT WAS REACHABLE FROM THIS METHOD.
        `consume` for a Work Item that does not exist yet parks the event under M-26, and the park
        row carries the accountable human who will be handed the problem when its TTL expires. With
        no `accountable_owner_id` supplied and none on the envelope, that column was written NULL:
        rule 13's one exception, created by the very method whose docstring promises the park
        surfaces *"with the human accountable for it"*. An expiry with no name is the silent drop
        M-26 exists to forbid.

        So the owner is ESTABLISHED before anything is written, from authoritative state wherever
        authoritative state has the answer:

            1. the caller's explicit `accountable_owner_id` — checked against the recorded roster,
               never taken as a string;
            2. the Work Item's own `owner_id`, when the item exists — the authoritative answer, and
               the case in which no park can occur at all;
            3. the park this event is ALREADY held in — its owner was established when it was
               parked, and a redelivery only bumps the attempt counter;
            4. the envelope's `accountable_owner_id` — again checked against the roster.

        ### AND IF NONE OF THE FOUR ANSWERS, THE CALL REFUSES AND WRITES NOTHING. There is no fifth
        branch: no `system`, no `Neyma`, no ops-team queue, no `unassigned`, no detector and no
        model. Every one of those is an owner nobody agreed to be, and inventing one would make
        rule 13 true of a roster this machine wrote for itself.
        """
        if str(accountable_owner_id or "").strip():
            return self._require_active_human(
                accountable_owner_id, what="the accountable owner of a consumed trigger").human_id
        item = self.get(work_item_id)
        if item is not None:
            return item.owner_id
        held = next((p for p in box.parked() if p.event_id == envelope.event_id), None)
        if held is not None:
            return held.accountable_owner_id
        if str(envelope.accountable_owner_id or "").strip():
            return self._require_active_human(
                envelope.accountable_owner_id,
                what=f"the accountable owner carried by {envelope.event_name}").human_id
        raise OwnershipRefused(
            f"{envelope.event_name} references Work Item {work_item_id!r}, which does not exist "
            f"for tenant {self._tenant!r}, and names no accountable human — not on the call, not "
            f"on the envelope. Consuming it would park an obligation under M-26 with NO accountable "
            f"owner, and every open obligation has exactly one (CLAUDE.md rule 13). Refused with "
            f"nothing written: supply `accountable_owner_id`, or create the Work Item first. A "
            f"placeholder owner is not the alternative — 'system', 'ops', 'unassigned' and their "
            f"neighbours are owners nobody agreed to be."
        )

    # --- the write ------------------------------------------------------------------------------

    def _commit_transition_locked(
        self,
        row: TransitionRow,
        item: WorkItem,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        facts: _Facts,
    ) -> TransitionResult:
        assert row.to_state is not None and row.event_name is not None
        now = format_instant(self._clock())
        new_version = item.version + 1
        owner_after = self._owner_after(row, item, facts)
        payload = self._payload(row, item, facts)

        sets = ["state = ?", "version = ?", "updated_at = ?"]
        params: list[Any] = [row.to_state.value, new_version, now]
        if owner_after != item.owner_id:
            # `owner_id` is named in the SET list ONLY when ownership actually moves. The
            # `UPDATE OF owner_id` triggers fire on a column being NAMED, not on its value changing,
            # so naming it every time would make every ordinary transition re-assert the owner is
            # active — and would block a cancellation of work whose owner had been retired, which is
            # a state the offboarding refusal already prevents and cancellation must survive anyway.
            sets.append("owner_id = ?")
            params.append(owner_after)
        if row.to_state.value in TERMINAL_WORK_ITEM_STATES:
            sets.extend(["closure_decision_ref = ?", "closure_decision_ref_kind = ?"])
            params.extend([facts.decision_ref, facts.decision_ref_kind])
        if row.id == "WI-13":
            sets.extend(["phase_seq = ?", "prior_closure_ref = ?",
                         "closure_decision_ref = NULL", "closure_decision_ref_kind = NULL"])
            params.extend([item.phase_seq + 1, item.closure_decision_ref])
        if row.id == "WI-10":
            sets.append("escalation_at = ?")
            params.append(now)
        if row.to_state is WorkItemState.BLOCKED:
            sets.append("blocker_ref = ?")
            params.append(facts.reason)
        if row.id == "WI-8":
            sets.append("blocker_ref = NULL")

        # ### THE OCC WRITE. `WHERE version = :expected` is GR-3, and zero rows is a lost update
        # rather than a no-op. The `state = ?` predicate is carried too, so a concurrent transition
        # that moved the state without moving the version — which the version trigger already makes
        # impossible — could not slip past either. A revalidating WHERE clause never loses a
        # predicate (the P3 claim-CAS rule, kept).
        cursor = self._conn.execute(
            f"UPDATE work_items SET {', '.join(sets)} "
            f" WHERE tenant = ? AND work_item_id = ? AND version = ? AND state = ?",
            (*params, self._tenant, item.work_item_id, item.version, item.state.value),
        )
        if cursor.rowcount != 1:
            raise VersionConflict(
                f"{item.work_item_id!r} moved under this transition: the UPDATE matched "
                f"{cursor.rowcount} rows at version {item.version}/state {item.state.value}. "
                f"Reload and retry (GR-3)."
            )
        envelope = self._envelope(
            event_name=row.event_name, transition_id=row.id, work_item_id=item.work_item_id,
            aggregate_version=new_version, owner_id=owner_after, actor_type=actor_type,
            actor_id=actor_id, payload=payload, correlation_id=correlation_id or item.work_item_id,
            causation_id=causation_id, trace_id=trace_id, event_id=event_id, now=now,
        )
        TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock).emit(envelope)
        updated = self._conn.execute(
            "SELECT * FROM work_items WHERE tenant = ? AND work_item_id = ?",
            (self._tenant, item.work_item_id),
        ).fetchone()
        return TransitionResult(
            transition_id=row.id, work_item=_row_to_work_item(updated), event_id=envelope.event_id,
            event_name=row.event_name, from_state=item.state, to_state=row.to_state,
            owner_before=item.owner_id, owner_after=owner_after,
        )

    # --- GR-1 -------------------------------------------------------------------------------------

    def illegal_attempt_identity(self, item: WorkItem, attempt_id: str) -> str:
        """The idempotency identity of ONE refused attempt. §4's shape, plus the attempt.

        Exposed rather than private because it is the thing a test — and a reviewer — has to be able
        to compute independently to check that two distinct attempts really do claim two identities
        and that one attempt redelivered claims one.
        """
        text = _require_attempt_id(attempt_id)
        return "|".join((
            ILLEGAL_ATTEMPT_IDENTITY_PREFIX, self._tenant, AGGREGATE_TYPE, item.work_item_id,
            str(item.version), ILLEGAL_TRANSITION_PRODUCER, "IllegalTransitionAttempted", text,
        ))

    def _recorded_illegal_attempt(self, identity: str) -> str | None:
        """The `event_id` this attempt was already recorded under, or None. Never a guess."""
        row = self._conn.execute(
            "SELECT event_id FROM event_outbox WHERE tenant = ? AND idempotency_identity = ?",
            (self._tenant, identity),
        ).fetchone()
        return None if row is None else row["event_id"]

    def _record_illegal_locked(
        self,
        item: WorkItem,
        trigger: Trigger,
        *,
        actor_type: str,
        actor_id: str,
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        attempt_id: str,
        event_id: str | None = None,
    ) -> IllegalAttemptRecord:
        """`IllegalTransitionAttempted` — into the audit backbone AND `security_events`, ONE commit.

        ### BOTH, ATOMICALLY, BECAUSE [C-4] SAYS BOTH. Writing them in two commits would leave a
        window where the audit knows about an attempt the security surface does not, and the
        security surface is the one somebody is paged from.

        The state row is untouched: `persists nothing` is literal. The caller rolls nothing back
        because there is nothing to roll back — and then raises.

        ### THIS PATH MAY NOT POISON A TRANSPORT, AND THAT IS A SEPARATE PROPERTY FROM RECORDING.
        On a consumed trigger this runs INSIDE the inbox's one transaction (M-24), so anything it
        raises rolls back the inbox receipt too and the event is redelivered — forever. A
        `DuplicateEmission` escaping here was therefore not a loud failure but an infinite loop, and
        the refusal it was reporting was a refusal the API contract already covers.
        So the already-recorded case is DECIDED, not discovered by exception: the identity is looked
        up under the write lock this method is always called with, and a second attempt at recording
        ONE attempt writes nothing and says so on the returned record.
        ### THE EXCEPTION PATH IS STILL HANDLED, AND IT DOES NOT LIE. If the emit fails anyway, the
        identity is re-read; a row means the attempt genuinely is recorded, and NO row means the
        evidence could not be written — which is raised as a `WorkItemError`, never swallowed and
        never reported as a successful recording. Fail-closed stays fail-closed; what changes is
        that it fails as this machine's refusal rather than as the transport's.

        ### THE TWO SURFACES CANNOT DIVERGE, WHICH IS WHY THE SKIP SKIPS BOTH. The outbox row and
        the `security_events` row are written in one transaction and only ever together, so an
        identity already present in the outbox has its security row already present too. Re-writing
        the security half on a repeat would be recording one attempt twice on the surface an
        operator counts.
        """
        now = format_instant(self._clock())
        identity = self.illegal_attempt_identity(item, attempt_id)
        already = self._recorded_illegal_attempt(identity)
        if already is not None:
            return IllegalAttemptRecord(
                event_id=already, idempotency_identity=identity, already_recorded=True)
        envelope = self._envelope(
            event_name="IllegalTransitionAttempted", transition_id=ILLEGAL_TRANSITION_PRODUCER,
            work_item_id=item.work_item_id, aggregate_version=item.version,
            owner_id=item.owner_id, actor_type=actor_type, actor_id=actor_id,
            payload={"machine": "M1", "state": item.state.value, "trigger": trigger.value,
                     "attempted_by": actor_id},
            correlation_id=correlation_id or item.work_item_id, causation_id=causation_id,
            trace_id=trace_id, event_id=event_id, now=now,
            idempotency_identity=identity,
        )
        try:
            TransactionalOutbox(self._conn, tenant=self._tenant, clock=self._clock).emit(envelope)
        except DuplicateEmission as exc:
            repeat = self._recorded_illegal_attempt(identity)
            if repeat is None:
                raise WorkItemError(
                    f"the refusal of {trigger.value} on {item.work_item_id!r} could not be "
                    f"recorded: {exc}. The attempt identity {identity!r} is NOT in the outbox, so "
                    f"this is a genuine failure to write the evidence and not the same attempt "
                    f"arriving twice. Reported as a refusal of this machine — an operator must not "
                    f"be told the attempt was recorded when it was not."
                ) from exc
            return IllegalAttemptRecord(
                event_id=repeat, idempotency_identity=identity, already_recorded=True)
        next_id = int(self._conn.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM security_events WHERE tenant = ?",
            (self._tenant,),
        ).fetchone()[0])
        self._conn.execute(
            "INSERT INTO security_events (tenant, id, event_type, actor, payload_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (self._tenant, next_id, "IllegalTransitionAttempted", actor_id,
             json.dumps({"machine": "M1", "work_item_id": item.work_item_id,
                         "state": item.state.value, "trigger": trigger.value,
                         "event_id": envelope.event_id, "attempted_by": actor_id,
                         "attempt_id": _require_attempt_id(attempt_id)},
                        sort_keys=True),
             now),
        )
        return IllegalAttemptRecord(
            event_id=envelope.event_id, idempotency_identity=identity, already_recorded=False)

    # --- guards -----------------------------------------------------------------------------------

    def _guard_problem(
        self,
        row: TransitionRow,
        item: WorkItem,
        trigger: Trigger,
        facts: _Facts,
        actor_type: str,
        actor_id: str,
    ) -> str | None:
        """The EXACT guards of §14, one branch per row. `None` means satisfied.

        Returned as a reason rather than raised, because several rows may match one (state, trigger)
        and the caller needs to know why each one refused — "no guard is satisfied" with no reasons
        is a refusal nobody can act on.
        """
        # Trigger-type authority, before any row-specific guard. An `H` transition is an
        # authenticated human action (registry §1), and this machine will not take a human's word
        # from a system actor: WI-9, WI-11, WI-12 and WI-13 are the four places a human changes what
        # the business owes, and each is checked against the RECORDED roster, not against a string.
        if "H" in row.trigger_types and len(row.trigger_types) == 1:
            if actor_type != "human":
                return (
                    f"{row.id} is an H transition (authenticated human action) and the actor is "
                    f"actor_type={actor_type!r}. Automation may narrow authority and never broaden "
                    f"it (§7)."
                )
            try:
                self._require_active_human(actor_id, what=f"the actor of {row.id}")
            except OwnershipRefused as exc:
                return str(exc)

        if row.id == "WI-3":
            if facts.obligation_satisfied is not True:
                return (
                    "WI-3 requires `obligation_satisfied` to be stated TRUE. A finishing Pipeline "
                    "Instance does not close the item (acceptance (d)): billed is not paid, and a "
                    "Work Item is 1:N to its Pipelines. This machine will not infer it."
                )
            return self._decision_problem(facts, what="closure (I11, GR-14)")
        if row.id == "WI-4":
            if facts.disposition is not FailureDisposition.TRANSIENT:
                return "WI-4 requires a TRANSIENT failure disposition"
            if (facts.retries_remain or 0) <= 0:
                return "WI-4 requires retries to remain; exhausted retries are WI-5"
            return None
        if row.id == "WI-5":
            if facts.disposition is FailureDisposition.PERMANENT:
                return None
            if facts.disposition is FailureDisposition.TRANSIENT and (facts.retries_remain or 0) <= 0:
                return None
            if facts.disposition is None:
                return "WI-5 requires a failure disposition to be stated"
            return "WI-5 requires a PERMANENT failure, or a transient one with retries exhausted"
        if row.id == "WI-6":
            if not (facts.reason or "").strip():
                return (
                    "WI-6 blocks on a MATERIAL field (GR-10) and requires the reason to be named. "
                    "A block with no stated reason is an item a human cannot unblock."
                )
            return None
        if row.id == "WI-8":
            if facts.evidence_condition != "consistent":
                return (
                    f"WI-8 requires the evidence to have become `consistent`; it is "
                    f"{facts.evidence_condition!r}. GR-10: a conflicting material field blocks "
                    f"every consequential transition on the affected entity, and fails closed."
                )
            if facts.open_conflict is not False:
                return (
                    "WI-8 requires `open_conflict=False` to be stated. An open Conflict blocks the "
                    "unblock (GR-10), and 'we did not check' is not 'there is none'."
                )
            return None
        if row.id == "WI-9":
            return self._decision_problem(facts, what="WI-9 (HumanDecided)")
        if row.id == "WI-10":
            return self._timer_problem(item, facts)
        if row.id == "WI-11":
            if not (facts.to_owner or "").strip():
                return "WI-11 requires `to_owner`: a reassignment with no new owner drops the owner"
            if facts.to_owner == item.owner_id:
                return (
                    f"WI-11 would reassign {item.work_item_id!r} to its current owner "
                    f"{item.owner_id!r}. An OwnershipTransferred that moved nothing is a fact that "
                    f"did not happen."
                )
            try:
                self._require_active_human(facts.to_owner, what="the new owner (WI-11)")
            except OwnershipRefused as exc:
                return str(exc)
            return None
        if row.id == "WI-12":
            return self._decision_problem(facts, what="cancellation (§25, I11)")
        if row.id == "WI-13":
            problem = self._decision_problem(facts, what="reopening (WI-13, spec §12.14)")
            if problem is not None:
                return problem
            if not item.closure_decision_ref:
                return (
                    "WI-13 reopens a CLOSED item and found no prior closure reference on the row. "
                    "The prior closure event is immutable and must remain readable (GR-12)."
                )
            if not (facts.assignee or "").strip():
                return (
                    "WI-13 requires an `assignee`: §14 says the owner after a reopen is the "
                    "reopening actor's assignee. A reopened obligation with no named owner is an "
                    "ownerless obligation with a decision attached."
                )
            try:
                self._require_active_human(facts.assignee, what="the reopen assignee (WI-13)")
            except OwnershipRefused as exc:
                return str(exc)
            return None
        # WI-2, and WI-7: no precondition beyond "current state matches" (registry §2 default).
        return None

    def _decision_problem(self, facts: _Facts, *, what: str) -> str | None:
        if not (facts.decision_ref or "").strip() or not facts.decision_ref_kind:
            return (
                f"{what} requires a `decision_ref` AND its kind (K-1). Inactivity is not closure "
                f"(I11), and a reference with no namespace is a reference that resolves differently "
                f"tomorrow."
            )
        try:
            resolve_decision_ref(
                self._conn, tenant=self._tenant, ref=facts.decision_ref,
                kind=facts.decision_ref_kind,
            )
        except DecisionRefUnresolvable as exc:
            return str(exc)
        return None

    def _timer_problem(self, item: WorkItem, facts: _Facts) -> str | None:
        """WI-10's "durable timer, not a sweep", as a resolvable fact rather than a promise.

        The guard reads an actual `durable_timers` row (P5's M-36 table) for THIS tenant and THIS
        work item, in state `FIRED`, of the age-threshold kind. A polling sweep cannot produce that
        row, so the specification's parenthesis stops being decorative.
        """
        if not (facts.timer_id or "").strip():
            return (
                "WI-10 requires the `timer_id` of the durable timer that fired. §14 says "
                "'(durable timer, not a sweep)', and a caller that merely asserts an age has run a "
                "sweep."
            )
        row = self._conn.execute(
            "SELECT aggregate_type, aggregate_id, state, timer_kind FROM durable_timers "
            " WHERE tenant = ? AND timer_id = ?",
            (self._tenant, facts.timer_id),
        ).fetchone()
        if row is None:
            return (
                f"timer {facts.timer_id!r} resolves to no durable timer for tenant "
                f"{self._tenant!r}. WI-10 escalates on a timer that exists, not on a claim that one "
                f"did."
            )
        if row["state"] != "FIRED":
            return (
                f"timer {facts.timer_id!r} is {row['state']!r}, not FIRED. An escalation on a "
                f"SCHEDULED timer is an escalation before the deadline."
            )
        if row["aggregate_type"] != AGGREGATE_TYPE or row["aggregate_id"] != item.work_item_id:
            return (
                f"timer {facts.timer_id!r} belongs to "
                f"{row['aggregate_type']}:{row['aggregate_id']}, not to this Work Item. One item "
                f"aging does not escalate another."
            )
        if row["timer_kind"] != AGE_THRESHOLD_TIMER_KIND:
            return (
                f"timer {facts.timer_id!r} is a {row['timer_kind']!r} timer, not "
                f"{AGE_THRESHOLD_TIMER_KIND!r}. WI-10 is the AGE threshold, and borrowing another "
                f"deadline would escalate for a reason nobody chose."
            )
        return None

    # --- helpers ----------------------------------------------------------------------------------

    def _require_actor(self, actor_type: str) -> None:
        if actor_type not in PERMITTED_ACTOR_TYPES:
            raise AuthorityRefused(
                f"actor_type={actor_type!r} may not drive machine M1. Permitted: "
                f"{sorted(PERMITTED_ACTOR_TYPES)}. ### `model` is absent deliberately — C-6 and "
                f"GR-7 give a model exactly one output, a ProposedIntent, which is inert data. A "
                f"model may propose that work is needed; it may never own, advance, close or cancel "
                f"an obligation."
            )

    def _require_active_human(self, human_id: str | None, *, what: str) -> HumanAuthority:
        text = str(human_id or "").strip()
        if not text:
            raise OwnershipRefused(
                f"{what} is blank. I1/M-35: never null, never 'the system', never a placeholder."
            )
        found = human_authority(self._conn, tenant=self._tenant, human_id=text)
        if found is None:
            raise OwnershipRefused(
                f"{what}: {text!r} is not a recorded human of tenant {self._tenant!r}. Ownership "
                f"comes from a recorded, attributed authority (tenant_humans) — never from a name "
                f"that appeared in a message, an event actor, or a caller argument."
            )
        if not found.is_active:
            raise OwnershipRefused(
                f"{what}: {text!r} is {found.state} in tenant {self._tenant!r} (since "
                f"{found.offboarded_at}). Work owned by somebody who has left does not silently "
                f"continue (`entities/01-work-item.md` point 36)."
            )
        return found

    def _owner_after(self, row: TransitionRow, item: WorkItem, facts: _Facts) -> str:
        if row.owner_after is OwnerAfter.UNCHANGED:
            return item.owner_id
        if row.owner_after is OwnerAfter.NEW_OWNER:
            assert facts.to_owner
            return facts.to_owner
        if row.owner_after is OwnerAfter.REOPENING_ASSIGNEE:
            assert facts.assignee
            return facts.assignee
        raise WorkItemError(f"{row.id} has owner_after={row.owner_after} outside a transition")

    def _payload(self, row: TransitionRow, item: WorkItem, facts: _Facts) -> Mapping[str, Any]:
        """The event body §5 declares for this transition's contract.

        ### THE DERIVED FIELDS ARE READ FROM THE ROW, NOT FROM THE CALLER. `from_owner` on
        `OwnershipTransferred` and `prior_closure_ref` on `Reopened` are facts about the item as it
        stood a moment ago; taking them from the caller would let a reassignment claim it moved work
        away from somebody who never held it, and a reopen claim a closure that was not the one being
        reopened. Both are the shape of lie an audit cannot detect afterwards.
        """
        if row.id in ("WI-5", "WI-6"):
            return {"reason": facts.reason}
        if row.id == "WI-4":
            return {"reason": facts.reason or "transient pipeline failure"}
        if row.id == "WI-7":
            return _prune({"question": facts.question})
        if row.id == "WI-9":
            return {"decision_ref": facts.decision_ref}
        if row.id == "WI-11":
            return {"from_owner": item.owner_id, "to_owner": facts.to_owner}
        if row.id in ("WI-3", "WI-12"):
            return {"decision_ref": facts.decision_ref}
        if row.id == "WI-13":
            return {"prior_closure_ref": item.closure_decision_ref,
                    "decision_ref": facts.decision_ref,
                    "phase_seq": item.phase_seq + 1}
        return {}

    def _envelope(
        self,
        *,
        event_name: str,
        transition_id: str,
        work_item_id: str,
        aggregate_version: int,
        owner_id: str,
        actor_type: str,
        actor_id: str,
        payload: Mapping[str, Any],
        correlation_id: str | None,
        causation_id: str | None,
        trace_id: str | None,
        event_id: str | None,
        now: str,
        idempotency_identity: str | None = None,
    ) -> EventEnvelope:
        """One canonical envelope. ### `accountable_owner_id` IS ALWAYS SET, ON EVERY M1 EVENT.

        `idempotency_identity` is left unset for every transition event, which derives §4's
        transition-natural identity — the correct one, because a transition advances the version it
        is keyed on. It is supplied ONLY for `IllegalTransitionAttempted`, whose subject is an
        attempt that moved nothing; see `ILLEGAL_ATTEMPT_IDENTITY_PREFIX`.

        §1 marks it `C` (required-when-applicable), and on a Work Item it is always applicable —
        that is the entity's defining property. Setting it means the accountable owner travels WITH
        the fact, so `event_audit.explain(...)` reconstructs `accountable_owner` from the beliefs of
        that day rather than by asking who owns it now. An audit that answers "who was accountable"
        with today's roster is an audit that cannot be trusted about the past.
        """
        return EventEnvelope(
            event_id=event_id or str(uuid.uuid4()),
            event_name=event_name,
            event_version=CONTRACTS[event_name].current_version,
            occurred_at=now,
            recorded_at=now,
            tenant_id=self._tenant,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id=work_item_id,
            aggregate_version=aggregate_version,
            causation_id=causation_id,
            correlation_id=correlation_id or work_item_id,
            producer_component=self._component,
            producer_transition_id=transition_id,
            actor_type=actor_type,
            actor_id=actor_id,
            trace_id=trace_id or f"trace-{work_item_id}",
            payload=dict(payload),
            work_item_id=work_item_id,
            accountable_owner_id=owner_id,
            idempotency_identity=idempotency_identity,
        )


# ------------------------------------------------------------------------------------- plumbing

def _prune(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop absent optional fields.

    ### `null` AND ABSENT ARE DIFFERENT FACTS INSIDE A PAYLOAD (`ev_v1`), so this drops only the
    fields the caller never supplied. It is used exclusively for CONTRACT-OPTIONAL fields, where
    "not applicable" is the meaning; it is never used to quietly drop a required one.
    """
    return {k: v for k, v in payload.items() if v is not None}


def _require_attempt_id(attempt_id: str | None) -> str:
    """An attempt identity is a real identity or it is nothing. Never blank, never derived here.

    Refused rather than defaulted: a blank attempt id would silently collapse every hostile attempt
    at one Work Item version back onto one identity, which is precisely the defect the explicit
    identity exists to remove — and it would do it quietly, on the surface a security operator
    counts.
    """
    text = str(attempt_id or "").strip()
    if not text:
        raise WorkItemError(
            "an illegal-transition record requires the identity of the ATTEMPT it records. On a "
            "consumed trigger that is the incoming event's `event_id`; on the direct API it is the "
            "caller's `event_id` when one was supplied and a fresh identity for the call otherwise."
        )
    return text


_FACT_NAMES = frozenset(_Facts.__dataclass_fields__) - {"extra"}


def _split_facts(facts: Mapping[str, Any]) -> dict[str, Any]:
    known = {k: v for k, v in facts.items() if k in _FACT_NAMES}
    extra = {k: v for k, v in facts.items() if k not in _FACT_NAMES}
    if extra:
        known["extra"] = extra
    return known


def _row_to_work_item(row: Any) -> WorkItem:
    return WorkItem(
        tenant=row["tenant"], work_item_id=row["work_item_id"], type=row["type"],
        state=WorkItemState(row["state"]), version=int(row["version"]),
        owner_id=row["owner_id"], phase_seq=int(row["phase_seq"]),
        created_at=row["created_at"], updated_at=row["updated_at"],
        entity_ref=row["entity_ref"], reopens=row["reopens"],
        prior_closure_ref=row["prior_closure_ref"], escalation_at=row["escalation_at"],
        blocker_ref=row["blocker_ref"],
        exposure_amount_minor=(None if row["exposure_amount_minor"] is None
                               else int(row["exposure_amount_minor"])),
        exposure_currency=row["exposure_currency"],
        exposure_observation_ref=row["exposure_observation_ref"],
        closure_decision_ref=row["closure_decision_ref"],
        closure_decision_ref_kind=row["closure_decision_ref_kind"],
    )


# Re-exported so a caller reads one name rather than importing the migration for a constant.
STATES: tuple[str, ...] = WORK_ITEM_STATES
TERMINAL_STATES: tuple[str, ...] = TERMINAL_WORK_ITEM_STATES
ROLES: tuple[str, ...] = AUTHORITY_ROLES
AUTHORITY_STATES: tuple[str, ...] = HUMAN_STATES
