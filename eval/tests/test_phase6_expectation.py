"""P6 / M8 — the Expectation — acceptance and hostile battery.

Entity §44 names six adversarial tests by name; they are here by those names. Machine §14 names one
per-transition test by name; they are here too. The F8 family file names seven event-contract tests by
name; they are here as well. The rest of the battery covers the six states and the EX-1…EX-7
transitions, the honesty split (healthy coverage ⇒ OVERDUE, blind coverage ⇒ INDETERMINATE, and the
absence of a record is NOT health), the durable-timer deadline, the partial unique index, the late
arrival that always discharges, the facility-local DST evaluation, replay from the recorded coverage,
the checkpoint seam M8 must FEED but not become, and the ship-dark posture. Several node ids are the
guards `scripts/mutate_phase6_expectation.py` turns RED — a guard never seen to fail is a decoration.

The suite protects M8's actual behaviour: a blind window can never become an accusation, no sweep can
make an obligation quietly stop existing, and a rebuild months later reaches the same verdict from the
coverage recorded at the time.
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

from freight_recon.event_timers import TimerFired, TimerRelay  # noqa: E402
from freight_recon.expectation import (  # noqa: E402
    PRODUCED_CONTRACTS,
    ExState,
    GuardNotSatisfied,
    IllegalTransition,
    M8Machine,
    MalformedExpectation,
    StateConflict,
    UnknownExpectation,
    facility_local_deadline,
)
from freight_recon.migrations.phase6_expectations import (  # noqa: E402
    COVERAGE_HEALTH,
    EXPECTATION_STATES,
    phase6_expectations_readiness_problems,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

TENANT = "acme-brokerage"
HUMAN = "owner:dana"
CHANNEL = "carrier-mailbox"
DEADLINE = datetime(2026, 8, 28, 17, 0, 0, tzinfo=timezone.utc)


def _conn() -> sqlite3.Connection:
    tmp = Path(tempfile.mkdtemp(prefix="p6m8-test-"))
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


def _observation(conn: sqlite3.Connection, oid: str, *, bound_entity_ref: str = "load:4471",
                 state: str = "BOUND", tenant: str = TENANT) -> str:
    conn.execute(
        "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, external_id, "
        "content_digest, raw_value, as_of, received_at, state, version, provenance_class, "
        "bound_entity_ref, created_at, updated_at) VALUES (?,?, 'carrier', ?, ?, 'v', 't', 't', ?, "
        "1, 'SYSTEM_IMPORTED', ?, 't', 't')", (tenant, oid, oid, oid, state, bound_entity_ref))
    conn.commit()
    return oid


def _machine(conn: sqlite3.Connection, tenant: str = TENANT, *, clock: Clock | None = None) -> M8Machine:
    _human(conn, tenant)
    return M8Machine(conn, tenant=tenant, clock=clock or Clock())


def _raise(m: M8Machine, *, subject_ref: str = "load:4471", expected_type: str = "POD",
           expected_source: str = CHANNEL, owner_id: str = HUMAN, deadline: datetime = DEADLINE,
           subject_kind: str = "entity", terminal_age_ms: int | None = None, **kw):
    return m.raise_expectation(
        subject_ref=subject_ref, expected_type=expected_type, expected_source=expected_source,
        owner_id=owner_id, originating_timezone="UTC", deadline_utc=deadline,
        subject_kind=subject_kind, terminal_age_ms=terminal_age_ms, **kw)


def _cover(m: M8Machine, exp, health: str, *, coverage_id: str = "cov-1",
           channel: str | None = None) -> str:
    """Record a coverage row that spans the whole required window [created_at, deadline_utc]."""
    return m.record_coverage(
        coverage_id=coverage_id, channel=channel or exp.expected_source,
        window_start=exp.created_at, window_end=exp.deadline_utc, health=health, probe_source="probe")


def _events(conn: sqlite3.Connection, tenant: str = TENANT) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT event_name FROM event_outbox WHERE tenant = ? ORDER BY sequence", (tenant,))]


# ============================================================ readiness / schema

def test_the_expectation_schema_is_ready_on_a_fresh_canonical_database():
    conn = _conn()
    assert schema_readiness_problems(conn) == []
    assert phase6_expectations_readiness_problems(conn) == []


def test_the_six_canonical_states_and_no_seventh():
    assert EXPECTATION_STATES == (
        "RAISED", "DISCHARGED", "OVERDUE", "INDETERMINATE", "CANCELLED", "EXPIRED")
    for forbidden in ("TIMED_OUT", "STALE", "RESOLVED", "MISSED", "LATE", "CLOSED", "PENDING"):
        assert forbidden not in EXPECTATION_STATES


# ============================================================ the entity §44 adversarial tests

def test_deadline_passes_while_channel_down_yields_INDETERMINATE_not_OVERDUE():
    """entity §44 / M-32. Healthy is a positive assertion; a down channel is blindness, and blindness
    is INDETERMINATE — we do not accuse a counterparty of a failure that was ours."""
    m = _machine(_conn())
    r = _raise(m)
    _cover(m, r.expectation, "DOWN")
    res = m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)
    assert res.to_state is ExState.INDETERMINATE
    assert res.event_names == ("ExpectationIndeterminate",)
    assert m.get(r.expectation.expectation_id).coverage_gap.startswith("DOWN")


def test_late_arrival_discharges():
    """entity §44. The POD that arrives in month four is still a POD (EX-4)."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # OVERDUE
    _observation(conn, "pod-late", bound_entity_ref="load:4471")
    d = m.discharge(r.expectation.expectation_id, observation_id="pod-late")
    assert d.to_state is ExState.DISCHARGED and d.late is True and d.event_producer == "EX-4"


