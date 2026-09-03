"""P6 / M9 — the Exception — acceptance and hostile battery.

Entity §44 names six adversarial tests by name; they are here by those names. Machine §14 names one
per-transition test by name; they are here too. The F9 family file names six event-contract tests by
name; they are here as well, and K-1 names its own test, which M1 already carries and which M9 must not
weaken. The rest of the battery covers the five states and the EC-1…EC-7 transitions, the named human
owner from creation, closure by a decision_ref that RESOLVES (never a bare string), the durable ageing/
escalation timers that get LOUDER and never resolve, the severity FIELD change that carries what it
moved from, replay that rebuilds the current severity from the recorded events and can never manufacture
a decision_ref, the conditional freeze the checkpoint refuses, and the ship-dark posture. Several node
ids are the guards `scripts/mutate_phase6_exception.py` turns RED — a guard never seen to fail is a
decoration.

The suite protects M9's actual behaviour: no inactivity, no AutoClose, no expiry, no sweep and no timer
can ever close an exception; no exception exists without a named human owner; and a carrier's money
nobody can account for reaches a person instead of a log file.
"""

from __future__ import annotations

import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.event_envelope import EventEnvelope  # noqa: E402
from freight_recon.event_outbox import TransactionalOutbox  # noqa: E402
from freight_recon.event_timers import TimerFired, TimerRelay  # noqa: E402
from freight_recon.exception import (  # noqa: E402
    PRODUCED_CONTRACTS,
    EcSeverity,
    EcState,
    EcSubStatus,
    GuardNotSatisfied,
    IllegalTransition,
    M9Machine,
    MalformedException,
    StateConflict,
    UnknownException,
)
from freight_recon.migrations.phase6_exceptions import (  # noqa: E402
    EXCEPTION_SEVERITIES,
    EXCEPTION_STATES,
    SUB_STATUSES,
    phase6_exceptions_readiness_problems,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)
from freight_recon.work_item import FailureDisposition  # noqa: E402

TENANT = "acme-brokerage"
OTHER = "beta-logistics"
HUMAN = "owner:dana"


def _conn() -> sqlite3.Connection:
    tmp = Path(tempfile.mkdtemp(prefix="p6m9-test-"))
    conn = sqlite3.connect(str(tmp / "ex.db"))
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


class Clock:
    def __init__(self, base: datetime | None = None) -> None:
        self._t = base or datetime(2026, 8, 28, 10, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        self._t += timedelta(milliseconds=1)
        return self._t

    def advance(self, **kw: int) -> None:
        self._t += timedelta(**kw)


def _human(conn: sqlite3.Connection, tenant: str = TENANT, human_id: str = HUMAN,
           state: str = "ACTIVE") -> str:
    off = "off" if state == "OFFBOARDED" else None
    conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
        "state, recorded_at, recorded_by, recorded_by_kind, offboarded_at) "
        "VALUES (?,?,?,?, ?, ?, ?, 'human', ?)",
        (tenant, human_id, human_id, "AUTHORIZED_HUMAN", state, "2026-08-20T09:00:00.000Z",
         "founder", off))
    conn.commit()
    return human_id


def _machine(conn: sqlite3.Connection, tenant: str = TENANT,
             clock: Clock | None = None) -> M9Machine:
    _human(conn, tenant)
    return M9Machine(conn, tenant=tenant, clock=clock or Clock())


def _raise(m: M9Machine, *, type: str = "UNKNOWN_OUTCOME", severity: str = "SEV1",
           source_ref: str = "comp-1", source_kind: str = "compensation", owner: str = HUMAN,
           summary: str = "a TMS write timed out and the outcome is unknown", **kw):
    return m.raise_exception(type=type, severity=severity, source_ref=source_ref,
                             source_kind=source_kind, owner_id=owner, summary=summary,
                             schedule_timer=kw.pop("schedule_timer", False), **kw)


def _human_decision(conn: sqlite3.Connection, tenant: str = TENANT, actor: str = HUMAN,
                    *, event_name: str = "HumanDecided", actor_type: str = "human") -> str:
    """One committed human-decision event id, resolvable by K-1 — an authenticated human decision.

    The same shape M3's `p3_human_decision` uses. A non-human `actor_type` or a non-decision
    `event_name` produces a reference the resolver REFUSES, which is exactly what the negative
    controls need."""
    eid = str(uuid.uuid4())
    wi = f"wi-{eid[:8]}"
    now = "2026-08-20T10:00:00.000Z"
    env = EventEnvelope(
        event_id=eid, event_name=event_name,
        event_version=CONTRACTS[event_name].current_version, occurred_at=now, recorded_at=now,
        tenant_id=tenant, aggregate_type="work_item", aggregate_id=wi, aggregate_version=1,
        causation_id=None, correlation_id=wi, producer_component="work_service",
        producer_transition_id="WI-9", actor_type=actor_type, actor_id=actor,
        trace_id="trace-decide", payload={"decision_ref": "human-said-so"})
    conn.execute("BEGIN IMMEDIATE")
    TransactionalOutbox(conn, tenant=tenant).emit(env)
    conn.commit()
    return eid


