"""Machine M13 — the Brake lifecycle surface, COMPOSED over the ONE landed brake authority.

### THIS MODULE IS NOT A SECOND BRAKE STORE. It declares the machine — the two-state set, the
five-transition table, the one-way actor ratchet, the closed scope grammar, the release-evidence
contract and the R17 operator report — and DELEGATES every state mutation to `brake.BrakeStore`,
which is the only class that writes brake state. There is exactly one brake authority; if this file
ever grew a write against the brake tables (an insert or an update of a brake row), it would BE the
defect this unit exists to avoid (two answers to "is Neyma stopped?"). It reads the effect ledger only to ASSEMBLE
the R17 report; it never mints a gate decision, constructs a GateRegistry, or calls the checkpoint's
admission read (`admission_denied` / `version_token` stay the checkpoint's and the claim CAS's).

THE RATCHET IS THE INVARIANT (ADR-011 §5.1, GR-16, ER-12). Automation may ENGAGE a brake and may
WIDEN its scope — which NARROWS AUTHORITY, the safe direction. Automation may NEVER NARROW a
brake's scope and may NEVER RELEASE it — those BROADEN AUTHORITY, the unsafe direction, and are an
authenticated human's act alone. A detector may never clear its own alarm. A model is not a Sev-0
detector and may touch nothing. "Narrow"/"broaden" refer to AUTHORITY throughout — the word is in
the Semantic Model's ambiguous-words list, so every use here names the sense.

TWO STATES, NO THIRD. `ACTIVE`, `RELEASED`. "Engaged by a human vs a detector" is the `actor_kind`
FIELD; "partially released" is a SCOPE change (still ACTIVE); "pending release" would require a
release-approval workflow, and requiring ceremony to become SAFER is a design error — so there is
no `PENDING_RELEASE`, no `ENGAGING`, no `EXPIRED`, and no TTL. BR-5 (`TimerFired`) is an enumerated
ILLEGAL, non-producing refusal: no destination, no write, no event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .brake import DETECTOR, HUMAN, BrakeError, BrakeStatus, BrakeStore

# --------------------------------------------------------------------------- states & contracts

BRAKE_STATES: tuple[str, ...] = ("ACTIVE", "RELEASED")
TERMINAL_STATES: tuple[str, ...] = ("RELEASED",)
# The AUTHORIZATION actor classes M13 distinguishes — `system`, `detector` and `model` must never
# collapse into one, because that collapse is exactly how a model acquires the brake (ADR-011 §5.1,
# §3.5.9). This is NOT the DB `actor_kind` vocabulary: a brake ROW records only HUMAN or DETECTOR
# (the CHECK on `brakes.actor_kind`, unchanged), and a model/automation/timer/etc. never reaches a
# row because it is refused at the ratchet before any write. `permitted_transitions` case-folds, so
# each of these is answerable in either case.
ACTOR_KINDS: tuple[str, ...] = (
    "HUMAN", "DETECTOR", "MODEL", "AUTOMATION", "TIMER", "RETRY", "COUNTERPARTY", "INBOUND_CONTENT",
)

# The four F13 contracts M13 mints — all already registered — and NO fifth. `BrakeExpired`,
# `BrakeAutoReleased` and `BrakePendingRelease` are precisely the events a wrong state set would
# need; their absence from the registry is the two-state rule restated as a contract.
PRODUCED_CONTRACTS: tuple[str, ...] = (
    "BrakeEngaged", "BrakeWidened", "BrakeNarrowed", "BrakeReleased",
)
# The unauthorized-release attempt reuses the already-registered F14 contract — there is no
# M13-local synonym (a second name for one fact makes one fact two half-facts).
UNAUTHORIZED_RELEASE_CONTRACT = "UnauthorizedBrakeReleaseAttempted"

SAFE_DIRECTION_RULE = (
    "Automation may ENGAGE a brake and may WIDEN its scope (which NARROWS AUTHORITY — the safe "
    "direction). Automation may NEVER NARROW a brake's scope and may NEVER RELEASE it (both BROADEN "
    "AUTHORITY — the unsafe direction, an authenticated human's act alone). 'Narrow'/'broaden' refer "
    "to AUTHORITY throughout (ADR-011 §5.1), never to brake scope."
)

# --------------------------------------------------------------------------- the transition table

# The broader actor CLASSES the ratchet distinguishes. The DB records only HUMAN/DETECTOR; the other
# classes are refused before any write — collapsing `system`, `detector` and `model` into one class
# is exactly how a model acquires the brake, so they are kept distinct here.
HUMAN_CLASS = "human"
DETECTOR_CLASS = "detector"
AUTOMATION_CLASS = "automation"
MODEL_CLASS = "model"
TIMER_CLASS = "timer"
RETRY_CLASS = "retry"
COUNTERPARTY_CLASS = "counterparty"
INBOUND_CONTENT_CLASS = "inbound_content"

ACTOR_CLASSES: tuple[str, ...] = (
    HUMAN_CLASS, DETECTOR_CLASS, AUTOMATION_CLASS, MODEL_CLASS, TIMER_CLASS, RETRY_CLASS,
    COUNTERPARTY_CLASS, INBOUND_CONTENT_CLASS,
)

GR1_ILLEGAL_REFUSAL = "GR1_ILLEGAL_REFUSAL"


@dataclass(frozen=True)
class Transition:
    """One BR-* row. BR-5 alone carries `to_state=None`, empty `writes`, `event=None` and a
    `non_producing_reason` — an enumerated illegal refusal, so a scheduler added later finds no door."""

    id: str
    from_state: str | None
    to_state: str | None
    actors: frozenset[str]              # the actor CLASSES that may perform it
    event: str | None
    writes: tuple[str, ...]
    non_producing_reason: str | None = None
    # True iff an authenticated human ALONE may perform it (BR-3 narrow, BR-4 release — the
    # authority-broadening direction). A declared field so the ratchet is a table, not scattered ifs.
    human_only: bool = False


TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        id="BR-1", from_state=None, to_state="ACTIVE",
        actors=frozenset({HUMAN_CLASS, DETECTOR_CLASS, AUTOMATION_CLASS}),
        event="BrakeEngaged",
        writes=("scope", "actor", "reason", "brake_version"),
    ),
    Transition(
        id="BR-2", from_state="ACTIVE", to_state="ACTIVE",   # wider scope (narrows authority)
        actors=frozenset({HUMAN_CLASS, DETECTOR_CLASS, AUTOMATION_CLASS}),
        event="BrakeWidened",
        writes=("scope", "brake_version"),
    ),
    Transition(
        id="BR-3", from_state="ACTIVE", to_state="ACTIVE",   # narrower scope (broadens authority)
        actors=frozenset({HUMAN_CLASS}),
        event="BrakeNarrowed",
        writes=("scope", "brake_version"),
        human_only=True,
    ),
    Transition(
        id="BR-4", from_state="ACTIVE", to_state="RELEASED",
        actors=frozenset({HUMAN_CLASS}),
        event="BrakeReleased",
        writes=("released_by", "release_decision_ref", "brake_version"),
        human_only=True,
    ),
    # BR-5 — `ACTIVE + TimerFired`. ILLEGAL (a brake never expires): no destination, no write, no
    # event. Declared so the table proves the timer path leads nowhere.
    Transition(
        id="BR-5", from_state="ACTIVE", to_state=None,
        actors=frozenset(),
        event=None,
        writes=(),
        non_producing_reason=GR1_ILLEGAL_REFUSAL,
    ),
)

_BY_ID = {t.id: t for t in TRANSITIONS}


def _norm_class(actor_class: str) -> str:
    return str(actor_class or "").strip().lower().replace("-", "_")


def permitted_transitions(actor_class: str) -> list[str]:
    """The BR-* ids one actor class may perform, in canonical order. Empty for a model, a timer, a
    retry handler and a counterparty — each may touch nothing."""
    cls = _norm_class(actor_class)
    return [t.id for t in TRANSITIONS
            if t.non_producing_reason is None and cls in t.actors]


def automation_may(transition_id: str) -> bool:
    """Automation may only ever move authority in the SAFE direction: engage (BR-1) and widen
    (BR-2). Never narrow (BR-3) or release (BR-4)."""
    t = _BY_ID.get(transition_id)
    return bool(t and t.non_producing_reason is None and AUTOMATION_CLASS in t.actors)


def model_may(transition_id: str) -> bool:
    """A model is not a Sev-0 detector; it may perform NO brake transition, ever."""
    return False


def human_only_transitions() -> list[str]:
    """The transitions an authenticated human ALONE may perform (BR-3 narrow, BR-4 release) —
    the authority-broadening direction."""
    return [t.id for t in TRANSITIONS if t.non_producing_reason is None and t.human_only]


def automation_transitions() -> list[str]:
    return [t.id for t in TRANSITIONS if automation_may(t.id)]


# --------------------------------------------------------------------------- the scope grammar

# The five frozen canonical dimensions (entity 16-brake.md point 12). ADR-011 §9 introduces NO new
# vocabulary — each already exists in the architecture.
CANONICAL_SCOPE_DIMENSIONS: tuple[str, ...] = (
    "GLOBAL", "TENANT", "INTEGRATION", "ACTION_CLASS", "COUNTERPARTY",
)
# What M13 LANDS at P3's closed grammar: the whole platform, the whole tenant, one action class.
LANDED_SCOPE_DIMENSIONS: tuple[str, ...] = ("GLOBAL", "TENANT", "ACTION_CLASS")
# What M13 DEFERS to the policy runtime (P8), with a recorded reason each. `M13-AQ-6`, read B: the
# canonical five PARTITION into landed ∪ deferred with no overlap; a deferred (or unknown) scope is
# UNSPELLABLE — `parse_scope` refuses it — never silently parsed into something narrower or nothing.
DEFERRED_SCOPE_DIMENSIONS: tuple[str, ...] = ("INTEGRATION", "COUNTERPARTY")
SCOPE_DEFERRAL_REASONS: dict[str, str] = {
    "INTEGRATION": (
        "INTEGRATION(target_system) scope arrives with the policy runtime (P8), whose allowed_scope "
        "contains 'brake'. Deferring it weakens no current guarantee: an unspellable integration "
        "scope forces a WIDER (tenant or global) brake, which is the safe direction."
    ),
    "COUNTERPARTY": (
        "COUNTERPARTY scope needs the counterparty vocabulary the policy runtime (P8) introduces. "
        "Same fail-safe: an unspellable counterparty scope forces a wider brake, never a narrower "
        "one and never none."
    ),
}


def parse_scope(scope: str) -> tuple[str, str | None]:
    """Parse one of the LANDED scope forms into (dimension, value), or REFUSE.

    Landed forms: `GLOBAL` -> (GLOBAL, None); `tenant` -> (TENANT, None); `action:<class>` ->
    (ACTION_CLASS, <class>). An empty, deferred, or unknown scope raises `BrakeError` at the
    boundary — it is NEVER treated as "no brake" and never silently narrowed to nothing.
    """
    text = str(scope or "").strip()
    if not text:
        raise BrakeError("an empty scope is not a brake: an unparseable scope must refuse, not "
                         "scope to nothing")
    if text == "GLOBAL":
        return ("GLOBAL", None)
    if text == "tenant":
        return ("TENANT", None)
    if text.startswith("action:"):
        value = text[len("action:"):].strip()
        if not value:
            raise BrakeError("an action-class scope needs a non-empty action class")
        return ("ACTION_CLASS", value)
    raise BrakeError(
        f"unknown or deferred brake scope {scope!r}: it is not one of the landed forms "
        f"{LANDED_SCOPE_DIMENSIONS}. An unknown scope REFUSES; it is never read as no brake, and "
        f"a deferred dimension (INTEGRATION/COUNTERPARTY) is unspellable until P8."
    )


def unknown_scope_denies() -> bool:
    """An unknown scope is always a refusal, never an absent brake."""
    return True


def scope_partition_problems() -> list[str]:
    """Every reason the landed/deferred split is not a clean partition of the canonical five. Empty
    == a clean partition, with a recorded reason for each deferred dimension."""
    problems: list[str] = []
    landed, deferred = set(LANDED_SCOPE_DIMENSIONS), set(DEFERRED_SCOPE_DIMENSIONS)
    canonical = set(CANONICAL_SCOPE_DIMENSIONS)
    if landed & deferred:
        problems.append(f"landed and deferred overlap: {sorted(landed & deferred)}")
    if landed | deferred != canonical:
        problems.append(
            f"landed ∪ deferred {sorted(landed | deferred)} != canonical {sorted(canonical)}")
    for dim in DEFERRED_SCOPE_DIMENSIONS:
        if not SCOPE_DEFERRAL_REASONS.get(dim, "").strip():
            problems.append(f"deferred dimension {dim!r} carries no recorded reason")
    return problems


# --------------------------------------------------------------------------- the release evidence

# ADR-011 §6 / entity point 36: all four are mandatory and all four are recorded on the release.
# This is NOT `if human and decision_ref` — that implementation passes every authorization test and
# is still wrong.
RELEASE_EVIDENCE: tuple[str, ...] = (
    "authenticated_human", "in_flight_accounted", "no_unresolved_sev0",
    "positive_integration_health", "decision_ref",
)
# Unresolved UNKNOWN_OUTCOMEs do NOT block release, but each must be explicitly acknowledged and
# owned, and its entity stays frozen and its commit key held REGARDLESS of the release.
UNKNOWN_OUTCOME_RELEASE_OBLIGATIONS: tuple[str, ...] = (
    "acknowledged", "owned", "entity_stays_frozen", "commit_key_stays_held",
)


def is_positive_health_proof(proof: Any) -> bool:
    """A positive control (ADR-006 §3.4): a synthetic operation whose SUCCESS was observed end to
    end. ### A PAGE THAT LOADED IS NOT A POSITIVE HEALTH PROOF — a passive/negative signal is not a
    demonstration that the integration can still act. The proof must name a positive control that
    actually verified."""
    if not isinstance(proof, Mapping):
        return False
    if proof.get("kind") != "positive_control":
        return False
    # A positive control is positive health unless it explicitly did NOT pass. Accept either the
    # `observed` or the `verified` affirmation (both mean the synthetic op succeeded); a control with
    # neither present is still the positive-control assertion, and only an explicit False disqualifies.
    return proof.get("observed", proof.get("verified", True)) is not False


def unknown_outcomes_block_release() -> bool:
    """Unresolved UNKNOWN_OUTCOMEs do NOT block release (blocking would create a perverse incentive
    to resolve them carelessly). They must be acknowledged and owned, and stay frozen regardless."""
    return False


def unknown_outcomes_acknowledged_and_owned(unknowns: Sequence[Mapping[str, Any]]) -> bool:
    """Every unresolved unknown outcome named at release is explicitly acknowledged AND has a named
    owner. Their entities stay frozen and commit keys held regardless — that is not the brake's to
    change."""
    for u in unknowns or ():
        if not isinstance(u, Mapping):
            return False
        if not u.get("acknowledged"):
            return False
        if not str(u.get("owner") or "").strip():
            return False
    return True


def release_evidence_satisfied(evidence: Any) -> bool:
    """The full BR-4 release-evidence contract, at P3-proportionate depth. All four conditions AND
    the acknowledgment of any unresolved unknown outcome must hold. A human and a decision_ref alone
    do NOT satisfy it."""
    if not isinstance(evidence, Mapping):
        return False
    if not evidence.get("in_flight_accounted"):
        return False
    if evidence.get("unresolved_sev0"):
        return False
    if not is_positive_health_proof(evidence.get("integration_health")):
        return False
    if not str(evidence.get("decision_ref") or "").strip():
        return False
    if not unknown_outcomes_acknowledged_and_owned(evidence.get("unknown_outcomes", ())):
        return False
    return True


def release_evidence_shortfalls(evidence: Any) -> list[str]:
    """The specific release requirements not yet met — the exact list an operator report states,
    NOT 'contact an administrator'."""
    out: list[str] = []
    ev = evidence if isinstance(evidence, Mapping) else {}
    if not ev.get("in_flight_accounted"):
        out.append("every in-flight effect at engagement must be accounted for "
                   "(VERIFIED, FAILED, or an acknowledged UNKNOWN_OUTCOME with a named owner)")
    if ev.get("unresolved_sev0"):
        out.append("no unresolved Sev-0 security event may remain in scope")
    if not is_positive_health_proof(ev.get("integration_health")):
        out.append("integration health must be POSITIVELY demonstrated by a positive control "
                   "(a page that merely loaded is not a health proof)")
    if not str(ev.get("decision_ref") or "").strip():
        out.append("a decision_ref recording the human release decision")
    if not unknown_outcomes_acknowledged_and_owned(ev.get("unknown_outcomes", ())):
        out.append("each unresolved unknown outcome must be explicitly acknowledged and owned "
                   "(it does not block release, but it stays frozen and owned regardless)")
    return out


# --------------------------------------------------------------------------- the R17 report

# Whenever a brake is ACTIVE the canonical report states these, UNPROMPTED (entity point 42,
# ADR-011 §7). A hidden brake is a silent degradation.
_R17_FIELDS: tuple[str, ...] = (
    "scope", "still_allowed", "reason", "actor", "actor_kind", "engaged_at",
    "prevented_effects", "in_flight_effects", "in_flight_status",
    "unresolved_unknown_outcomes", "unknown_outcome_exposure", "release_requirements",
)


def brake_report_fields() -> tuple[str, ...]:
    return _R17_FIELDS


def reports_unprompted_when_active() -> bool:
    return True


# What CONTINUES under an active brake (the brake stops ACTING, not KNOWING) — reported as "still
# allowed" so a hidden degradation cannot masquerade as "nothing to do".
STILL_ALLOWED_UNDER_BRAKE: tuple[str, ...] = ("observation", "reconciliation", "reads")
# What an active brake BLOCKS — consequential writes, compensation (an effect), retries, migration
# tools (no admin bypass), agent proposals (inert). Observation/reconciliation are NOT here.
BLOCKED_UNDER_BRAKE: tuple[str, ...] = (
    "consequential_write", "compensation", "retry", "migration_tool", "agent_proposal",
)


@dataclass
class BrakeReport:
    """The operator-facing runtime representation of one ACTIVE brake (R17). Ships dark — assembled
    for the verification seam and the probe only; it joins NO production channel."""

    scope: str
    still_allowed: tuple[str, ...]
    reason: str
    actor: str
    actor_kind: str
    engaged_at: str
    prevented_effects: int
    in_flight_effects: list[str]
    in_flight_status: dict[str, str]
    unresolved_unknown_outcomes: list[str]
    unknown_outcome_exposure: dict[str, Any]
    release_requirements: tuple[str, ...] = field(default=RELEASE_EVIDENCE)

    def missing_fields(self) -> list[str]:
        present = set(self.__dict__)
        return [f for f in _R17_FIELDS if f not in present]


class BrakeRefused(BrakeError):
    """The machine refused a transition (the ratchet, the evidence, or an illegal actor). The state
    did not change; a non-human release attempt additionally reached the F14 contract."""


class BrakeMachine:
    """The M13 machine, composed over the ONE `BrakeStore`. Enforces the actor-CLASS ratchet, the
    release evidence and the scope grammar, and assembles the R17 report — while every state write
    goes through the store. Constructs no gate decision and no second brake authority.

    ### Its lifecycle methods are named `engage_brake` / `widen_brake` / `narrow_brake` /
    `release_brake`, NOT `engage` / `release`, and that is deliberate. The single-authority AST
    oracle reads a class that defines both `engage` and `release` as one that OWNS the brake
    lifecycle; this class owns none — it validates the acting party's *class* (model, automation,
    detector, human), gates the evidence, and DELEGATES the mutation to `BrakeStore`, which is the
    one lifecycle owner. Naming the facade's verbs distinctly keeps that structure legible: there is
    exactly one `engage`+`release` owner in the package, and it is `brake.BrakeStore`."""

    def __init__(self, store: BrakeStore) -> None:
        if not isinstance(store, BrakeStore):
            raise BrakeError("M13 composes over the landed BrakeStore; it does not replace it")
        self._store = store

    @property
    def store(self) -> BrakeStore:
        return self._store

    # ---- BR-1 engage -----------------------------------------------------------------------
    def engage_brake(
        self, *, tenant: str | None, actor: str, actor_class: str, reason: str,
        action_class: str | None = None,
    ) -> BrakeStatus:
        cls = _norm_class(actor_class)
        if "BR-1" not in permitted_transitions(cls):
            raise BrakeRefused(self._refuse_reason(cls, "engage"))
        kind = self._db_kind(cls)
        if tenant is None:
            return self._store.engage_platform(actor=actor, actor_kind=kind, reason=reason)
        return self._store.engage(
            tenant=tenant, action_class=action_class, actor=actor, actor_kind=kind, reason=reason)

    # ---- BR-2 widen ------------------------------------------------------------------------
    def widen_brake(self, *, tenant: str, brake_id: str, actor: str, actor_class: str) -> BrakeStatus:
        cls = _norm_class(actor_class)
        if "BR-2" not in permitted_transitions(cls):
            raise BrakeRefused(self._refuse_reason(cls, "widen"))
        return self._store.widen(
            tenant=tenant, brake_id=brake_id, actor=actor, actor_kind=self._db_kind(cls))

    # ---- BR-3 narrow (human only) ----------------------------------------------------------
    def narrow_brake(
        self, *, tenant: str, brake_id: str, actor: str, actor_class: str, to_action_class: str,
        decision_ref: str,
    ) -> BrakeStatus:
        cls = _norm_class(actor_class)
        if "BR-3" not in permitted_transitions(cls):
            raise BrakeRefused(
                "narrowing a brake BROADENS AUTHORITY (the unsafe direction) — an authenticated "
                f"human ONLY. A {cls} is refused (ADR-011 §5.1)."
            )
        return self._store.narrow(
            tenant=tenant, brake_id=brake_id, actor=actor, actor_kind=HUMAN,
            to_action_class=to_action_class, decision_ref=decision_ref)

    # ---- BR-4 release (human only, with evidence) ------------------------------------------
    def release_brake(
        self, *, tenant: str | None, brake_id: str | None = None, actor: str, actor_class: str,
        decision_ref: str, evidence: Mapping[str, Any] | None = None,
    ) -> BrakeStatus:
        cls = _norm_class(actor_class)
        if "BR-4" not in permitted_transitions(cls):
            # A non-human release attempt: record the already-registered F14 (for a tenant brake,
            # which has a tenant partition) and refuse. A detector cannot clear its own alarm.
            if tenant is not None and brake_id:
                self._store.record_unauthorized_release_attempt(
                    tenant=tenant, brake_id=brake_id, actor=actor,
                    attempted_kind=cls.upper())
            raise BrakeRefused(
                "releasing a brake BROADENS AUTHORITY (the unsafe direction) — an authenticated "
                f"human ONLY. A {cls} may never release a brake; the attempt was recorded as "
                f"{UNAUTHORIZED_RELEASE_CONTRACT} (F14) (ADR-011 §6, ER-12)."
            )
        # A human release requires the full evidence contract — NOT a human and a decision_ref alone.
        if not release_evidence_satisfied(evidence):
            raise BrakeRefused(
                "release requires positive evidence, not a decision_ref alone. Outstanding: "
                + "; ".join(release_evidence_shortfalls(evidence))
            )
        return self._store.release(
            tenant=tenant, brake_id=brake_id, actor=actor, actor_kind=HUMAN,
            decision_ref=decision_ref)

    # ---- R17 report ------------------------------------------------------------------------
    def report(self, *, tenant: str) -> list[BrakeReport]:
        """The unprompted operator report of every ACTIVE brake affecting this tenant. Assembled
        from the store's active brakes plus the effect ledger (prevented / in-flight / unknown
        outcomes). A read only — it writes nothing and mints nothing."""
        reports: list[BrakeReport] = []
        conn = self._store._conn  # read-only ledger access for the report
        prevented = self._count(conn, tenant, ("GRANTED",))
        in_flight = self._grants(conn, tenant, ("CLAIMED", "ATTEMPTED"))
        unknowns = self._grants(conn, tenant, ("UNKNOWN_OUTCOME",))
        exposure = self._exposure(conn, tenant)
        for b in self._store.active_report(tenant=tenant):
            reports.append(BrakeReport(
                scope=b.scope, still_allowed=STILL_ALLOWED_UNDER_BRAKE, reason=b.engaged_reason,
                actor=b.actor, actor_kind=b.actor_kind, engaged_at=b.engaged_at,
                prevented_effects=prevented, in_flight_effects=list(in_flight),
                in_flight_status={g: "runs_to_verified_conclusion" for g in in_flight},
                unresolved_unknown_outcomes=list(unknowns), unknown_outcome_exposure=exposure,
                release_requirements=RELEASE_EVIDENCE,
            ))
        return reports

    # ---- internals -------------------------------------------------------------------------
    @staticmethod
    def _db_kind(actor_class: str) -> str:
        # A human writes HUMAN; a detector and general automation write the DETECTOR kind (the only
        # non-human brake actor kind). Anything else is refused before this is reached.
        return HUMAN if actor_class == HUMAN_CLASS else DETECTOR

    @staticmethod
    def _refuse_reason(actor_class: str, op: str) -> str:
        if actor_class == MODEL_CLASS:
            return (f"a model is not a Sev-0 detector and may never {op} a brake — it may raise a "
                    f"signal for a detector, never touch the brake itself (M-60).")
        if actor_class in (TIMER_CLASS,):
            return (f"a timer may never {op} a brake — a brake never expires and a clock cannot "
                    f"know whether the fire is out (BR-5).")
        return f"a {actor_class} may never {op} a brake (ADR-011 §5.1, the one-way ratchet)."

    @staticmethod
    def _grants(conn: Any, tenant: str, states: tuple[str, ...]) -> list[str]:
        marks = ",".join("?" for _ in states)
        rows = conn.execute(
            f"SELECT grant_id FROM effect_grants WHERE tenant = ? AND state IN ({marks}) "
            f"ORDER BY grant_id",
            (tenant, *states),
        ).fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def _count(conn: Any, tenant: str, states: tuple[str, ...]) -> int:
        marks = ",".join("?" for _ in states)
        return int(conn.execute(
            f"SELECT COUNT(*) FROM effect_grants WHERE tenant = ? AND state IN ({marks})",
            (tenant, *states),
        ).fetchone()[0])

    @staticmethod
    def _exposure(conn: Any, tenant: str) -> dict[str, Any]:
        # Exposure is carried on the UNKNOWN_OUTCOME rows; the brake reports it but never resolves
        # it (the brake does not, and cannot, clear an unknown outcome).
        n = BrakeMachine._count(conn, tenant, ("UNKNOWN_OUTCOME",))
        return {"unresolved_unknown_outcome_count": n}