def test_duplicate_expectation_prevented():
    """entity §44 / §17. Two raises for one owed observation are one live expectation — the partial
    unique index, not an application check-then-insert."""
    m = _machine(_conn())
    r1 = _raise(m)
    r2 = _raise(m)  # same (subject, expected_type)
    assert r2.coalesced is True
    assert r2.expectation.expectation_id == r1.expectation.expectation_id
    live = m.conn.execute(
        "SELECT COUNT(*) FROM expectations WHERE tenant = ? AND state = 'RAISED'",
        (TENANT,)).fetchone()[0]
    assert live == 1


def test_appointment_window_evaluated_in_facility_local_time_across_dst():
    """entity §44 / F-25. A 17:00 Denver appointment is localised in America/Denver — UTC-6 under
    daylight time, UTC-7 in standard time — never read as 17:00 UTC, and a DST boundary does not move
    a correctly-computed deadline."""
    m = _machine(_conn())
    summer = facility_local_deadline(datetime(2026, 7, 15, 17, 0, 0), "America/Denver")  # MDT
    winter = facility_local_deadline(datetime(2026, 12, 15, 17, 0, 0), "America/Denver")  # MST
    assert summer.hour == 23 and winter.hour == 0  # 17:00 MDT = 23:00Z; 17:00 MST = 00:00Z next day
    # a naive-UTC evaluation would put both at 17:00Z — the wrong instant.
    assert summer.hour != 17 and winter.hour != 17
    r = m.raise_expectation(
        subject_ref="load:9", expected_type="appointment_confirmation", expected_source=CHANNEL,
        owner_id=HUMAN, originating_timezone="America/Denver",
        appointment_local=datetime(2026, 7, 15, 17, 0, 0))
    assert m.get(r.expectation.expectation_id).deadline_utc == "2026-07-15T23:00:00.000Z"


def test_expiry_raises_an_exception_never_silence():
    """entity §44 / ### M8-AQ-1. Expiry emits ExpectationExpired, retains the row, and it still names
    its human — the M8-owned half of the exception seam. M8 mints NO M9 event and builds NO exceptions
    table; the seam is named in prose, never by the M9 contract's registered identifier."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # OVERDUE
    e = m.expire(r.expectation.expectation_id)
    assert e.to_state is ExState.EXPIRED and e.event_names == ("ExpectationExpired",)
    row = m.get(r.expectation.expectation_id)
    assert row is not None and row.owner_id == HUMAN  # retained, still owned
    assert "ExpectationExpired" in _events(conn)
    # M8 mints no M9 contract and its OWN migration builds no exceptions table. (The `exceptions`
    # table became canonical when M9 landed; rule 20 — corrected from the pre-M9 whole-schema
    # assertion.)
    assert "ExceptionRaised" not in _events(conn)
    from freight_recon.migrations.phase6_expectations import P6EX_TENANT_TABLES
    assert "exceptions" not in P6EX_TENANT_TABLES


def test_overdue_requires_healthy_coverage():
    """entity §44 / §16. OVERDUE without a healthy coverage_ref is structurally impossible — the
    machine goes INDETERMINATE when coverage is not healthy, and a raw OVERDUE with non-healthy
    coverage_health is refused by the database CHECK."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _cover(m, r.expectation, "UNKNOWN")
    assert m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN).to_state is (
        ExState.INDETERMINATE)
    # the database itself refuses an OVERDUE with non-healthy coverage_health.
    conn.execute("INSERT INTO observation_coverage (tenant, coverage_id, channel, window_start, "
                 "window_end, health, probe_source, recorded_at) VALUES (?, 'cd', 'c', 'a', 'z', "
                 "'DOWN', 'p', 't')", (TENANT,))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expectations (tenant, expectation_id, subject_ref, subject_kind, "
            "subject_observation_ref, expected_type, expected_source, expectation_key, deadline_utc, "
            "originating_timezone, state, version, coverage_ref, coverage_health, owner_id, "
            "created_at, updated_at) VALUES (?, 'bad', 'l', 'entity', NULL, 'POD', 'c', 'l::POD', 't', "
            "'UTC', 'OVERDUE', 1, 'cd', 'DOWN', ?, 't', 't')", (TENANT, HUMAN))
        conn.commit()


# ============================================================ the machine §14 per-transition tests