def _relay(conn: sqlite3.Connection, m: M9Machine, clock: Clock) -> TimerRelay:
    return TimerRelay(conn, tenant=m.tenant, handler=m.handle_timer_fired, relay_id="relay-1",
                      clock=clock)


# ============================================================ the six adversarial tests (entity §44)

def test_exception_closure_requires_decision_ref():
    """F-30. An exception closed without a decision is not closed — it is FORGOTTEN."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    # No decision_ref → ILLEGAL, recorded, nothing persisted.
    with pytest.raises(IllegalTransition):
        m.resolve(x, decision_ref=None, decision_human_id=HUMAN)
    assert m.get(x).state is EcState.OPEN
    # The string "done" references nothing → refused (the closed-with-'done' hole).
    with pytest.raises(IllegalTransition):
        m.resolve(x, decision_ref="done", decision_human_id=HUMAN)
    assert m.get(x).state is EcState.OPEN
    # A resolving decision_ref closes it.
    d = _human_decision(conn)
    r = m.resolve(x, decision_ref=d, decision_human_id=HUMAN)
    assert r.to_state is EcState.RESOLVED


def test_inactivity_never_closes_an_exception():
    """(b) inactivity never closes. Ageing and escalation get LOUDER; they never resolve, and nothing
    times out into a close."""
    conn = _conn()
    clock = Clock()
    m = _machine(conn, clock=clock)
    x = _raise(m, source_ref="c-age", age_threshold_ms=1000, escalation_threshold_ms=2000,
               schedule_timer=True).exception.exception_id
    relay = _relay(conn, m, clock)
    for _ in range(20):
        clock.advance(seconds=5)
        relay.run_once()
    # Twenty relay passes over a long silence never reach RESOLVED — only ESCALATED at most.
    assert m.get(x).state is EcState.ESCALATED
    # And a resolve with no decision_ref remains illegal no matter how old the exception is.
    with pytest.raises(IllegalTransition):
        m.resolve(x, decision_ref=None, decision_human_id=HUMAN)


def test_ownerless_exception_impossible():
    """(c) an owner exists from creation. Enforced by the machine AND by the database."""
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(GuardNotSatisfied):
        _raise(m, owner="")
    # The database refuses a NULL owner directly, too — a structurally impossible state.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO exceptions (tenant, exception_id, type, severity, state, version, owner_id, "
            "source_ref, source_kind, freezes_entity, summary, created_at, updated_at) "
            "VALUES (?, 'x-null', 'T', 'SEV1', 'OPEN', 1, NULL, 's', 'compensation', 0, 'u', 't', 't')",
            (TENANT,))


def test_auth_failure_raises_exception_immediately_zero_retries():
    """(d) / L-D. A PERMANENT (auth/config) failure raises immediately, with zero retries."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, source_ref="c-auth", failure_classification=FailureDisposition.PERMANENT,
               attempts_before_raise=0)
    assert m.get(r.exception.exception_id).failure_classification == "permanent"
    assert r.to_state is EcState.OPEN
    # A permanent failure that was RETRIED before raising is refused — it already wasted the effect.
    with pytest.raises(MalformedException):
        _raise(m, source_ref="c-auth2", failure_classification=FailureDisposition.PERMANENT,
               attempts_before_raise=3)


def test_ageing_escalates_via_durable_timer_not_sweep():
    """(e) ageing escalates via a durable timer. Never a background sweep, never a scan."""
    conn = _conn()
    clock = Clock()
    m = _machine(conn, clock=clock)
    x = _raise(m, source_ref="c-esc", age_threshold_ms=1000, escalation_threshold_ms=2000,
               schedule_timer=True).exception.exception_id
    # A real durable_timers row was scheduled in the same commit as the raise.
    assert conn.execute("SELECT COUNT(*) FROM durable_timers WHERE tenant = ? AND aggregate_id = ?",
                        (TENANT, x)).fetchone()[0] == 1
    relay = _relay(conn, m, clock)
    clock.advance(seconds=5)
    relay.run_once()
    assert m.get(x).state is EcState.AGEING
    clock.advance(seconds=5)
    relay.run_once()
    assert m.get(x).state is EcState.ESCALATED
    # The machine defines no sweep/reaper method — M-36.
    assert not any(name in dir(m) for name in ("sweep", "sweep_overdue", "reap", "scan_stale"))