def test_ex_raise_declares_channel():
    """EX-1. A deadline + a DECLARED channel + a duplicate-prevention key. No channel ⇒ no expectation."""
    m = _machine(_conn())
    r = _raise(m)
    exp = m.get(r.expectation.expectation_id)
    assert (exp.state is ExState.RAISED and exp.expected_source == CHANNEL
            and exp.expectation_key == "load:4471::POD" and exp.originating_timezone == "UTC")
    with pytest.raises(MalformedExpectation):
        _raise(m, expected_source="")


def test_ex_discharge_on_bound_observation():
    """EX-2. A bound Observation matching the expectation discharges it."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _observation(conn, "pod-1", bound_entity_ref="load:4471")
    d = m.discharge(r.expectation.expectation_id, observation_id="pod-1")
    assert (d.to_state is ExState.DISCHARGED and d.event_producer == "EX-2" and d.late is False
            and m.get(r.expectation.expectation_id).discharge_observation_id == "pod-1")


def test_ex_overdue_requires_healthy_coverage():
    """EX-3. Deadline passed AND the channel was demonstrably healthy throughout the window."""
    m = _machine(_conn())
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    res = m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)
    assert (res.to_state is ExState.OVERDUE and res.event_names == ("ExpectationOverdue",)
            and m.get(r.expectation.expectation_id).coverage_health == "HEALTHY")


def test_ex_deadline_while_blind_is_indeterminate_not_overdue():
    """EX-3i. Deadline passed AND the channel was down or coverage unknown ⇒ INDETERMINATE."""
    m = _machine(_conn())
    r = _raise(m)
    # no coverage recorded at all — the absence of a record is not health.
    res = m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)
    assert res.to_state is ExState.INDETERMINATE
    assert "INDETERMINATE" in EXPECTATION_STATES  # the honesty split has its own state


def test_ex_late_arrival_discharges():
    """EX-4. A late arrival is ALWAYS accepted, from OVERDUE or INDETERMINATE."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # INDETERMINATE (absent)
    _observation(conn, "pod-4", bound_entity_ref="load:4471")
    d = m.discharge(r.expectation.expectation_id, observation_id="pod-4")
    assert d.to_state is ExState.DISCHARGED and d.late is True


def test_ex_deadline_amend():
    """EX-5. A deadline amendment re-versions and retains deadline_history; it is not a supersession."""
    m = _machine(_conn())
    r = _raise(m)
    original = m.get(r.expectation.expectation_id).deadline_utc
    res = m.amend_deadline(r.expectation.expectation_id,
                           new_deadline_utc=datetime(2026, 8, 29, 17, 0, 0, tzinfo=timezone.utc))
    exp = m.get(r.expectation.expectation_id)
    assert (res.to_state is ExState.RAISED and exp.version == 2
            and original in exp.deadline_history_list
            and res.event_names == ("ExpectationReVersioned",))


def test_ex_cancel_on_reason_gone():
    """EX-6. ReasonDisappeared (the load cancelled) ⇒ CANCELLED; the row is retained."""
    m = _machine(_conn())
    r = _raise(m)
    res = m.cancel(r.expectation.expectation_id, reason="load cancelled")
    assert res.to_state is ExState.CANCELLED and res.event_names == ("ExpectationCancelled",)
    assert m.get(r.expectation.expectation_id) is not None  # retained


def test_ex_expiry_raises_exception_never_silence():
    """EX-7. Terminal age ⇒ EXPIRED, emitting ExpectationExpired — never silence, and without minting
    an M9 event or building an exceptions table (### M8-AQ-1)."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # INDETERMINATE
    e = m.expire(r.expectation.expectation_id)
    assert e.to_state is ExState.EXPIRED and "ExpectationExpired" in _events(conn)
    assert "ExceptionRaised" not in _events(conn)


# ============================================================ the F8 event-contract tests

def test_ev_expectationraised_declares_channel():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    env = m._event_stream(r.expectation.expectation_id)[0]
    assert env.event_name == "ExpectationRaised"
    for field in ("deadline_utc", "originating_timezone", "expected_source", "expectation_key"):
        assert field in env.payload


def test_ev_expectationdischarged_late_ok():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # INDETERMINATE
    _observation(conn, "pod", bound_entity_ref="load:4471")
    m.discharge(r.expectation.expectation_id, observation_id="pod")
    env = [e for e in m._event_stream(r.expectation.expectation_id)
           if e.event_name == "ExpectationDischarged"][0]
    assert env.payload["discharge_observation_id"] == "pod" and env.payload["late"] is True


def test_ev_overdue_requires_healthy_coverage():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)
    env = [e for e in m._event_stream(r.expectation.expectation_id)
           if e.event_name == "ExpectationOverdue"][0]
    assert env.payload.get("coverage_ref")  # REQUIRED — it is what proves health


def test_ev_indeterminate_on_blind_window():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # absent -> INDETERMINATE
    env = [e for e in m._event_stream(r.expectation.expectation_id)
           if e.event_name == "ExpectationIndeterminate"][0]
    assert env.payload.get("coverage_gap")  # REQUIRED


def test_ev_expectation_reversioned():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.amend_deadline(r.expectation.expectation_id,
                     new_deadline_utc=datetime(2026, 8, 29, 17, 0, 0, tzinfo=timezone.utc))
    env = [e for e in m._event_stream(r.expectation.expectation_id)
           if e.event_name == "ExpectationReVersioned"][0]
    assert isinstance(env.payload.get("deadline_history"), list)


def test_ev_expectation_cancelled():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.cancel(r.expectation.expectation_id, reason="load cancelled")
    env = [e for e in m._event_stream(r.expectation.expectation_id)
           if e.event_name == "ExpectationCancelled"][0]
    assert env.payload.get("reason") == "load cancelled"


def test_ev_expectation_expired_raises():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)
    m.expire(r.expectation.expectation_id)
    names = [e.event_name for e in m._event_stream(r.expectation.expectation_id)]
    assert "ExpectationExpired" in names


def test_only_the_seven_registered_f8_contracts_are_produced():
    assert PRODUCED_CONTRACTS == frozenset((
        "ExpectationRaised", "ExpectationDischarged", "ExpectationOverdue", "ExpectationIndeterminate",
        "ExpectationReVersioned", "ExpectationCancelled", "ExpectationExpired"))


# ============================================================ the honesty split, in depth

def test_absent_coverage_is_not_health():
    """### THE ABSENCE OF A COVERAGE RECORD IS NOT HEALTH (M-32). No row ⇒ INDETERMINATE."""
    m = _machine(_conn())
    r = _raise(m)
    res = m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)
    assert res.to_state is ExState.INDETERMINATE
    assert m.get(r.expectation.expectation_id).coverage_gap.startswith("ABSENT")


def test_partial_coverage_is_not_health():
    """A HEALTHY record that does not span the whole required window is PARTIAL, not health — the
    'throughout the window' half of EX-3."""
    m = _machine(_conn())
    r = _raise(m)
    # a HEALTHY row that only covers the second half of the window.
    m.record_coverage(coverage_id="cp", channel=CHANNEL,
                      window_start="2026-08-28T16:00:00.000Z", window_end=r.expectation.deadline_utc,
                      health="HEALTHY", probe_source="probe")
    res = m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)
    assert res.to_state is ExState.INDETERMINATE


def test_explicit_partial_health_is_not_overdue():
    m = _machine(_conn())
    r = _raise(m)
    _cover(m, r.expectation, "PARTIAL")
    assert m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN).to_state is (
        ExState.INDETERMINATE)


def test_confidence_never_turns_indeterminate_into_overdue():
    """GR-8. Confidence is not a guard input, at any value including 1.0."""
    m = _machine(_conn())
    r = _raise(m, proposed_confidence=1.0)
    # absent coverage — a confident model cannot make it OVERDUE.
    assert m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN).to_state is (
        ExState.INDETERMINATE)


def test_forcing_overdue_without_healthy_coverage_is_illegal():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _cover(m, r.expectation, "DOWN")
    with pytest.raises(IllegalTransition):
        m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN, insist="OVERDUE")
    assert [x[0] for x in conn.execute(
        "SELECT event_type FROM security_events WHERE tenant = ?", (TENANT,))] == [
        "IllegalTransitionAttempted"]


# ============================================================ discharge guards

def test_unbound_observation_cannot_discharge():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _observation(conn, "obs-unbound", bound_entity_ref="load:4471", state="RECEIVED")
    with pytest.raises(GuardNotSatisfied):
        m.discharge(r.expectation.expectation_id, observation_id="obs-unbound")
    assert m.get(r.expectation.expectation_id).state is ExState.RAISED


def test_wrong_subject_observation_cannot_discharge():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _observation(conn, "obs-other", bound_entity_ref="load:9999")
    with pytest.raises(GuardNotSatisfied):
        m.discharge(r.expectation.expectation_id, observation_id="obs-other")


def test_wrong_tenant_observation_cannot_discharge():
    conn = _conn()
    m = _machine(conn)
    _human(conn, "other-tenant")
    _observation(conn, "obs-x", bound_entity_ref="load:4471", tenant="other-tenant")
    r = _raise(m)
    with pytest.raises(GuardNotSatisfied):
        m.discharge(r.expectation.expectation_id, observation_id="obs-x")


def test_late_evidence_is_never_rejected_because_the_deadline_passed():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # OVERDUE
    _observation(conn, "pod-m4", bound_entity_ref="load:4471")
    d = m.discharge(r.expectation.expectation_id, observation_id="pod-m4")
    assert d.to_state is ExState.DISCHARGED  # never rejected for lateness


# ============================================================ owner / human-owned states

def test_ownerless_human_owned_state_is_impossible():
    """AC-SAFE-028. A raw OVERDUE/INDETERMINATE row with no owner_id is refused by the CHECK."""
    conn = _conn()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expectations (tenant, expectation_id, subject_ref, subject_kind, "
            "subject_observation_ref, expected_type, expected_source, expectation_key, deadline_utc, "
            "originating_timezone, state, version, coverage_gap, owner_id, created_at, updated_at) "
            "VALUES (?, 'e', 'l', 'entity', NULL, 'POD', 'c', 'l::POD', 't', 'UTC', 'INDETERMINATE', "
            "1, 'blind', NULL, 't', 't')", (TENANT,))
        conn.commit()