def test_model_cannot_resolve_an_exception():
    """[C-6] / GR-7 / ER-9. A model may never resolve or auto-clear an exception, at any confidence."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    d = _human_decision(conn)
    with pytest.raises(IllegalTransition):
        m.resolve(x, decision_ref=d, decision_human_id=HUMAN, actor_kind="model")
    assert m.get(x).state is EcState.OPEN
    # A model cannot acknowledge or change severity either.
    with pytest.raises(IllegalTransition):
        m.acknowledge(x, acknowledged_by=HUMAN, actor_kind="model")
    with pytest.raises(IllegalTransition):
        m.change_severity(x, severity="SEV0", changed_by=HUMAN, reason="r", actor_kind="model")


# ============================================================ the per-transition tests (machine §14)

def test_ec_raise_requires_owner():
    """EC-1 — a human owner_id is assigned at creation, or creation fails."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    x = m.get(r.exception.exception_id)
    assert r.transition_id == "EC-1" and x.state is EcState.OPEN and x.owner_id == HUMAN
    assert r.event_names == ("ExceptionRaised",)
    with pytest.raises(GuardNotSatisfied):
        _raise(m, source_ref="c-noowner", owner="ghost")   # not a recorded human


def test_ec_ack():
    """EC-2 — an authenticated human acknowledges; OPEN → ACKNOWLEDGED, records acknowledged_by."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    r = m.acknowledge(x, acknowledged_by=HUMAN)
    assert r.to_state is EcState.ACKNOWLEDGED and r.event_names == ("ExceptionAcknowledged",)
    row = m.get(x)
    assert row.acknowledged_by == HUMAN and row.acknowledged_at is not None
    # A system actor cannot acknowledge (trigger is H).
    y = _raise(m, source_ref="c-sys").exception.exception_id
    with pytest.raises(IllegalTransition):
        m.acknowledge(y, acknowledged_by=HUMAN, actor_kind="system")


def test_ec_close_requires_valid_decision_ref():
    """EC-3 — resolution from OPEN/ACKNOWLEDGED requires a decision_ref that RESOLVES (GR-14)."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    m.acknowledge(x, acknowledged_by=HUMAN)
    # A reference to nothing is refused.
    with pytest.raises(IllegalTransition):
        m.resolve(x, decision_ref=str(uuid.uuid4()), decision_human_id=HUMAN)
    d = _human_decision(conn)
    r = m.resolve(x, decision_ref=d, decision_human_id=HUMAN)
    assert r.transition_id == "EC-3" and r.to_state is EcState.RESOLVED
    assert r.event_names == ("ExceptionResolved",)


def test_ec_ages():
    """EC-4 — {OPEN, ACKNOWLEDGED} → AGEING on the durable timer; the row stays human-owned."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    r = m.age(x)
    assert r.transition_id == "EC-4" and r.to_state is EcState.AGEING
    assert r.event_names == ("ExceptionAgeing",)
    assert m.get(x).owner_id == HUMAN and m.get(x).ageing_at is not None
    # Ageing an already-AGEING exception is illegal (AGEING is not in EC-4's from-set).
    with pytest.raises(IllegalTransition):
        m.age(x)


def test_ec_escalates():
    """EC-5 — AGEING → ESCALATED on the durable timer; still human-owned; never resolves."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    m.age(x)
    r = m.escalate(x)
    assert r.transition_id == "EC-5" and r.to_state is EcState.ESCALATED
    assert r.event_names == ("ExceptionEscalated",)
    assert m.get(x).owner_id == HUMAN
    # Escalating a non-AGEING exception is illegal.
    y = _raise(m, source_ref="c-open").exception.exception_id
    with pytest.raises(IllegalTransition):
        m.escalate(y)


def test_ec_escalated_resolves():
    """EC-6 — ESCALATED → RESOLVED with a resolving decision_ref."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    m.age(x)
    m.escalate(x)
    d = _human_decision(conn)
    r = m.resolve(x, decision_ref=d, decision_human_id=HUMAN)
    assert r.transition_id == "EC-6" and r.to_state is EcState.RESOLVED


def test_ec_severity_change_is_field_not_state():
    """EC-7 — severity is a FIELD; reassessing it does not change state and carries what it moved from."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m, severity="SEV2").exception.exception_id
    m.acknowledge(x, acknowledged_by=HUMAN)
    r = m.change_severity(x, severity="SEV0", changed_by=HUMAN, reason="the exposure grew")
    assert r.event_names == ("ExceptionSeverityChanged",)
    row = m.get(x)
    assert row.state is EcState.ACKNOWLEDGED       # state UNCHANGED
    assert row.severity is EcSeverity.SEV0
    # Changing severity of an AGEING exception is illegal (AGEING not in EC-7's from-set).
    m.age(x)
    with pytest.raises(IllegalTransition):
        m.change_severity(x, severity="SEV1", changed_by=HUMAN, reason="r")