def test_overdue_and_indeterminate_carry_a_named_human_owner():
    m = _machine(_conn())
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)
    assert m.get(r.expectation.expectation_id).owner_id == HUMAN


def test_a_model_cannot_own_an_expectation():
    m = _machine(_conn())
    with pytest.raises(GuardNotSatisfied):
        _raise(m, owner_id="model:extractor")


def test_an_inactive_owner_fails_closed():
    conn = _conn()
    _human(conn, TENANT, "owner:gone", state="OFFBOARDED")
    m = M8Machine(conn, tenant=TENANT, clock=Clock())
    with pytest.raises(GuardNotSatisfied):
        _raise(m, owner_id="owner:gone")


# ============================================================ duplicate prevention / OCC / tenancy

def test_partial_unique_index_refuses_two_live_raised():
    conn = _conn()
    _human(conn)
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO expectations (tenant, expectation_id, subject_ref, subject_kind, "
        "subject_observation_ref, expected_type, expected_source, expectation_key, deadline_utc, "
        "originating_timezone, state, version, created_at, updated_at) VALUES (?, 'e1', 'l', 'entity', "
        "NULL, 'POD', 'c', 'l::POD', 't', 'UTC', 'RAISED', 1, 't', 't')", (TENANT,))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expectations (tenant, expectation_id, subject_ref, subject_kind, "
            "subject_observation_ref, expected_type, expected_source, expectation_key, deadline_utc, "
            "originating_timezone, state, version, created_at, updated_at) VALUES (?, 'e2', 'l', "
            "'entity', NULL, 'POD', 'c', 'l::POD', 't', 'UTC', 'RAISED', 1, 't', 't')", (TENANT,))
        conn.commit()


def test_a_discharged_key_can_be_raised_again():
    """The partial index permits a NEW live expectation once the prior one left RAISED."""
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _observation(conn, "pod", bound_entity_ref="load:4471")
    m.discharge(r.expectation.expectation_id, observation_id="pod")  # -> DISCHARGED
    r2 = _raise(m)  # same key, now allowed
    assert not r2.coalesced and r2.expectation.expectation_id != r.expectation.expectation_id


def test_occ_refuses_a_stale_version():
    m = _machine(_conn())
    r = _raise(m)
    stale = m.get(r.expectation.expectation_id)
    m.amend_deadline(r.expectation.expectation_id,
                     new_deadline_utc=datetime(2026, 8, 30, tzinfo=timezone.utc))  # bumps version
    with pytest.raises(StateConflict):
        m.cancel(r.expectation.expectation_id, reason="load cancelled", expected=stale)


def test_the_same_key_in_two_tenants_are_two_isolated_expectations():
    conn = _conn()
    a = _machine(conn, "tenant-a")
    b = _machine(conn, "tenant-b")
    ra = a.raise_expectation(subject_ref="load:4471", expected_type="POD", expected_source=CHANNEL,
                             owner_id=HUMAN, originating_timezone="UTC", deadline_utc=DEADLINE)
    rb = b.raise_expectation(subject_ref="load:4471", expected_type="POD", expected_source=CHANNEL,
                             owner_id=HUMAN, originating_timezone="UTC", deadline_utc=DEADLINE)
    assert not ra.coalesced and not rb.coalesced
    assert a.get(rb.expectation.expectation_id) is None  # cross-tenant read fails closed


def test_cross_tenant_coverage_fails_closed():
    """A coverage record in another tenant cannot make this tenant's window healthy."""
    conn = _conn()
    a = _machine(conn, "tenant-a")
    b = _machine(conn, "tenant-b")
    rb = b.raise_expectation(subject_ref="l", expected_type="POD", expected_source=CHANNEL,
                             owner_id=HUMAN, originating_timezone="UTC", deadline_utc=DEADLINE)
    # a healthy coverage in tenant-a for the same channel
    a.record_coverage(coverage_id="cov-a", channel=CHANNEL, window_start=rb.expectation.created_at,
                      window_end=rb.expectation.deadline_utc, health="HEALTHY", probe_source="p")
    res = b.evaluate_deadline(rb.expectation.expectation_id, owner_id=HUMAN)
    assert res.to_state is ExState.INDETERMINATE  # tenant-a's health is invisible to tenant-b


# ============================================================ expiry / never-silent / no-sweep

def test_a_raised_expectation_never_expires():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    with pytest.raises(IllegalTransition):
        m.expire(r.expectation.expectation_id)
    assert m.get(r.expectation.expectation_id).state is ExState.RAISED
    assert "IllegalTransitionAttempted" in [x[0] for x in conn.execute(
        "SELECT event_type FROM security_events WHERE tenant = ?", (TENANT,))]