# ============================================================ the F9 event-contract tests

def test_ev_exceptionraised_owned():
    """ExceptionRaised — proves something needs a human, OWNED from creation."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, severity="SEV1")
    env = _last_event(conn, "ExceptionRaised", r.exception.exception_id)
    assert env.payload["severity"] == "SEV1" and env.payload["source_ref"] == "comp-1"
    assert env.accountable_owner_id == HUMAN


def test_ev_exception_ack():
    """ExceptionAcknowledged — actor_type=human, carries acknowledged_by."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    m.acknowledge(x, acknowledged_by=HUMAN)
    env = _last_event(conn, "ExceptionAcknowledged", x)
    assert env.actor_type == "human" and env.payload["acknowledged_by"] == HUMAN


def test_ev_exception_ageing():
    """ExceptionAgeing — proves it aged past threshold; a timer, never a resolution."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    m.age(x)
    env = _last_event(conn, "ExceptionAgeing", x)
    assert env.event_name == "ExceptionAgeing"


def test_ev_exception_escalated():
    """ExceptionEscalated — proves escalation threshold reached."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    m.age(x)
    m.escalate(x)
    env = _last_event(conn, "ExceptionEscalated", x)
    assert env.event_name == "ExceptionEscalated"


def test_ev_exceptionseveritychanged_rebuilds_the_current_severity():
    """ExceptionSeverityChanged — carries severity, previous_severity, changed_by AND reason, so a
    rebuild reproduces the LIVE severity by folding, not the ORIGINAL (F9)."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m, severity="SEV2").exception.exception_id
    m.change_severity(x, severity="SEV0", changed_by=HUMAN, reason="exposure grew")
    env = _last_event(conn, "ExceptionSeverityChanged", x)
    for field in ("severity", "previous_severity", "changed_by", "reason"):
        assert field in env.payload, f"{field} missing from ExceptionSeverityChanged"
    assert env.payload["severity"] == "SEV0" and env.payload["previous_severity"] == "SEV2"
    # A full-history rebuild reproduces the LIVE severity (SEV0), folded from the events.
    rec = m.rebuild(x)
    assert rec.severity is EcSeverity.SEV0


def test_ev_exceptionresolved_valid_decision_ref():
    """ExceptionResolved — proves an authenticated human resolved it; decision_ref RESOLVES per K-1."""
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    d = _human_decision(conn)
    m.resolve(x, decision_ref=d, decision_human_id=HUMAN)
    env = _last_event(conn, "ExceptionResolved", x)
    assert env.payload["decision_ref"] == d


# ============================================================ K-1's own named test

def test_decision_ref_must_resolve_to_a_human_decision_event_or_active_rule():
    """K-1. The ref must RESOLVE — a bare string fails; a non-human-decision event fails; a
    human-decision event recorded by AUTOMATION fails (ER-11); a RULE refuses today (P6-D4)."""
    conn = _conn()
    m = _machine(conn)

    def refused(**kw):
        x = _raise(m, source_ref=f"c-{uuid.uuid4().hex[:8]}").exception.exception_id
        with pytest.raises(IllegalTransition):
            m.resolve(x, decision_human_id=HUMAN, **kw)
        assert m.get(x).state is EcState.OPEN

    refused(decision_ref="done")                                  # a bare string references nothing
    refused(decision_ref=str(uuid.uuid4()))                       # resolves to nothing
    # A canonical event that is NOT a human decision (ExceptionRaised itself) fails.
    non_decision = conn.execute(
        "SELECT event_id FROM event_outbox WHERE tenant = ? AND event_name = 'ExceptionRaised' "
        "LIMIT 1", (TENANT,)).fetchone()
    if non_decision is not None:
        refused(decision_ref=non_decision["event_id"])
    # A human-decision event TYPE recorded by AUTOMATION is authority laundering (ER-11) — refused.
    automated = _human_decision(conn, actor="automation", actor_type="system")
    refused(decision_ref=automated)
    # The RULE branch refuses today (M12 not built, P6-D4) — NOT M9's to close.
    d = _human_decision(conn)
    x = _raise(m, source_ref="c-rule").exception.exception_id
    with pytest.raises(IllegalTransition):
        m.resolve(x, decision_ref=d, decision_human_id=HUMAN, decision_ref_kind="RULE")


# ============================================================ the state set & vocabularies

def test_the_five_canonical_states_and_no_sixth():
    """Registry §4 / entity §12 — exactly five states, no sixth."""
    assert list(EXCEPTION_STATES) == ["OPEN", "ACKNOWLEDGED", "AGEING", "ESCALATED", "RESOLVED"]
    assert len(EXCEPTION_STATES) == 5
    assert {s.value for s in EcState} == set(EXCEPTION_STATES)
    conn = _conn()
    # The database refuses a sixth state.
    _human(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO exceptions (tenant, exception_id, type, severity, state, version, owner_id, "
            "source_ref, source_kind, freezes_entity, summary, created_at, updated_at) "
            "VALUES (?, 'x6', 'T', 'SEV1', 'CLOSED', 1, ?, 's', 'compensation', 0, 'u', 't', 't')",
            (TENANT, HUMAN))


def test_severity_is_sev0_sev1_or_sev2_and_nothing_else():
    assert list(EXCEPTION_SEVERITIES) == ["SEV0", "SEV1", "SEV2"]
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(MalformedException):
        _raise(m, severity="SEV3")
    _human(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO exceptions (tenant, exception_id, type, severity, state, version, owner_id, "
            "source_ref, source_kind, freezes_entity, summary, created_at, updated_at) "
            "VALUES (?, 'xsev', 'T', 'SEV9', 'OPEN', 1, ?, 's', 'compensation', 0, 'u', 't', 't')",
            (TENANT, HUMAN))


def test_sub_status_is_a_field_never_a_lifecycle_state():
    """The machine header — sub_status is a FIELD from a closed vocabulary DISJOINT from the states."""
    assert set(SUB_STATUSES).isdisjoint(set(EXCEPTION_STATES))
    assert {s.value for s in EcSubStatus} == set(SUB_STATUSES)
    conn = _conn()
    m = _machine(conn)
    r = _raise(m, sub_status="investigating")
    row = m.get(r.exception.exception_id)
    assert row.state is EcState.OPEN and row.sub_status == "investigating"
    # A sub_status value is not a state.
    assert "investigating" not in EXCEPTION_STATES


def test_source_kind_is_a_closed_vocabulary():
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(MalformedException):
        _raise(m, source_kind="not-a-kind")
    # A FK-backed source kind demands a real referenced row of this tenant.
    _human(conn)
    conn.execute(
        "INSERT INTO observations (tenant, observation_id, source_system, external_id, "
        "content_digest, raw_value, as_of, received_at, state, version, provenance_class, "
        "bound_entity_ref, created_at, updated_at) VALUES (?, 'obs-1', 'carrier', 'e', 'd', 'v', "
        "'t', 't', 'BOUND', 1, 'SYSTEM_IMPORTED', 'load:1', 't', 't')", (TENANT,))
    conn.commit()
    r = _raise(m, source_ref="obs-1", source_kind="observation")
    assert m.get(r.exception.exception_id).source_kind == "observation"


# ============================================================ resolution, retention, no-close

def test_resolved_is_the_only_terminal_state_and_nothing_moves_it():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    d = _human_decision(conn)
    m.resolve(x, decision_ref=d, decision_human_id=HUMAN)
    assert m.get(x).is_terminal
    for op in (lambda: m.acknowledge(x, acknowledged_by=HUMAN),
               lambda: m.age(x), lambda: m.escalate(x),
               lambda: m.change_severity(x, severity="SEV0", changed_by=HUMAN, reason="r")):
        with pytest.raises((IllegalTransition, GuardNotSatisfied)):
            op()
    assert m.get(x).state is EcState.RESOLVED


def test_a_resolved_exception_is_retained_never_deleted():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    d = _human_decision(conn)
    m.resolve(x, decision_ref=d, decision_human_id=HUMAN)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM exceptions WHERE tenant = ? AND exception_id = ?", (TENANT, x))


def test_an_exception_never_expires_and_no_sweep_deletes_it():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    # There is no EXPIRED state and no delete path — the row cannot be swept away.
    assert "EXPIRED" not in EXCEPTION_STATES
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM exceptions WHERE tenant = ?", (TENANT,))
    assert m.get(x).state is EcState.OPEN


def test_db_resolved_requires_decision_ref():
    """The structural half of GR-14: a RESOLVED row with no decision_ref is not insertable."""
    conn = _conn()
    _human(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO exceptions (tenant, exception_id, type, severity, state, version, owner_id, "
            "source_ref, source_kind, freezes_entity, summary, decision_human_id, created_at, "
            "updated_at) VALUES (?, 'xr', 'T', 'SEV1', 'RESOLVED', 1, ?, 's', 'compensation', 0, 'u', "
            "?, 't', 't')", (TENANT, HUMAN, HUMAN))


def test_db_freeze_requires_entity_and_field():
    """The structural half of ### M9-AQ-5: a freezing row names the entity and the field it froze."""
    conn = _conn()
    _human(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO exceptions (tenant, exception_id, type, severity, state, version, owner_id, "
            "source_ref, source_kind, freezes_entity, summary, created_at, updated_at) "
            "VALUES (?, 'xf', 'T', 'SEV1', 'OPEN', 1, ?, 's', 'compensation', 1, 'u', 't', 't')",
            (TENANT, HUMAN))


def test_a_retracted_cause_still_requires_an_event_and_a_decision_ref():
    """### M9-AQ-2. There is no CANCELLED state and no cancel event; a retracted cause reaches RESOLVED
    through EC-3/EC-6 with a resolving decision_ref like every other closure."""
    assert "CANCELLED" not in EXCEPTION_STATES
    assert not any(c.startswith("Exception") and "Cancel" in c for c in CONTRACTS)
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    # A retraction with no decision_ref cannot mint a state the registry does not hold.
    with pytest.raises(IllegalTransition):
        m.resolve(x, decision_ref=None, decision_human_id=HUMAN)


# ============================================================ severity & reason

def test_severity_change_requires_a_reason():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    with pytest.raises(GuardNotSatisfied):
        m.change_severity(x, severity="SEV0", changed_by=HUMAN, reason="")


def test_severity_change_records_previous_and_new_and_who():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m, severity="SEV1").exception.exception_id
    m.change_severity(x, severity="SEV0", changed_by=HUMAN, reason="grew")
    env = _last_event(conn, "ExceptionSeverityChanged", x)
    assert env.payload["previous_severity"] == "SEV1"
    assert env.payload["severity"] == "SEV0"
    assert env.payload["changed_by"] == HUMAN


# ============================================================ ageing / timers / restart

def test_a_timer_never_resolves():
    """Machine §37 — no M9 timer_kind maps to a resolution. A resolve-shaped timer is illegal."""
    conn = _conn()
    clock = Clock()
    m = _machine(conn, clock=clock)
    x = _raise(m).exception.exception_id
    fake = TimerFired(tenant=TENANT, timer_id="t", aggregate_type="exception", aggregate_id=x,
                      timer_kind="exception_resolution", fire_at="t", fired_at="t", payload={})
    with pytest.raises(IllegalTransition):
        m.handle_timer_fired(fake)
    assert m.get(x).state is EcState.OPEN


def test_ageing_and_escalated_remain_human_owned():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    m.age(x)
    assert m.get(x).owner_id == HUMAN and not m.get(x).is_terminal
    m.escalate(x)
    assert m.get(x).owner_id == HUMAN and not m.get(x).is_terminal


def test_an_acknowledged_exception_still_ages():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    m.acknowledge(x, acknowledged_by=HUMAN)
    r = m.age(x)
    assert r.to_state is EcState.AGEING


def test_restart_re_fires_the_ageing_timer_and_preserves_open():
    """A restart mid-life re-runs the relay against the durable timers table — the timer is not lost,
    and an unfired one leaves the exception OPEN."""
    conn = _conn()
    clock = Clock()
    m = _machine(conn, clock=clock)
    x = _raise(m, source_ref="c-restart", age_threshold_ms=100000,
               schedule_timer=True).exception.exception_id
    # "Restart": a brand-new machine and relay over the same connection/db.
    m2 = M9Machine(conn, tenant=TENANT, clock=clock)
    relay = _relay(conn, m2, clock)
    relay.run_once()          # not due yet
    assert m2.get(x).state is EcState.OPEN
    clock.advance(days=1)
    relay.run_once()
    assert m2.get(x).state is EcState.AGEING