def test_cancelling_an_indeterminate_expectation_is_illegal():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # INDETERMINATE
    with pytest.raises(IllegalTransition):
        m.cancel(r.expectation.expectation_id, reason="load cancelled")
    assert m.get(r.expectation.expectation_id).state is ExState.INDETERMINATE


def test_terminal_age_expires_an_overdue_expectation():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # OVERDUE
    assert m.expire(r.expectation.expectation_id).to_state is ExState.EXPIRED


def test_terminal_age_timer_expires_via_relay():
    """The terminal-age durable timer fires EX-7 through the relay — expiry is timer-driven and never
    silent."""
    conn = _conn()
    clk = Clock()
    m = _machine(conn, clock=clk)
    r = _raise(m, terminal_age_ms=1000)
    _cover(m, r.expectation, "HEALTHY")
    clk.advance(hours=8)
    relay = TimerRelay(conn, tenant=TENANT, handler=m.handle_timer_fired, relay_id="r", clock=clk)
    relay.run_once()  # deadline -> OVERDUE, arms the terminal-age timer
    assert m.get(r.expectation.expectation_id).state is ExState.OVERDUE
    clk.advance(seconds=5)
    relay.run_once()  # terminal age -> EXPIRED
    assert m.get(r.expectation.expectation_id).state is ExState.EXPIRED
    assert "ExpectationExpired" in _events(conn)


def test_the_machine_defines_no_sweep_or_reaper_method():
    src = (ROOT / "src" / "freight_recon" / "expectation.py").read_text(encoding="utf-8").lower()
    assert "class m8machine" in src  # population proof: the machine source is really loaded (CLAUDE.md §6)
    assert "def sweep" not in src and "def _reap" not in src
    assert "deadline_utc <" not in src  # no age-predicate scan over the expectations table


def test_a_cancelled_expectation_cannot_be_deleted():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.cancel(r.expectation.expectation_id, reason="load cancelled")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM expectations WHERE tenant = ? AND expectation_id = ?",
                     (TENANT, r.expectation.expectation_id))
        conn.commit()


def test_db_requires_expected_source_not_null():
    """entity §21. The observability channel is declared at creation — a NULL expected_source is
    refused by the database, not only by the machine."""
    conn = _conn()
    _human(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expectations (tenant, expectation_id, subject_ref, subject_kind, "
            "subject_observation_ref, expected_type, expected_source, expectation_key, deadline_utc, "
            "originating_timezone, state, version, created_at, updated_at) VALUES (?, 'e', 'l', "
            "'entity', NULL, 'POD', NULL, 'l::POD', 't', 'UTC', 'RAISED', 1, 't', 't')", (TENANT,))
        conn.commit()


def test_no_component_scans_expectations_for_staleness():
    """### NO SWEEP, NO REAPER, NO STALE-EXPECTATION SCAN (machine §37). The machine reads
    durable_timers and its own row by id — never an age predicate over the expectations table."""
    src = (ROOT / "src" / "freight_recon" / "expectation.py").read_text(encoding="utf-8")
    lowered = src.lower()
    assert "time.sleep" not in lowered and "import time" not in lowered
    # no query selecting expectations by an age / deadline-in-the-past predicate.
    assert "from expectations where" in lowered  # it does read its own rows...
    assert "deadline_utc <" not in lowered and "deadline_utc <=" not in lowered
    assert "created_at <" not in lowered


# ============================================================ deadline / DST / re-version

def test_deadline_is_stored_in_utc_and_the_originating_timezone_is_retained():
    m = _machine(_conn())
    r = m.raise_expectation(
        subject_ref="load:1", expected_type="POD", expected_source=CHANNEL, owner_id=HUMAN,
        originating_timezone="America/Denver", appointment_local=datetime(2026, 8, 28, 17, 0, 0))
    exp = m.get(r.expectation.expectation_id)
    assert exp.deadline_utc.endswith("Z") and exp.originating_timezone == "America/Denver"


def test_a_window_evaluated_in_utc_is_illegal():
    conn = _conn()
    m = _machine(conn)
    with pytest.raises(IllegalTransition):
        m.raise_expectation(
            subject_ref="l", expected_type="POD", expected_source=CHANNEL, owner_id=HUMAN,
            originating_timezone="America/Denver",
            appointment_local=datetime(2026, 8, 28, 17, 0, 0), evaluate_in_utc=True)
    # nothing persisted.
    assert conn.execute("SELECT COUNT(*) FROM expectations WHERE tenant = ?",
                        (TENANT,)).fetchone()[0] == 0


def test_the_subject_and_expected_type_cannot_be_mutated():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE expectations SET subject_ref = 'load:9999' WHERE tenant = ? AND "
                     "expectation_id = ?", (TENANT, r.expectation.expectation_id))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE expectations SET expected_type = 'remittance' WHERE tenant = ? AND "
                     "expectation_id = ?", (TENANT, r.expectation.expectation_id))