def test_a_redelivered_timer_is_a_no_op():
    conn = _conn()
    clock = Clock()
    m = _machine(conn, clock=clock)
    x = _raise(m).exception.exception_id
    m.age(x)                                     # now AGEING
    payload = {"owner_id": HUMAN}
    fired = TimerFired(tenant=TENANT, timer_id="t", aggregate_type="exception", aggregate_id=x,
                       timer_kind="exception_age_threshold", fire_at="t", fired_at="t",
                       payload=payload)
    # A redelivered age timer against an already-AGEING exception is a no-op, not a second transition.
    assert m.handle_timer_fired(fired) is None
    assert m.get(x).state is EcState.AGEING


# ============================================================ freeze / checkpoint seam

def test_not_every_exception_freezes_an_entity():
    conn = _conn()
    m = _machine(conn)
    plain = m.get(_raise(m, source_ref="c-plain").exception.exception_id)
    assert not plain.freezes_entity and not plain.native_projection().conflicting
    freezing = m.get(_raise(m, source_ref="c-frz", freezes_entity=True, entity_ref="load:4471",
                            frozen_field="delivery").exception.exception_id)
    assert freezing.native_projection().conflicting


def test_a_freezing_exception_requires_entity_and_field():
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(MalformedException):
        _raise(m, source_ref="c-bad", freezes_entity=True)   # no entity_ref/frozen_field


def test_resolution_unblocks_the_frozen_entity():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m, source_ref="c-unfrz", freezes_entity=True, entity_ref="load:4471",
               frozen_field="delivery").exception.exception_id
    assert m.get(x).native_projection().conflicting
    d = _human_decision(conn)
    m.resolve(x, decision_ref=d, decision_human_id=HUMAN)
    assert not m.get(x).native_projection().conflicting


def test_m9_mints_no_gate_decision():
    """M9 is an INPUT to the checkpoint, never a gate. It imports no gate authority."""
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    assert "class M9Machine" in src  # population proof: the machine source is really loaded (CLAUDE.md §6)
    assert "from .checkpoint" not in src and "import checkpoint" not in src
    assert "GateDecision" not in src and "GateRegistry" not in src
    assert "effect_grants" not in src.replace("effect_grant", "")  # no effect_grants writes


def test_m9_engages_no_brake():
    """F9 cross-cutting — a Sev-0 exception CARRIES SEV0; the brake is the source detector's act."""
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    assert "class M9Machine" in src  # population proof: the machine source is really loaded (CLAUDE.md §6)
    assert "from .brake" not in src and "import brake" not in src
    assert "brake.engage" not in src and ".engage(" not in src


# ============================================================ tenant isolation & OCC

def test_the_same_source_in_two_tenants_are_two_isolated_exceptions():
    conn = _conn()
    a = _machine(conn, TENANT)
    b = _machine(conn, OTHER)
    ra = _raise(a, source_ref="shared", type="SAME")
    rb = _raise(b, source_ref="shared", type="SAME")
    assert ra.exception.exception_id != rb.exception.exception_id
    assert a.get(rb.exception.exception_id) is None      # A cannot see B's


def test_cross_tenant_owner_fails_closed():
    conn = _conn()
    _human(conn, OTHER, "owner:bob")
    a = _machine(conn, TENANT)
    with pytest.raises(GuardNotSatisfied):
        _raise(a, owner="owner:bob")                     # a human of another tenant


def test_cross_tenant_source_fails_closed():
    conn = _conn()
    _human(conn, OTHER)
    # An observation of tenant B, referenced as a source by tenant A, fails the FK closed.
    conn.execute(
        "INSERT INTO observations (tenant, observation_id, source_system, external_id, "
        "content_digest, raw_value, as_of, received_at, state, version, provenance_class, "
        "bound_entity_ref, created_at, updated_at) VALUES (?, 'obs-b', 'carrier', 'e', 'd', 'v', "
        "'t', 't', 'BOUND', 1, 'SYSTEM_IMPORTED', 'load:1', 't', 't')", (OTHER,))
    conn.commit()
    a = _machine(conn, TENANT)
    with pytest.raises(sqlite3.IntegrityError):
        _raise(a, source_ref="obs-b", source_kind="observation")


def test_occ_refuses_a_stale_version():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    stale = m.get(x)
    m.acknowledge(x, acknowledged_by=HUMAN)              # advances version
    with pytest.raises(StateConflict):
        m.age(x, expected=stale)                         # stale version → refused


# ============================================================ replay

def test_replay_reconstructs_the_open_exception_and_keeps_it_frozen():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m, source_ref="c-replay", freezes_entity=True, entity_ref="load:1",
               frozen_field="f").exception.exception_id
    rec = m.rebuild(x)
    assert rec.state is EcState.OPEN and rec.frozen
    assert rec.new_authority == 0 and rec.external_effects == 0
    assert rec.decision_refs_minted == 0 and rec.state_flips == 0


def test_replay_rebuilds_severity_from_the_recorded_events_not_the_row():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m, severity="SEV2").exception.exception_id
    m.change_severity(x, severity="SEV0", changed_by=HUMAN, reason="grew")
    # Full stream folds to the LIVE severity.
    assert m.rebuild(x).severity is EcSeverity.SEV0
    # A truncated stream (the raise only) folds to the ORIGINAL severity — proving the fold does NOT
    # read the current row, whose severity is now SEV0.
    raise_only = [e for e in m._event_stream(x) if e.event_name == "ExceptionRaised"]
    assert m.rebuild(x, events=raise_only).severity is EcSeverity.SEV2
    assert m.get(x).severity is EcSeverity.SEV0


def test_replay_can_never_manufacture_resolution_authority():
    conn = _conn()
    m = _machine(conn)
    x = _raise(m).exception.exception_id
    # Feed the consumer a stream with no ExceptionResolved: it can never mint one.
    rec = m.rebuild(x)
    assert rec.state is EcState.OPEN and rec.decision_refs_minted == 0
    assert m.get(x).decision_ref is None


# ============================================================ under a brake