def test_deadline_history_is_retained():
    m = _machine(_conn())
    r = _raise(m)
    d0 = m.get(r.expectation.expectation_id).deadline_utc
    m.amend_deadline(r.expectation.expectation_id,
                     new_deadline_utc=datetime(2026, 8, 29, tzinfo=timezone.utc))
    m.amend_deadline(r.expectation.expectation_id,
                     new_deadline_utc=datetime(2026, 8, 30, tzinfo=timezone.utc))
    hist = m.get(r.expectation.expectation_id).deadline_history_list
    assert d0 in hist and len(hist) == 2


# ============================================================ durable timer / crash / restart

def test_the_deadline_is_a_durable_timer_scheduled_in_the_raise_commit():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    timers = conn.execute(
        "SELECT timer_kind, aggregate_id FROM durable_timers WHERE tenant = ? AND state = 'SCHEDULED'",
        (TENANT,)).fetchall()
    assert any(t["timer_kind"] == "expectation_deadline"
               and t["aggregate_id"] == r.expectation.expectation_id for t in timers)


def test_restart_re_fires_the_deadline_timer_and_reaches_the_canonical_state():
    conn = _conn()
    clk = Clock()
    m = _machine(conn, clock=clk)
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    # "restart": a fresh machine + relay over the same durable database.
    clk.advance(hours=8)
    m2 = M8Machine(conn, tenant=TENANT, clock=clk)
    relay = TimerRelay(conn, tenant=TENANT, handler=m2.handle_timer_fired, relay_id="r", clock=clk)
    fired = relay.run_once()
    assert fired.fired_count == 1
    assert m2.get(r.expectation.expectation_id).state is ExState.OVERDUE


def test_a_redelivered_timer_is_a_no_op():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _observation(conn, "pod", bound_entity_ref="load:4471")
    m.discharge(r.expectation.expectation_id, observation_id="pod")  # DISCHARGED before the deadline
    trigger = TimerFired(
        tenant=TENANT, timer_id="t", aggregate_type="expectation",
        aggregate_id=r.expectation.expectation_id, timer_kind="expectation_deadline",
        fire_at="t", fired_at="t", payload={"owner_id": HUMAN})
    assert m.handle_timer_fired(trigger) is None  # a fired deadline on a discharged expectation no-ops
    assert m.get(r.expectation.expectation_id).state is ExState.DISCHARGED


def test_discharge_beats_the_deadline_whichever_races():
    """§16. Whether the discharge or the deadline commits first, the final state is DISCHARGED: from
    RAISED it is EX-2, and from OVERDUE/INDETERMINATE the late arrival still discharges (EX-4)."""
    conn = _conn()
    m = _machine(conn)
    # deadline first
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # OVERDUE wins the race
    _observation(conn, "pod", bound_entity_ref="load:4471")
    assert m.discharge(r.expectation.expectation_id, observation_id="pod").to_state is (
        ExState.DISCHARGED)


# ============================================================ replay / co-commit

def test_replay_reconstructs_overdue_from_the_recorded_coverage_not_the_live_channel():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _cover(m, r.expectation, "HEALTHY")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # OVERDUE recorded
    # The coverage table is immutable, so we cannot mutate it — but the rebuild reads events only.
    rc = m.rebuild(r.expectation.expectation_id)
    assert (rc.state is ExState.OVERDUE and rc.new_authority == 0 and rc.external_effects == 0
            and rc.coverage_rewritten == 0 and rc.state_flips == 0)


def test_replay_reconstructs_indeterminate_from_the_recorded_coverage():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # INDETERMINATE
    assert m.rebuild(r.expectation.expectation_id).state is ExState.INDETERMINATE


def test_rebuild_does_not_read_the_coverage_table():
    """### REPLAY NEVER READS THE CURRENT CHANNEL STATE — the rebuild folds events only. Structural:
    rebuild's body queries the outbox, never observation_coverage."""
    import inspect
    from freight_recon.expectation import M8Machine as _M8
    src = inspect.getsource(_M8.rebuild)
    assert "observation_coverage" not in src and "_coverage_verdict" not in src


def test_state_and_event_commit_together():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    n_events = len(_events(conn))
    m.cancel(r.expectation.expectation_id, reason="load cancelled")
    assert m.get(r.expectation.expectation_id).state is ExState.CANCELLED
    assert "ExpectationCancelled" in _events(conn) and len(_events(conn)) == n_events + 1


def test_inbox_idempotency_a_redelivered_event_is_a_no_op():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=HUMAN)  # INDETERMINATE
    env = [e for e in m._event_stream(r.expectation.expectation_id)
           if e.event_name == "ExpectationIndeterminate"][0]
    m.consume_event(env)
    second = m.consume_event(env)
    assert second.consume.is_noop and not second.moved


# ============================================================ checkpoint seam / ship-dark

def test_an_undischarged_expectation_makes_a_field_unknown_never_consistent():
    m = _machine(_conn())
    r = _raise(m)
    proj = m.get(r.expectation.expectation_id).native_projection()
    assert proj.evidence_condition == "unknown" and proj.owed is True
    # unknown is not conflicting (I8) — M8 is not a Conflict detector.
    assert proj.evidence_condition != "conflicting"