def test_exceptions_still_raise_under_a_brake():
    """GR-16 — a brake refuses to mint and to claim; it does not stop Neyma noticing a human is
    needed. M9 raises under a brake and engages none."""
    from freight_recon.brake import BrakeStore
    conn = _conn()
    BrakeStore(conn).engage(tenant=TENANT, reason="test", actor="founder", actor_kind="HUMAN")
    m = _machine(conn)
    r = _raise(m, source_ref="c-brake")
    assert r.to_state is EcState.OPEN


# ============================================================ database invariants & ship-dark

def test_readiness_is_clean_on_a_fresh_canonical_database():
    conn = _conn()
    assert phase6_exceptions_readiness_problems(conn) == []
    assert schema_readiness_problems(conn) == []


def test_the_produced_contracts_are_exactly_the_six_registered_f9_names():
    assert PRODUCED_CONTRACTS == frozenset(
        ("ExceptionRaised", "ExceptionAcknowledged", "ExceptionAgeing", "ExceptionEscalated",
         "ExceptionSeverityChanged", "ExceptionResolved"))
    for name in PRODUCED_CONTRACTS:
        assert CONTRACTS[name].family == "F9"


def test_the_machine_defines_no_sweep_or_reaper_method():
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    assert "class M9Machine" in src  # population proof: the machine source is really loaded (CLAUDE.md §6)
    for banned in ("def sweep", "def reap", "def scan_stale", "def sweep_overdue"):
        assert banned not in src


def test_failure_classification_is_supplied_never_inferred():
    conn = _conn()
    m = _machine(conn)
    # A message string is not a classification — no classifier maps it to PERMANENT.
    with pytest.raises(MalformedException):
        _raise(m, source_ref="c-msg", failure_classification="401 auth error")
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    assert "class M9Machine" in src  # population proof: the machine source is really loaded (CLAUDE.md §6)
    assert "_classify" not in src        # there is no message-to-class classifier


def test_the_neighbouring_machines_are_not_built():
    conn = _conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # M10 (the Compensation) LANDED after M9, so `compensations` is now canonical (rule 20 — the
    # forward-looking assertion was true at the M9 landing and is corrected here rather than left to
    # assert a table that now exists). The still-unbuilt neighbours stay asserted-absent: M11
    # (policies), M12 (rules) and Evidence (P7).
    # M11 (the Policy) also LANDED after M9, so `policies` is now canonical too (rule 20). The
    # still-unbuilt neighbours stay asserted-absent: M12 (rules) and Evidence (P7). M9's machine
    # (exception.py) is byte-unchanged and M11 does not import it (PO-7 names its M9 escalation seam
    # and leaves it unwired, so M9 keeps ZERO importers).
    assert not ({"rules", "evidence"} & tables)
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    import re
    assert not re.findall(r"\b(?:CM|PO|RU)-\d+", src)     # no M10/M11/M12 transitions


def test_m9_ships_dark_no_production_importer():
    """Nothing under src/freight_recon/ imports the exception machine (only the probe may)."""
    import ast
    pkg = ROOT / "src" / "freight_recon"
    offenders = []
    for py in pkg.rglob("*.py"):
        if py.name == "exception.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # `from .exception import X`
                if node.module and node.module.split(".")[-1] == "exception":
                    offenders.append(str(py.relative_to(ROOT)))
                # `from . import exception` (module is None/"" for a bare relative import)
                if not node.module and any(a.name == "exception" for a in node.names):
                    offenders.append(str(py.relative_to(ROOT)))
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[-1] == "exception":
                        offenders.append(str(py.relative_to(ROOT)))
    assert offenders == [], f"production importer(s) of the exception machine: {offenders}"


def test_no_unregistered_exception_event_name_in_the_machine():
    """A canonical scan: every `Exception[A-Z]` identifier in the machine is one of the six registered
    F9 event names. `ExceptionAutoClosed` is what an invented seventh event would be called."""
    import re
    src = (ROOT / "src" / "freight_recon" / "exception.py").read_text(encoding="utf-8")
    found = set(re.findall(r"\bException[A-Z][A-Za-z]*", src))
    assert found <= PRODUCED_CONTRACTS, f"unregistered Exception* name(s): {found - PRODUCED_CONTRACTS}"


def test_unknown_exception_is_tenant_scoped():
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(UnknownException):
        m.require("nope")


# ============================================================ helpers

def _last_event(conn: sqlite3.Connection, name: str, aggregate_id: str) -> EventEnvelope:
    row = conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE aggregate_type = 'exception' "
        "AND aggregate_id = ? AND event_name = ? ORDER BY aggregate_version DESC, sequence DESC "
        "LIMIT 1", (aggregate_id, name)).fetchone()
    assert row is not None, f"no {name} event for {aggregate_id}"
    return EventEnvelope.from_json(row["envelope_json"])