def test_a_discharged_expectation_is_consistent():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    _observation(conn, "pod", bound_entity_ref="load:4471")
    m.discharge(r.expectation.expectation_id, observation_id="pod")
    assert m.get(r.expectation.expectation_id).native_projection().evidence_condition == "consistent"


def test_m8_mints_no_gate_decision():
    src = (ROOT / "src" / "freight_recon" / "expectation.py").read_text(encoding="utf-8")
    assert "class M8Machine" in src  # population proof: the machine source is really loaded (CLAUDE.md §6)
    assert ("GateDecision(" not in src and "GateRegistry(" not in src
            and "from .checkpoint" not in src and "import checkpoint" not in src)


def test_m8_ships_dark_no_production_importer():
    pkg = ROOT / "src" / "freight_recon"
    offenders = []
    for path in pkg.rglob("*.py"):
        if path.name in ("expectation.py", "__init__.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if "import expectation" in text or "from .expectation" in text or "from freight_recon.expectation" in text:
            offenders.append(path.name)
    assert offenders == [], f"production importers of the expectation machine: {offenders}"


def test_no_foreign_contract_or_transition_names_in_the_source():
    """The permanent scenario sweeps for foreign contract names. This unit's source names no other
    machine's contract and no EC-*/CM-*/PO-*/RU-*/CF-* transition id, and every `Expectation`+capital
    identifier is one of the seven registered F8 event names (### M8-AQ-1)."""
    import re
    for name in ("expectation.py", "migrations/phase6_expectations.py"):
        src = (ROOT / "src" / "freight_recon" / name).read_text(encoding="utf-8")
        for foreign in ("ExceptionRaised", "ExceptionAgeing", "ExceptionEscalated",
                        "CompensationRequired", "ConflictRaised"):
            assert foreign not in src, f"{name} names the foreign contract {foreign}"
        for tid in re.findall(r"\b(?:EC|CM|PO|RU|CF)-\d+[a-z]*\b", src):
            raise AssertionError(f"{name} names a foreign transition id {tid}")
        for ident in re.findall(r"\bExpectation[A-Z][A-Za-z]*\b", src):
            assert ident in PRODUCED_CONTRACTS, f"{name} names unregistered {ident!r}"


def test_the_neighbouring_machines_are_not_built():
    # M9 (the Exception), M10 (the Compensation) and now M11 (the Policy) LANDED after M8, so `exceptions`,
    # `compensations` and `policies` are now canonical (rule 20 — each corrected from the pre-landing
    # assertion). The still-unbuilt neighbours stay asserted-absent: M12 (rules) and Evidence (P7).
    conn = _conn()
    tables = {t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for forbidden in ("rules", "evidence"):
        assert forbidden not in tables


def test_coverage_health_vocabulary_is_closed():
    assert COVERAGE_HEALTH == ("HEALTHY", "DOWN", "UNKNOWN", "PARTIAL")
    m = _machine(_conn())
    with pytest.raises(MalformedExpectation):
        m.record_coverage(coverage_id="c", channel=CHANNEL, window_start="a", window_end="z",
                          health="ABSENT", probe_source="p")  # ABSENT is not a health value


def test_a_cross_tenant_expectation_read_fails_closed():
    conn = _conn()
    m = _machine(conn)
    r = _raise(m)
    other = M8Machine(conn, tenant="tenant-x", clock=Clock())
    assert other.get(r.expectation.expectation_id) is None
    with pytest.raises(UnknownExpectation):
        other.require(r.expectation.expectation_id)


def test_a_legacy_database_migrates_to_the_canonical_shape():
    """A database reached through the migration path builds to the same shape as a fresh canonical one."""
    from fixtures.legacy_workspace import build_legacy_workspace
    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate
    tmp = Path(tempfile.mkdtemp(prefix="p6m8-legacy-"))
    legacy = tmp / "legacy.db"
    build_legacy_workspace(legacy)
    migrate(str(legacy), assertion=OwnerAssertion(
        actor_id="rasheed@neyma", tenant="acme-brokerage", scope="all legacy rows",
        operational_basis="sole workspace onboarded for Acme; verified against record",
        evidence_reference="docs/onboarding/acme.md"), dry_run=False)
    migrated = sqlite3.connect(legacy)
    migrated.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(migrated)
    assert phase6_expectations_readiness_problems(migrated) == []
    tables = {t[0] for t in migrated.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"expectations", "observation_coverage"} <= tables

    fresh = _conn()

    def shape(conn, table):
        cols = [(r[1], (r[2] or "").upper(), bool(r[3])) for r in conn.execute(
            f"PRAGMA table_info({table})")]
        fks = sorted((r[2], r[3], r[4]) for r in conn.execute(f"PRAGMA foreign_key_list({table})"))
        return cols, fks
    assert shape(migrated, "expectations") == shape(fresh, "expectations")
    assert shape(migrated, "observation_coverage") == shape(fresh, "observation_coverage")
