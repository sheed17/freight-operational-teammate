#!/usr/bin/env python3
"""M8 — the Expectation — deterministic narrative probe.

A load delivers and a POD is owed by 17:00 at the Denver facility, so an Expectation is raised over a
DECLARED channel with the deadline stored in UTC and Denver retained beside it. The deadline passes and
the mailbox was demonstrably healthy the whole window, so the Expectation is OVERDUE and a named human
owns it. The same deadline passes while the tracking feed was down, and it is INDETERMINATE instead,
because accusing the carrier of a failure that was OURS is the one thing this machine may never do. The
POD arrives in month four and it still discharges, because a late POD is still a POD. The appointment
moves and the deadline re-versions with its history rather than being edited. The load cancels and the
expectation cancels through its one canonical transition. And an aged expectation EXPIRES explicitly
and audibly rather than being swept away by a reaper nobody reads.

What matters is not that a deadline can fire — it is that nothing turns an unwatched window into an
accusation, that no sweep makes an obligation quietly stop existing, and that a rebuild months later
reaches the same verdict from the coverage that was recorded at the time.

M8 ships dark — no tracking service, no SLA dashboard, no live channel — so this probe is the ONLY
interface a generated Product-Driver scenario can compose M8's real behaviour through. Every ordering,
concurrency, timing, duplication, crash and replay variation has to be reachable through these
arguments, so the interface is taken seriously:

    --list-cases        the case names, one per line
    --list-dimensions   every dimension flag and every fault name
    --case <case>       run exactly one case (composes with the flags below)
    (no arguments)      run every case; exit 0 only if every one behaved as specified

    --concurrency 1-8   how many arrivals or timers race the one-live-expectation index
    --delay-ms 0-5000   timing skew between them
    --repeat 1-5        duplicate raise / redelivered timer pressure
    --tenants 1-3       isolation pressure
    --age-ms 0-86400000 how far the durable timer is advanced: the deadline, then the terminal age
    --coverage <health> the coverage record the window is judged against: healthy|down|unknown|absent|partial
    --timezone <IANA>   the FACILITY's zone the appointment window is evaluated in
    --confidence 0.0-1.0 the negative control: it must change NOTHING, at 1.0 or 0.0
    --seed <int>        deterministic interleaving; the same seed reproduces the failure
    --inject <fault>    the closed fault set (see --list-dimensions); an unknown fault, or a value out
                        of range, exits 2 with a readable message and NEVER a traceback

### CLOSED MEANS CLOSED. `--inject not-a-real-fault` exits 2. `--inject reopen-expectation` exits 2 —
entity §27 and machine §24 say "Reopening rules. N/A". `--inject correct-expectation` exits 2 — entity
§23 and machine §25 say a wrong expectation is CANCELLED, not corrected. `--inject supersede-expectation`
exits 2 — entity §24 and machine §26 say a re-versioned deadline is NOT a supersession, and no SUPERSEDED
state or ExpectationSuperseded event is registered anywhere. In CONTRAST, `--inject
overdue-without-coverage`, `--inject silent-expiry`, `--inject utc-window`, `--inject expire-raised` and
`--inject cancel-indeterminate` ARE in the vocabulary: they name shapes the corpus defines as ILLEGAL
(machine §15, and the EX-6/EX-7 from-sets), so the machine must be SEEN to REFUSE them under GR-1. A
fault refused as UNKNOWN and a fault refused as ILLEGAL are two different proofs, and M8 owes both.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "eval" / "tests"))

from freight_recon.brake import BrakeStore  # noqa: E402
from freight_recon.event_timers import TimerFired, TimerRelay  # noqa: E402
from freight_recon.expectation import (  # noqa: E402
    PRODUCED_CONTRACTS,
    ExState,
    GuardNotSatisfied,
    IllegalTransition,
    M8Machine,
    MalformedExpectation,
    StateConflict,
    facility_local_deadline,
)
from freight_recon.migrations.phase6_expectations import (  # noqa: E402
    COVERAGE_HEALTH,
    EXPECTATION_STATES,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

HUMANS = ("owner:rasheed", "owner:dana", "owner:sam")
CHANNEL = "carrier-mailbox"

# ---- the closed vocabularies ------------------------------------------------------------------

CASES: tuple[str, ...] = (
    "raise-creates-raised-with-a-declared-channel",
    "an-expectation-cannot-be-raised-without-expected-source",
    "an-expectation-cannot-be-raised-without-a-deadline",
    "raise-stores-deadline-in-utc-and-retains-the-originating-timezone",
    "raise-and-its-durable-timer-are-one-commit",
    "the-expectation-key-is-tenant-subject-and-expected-type",
    "at-most-one-live-raised-expectation-per-key",
    "concurrent-raises-produce-one-live-expectation",
    "a-model-may-propose-an-expectation-but-not-set-the-deadline",
    "a-model-cannot-assert-coverage-health",
    "counterparty-content-cannot-declare-the-channel-healthy",
    "bound-observation-discharges-the-expectation",
    "discharge-records-the-discharge-observation-id",
    "an-unbound-observation-cannot-discharge",
    "a-wrong-subject-observation-cannot-discharge",
    "a-wrong-tenant-observation-cannot-discharge",
    "healthy-coverage-and-a-missed-deadline-is-overdue",
    "overdue-requires-a-healthy-coverage-ref",
    "overdue-without-healthy-coverage-is-structurally-impossible",
    "a-blind-window-is-indeterminate-not-overdue",
    "unknown-coverage-is-indeterminate-not-overdue",
    "absent-coverage-is-not-health",
    "partial-coverage-over-the-window-is-not-health",
    "indeterminate-records-the-coverage-gap",
    "confidence-cannot-turn-indeterminate-into-overdue",
    "overdue-and-indeterminate-carry-a-named-human-owner",
    "an-ownerless-human-owned-state-is-impossible",
    "a-late-arrival-discharges-an-overdue-expectation",
    "a-late-arrival-discharges-an-indeterminate-expectation",
    "late-discharge-is-marked-late",
    "late-evidence-is-never-rejected-because-the-deadline-passed",
    "deadline-change-re-versions-the-expectation",
    "deadline-history-is-retained",
    "an-amendment-is-not-a-supersession",
    "the-subject-and-expected-type-cannot-be-mutated",
    "a-stale-version-cannot-overwrite-newer-state",
    "reason-disappeared-cancels-a-raised-expectation",
    "reason-disappeared-cancels-an-overdue-expectation",
    "cancelling-an-indeterminate-expectation-is-illegal",
    "a-cancelled-expectation-is-retained-never-deleted",
    "terminal-age-expires-an-overdue-expectation",
    "terminal-age-expires-an-indeterminate-expectation",
    "a-raised-expectation-never-expires",
    "expiry-is-never-silent",
    "no-sweep-or-reaper-closes-an-expectation",
    "there-is-no-timed-out-stale-or-resolved-state",
    "discharge-beats-overdue-when-they-race",
    "discharge-beats-indeterminate-when-they-race",
    "the-deadline-is-a-durable-timer-not-a-sleep",
    "restart-re-fires-the-deadline-timer",
    "restart-preserves-the-raised-expectation",
    "restart-after-overdue-reaches-the-canonical-state",
    "a-redelivered-timer-is-a-no-op",
    "timer-coverage-read-and-state-are-one-commit",
    "persistence-failure-rolls-back-the-deadline-decision",
    "state-and-event-co-commit",
    "replay-reconstructs-overdue-from-the-recorded-coverage",
    "replay-reconstructs-indeterminate-from-the-recorded-coverage",
    "replay-does-not-read-the-current-channel-state",
    "replay-creates-no-new-authority-and-no-effect",
    "an-appointment-window-is-evaluated-in-facility-local-time",
    "a-dst-boundary-does-not-move-the-deadline",
    "a-window-evaluated-in-utc-instead-of-facility-local-is-wrong",
    "m8-mints-no-gate-decision",
    "an-expectation-owes-it-does-not-authorize",
    "an-undischarged-expectation-makes-a-field-unknown-never-consistent",
    "discharge-and-indeterminate-detection-continue-under-a-brake",
    "a-brake-never-fabricates-overdue-state",
    "tenant-isolation",
    "cross-tenant-identical-expectation-key",
    "cross-tenant-observation-cannot-discharge",
    "cross-tenant-coverage-record-fails-closed",
    "cross-tenant-owner-fails-closed",
    "occ-on-expectation-version",
    "inbox-idempotency",
    "database-invariants",
    "malformed-expectation-fails-closed",
    "the-m5-observation-machine-is-not-rewritten",
    "the-m3-awaiting-observation-seam-is-unchanged",
    "the-m7-conflict-machine-is-not-rewritten",
    "an-overdue-expectation-is-not-automatically-a-conflict",
    "m9-m10-m11-and-m12-are-not-built",
)

# The closed fault vocabulary — every member named by the canonical machine, the entity spec, the
# target spec, an ADR or the event registry. `phase` is used only to refuse an INCOHERENT (case, fault)
# combination rather than run it degenerately.
FAULTS: dict[str, str] = {
    "none": "any",
    "raise": "raise",
    "missing-expected-source": "raise",
    "missing-deadline": "raise",
    "missing-key": "raise",
    "duplicate-raise": "raise",
    "concurrent-raise": "raise",
    "bound-discharge": "discharge",
    "unbound-discharge": "discharge",
    "wrong-subject-discharge": "discharge",
    "wrong-tenant-discharge": "discharge",
    "late-discharge": "discharge",
    "reject-late": "discharge",
    "deadline-passed": "deadline",
    "coverage-healthy": "deadline",
    "coverage-down": "deadline",
    "coverage-unknown": "deadline",
    "coverage-absent": "deadline",
    "coverage-partial": "deadline",
    "model-set-coverage": "deadline",
    "counterparty-coverage": "deadline",
    "confidence-overdue": "deadline",
    "overdue-without-coverage": "deadline",       # ILLEGAL (machine §15) — refused under GR-1
    "ownerless-overdue": "deadline",
    "deadline-change": "amend",
    "subject-mutation": "amend",
    "type-mutation": "amend",
    "stale-version": "amend",
    "reason-disappeared": "cancel",
    "cancel-indeterminate": "cancel",             # ILLEGAL — EX-6 from-set excludes INDETERMINATE
    "terminal-age": "expire",
    "expire-raised": "expire",                    # ILLEGAL — EX-7 from-set excludes RAISED
    "silent-expiry": "expire",                    # ILLEGAL — expiry is never silent
    "sweep-close": "expire",                      # ILLEGAL — no sweep/reaper
    "discharge-vs-deadline-race": "race",
    "restart-before-deadline": "restart",
    "restart-after-overdue": "restart",
    "replay": "replay",
    "replay-from-live-channel": "replay",         # ILLEGAL — replay never reads the live channel
    "dst-boundary": "timezone",
    "utc-window": "timezone",                     # ILLEGAL — window evaluated in UTC
    "occ-expectation": "occ",
    "cross-tenant-observation": "tenant",
    "cross-tenant-coverage": "tenant",
    "cross-tenant-owner": "tenant",
    "malformed-expectation": "raise",
    "persistence-failure": "deadline",
    "redelivered-timer": "restart",
    "brake": "brake",
    "gate-mint": "gate",
    "reorder-stream": "replay",
}

DIMENSIONS: tuple[str, ...] = (
    "concurrency", "delay-ms", "repeat", "tenants", "age-ms", "coverage", "timezone", "confidence",
    "seed", "inject",
)

COVERAGE_VALUES = ("healthy", "down", "unknown", "absent", "partial")


# ### THE INVARIANT SENTENCES THE VERIFICATION SCENARIO MATCHES AS LITERAL SUBSTRINGS.
_SIG: dict[str, str] = {
    "raise-creates-raised-with-a-declared-channel":
        "THE OBSERVABILITY CHANNEL IS DECLARED AT CREATION OR THERE IS NO EXPECTATION",
    "an-expectation-cannot-be-raised-without-expected-source":
        "THE OBSERVABILITY CHANNEL IS DECLARED AT CREATION OR THERE IS NO EXPECTATION",
    "an-expectation-cannot-be-raised-without-a-deadline":
        "AN EXPECTATION IS A DURABLE COMMITMENT THAT SOMETHING SHOULD BE OBSERVED BY A DEADLINE",
    "raise-stores-deadline-in-utc-and-retains-the-originating-timezone":
        "A DEADLINE IS STORED IN UTC AND THE ORIGINATING TIMEZONE IS RETAINED",
    "raise-and-its-durable-timer-are-one-commit":
        "RAISING THE EXPECTATION AND SCHEDULING ITS DURABLE TIMER ARE ONE COMMIT",
    "the-expectation-key-is-tenant-subject-and-expected-type":
        "AT MOST ONE LIVE RAISED EXPECTATION PER TENANT AND EXPECTATION KEY",
    "at-most-one-live-raised-expectation-per-key":
        "AT MOST ONE LIVE RAISED EXPECTATION PER TENANT AND EXPECTATION KEY",
    "concurrent-raises-produce-one-live-expectation":
        "CONCURRENT RAISES PRODUCE ONE LIVE EXPECTATION",
    "a-model-may-propose-an-expectation-but-not-set-the-deadline":
        "A MODEL MAY PROPOSE AN EXPECTATION; THE DEADLINE AND THE COVERAGE ARE RUNTIME-SET",
    "a-model-cannot-assert-coverage-health":
        "A MODEL MAY PROPOSE AN EXPECTATION; THE DEADLINE AND THE COVERAGE ARE RUNTIME-SET",
    "counterparty-content-cannot-declare-the-channel-healthy":
        "COUNTERPARTY CONTENT NEVER ASSERTS THAT THE CHANNEL WAS HEALTHY",
    "bound-observation-discharges-the-expectation":
        "A BOUND OBSERVATION DISCHARGES THE EXPECTATION",
    "discharge-records-the-discharge-observation-id":
        "A BOUND OBSERVATION DISCHARGES THE EXPECTATION",
    "an-unbound-observation-cannot-discharge": "AN UNBOUND OBSERVATION NEVER DISCHARGES",
    "a-wrong-subject-observation-cannot-discharge": "A WRONG-SUBJECT OBSERVATION NEVER DISCHARGES",
    "a-wrong-tenant-observation-cannot-discharge": "A WRONG-TENANT OBSERVATION NEVER DISCHARGES",
    "healthy-coverage-and-a-missed-deadline-is-overdue":
        "A MISSED DEADLINE OVER A DEMONSTRABLY HEALTHY WINDOW IS OVERDUE",
    "overdue-requires-a-healthy-coverage-ref":
        "OVERDUE WITHOUT A HEALTHY coverage_ref IS STRUCTURALLY IMPOSSIBLE",
    "overdue-without-healthy-coverage-is-structurally-impossible":
        "OVERDUE WITHOUT A HEALTHY coverage_ref IS STRUCTURALLY IMPOSSIBLE",
    "a-blind-window-is-indeterminate-not-overdue":
        "A MISSED DEADLINE OVER A BLIND WINDOW IS INDETERMINATE, NOT OVERDUE",
    "unknown-coverage-is-indeterminate-not-overdue": "UNKNOWN COVERAGE IS INDETERMINATE, NOT OVERDUE",
    "absent-coverage-is-not-health": "THE ABSENCE OF A COVERAGE RECORD IS NOT HEALTH",
    "partial-coverage-over-the-window-is-not-health": "PARTIAL COVERAGE OVER THE WINDOW IS NOT HEALTH",
    "indeterminate-records-the-coverage-gap":
        "A MISSED DEADLINE OVER A BLIND WINDOW IS INDETERMINATE, NOT OVERDUE",
    "confidence-cannot-turn-indeterminate-into-overdue":
        "CONFIDENCE NEVER TURNS INDETERMINATE INTO OVERDUE",
    "overdue-and-indeterminate-carry-a-named-human-owner":
        "AN OVERDUE OR INDETERMINATE EXPECTATION HAS A NAMED HUMAN OWNER",
    "an-ownerless-human-owned-state-is-impossible":
        "AN OWNERLESS HUMAN-OWNED STATE IS STRUCTURALLY IMPOSSIBLE",
    "a-late-arrival-discharges-an-overdue-expectation":
        "A LATE ARRIVAL DISCHARGES AN OVERDUE EXPECTATION",
    "a-late-arrival-discharges-an-indeterminate-expectation":
        "A LATE ARRIVAL DISCHARGES AN INDETERMINATE EXPECTATION",
    "late-discharge-is-marked-late": "A LATE ARRIVAL IS ALWAYS ACCEPTED",
    "late-evidence-is-never-rejected-because-the-deadline-passed":
        "LATE EVIDENCE IS NEVER REJECTED BECAUSE THE DEADLINE PASSED",
    "deadline-change-re-versions-the-expectation":
        "A DEADLINE AMENDMENT RE-VERSIONS AND IS NOT A SUPERSESSION",
    "deadline-history-is-retained": "THE DEADLINE HISTORY IS RETAINED",
    "an-amendment-is-not-a-supersession": "A DEADLINE AMENDMENT RE-VERSIONS AND IS NOT A SUPERSESSION",
    "the-subject-and-expected-type-cannot-be-mutated":
        "THE SUBJECT AND THE EXPECTED TYPE CANNOT BE MUTATED",
    "a-stale-version-cannot-overwrite-newer-state": "A STALE VERSION NEVER OVERWRITES NEWER STATE",
    "reason-disappeared-cancels-a-raised-expectation":
        "A DISAPPEARED REASON CANCELS THROUGH EX-6 AND NOTHING ELSE",
    "reason-disappeared-cancels-an-overdue-expectation":
        "A DISAPPEARED REASON CANCELS THROUGH EX-6 AND NOTHING ELSE",
    "cancelling-an-indeterminate-expectation-is-illegal":
        "CANCELLING AN INDETERMINATE EXPECTATION IS AN ILLEGAL TRANSITION",
    "a-cancelled-expectation-is-retained-never-deleted":
        "A CANCELLED EXPECTATION IS RETAINED, NEVER DELETED",
    "terminal-age-expires-an-overdue-expectation":
        "TERMINAL AGE EXPIRES AN OVERDUE OR INDETERMINATE EXPECTATION",
    "terminal-age-expires-an-indeterminate-expectation":
        "TERMINAL AGE EXPIRES AN OVERDUE OR INDETERMINATE EXPECTATION",
    "a-raised-expectation-never-expires": "A RAISED EXPECTATION NEVER EXPIRES",
    "expiry-is-never-silent": "EXPIRY IS NEVER SILENT",
    "no-sweep-or-reaper-closes-an-expectation": "NO SWEEP, REAPER OR SCAN CLOSES AN EXPECTATION",
    "there-is-no-timed-out-stale-or-resolved-state": "THERE IS NO TIMED_OUT, STALE OR RESOLVED STATE",
    "discharge-beats-overdue-when-they-race": "DISCHARGE BEATS OVERDUE AND INDETERMINATE WHEN THEY RACE",
    "discharge-beats-indeterminate-when-they-race":
        "DISCHARGE BEATS OVERDUE AND INDETERMINATE WHEN THEY RACE",
    "the-deadline-is-a-durable-timer-not-a-sleep":
        "THE DEADLINE IS A DURABLE TIMER, NEVER AN IN-MEMORY SLEEP OR SWEEP",
    "restart-re-fires-the-deadline-timer": "A RESTART RE-FIRES THE DEADLINE TIMER",
    "restart-preserves-the-raised-expectation": "A RESTART LEAVES THE RAISED EXPECTATION RAISED",
    "restart-after-overdue-reaches-the-canonical-state": "A RESTART RE-FIRES THE DEADLINE TIMER",
    "a-redelivered-timer-is-a-no-op": "A REDELIVERED TIMER IS A NO-OP",
    "timer-coverage-read-and-state-are-one-commit":
        "THE TIMER, THE COVERAGE READ AND THE RESULTING STATE ARE ONE COMMIT",
    "persistence-failure-rolls-back-the-deadline-decision":
        "A PERSISTENCE FAILURE LEAVES NO HALF-DECIDED DEADLINE",
    "state-and-event-co-commit": "THE STATE ROW AND ITS EVENT COMMIT TOGETHER",
    "replay-reconstructs-overdue-from-the-recorded-coverage":
        "REPLAY REBUILDS OVERDUE AND INDETERMINATE FROM THE RECORDED COVERAGE",
    "replay-reconstructs-indeterminate-from-the-recorded-coverage":
        "REPLAY REBUILDS OVERDUE AND INDETERMINATE FROM THE RECORDED COVERAGE",
    "replay-does-not-read-the-current-channel-state": "REPLAY NEVER READS THE CURRENT CHANNEL STATE",
    "replay-creates-no-new-authority-and-no-effect":
        "replay: 0 new authority, 0 external effects, 0 coverage rewritten, 0 state flips",
    "an-appointment-window-is-evaluated-in-facility-local-time":
        "AN APPOINTMENT WINDOW IS EVALUATED IN THE FACILITY'S LOCAL TIMEZONE",
    "a-dst-boundary-does-not-move-the-deadline": "A DST BOUNDARY DOES NOT MOVE THE DEADLINE",
    "a-window-evaluated-in-utc-instead-of-facility-local-is-wrong":
        "EVALUATING THE WINDOW IN UTC INSTEAD OF FACILITY-LOCAL IS WRONG",
    "m8-mints-no-gate-decision": "M8 MINTS NO GATE DECISION",
    "an-expectation-owes-it-does-not-authorize":
        "AN EXPECTATION OWES SOMETHING; IT DOES NOT AUTHORIZE ANYTHING",
    "an-undischarged-expectation-makes-a-field-unknown-never-consistent":
        "AN UNDISCHARGED EXPECTATION MAKES A FIELD unknown, NEVER consistent",
    "discharge-and-indeterminate-detection-continue-under-a-brake":
        "DISCHARGE AND INDETERMINATE DETECTION CONTINUE UNDER A BRAKE",
    "a-brake-never-fabricates-overdue-state": "A BRAKE NEVER FABRICATES OVERDUE STATE",
    "tenant-isolation": "THE SAME EXPECTATION KEY IN TWO TENANTS ARE TWO ISOLATED EXPECTATIONS",
    "cross-tenant-identical-expectation-key":
        "THE SAME EXPECTATION KEY IN TWO TENANTS ARE TWO ISOLATED EXPECTATIONS",
    "cross-tenant-observation-cannot-discharge": "A WRONG-TENANT OBSERVATION NEVER DISCHARGES",
    "cross-tenant-coverage-record-fails-closed": "A CROSS-TENANT COVERAGE RECORD FAILS CLOSED",
    "cross-tenant-owner-fails-closed": "AN OWNERLESS HUMAN-OWNED STATE IS STRUCTURALLY IMPOSSIBLE",
    "occ-on-expectation-version": "A LOST UPDATE ON AN EXPECTATION IS REFUSED",
    "inbox-idempotency": "A REDELIVERED TIMER IS A NO-OP",
    "database-invariants": "THE DATABASE ENFORCES THE EXPECTATION INVARIANTS",
    "malformed-expectation-fails-closed": "THE DATABASE ENFORCES THE EXPECTATION INVARIANTS",
    "the-m5-observation-machine-is-not-rewritten": "THE M5 OBSERVATION MACHINE IS UNCHANGED",
    "the-m3-awaiting-observation-seam-is-unchanged": "THE M3 AWAITING_OBSERVATION SEAM IS UNCHANGED",
    "the-m7-conflict-machine-is-not-rewritten": "THE M7 CONFLICT MACHINE IS UNCHANGED",
    "an-overdue-expectation-is-not-automatically-a-conflict":
        "AN OVERDUE EXPECTATION IS NOT AUTOMATICALLY A CONFLICT",
    "m9-m10-m11-and-m12-are-not-built": "THE M9, M10, M11 AND M12 MACHINES ARE NOT BUILT",
}

# The whole-run headline plus the lines not primarily owned by one case, so a full battery cannot pass
# while any required sentence is silently missing.
_EXTRA_REQUIRED: tuple[str, ...] = (
    "AN EXPECTATION IS A DURABLE COMMITMENT THAT SOMETHING SHOULD BE OBSERVED BY A DEADLINE",
    "OVERDUE MEANS IT NEVER CAME; INDETERMINATE MEANS WE WERE NOT WATCHING",
    "WE DO NOT ACCUSE A COUNTERPARTY OF A FAILURE THAT WAS OURS",
    "A LATE ARRIVAL IS ALWAYS ACCEPTED",
    "A LEGACY DATABASE MIGRATES TO THE CANONICAL EXPECTATION SHAPE",
)

_REQUIRED_ON_FULL_RUN: tuple[str, ...] = tuple(dict.fromkeys(
    list(_SIG.values()) + list(_EXTRA_REQUIRED)))


# ---- harness -----------------------------------------------------------------------------------

class ProbeExit(Exception):
    """A malformed-input refusal: exit code 2, a readable message, and NEVER a traceback."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Clock:
    """A deterministic, monotonically-advancing clock."""

    def __init__(self, base: datetime) -> None:
        self._t = base

    def __call__(self) -> datetime:
        self._t += timedelta(milliseconds=1)
        return self._t

    @property
    def now(self) -> datetime:
        return self._t

    def advance(self, **kw: int) -> None:
        self._t += timedelta(**kw)


@dataclass
class Ctx:
    concurrency: int = 1
    delay_ms: int = 0
    repeat: int = 1
    tenants: int = 1
    age_ms: int = 0
    coverage: str = "healthy"
    timezone: str = "America/Denver"
    confidence: float = 0.5
    seed: int = 1
    inject: str = "none"
    rng: random.Random = field(default_factory=lambda: random.Random(1))


@dataclass
class CaseResult:
    ok: bool
    lines: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)


class World:
    """One canonical database, a controllable clock and a pool of recorded humans per tenant.

    Observations and coverage rows are inserted through the machine's own writer or plain SQL — the
    probe never imports the M5/M6/M7 machines, so their ship-dark posture is untouched."""

    def __init__(self, ctx: Ctx, tmp: Path) -> None:
        self.ctx = ctx
        self.path = tmp / "ex.db"
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        enable_and_verify_foreign_keys(self.conn)
        create_canonical_schema(self.conn)
        enable_and_verify_foreign_keys(self.conn)
        self.clock = Clock(datetime(2026, 8, 28, 8, 0, 0, tzinfo=timezone.utc))
        self._humans: set[tuple[str, str]] = set()
        self._obs: set[tuple[str, str]] = set()

    def tenant(self, i: int = 0) -> str:
        return f"tenant-{'abc'[i % 3]}" + ("" if self.ctx.tenants == 1 else str(i))

    def human(self, tenant: str, human_id: str = HUMANS[0], *, state: str = "ACTIVE") -> str:
        key = (tenant, human_id)
        if key not in self._humans:
            off = "off" if state == "OFFBOARDED" else None
            self.conn.execute(
                "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, "
                "authority_role, state, recorded_at, recorded_by, recorded_by_kind, offboarded_at) "
                "VALUES (?,?,?,?, ?, ?, ?, 'human', ?)",
                (tenant, human_id, human_id, "AUTHORIZED_HUMAN", state, "2026-08-20T09:00:00.000Z",
                 "founder", off))
            self.conn.commit()
            self._humans.add(key)
        return human_id

    def observation(self, tenant: str, oid: str, *, bound: str = "load:4471",
                    state: str = "BOUND") -> str:
        if (tenant, oid) not in self._obs:
            self.conn.execute(
                "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, "
                "external_id, content_digest, raw_value, as_of, received_at, state, version, "
                "provenance_class, bound_entity_ref, created_at, updated_at) VALUES (?,?, 'carrier', "
                "?, ?, 'v', 't', 't', ?, 1, 'SYSTEM_IMPORTED', ?, 't', 't')",
                (tenant, oid, oid, oid, state, bound))
            self.conn.commit()
            self._obs.add((tenant, oid))
        return oid

    def machine(self, tenant: str | None = None) -> M8Machine:
        t = tenant or self.tenant()
        self.human(t)
        return M8Machine(self.conn, tenant=t, clock=self.clock)

    def raised(self, m: M8Machine, *, subject="load:4471", etype="POD", source=CHANNEL,
               owner=None, deadline=None, terminal_age_ms=None, **kw):
        owner = owner or self.human(m.tenant)
        deadline = deadline or datetime(2026, 8, 28, 17, 0, 0, tzinfo=timezone.utc)
        return m.raise_expectation(
            subject_ref=subject, expected_type=etype, expected_source=source, owner_id=owner,
            originating_timezone="UTC", deadline_utc=deadline, terminal_age_ms=terminal_age_ms, **kw)

    def cover(self, m: M8Machine, exp, health: str, *, coverage_id=None, partial_span=False):
        ws = "2026-08-28T16:00:00.000Z" if partial_span else exp.created_at
        cid = coverage_id or f"cov-{exp.expectation_id}"
        return m.record_coverage(coverage_id=cid, channel=exp.expected_source,
                                 window_start=ws, window_end=exp.deadline_utc, health=health,
                                 probe_source="probe")

    def expectations(self, tenant: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM expectations WHERE tenant = ?", (tenant,)).fetchone()[0]

    def live(self, tenant: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM expectations WHERE tenant = ? AND state = 'RAISED'",
            (tenant,)).fetchone()[0]

    def events(self, tenant: str, name: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = ?",
            (tenant, name)).fetchone()[0]

    def security(self, tenant: str) -> list[str]:
        return [r["event_type"] for r in self.conn.execute(
            "SELECT event_type FROM security_events WHERE tenant = ?", (tenant,))]


def _world(ctx: Ctx) -> World:
    return World(ctx, Path(tempfile.mkdtemp(prefix="p6m8-")))


def _health(ctx: Ctx) -> str:
    return {"healthy": "HEALTHY", "down": "DOWN", "unknown": "UNKNOWN",
            "partial": "PARTIAL"}.get(ctx.coverage, "HEALTHY")


# ---- the checkpoint seam (the probe FEEDS the one gate authority, never duplicates it) ----------

def _checkpoint_unknown():
    """The ProvenancedFact seam: a material fact whose evidence_condition is UNKNOWN (what an
    undischarged Expectation projects), composed INTO the approval so there is no fingerprint drift —
    step 4 refuses it as EVIDENCE_NOT_CONSISTENT (entity §38). `unknown` is not `conflicting` (I8)."""
    import dataclasses

    from phase3_kit import (T_A, live_reader, make_approval, make_effect, make_facts, make_kernel,
                            make_store)
    from freight_recon.checkpoint import (CheckpointInputs, CheckpointRequest, EvidenceCondition,
                                          run_checkpoint)
    tmp = Path(tempfile.mkdtemp(prefix="p6m8-ckpt-"))
    store = make_store(tmp, T_A)
    kernel, clock = make_kernel(store)
    effect = make_effect()
    versions = {"load:4471": 17}
    facts = make_facts()
    facts["amount"] = dataclasses.replace(facts["amount"],
                                          evidence_condition=EvidenceCondition.UNKNOWN)
    approval = make_approval(effect, facts, versions, clock)
    inputs = CheckpointInputs(
        material_facts_reader=live_reader(lambda: dict(facts)),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=live_reader(lambda: {"status": "DELIVERED"}),
        entity_version_reader=live_reader(lambda: dict(versions)), approval=approval)
    request = CheckpointRequest(effect=effect, actor="pipeline",
                               accountable_owner="owner:rasheed", target_entity_ref="load:4471")
    outcome = run_checkpoint(kernel, request, inputs)
    grants = store.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
    store.close()
    return outcome, grants


# ---- helpers for common flows ------------------------------------------------------------------

def _overdue(w: World, m: M8Machine, *, owner=None):
    r = w.raised(m, owner=owner)
    w.cover(m, r.expectation, "HEALTHY")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=owner or w.human(m.tenant))
    return r.expectation.expectation_id


def _indeterminate(w: World, m: M8Machine, *, health="DOWN", owner=None, cover=True):
    r = w.raised(m, owner=owner)
    if cover and health != "ABSENT":
        w.cover(m, r.expectation, health)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=owner or w.human(m.tenant))
    return r.expectation.expectation_id


# ---- the cases ---------------------------------------------------------------------------------

def case_raise_creates_raised_with_a_declared_channel(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    c = m.get(r.expectation.expectation_id)
    ok = (r.transition_id == "EX-1" and c.state is ExState.RAISED and c.expected_source == CHANNEL
          and r.event_names == ("ExpectationRaised",))
    if not ok:
        return CaseResult(False, markers=["### EXPECTATION RAISED WITHOUT A DECLARED CHANNEL ###"])
    return CaseResult(True, lines=[
        _SIG["raise-creates-raised-with-a-declared-channel"],
        "AN EXPECTATION IS A DURABLE COMMITMENT THAT SOMETHING SHOULD BE OBSERVED BY A DEADLINE",
        "OVERDUE MEANS IT NEVER CAME; INDETERMINATE MEANS WE WERE NOT WATCHING"])


def case_an_expectation_cannot_be_raised_without_expected_source(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.raised(m, source="")
    except MalformedExpectation:
        refused = True
    ok = refused and w.expectations(m.tenant) == 0
    if not ok:
        return CaseResult(False, markers=["### EXPECTATION RAISED WITHOUT A DECLARED CHANNEL ###"])
    return CaseResult(True, lines=[_SIG["an-expectation-cannot-be-raised-without-expected-source"]])


def case_an_expectation_cannot_be_raised_without_a_deadline(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        m.raise_expectation(subject_ref="l", expected_type="POD", expected_source=CHANNEL,
                            owner_id=w.human(m.tenant), originating_timezone="UTC")
    except MalformedExpectation:
        refused = True
    ok = refused and w.expectations(m.tenant) == 0
    if not ok:
        return CaseResult(False, markers=["### EXPECTATION RAISED WITHOUT A DEADLINE ###"])
    return CaseResult(True, lines=[_SIG["an-expectation-cannot-be-raised-without-a-deadline"]])


def case_raise_stores_deadline_in_utc_and_retains_the_originating_timezone(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_expectation(subject_ref="load:1", expected_type="POD", expected_source=CHANNEL,
                            owner_id=w.human(m.tenant), originating_timezone="America/Denver",
                            appointment_local=datetime(2026, 8, 28, 17, 0, 0))
    c = m.get(r.expectation.expectation_id)
    ok = c.deadline_utc.endswith("Z") and c.originating_timezone == "America/Denver"
    if not ok:
        return CaseResult(False, markers=["### MISS ### deadline not UTC or tz not retained"])
    return CaseResult(True, lines=[_SIG["raise-stores-deadline-in-utc-and-retains-the-originating-timezone"]])


def case_raise_and_its_durable_timer_are_one_commit(w: World) -> CaseResult:
    m = w.machine()
    before = w.events(m.tenant, "ExpectationRaised")
    r = w.raised(m)
    timers = w.conn.execute(
        "SELECT COUNT(*) FROM durable_timers WHERE tenant = ? AND aggregate_id = ? AND "
        "timer_kind = 'expectation_deadline'", (m.tenant, r.expectation.expectation_id)).fetchone()[0]
    ok = (m.get(r.expectation.expectation_id) is not None and timers == 1
          and w.events(m.tenant, "ExpectationRaised") == before + 1)
    if not ok:
        return CaseResult(False, markers=[f"### MISS ### row/timer/event not one commit timers={timers}"])
    return CaseResult(True, lines=[_SIG["raise-and-its-durable-timer-are-one-commit"]])


def case_the_expectation_key_is_tenant_subject_and_expected_type(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m, subject="load:4471", etype="POD")
    ok = m.get(r.expectation.expectation_id).expectation_key == "load:4471::POD"
    if not ok:
        return CaseResult(False, markers=["### MISS ### expectation_key not (subject, expected_type)"])
    return CaseResult(True, lines=[_SIG["the-expectation-key-is-tenant-subject-and-expected-type"]])


def case_at_most_one_live_raised_expectation_per_key(w: World) -> CaseResult:
    m = w.machine()
    r1 = w.raised(m)
    r2 = w.raised(m)
    ok = r2.coalesced and r2.expectation.expectation_id == r1.expectation.expectation_id and w.live(
        m.tenant) == 1
    if not ok:
        return CaseResult(False, markers=["### TWO LIVE RAISED EXPECTATIONS FOR ONE KEY ###"])
    return CaseResult(True, lines=[_SIG["at-most-one-live-raised-expectation-per-key"]])


def case_concurrent_raises_produce_one_live_expectation(w: World) -> CaseResult:
    m = w.machine()
    n = max(2, w.ctx.concurrency)
    for _ in range(n * w.ctx.repeat):
        w.raised(m)
    ok = w.live(m.tenant) == 1
    if not ok:
        return CaseResult(False, markers=["### TWO LIVE RAISED EXPECTATIONS FOR ONE KEY ###"])
    return CaseResult(True, lines=[_SIG["concurrent-raises-produce-one-live-expectation"]])


def case_a_model_may_propose_an_expectation_but_not_set_the_deadline(w: World) -> CaseResult:
    m = w.machine()
    # a model may propose (system actor raises on its behalf), but a model may not OWN it, and the
    # confidence/model content never sets the deadline or the coverage verdict.
    model_rejected = False
    try:
        w.raised(m, owner="model:extractor")
    except GuardNotSatisfied:
        model_rejected = True
    r = w.raised(m, proposed_confidence=1.0)  # a proposal with confidence 1.0
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=w.human(m.tenant))  # absent coverage
    ok = model_rejected and m.get(r.expectation.expectation_id).state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### MODEL SET COVERAGE TRUTH ###"])
    return CaseResult(True, lines=[_SIG["a-model-may-propose-an-expectation-but-not-set-the-deadline"]])


def case_a_model_cannot_assert_coverage_health(w: World) -> CaseResult:
    m = w.machine()
    # There is NO parameter by which model/content asserts health; the verdict reads the persisted
    # coverage table. With absent coverage a confident proposal is still INDETERMINATE.
    r = w.raised(m, proposed_confidence=1.0)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=w.human(m.tenant))
    ok = m.get(r.expectation.expectation_id).state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### MODEL SET COVERAGE TRUTH ###"])
    return CaseResult(True, lines=[_SIG["a-model-cannot-assert-coverage-health"]])


def case_counterparty_content_cannot_declare_the_channel_healthy(w: World) -> CaseResult:
    m = w.machine()
    # A counterparty's content ("we sent it, the channel was fine") is not coverage — coverage is a
    # persisted probe assertion. Down coverage over the window is INDETERMINATE regardless of content.
    r = w.raised(m)
    w.cover(m, r.expectation, "DOWN")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=w.human(m.tenant))
    ok = m.get(r.expectation.expectation_id).state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### COUNTERPARTY ASSERTED CHANNEL HEALTH ###"])
    return CaseResult(True, lines=[_SIG["counterparty-content-cannot-declare-the-channel-healthy"]])


def case_bound_observation_discharges_the_expectation(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    w.observation(m.tenant, "pod-1", bound="load:4471")
    d = m.discharge(r.expectation.expectation_id, observation_id="pod-1")
    ok = d.to_state is ExState.DISCHARGED and d.event_producer == "EX-2"
    if not ok:
        return CaseResult(False, markers=["### MISS ### bound observation did not discharge"])
    return CaseResult(True, lines=[_SIG["bound-observation-discharges-the-expectation"]])


def case_discharge_records_the_discharge_observation_id(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    w.observation(m.tenant, "pod-2", bound="load:4471")
    m.discharge(r.expectation.expectation_id, observation_id="pod-2")
    ok = m.get(r.expectation.expectation_id).discharge_observation_id == "pod-2"
    if not ok:
        return CaseResult(False, markers=["### MISS ### discharge_observation_id not recorded"])
    return CaseResult(True, lines=[_SIG["discharge-records-the-discharge-observation-id"]])


def case_an_unbound_observation_cannot_discharge(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    w.observation(m.tenant, "obs-unbound", bound="load:4471", state="RECEIVED")
    refused = False
    try:
        m.discharge(r.expectation.expectation_id, observation_id="obs-unbound")
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(r.expectation.expectation_id).state is ExState.RAISED
    if not ok:
        return CaseResult(False, markers=["### UNBOUND OBSERVATION DISCHARGED ###"])
    return CaseResult(True, lines=[_SIG["an-unbound-observation-cannot-discharge"]])


def case_a_wrong_subject_observation_cannot_discharge(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m, subject="load:4471")
    w.observation(m.tenant, "obs-other", bound="load:9999")
    refused = False
    try:
        m.discharge(r.expectation.expectation_id, observation_id="obs-other")
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(r.expectation.expectation_id).state is ExState.RAISED
    if not ok:
        return CaseResult(False, markers=["### WRONG-SUBJECT OBSERVATION DISCHARGED ###"])
    return CaseResult(True, lines=[_SIG["a-wrong-subject-observation-cannot-discharge"]])


def case_a_wrong_tenant_observation_cannot_discharge(w: World) -> CaseResult:
    m = w.machine("tenant-a")
    other = "tenant-b"
    w.human(other)
    w.observation(other, "obs-b", bound="load:4471")
    r = w.raised(m)
    refused = False
    try:
        m.discharge(r.expectation.expectation_id, observation_id="obs-b")
    except GuardNotSatisfied:
        refused = True
    ok = refused and m.get(r.expectation.expectation_id).state is ExState.RAISED
    if not ok:
        return CaseResult(False, markers=["### WRONG-TENANT OBSERVATION DISCHARGED ###"])
    return CaseResult(True, lines=[_SIG["a-wrong-tenant-observation-cannot-discharge"]])


def case_healthy_coverage_and_a_missed_deadline_is_overdue(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    ok = m.get(cid).state is ExState.OVERDUE
    if not ok:
        return CaseResult(False, markers=["### MISS ### healthy window did not go OVERDUE"])
    return CaseResult(True, lines=[_SIG["healthy-coverage-and-a-missed-deadline-is-overdue"],
                                   "WE DO NOT ACCUSE A COUNTERPARTY OF A FAILURE THAT WAS OURS"])


def case_overdue_requires_a_healthy_coverage_ref(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="DOWN")
    # the machine will not mint OVERDUE without healthy coverage — insisting is refused under GR-1.
    r2 = w.raised(m, subject="load:2")
    w.cover(m, m.get(r2.expectation.expectation_id), "DOWN", coverage_id="cov-2")
    refused = False
    try:
        m.evaluate_deadline(r2.expectation.expectation_id, owner_id=w.human(m.tenant), insist="OVERDUE")
    except IllegalTransition:
        refused = True
    ok = m.get(cid).state is ExState.INDETERMINATE and refused
    if not ok:
        return CaseResult(False, markers=["### OVERDUE WITHOUT HEALTHY COVERAGE ###"])
    return CaseResult(True, lines=[_SIG["overdue-requires-a-healthy-coverage-ref"]])


def case_overdue_without_healthy_coverage_is_structurally_impossible(w: World) -> CaseResult:
    m = w.machine()
    # the DATABASE refuses an OVERDUE with non-healthy coverage_health.
    w.conn.execute("INSERT INTO observation_coverage (tenant, coverage_id, channel, window_start, "
                   "window_end, health, probe_source, recorded_at) VALUES (?, 'cd', 'c', 'a', 'z', "
                   "'DOWN', 'p', 't')", (m.tenant,))
    w.conn.commit()
    refused = False
    try:
        w.conn.execute(
            "INSERT INTO expectations (tenant, expectation_id, subject_ref, subject_kind, "
            "subject_observation_ref, expected_type, expected_source, expectation_key, deadline_utc, "
            "originating_timezone, state, version, coverage_ref, coverage_health, owner_id, "
            "created_at, updated_at) VALUES (?, 'bad', 'l', 'entity', NULL, 'POD', 'c', 'l::POD', 't', "
            "'UTC', 'OVERDUE', 1, 'cd', 'DOWN', ?, 't', 't')", (m.tenant, w.human(m.tenant)))
        w.conn.commit()
    except sqlite3.IntegrityError:
        w.conn.rollback()
        refused = True
    if not refused:
        return CaseResult(False, markers=["### OVERDUE WITHOUT HEALTHY COVERAGE ###"])
    return CaseResult(True, lines=[_SIG["overdue-without-healthy-coverage-is-structurally-impossible"]])


def case_a_blind_window_is_indeterminate_not_overdue(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="DOWN")
    ok = m.get(cid).state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### BLIND WINDOW BECAME OVERDUE ###"])
    return CaseResult(True, lines=[_SIG["a-blind-window-is-indeterminate-not-overdue"]])


def case_unknown_coverage_is_indeterminate_not_overdue(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="UNKNOWN")
    ok = m.get(cid).state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### UNKNOWN COVERAGE BECAME OVERDUE ###"])
    return CaseResult(True, lines=[_SIG["unknown-coverage-is-indeterminate-not-overdue"]])


def case_absent_coverage_is_not_health(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="ABSENT", cover=False)
    c = m.get(cid)
    ok = c.state is ExState.INDETERMINATE and c.coverage_gap.startswith("ABSENT")
    if not ok:
        return CaseResult(False, markers=["### ABSENT COVERAGE TREATED AS HEALTHY ###"])
    return CaseResult(True, lines=[_SIG["absent-coverage-is-not-health"]])


def case_partial_coverage_over_the_window_is_not_health(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    # a HEALTHY row that does not span the whole window -> partial, not health.
    w.cover(m, r.expectation, "HEALTHY", partial_span=True)
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=w.human(m.tenant))
    ok = m.get(r.expectation.expectation_id).state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### PARTIAL COVERAGE TREATED AS HEALTHY ###"])
    return CaseResult(True, lines=[_SIG["partial-coverage-over-the-window-is-not-health"]])


def case_indeterminate_records_the_coverage_gap(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="DOWN")
    ok = bool(m.get(cid).coverage_gap)
    if not ok:
        return CaseResult(False, markers=["### MISS ### INDETERMINATE has no coverage_gap"])
    return CaseResult(True, lines=[_SIG["indeterminate-records-the-coverage-gap"]])


def case_confidence_cannot_turn_indeterminate_into_overdue(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m, proposed_confidence=1.0)
    w.cover(m, r.expectation, "DOWN")
    m.evaluate_deadline(r.expectation.expectation_id, owner_id=w.human(m.tenant))
    ok = m.get(r.expectation.expectation_id).state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### CONFIDENCE TURNED INDETERMINATE INTO OVERDUE ###"])
    return CaseResult(True, lines=[_SIG["confidence-cannot-turn-indeterminate-into-overdue"]])


def case_overdue_and_indeterminate_carry_a_named_human_owner(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    over = _overdue(w, m, owner=h)
    ind = _indeterminate(w, m, health="DOWN", owner=h)
    ok = m.get(over).owner_id == h and m.get(ind).owner_id == h
    if not ok:
        return CaseResult(False, markers=["### OWNERLESS HUMAN-OWNED STATE CREATED ###"])
    return CaseResult(True, lines=[_SIG["overdue-and-indeterminate-carry-a-named-human-owner"]])


def case_an_ownerless_human_owned_state_is_impossible(w: World) -> CaseResult:
    m = w.machine()
    refused = False
    try:
        w.conn.execute(
            "INSERT INTO expectations (tenant, expectation_id, subject_ref, subject_kind, "
            "subject_observation_ref, expected_type, expected_source, expectation_key, deadline_utc, "
            "originating_timezone, state, version, coverage_gap, owner_id, created_at, updated_at) "
            "VALUES (?, 'e', 'l', 'entity', NULL, 'POD', 'c', 'l::POD', 't', 'UTC', 'INDETERMINATE', "
            "1, 'blind', NULL, 't', 't')", (m.tenant,))
        w.conn.commit()
    except sqlite3.IntegrityError:
        w.conn.rollback()
        refused = True
    if not refused:
        return CaseResult(False, markers=["### OWNERLESS HUMAN-OWNED STATE CREATED ###"])
    return CaseResult(True, lines=[_SIG["an-ownerless-human-owned-state-is-impossible"]])


def case_a_late_arrival_discharges_an_overdue_expectation(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    w.observation(m.tenant, "pod-late-o", bound="load:4471")
    d = m.discharge(cid, observation_id="pod-late-o")
    ok = d.to_state is ExState.DISCHARGED and d.late and d.event_producer == "EX-4"
    if not ok:
        return CaseResult(False, markers=["### LATE ARRIVAL REFUSED ###"])
    return CaseResult(True, lines=[_SIG["a-late-arrival-discharges-an-overdue-expectation"],
                                   "A LATE ARRIVAL IS ALWAYS ACCEPTED"])


def case_a_late_arrival_discharges_an_indeterminate_expectation(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="DOWN")
    w.observation(m.tenant, "pod-late-i", bound="load:4471")
    d = m.discharge(cid, observation_id="pod-late-i")
    ok = d.to_state is ExState.DISCHARGED and d.late
    if not ok:
        return CaseResult(False, markers=["### LATE ARRIVAL REFUSED ###"])
    return CaseResult(True, lines=[_SIG["a-late-arrival-discharges-an-indeterminate-expectation"]])


def case_late_discharge_is_marked_late(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    w.observation(m.tenant, "pod-late-m", bound="load:4471")
    m.discharge(cid, observation_id="pod-late-m")
    ok = m.get(cid).late == 1
    if not ok:
        return CaseResult(False, markers=["### LATE DISCHARGE LOST ITS late MARKER ###"])
    return CaseResult(True, lines=[_SIG["late-discharge-is-marked-late"]])


def case_late_evidence_is_never_rejected_because_the_deadline_passed(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    # advance the clock four months — the deadline is long past.
    w.clock.advance(days=120)
    w.observation(m.tenant, "pod-m4", bound="load:4471")
    d = m.discharge(cid, observation_id="pod-m4")
    ok = d.to_state is ExState.DISCHARGED
    if not ok:
        return CaseResult(False, markers=["### LATE ARRIVAL REFUSED ###"])
    return CaseResult(True, lines=[_SIG["late-evidence-is-never-rejected-because-the-deadline-passed"]])


def case_deadline_change_re_versions_the_expectation(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    res = m.amend_deadline(r.expectation.expectation_id,
                           new_deadline_utc=datetime(2026, 8, 29, 17, 0, 0, tzinfo=timezone.utc))
    c = m.get(r.expectation.expectation_id)
    ok = (res.event_names == ("ExpectationReVersioned",) and c.version == 2
          and c.state is ExState.RAISED)
    if not ok:
        return CaseResult(False, markers=["### DEADLINE AMENDED WITHOUT RE-VERSIONING ###"])
    return CaseResult(True, lines=[_SIG["deadline-change-re-versions-the-expectation"]])


def case_deadline_history_is_retained(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    d0 = m.get(r.expectation.expectation_id).deadline_utc
    m.amend_deadline(r.expectation.expectation_id,
                     new_deadline_utc=datetime(2026, 8, 29, tzinfo=timezone.utc))
    ok = d0 in m.get(r.expectation.expectation_id).deadline_history_list
    if not ok:
        return CaseResult(False, markers=["### DEADLINE HISTORY LOST ###"])
    return CaseResult(True, lines=[_SIG["deadline-history-is-retained"]])


def case_an_amendment_is_not_a_supersession(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    m.amend_deadline(r.expectation.expectation_id,
                     new_deadline_utc=datetime(2026, 8, 29, tzinfo=timezone.utc))
    # same row, same id, re-versioned — no SUPERSEDED state, no ExpectationSuperseded event.
    ok = (m.get(r.expectation.expectation_id).state is ExState.RAISED
          and "SUPERSEDED" not in EXPECTATION_STATES)
    if not ok:
        return CaseResult(False, markers=["### DEADLINE AMENDED WITHOUT RE-VERSIONING ###"])
    return CaseResult(True, lines=[_SIG["an-amendment-is-not-a-supersession"]])


def case_the_subject_and_expected_type_cannot_be_mutated(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    subj_ok = typ_ok = False
    try:
        w.conn.execute("UPDATE expectations SET subject_ref = 'load:9999' WHERE tenant = ? AND "
                       "expectation_id = ?", (m.tenant, r.expectation.expectation_id))
    except sqlite3.IntegrityError:
        w.conn.rollback()
        subj_ok = True
    try:
        w.conn.execute("UPDATE expectations SET expected_type = 'remittance' WHERE tenant = ? AND "
                       "expectation_id = ?", (m.tenant, r.expectation.expectation_id))
    except sqlite3.IntegrityError:
        w.conn.rollback()
        typ_ok = True
    if not subj_ok:
        return CaseResult(False, markers=["### SUBJECT SILENTLY MUTATED ###"])
    if not typ_ok:
        return CaseResult(False, markers=["### EXPECTED TYPE SILENTLY MUTATED ###"])
    return CaseResult(True, lines=[_SIG["the-subject-and-expected-type-cannot-be-mutated"]])


def case_a_stale_version_cannot_overwrite_newer_state(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    stale = m.get(r.expectation.expectation_id)
    m.amend_deadline(r.expectation.expectation_id,
                     new_deadline_utc=datetime(2026, 8, 30, tzinfo=timezone.utc))
    refused = False
    try:
        m.cancel(r.expectation.expectation_id, reason="load cancelled", expected=stale)
    except StateConflict:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### STALE VERSION OVERWROTE NEWER STATE ###"])
    return CaseResult(True, lines=[_SIG["a-stale-version-cannot-overwrite-newer-state"]])


def case_reason_disappeared_cancels_a_raised_expectation(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    res = m.cancel(r.expectation.expectation_id, reason="load cancelled")
    ok = res.to_state is ExState.CANCELLED and res.event_names == ("ExpectationCancelled",)
    if not ok:
        return CaseResult(False, markers=["### MISS ### EX-6 did not cancel a RAISED expectation"])
    return CaseResult(True, lines=[_SIG["reason-disappeared-cancels-a-raised-expectation"]])


def case_reason_disappeared_cancels_an_overdue_expectation(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    res = m.cancel(cid, reason="load cancelled")
    ok = res.to_state is ExState.CANCELLED
    if not ok:
        return CaseResult(False, markers=["### MISS ### EX-6 did not cancel an OVERDUE expectation"])
    return CaseResult(True, lines=[_SIG["reason-disappeared-cancels-an-overdue-expectation"]])


def case_cancelling_an_indeterminate_expectation_is_illegal(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="DOWN")
    refused = False
    try:
        m.cancel(cid, reason="load cancelled")
    except IllegalTransition:
        refused = True
    ok = refused and m.get(cid).state is ExState.INDETERMINATE and (
        "IllegalTransitionAttempted" in w.security(m.tenant))
    if not ok:
        return CaseResult(False, markers=["### INDETERMINATE SILENTLY CANCELLED ###"])
    return CaseResult(True, lines=[_SIG["cancelling-an-indeterminate-expectation-is-illegal"]])


def case_a_cancelled_expectation_is_retained_never_deleted(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    m.cancel(r.expectation.expectation_id, reason="load cancelled")
    retained = m.get(r.expectation.expectation_id) is not None
    deleted_refused = False
    try:
        w.conn.execute("DELETE FROM expectations WHERE tenant = ? AND expectation_id = ?",
                       (m.tenant, r.expectation.expectation_id))
    except sqlite3.IntegrityError:
        w.conn.rollback()
        deleted_refused = True
    ok = retained and deleted_refused
    if not ok:
        return CaseResult(False, markers=["### EXPECTATION DELETED ###"])
    return CaseResult(True, lines=[_SIG["a-cancelled-expectation-is-retained-never-deleted"]])


def case_terminal_age_expires_an_overdue_expectation(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    e = m.expire(cid)
    ok = e.to_state is ExState.EXPIRED
    if not ok:
        return CaseResult(False, markers=["### MISS ### terminal age did not expire an OVERDUE"])
    return CaseResult(True, lines=[_SIG["terminal-age-expires-an-overdue-expectation"]])


def case_terminal_age_expires_an_indeterminate_expectation(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="DOWN")
    e = m.expire(cid)
    ok = e.to_state is ExState.EXPIRED
    if not ok:
        return CaseResult(False, markers=["### MISS ### terminal age did not expire an INDETERMINATE"])
    return CaseResult(True, lines=[_SIG["terminal-age-expires-an-indeterminate-expectation"]])


def case_a_raised_expectation_never_expires(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    refused = False
    try:
        m.expire(r.expectation.expectation_id)
    except IllegalTransition:
        refused = True
    ok = refused and m.get(r.expectation.expectation_id).state is ExState.RAISED
    if not ok:
        return CaseResult(False, markers=["### RAISED EXPECTATION EXPIRED ###"])
    return CaseResult(True, lines=[_SIG["a-raised-expectation-never-expires"]])


def case_expiry_is_never_silent(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    before = w.events(m.tenant, "ExpectationExpired")
    m.expire(cid)
    row_retained = m.get(cid) is not None and m.get(cid).owner_id is not None
    ok = w.events(m.tenant, "ExpectationExpired") == before + 1 and row_retained
    if not ok:
        return CaseResult(False, markers=["### EXPECTATION SILENTLY EXPIRED ###"])
    return CaseResult(True, lines=[_SIG["expiry-is-never-silent"]])


def case_no_sweep_or_reaper_closes_an_expectation(w: World) -> CaseResult:
    # Structural: the machine has no in-memory sleep and no age-predicate scan over the expectations
    # table — a terminal state is reached only through a durable-timer transition, never a reaper.
    src = (ROOT / "src" / "freight_recon" / "expectation.py").read_text(encoding="utf-8").lower()
    ok = ("time.sleep" not in src and "deadline_utc <" not in src and "created_at <" not in src
          and "def _reap" not in src and "def sweep" not in src)
    if not ok:
        return CaseResult(False, markers=["### REAPER DELETED AN EXPECTATION ###"])
    return CaseResult(True, lines=[_SIG["no-sweep-or-reaper-closes-an-expectation"]])


def case_there_is_no_timed_out_stale_or_resolved_state(w: World) -> CaseResult:
    ok = all(s not in EXPECTATION_STATES for s in ("TIMED_OUT", "STALE", "RESOLVED", "MISSED",
                                                   "LATE", "CLOSED", "PENDING"))
    if not ok:
        return CaseResult(False, markers=["### UNREGISTERED STATE MINTED ###"])
    return CaseResult(True, lines=[_SIG["there-is-no-timed-out-stale-or-resolved-state"]])


def case_discharge_beats_overdue_when_they_race(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)  # deadline won the race
    w.observation(m.tenant, "pod-race-o", bound="load:4471")
    d = m.discharge(cid, observation_id="pod-race-o")  # the late arrival still discharges
    ok = d.to_state is ExState.DISCHARGED
    if not ok:
        return CaseResult(False, markers=["### OVERDUE BEAT A DISCHARGE ###"])
    return CaseResult(True, lines=[_SIG["discharge-beats-overdue-when-they-race"]])


def case_discharge_beats_indeterminate_when_they_race(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="DOWN")
    w.observation(m.tenant, "pod-race-i", bound="load:4471")
    d = m.discharge(cid, observation_id="pod-race-i")
    ok = d.to_state is ExState.DISCHARGED
    if not ok:
        return CaseResult(False, markers=["### OVERDUE BEAT A DISCHARGE ###"])
    return CaseResult(True, lines=[_SIG["discharge-beats-indeterminate-when-they-race"]])


def case_the_deadline_is_a_durable_timer_not_a_sleep(w: World) -> CaseResult:
    src = (ROOT / "src" / "freight_recon" / "expectation.py").read_text(encoding="utf-8")
    imports_timer = "from .event_timers import" in src and "DurableTimers" in src
    no_sleep = "time.sleep" not in src and "import time" not in src.lower()
    m = w.machine()
    r = w.raised(m)
    armed = w.conn.execute(
        "SELECT COUNT(*) FROM durable_timers WHERE tenant = ? AND aggregate_id = ?",
        (m.tenant, r.expectation.expectation_id)).fetchone()[0]
    ok = imports_timer and no_sleep and armed >= 1
    if not ok:
        return CaseResult(False, markers=["### IN-MEMORY SLEEP DECIDED THE DEADLINE ###"])
    return CaseResult(True, lines=[_SIG["the-deadline-is-a-durable-timer-not-a-sleep"]])


def _fire_deadline(w: World, m: M8Machine, cid: str, owner: str) -> None:
    w.clock.advance(hours=12)
    relay = TimerRelay(w.conn, tenant=m.tenant, handler=m.handle_timer_fired, relay_id="relay",
                       clock=w.clock)
    relay.run_once()


def case_restart_re_fires_the_deadline_timer(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = w.raised(m, owner=h)
    w.cover(m, r.expectation, "HEALTHY")
    # "restart": a fresh machine + relay over the same durable database.
    m2 = M8Machine(w.conn, tenant=m.tenant, clock=w.clock)
    _fire_deadline(w, m2, r.expectation.expectation_id, h)
    ok = m2.get(r.expectation.expectation_id).state is ExState.OVERDUE
    if not ok:
        return CaseResult(False, markers=["### TIMER LOST ACROSS RESTART ###"])
    return CaseResult(True, lines=[_SIG["restart-re-fires-the-deadline-timer"]])


def case_restart_preserves_the_raised_expectation(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    m2 = M8Machine(w.conn, tenant=m.tenant, clock=w.clock)
    ok = m2.get(r.expectation.expectation_id).state is ExState.RAISED
    if not ok:
        return CaseResult(False, markers=["### TIMER LOST ACROSS RESTART ###"])
    return CaseResult(True, lines=[_SIG["restart-preserves-the-raised-expectation"]])


def case_restart_after_overdue_reaches_the_canonical_state(w: World) -> CaseResult:
    m = w.machine()
    h = w.human(m.tenant)
    r = w.raised(m, owner=h)
    w.cover(m, r.expectation, "HEALTHY")
    m2 = M8Machine(w.conn, tenant=m.tenant, clock=w.clock)
    _fire_deadline(w, m2, r.expectation.expectation_id, h)
    # a rebuild from the recorded coverage reaches the same OVERDUE.
    rebuilt = m2.rebuild(r.expectation.expectation_id)
    ok = m2.get(r.expectation.expectation_id).state is ExState.OVERDUE and rebuilt.state is (
        ExState.OVERDUE)
    if not ok:
        return CaseResult(False, markers=["### TIMER LOST ACROSS RESTART ###"])
    return CaseResult(True, lines=[_SIG["restart-after-overdue-reaches-the-canonical-state"]])


def case_a_redelivered_timer_is_a_no_op(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    w.observation(m.tenant, "pod-r", bound="load:4471")
    m.discharge(r.expectation.expectation_id, observation_id="pod-r")  # discharged before deadline
    trig = TimerFired(tenant=m.tenant, timer_id="t", aggregate_type="expectation",
                      aggregate_id=r.expectation.expectation_id, timer_kind="expectation_deadline",
                      fire_at="t", fired_at="t", payload={"owner_id": w.human(m.tenant)})
    res = m.handle_timer_fired(trig)
    ok = res is None and m.get(r.expectation.expectation_id).state is ExState.DISCHARGED
    if not ok:
        return CaseResult(False, markers=["### MISS ### a redelivered timer was not a no-op"])
    return CaseResult(True, lines=[_SIG["a-redelivered-timer-is-a-no-op"]])


def case_timer_coverage_read_and_state_are_one_commit(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    w.cover(m, r.expectation, "HEALTHY")
    before = w.events(m.tenant, "ExpectationOverdue")
    res = m.evaluate_deadline(r.expectation.expectation_id, owner_id=w.human(m.tenant))
    c = m.get(r.expectation.expectation_id)
    ok = (c.state is ExState.OVERDUE and c.coverage_ref is not None
          and w.events(m.tenant, "ExpectationOverdue") == before + 1)
    if not ok:
        return CaseResult(False, markers=["### HALF-DECIDED DEADLINE PERSISTED ###"])
    return CaseResult(True, lines=[_SIG["timer-coverage-read-and-state-are-one-commit"]])


def case_persistence_failure_rolls_back_the_deadline_decision(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    w.cover(m, r.expectation, "HEALTHY")
    # inject a persistence failure: a bad outbox by monkeypatching the emit to raise mid-commit.
    original = M8Machine._outbox
    import types

    def boom(self):
        box = original(self)
        real_emit = box.emit

        def failing(env):
            raise sqlite3.OperationalError("injected persistence failure")
        box.emit = failing
        return box
    M8Machine._outbox = boom
    crashed = False
    try:
        m.evaluate_deadline(r.expectation.expectation_id, owner_id=w.human(m.tenant))
    except Exception:
        crashed = True
    finally:
        M8Machine._outbox = original
    # the state did NOT half-decide: it is still RAISED, no OVERDUE event.
    c = m.get(r.expectation.expectation_id)
    ok = crashed and c.state is ExState.RAISED and w.events(m.tenant, "ExpectationOverdue") == 0
    if not ok:
        return CaseResult(False, markers=["### HALF-DECIDED DEADLINE PERSISTED ###"])
    return CaseResult(True, lines=[_SIG["persistence-failure-rolls-back-the-deadline-decision"]])


def case_state_and_event_co_commit(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    before = w.events(m.tenant, "ExpectationCancelled")
    m.cancel(r.expectation.expectation_id, reason="load cancelled")
    c = m.get(r.expectation.expectation_id)
    ok = c.state is ExState.CANCELLED and w.events(m.tenant, "ExpectationCancelled") == before + 1
    if not ok:
        return CaseResult(False, markers=["### STATE WITHOUT ITS EVENT ###"])
    return CaseResult(True, lines=[_SIG["state-and-event-co-commit"]])


def case_replay_reconstructs_overdue_from_the_recorded_coverage(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    rc = m.rebuild(cid)
    ok = rc.state is ExState.OVERDUE and rc.coverage_basis is not None
    if not ok:
        return CaseResult(False, markers=["### REPLAY FLIPPED OVERDUE AND INDETERMINATE ###"])
    return CaseResult(True, lines=[_SIG["replay-reconstructs-overdue-from-the-recorded-coverage"]])


def case_replay_reconstructs_indeterminate_from_the_recorded_coverage(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="DOWN")
    rc = m.rebuild(cid)
    ok = rc.state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### REPLAY FLIPPED OVERDUE AND INDETERMINATE ###"])
    return CaseResult(True, lines=[_SIG["replay-reconstructs-indeterminate-from-the-recorded-coverage"]])


def case_replay_does_not_read_the_current_channel_state(w: World) -> CaseResult:
    import inspect
    src = inspect.getsource(M8Machine.rebuild)
    ok = "observation_coverage" not in src and "_coverage_verdict" not in src
    if not ok:
        return CaseResult(False, markers=["### REPLAY READ THE LIVE CHANNEL ###"])
    return CaseResult(True, lines=[_SIG["replay-does-not-read-the-current-channel-state"]])


def case_replay_creates_no_new_authority_and_no_effect(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    grants_before = w.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
    rc = m.rebuild(cid)
    grants_after = w.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
    ok = (rc.new_authority == 0 and rc.external_effects == 0 and rc.coverage_rewritten == 0
          and rc.state_flips == 0 and grants_before == grants_after)
    if not ok:
        return CaseResult(False, markers=["### REPLAY MINTED AUTHORITY ###"])
    return CaseResult(True, lines=[_SIG["replay-creates-no-new-authority-and-no-effect"]])


def case_an_appointment_window_is_evaluated_in_facility_local_time(w: World) -> CaseResult:
    m = w.machine()
    r = m.raise_expectation(subject_ref="load:1", expected_type="appointment_confirmation",
                            expected_source=CHANNEL, owner_id=w.human(m.tenant),
                            originating_timezone="America/Denver",
                            appointment_local=datetime(2026, 7, 15, 17, 0, 0))
    # 17:00 MDT (UTC-6) = 23:00Z, NOT 17:00Z.
    ok = m.get(r.expectation.expectation_id).deadline_utc == "2026-07-15T23:00:00.000Z"
    if not ok:
        return CaseResult(False, markers=["### WINDOW EVALUATED IN UTC ###"])
    return CaseResult(True, lines=[_SIG["an-appointment-window-is-evaluated-in-facility-local-time"]])


def case_a_dst_boundary_does_not_move_the_deadline(w: World) -> CaseResult:
    tz = w.ctx.timezone
    summer = facility_local_deadline(datetime(2026, 7, 15, 17, 0, 0), tz)
    winter = facility_local_deadline(datetime(2026, 12, 15, 17, 0, 0), tz)
    # Each is a fixed UTC instant computed with the correct offset; DST shifts the OFFSET, and the
    # correctly-computed instant does not silently move.
    ok = summer.tzinfo == timezone.utc and winter.tzinfo == timezone.utc and summer != winter
    if not ok:
        return CaseResult(False, markers=["### DST BOUNDARY MOVED THE DEADLINE ###"])
    return CaseResult(True, lines=[_SIG["a-dst-boundary-does-not-move-the-deadline"]])


def case_a_window_evaluated_in_utc_instead_of_facility_local_is_wrong(w: World) -> CaseResult:
    m = w.machine()
    local = facility_local_deadline(datetime(2026, 7, 15, 17, 0, 0), "America/Denver")
    naive_utc = datetime(2026, 7, 15, 17, 0, 0, tzinfo=timezone.utc)
    differs = local != naive_utc  # the UTC evaluation is a different (wrong) instant
    refused = False
    try:
        m.raise_expectation(subject_ref="l", expected_type="POD", expected_source=CHANNEL,
                            owner_id=w.human(m.tenant), originating_timezone="America/Denver",
                            appointment_local=datetime(2026, 7, 15, 17, 0, 0), evaluate_in_utc=True)
    except IllegalTransition:
        refused = True
    ok = differs and refused and w.expectations(m.tenant) == 0
    if not ok:
        return CaseResult(False, markers=["### WINDOW EVALUATED IN UTC ###"])
    return CaseResult(True, lines=[_SIG["a-window-evaluated-in-utc-instead-of-facility-local-is-wrong"]])


def case_m8_mints_no_gate_decision(w: World) -> CaseResult:
    src = (ROOT / "src" / "freight_recon" / "expectation.py").read_text(encoding="utf-8")
    no_gate = ("GateDecision(" not in src and "GateRegistry(" not in src
               and "from .checkpoint" not in src and "import checkpoint" not in src)
    m = w.machine()
    r = w.raised(m)
    proj = m.get(r.expectation.expectation_id).native_projection()
    is_input = hasattr(proj, "evidence_condition") and not hasattr(proj, "gate")
    ok = no_gate and is_input
    if not ok:
        return CaseResult(False, markers=["### M8 MINTED A GATE DECISION ###"])
    return CaseResult(True, lines=[_SIG["m8-mints-no-gate-decision"]])


def case_an_expectation_owes_it_does_not_authorize(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    proj = m.get(r.expectation.expectation_id).native_projection()
    outcome, grants = _checkpoint_unknown()
    ok = (proj.owed and proj.evidence_condition == "unknown" and not outcome.authorized
          and grants == 0)
    if not ok:
        return CaseResult(False, markers=["### EXPECTATION AUTHORIZED AN ACTION ###"])
    return CaseResult(True, lines=[_SIG["an-expectation-owes-it-does-not-authorize"]])


def case_an_undischarged_expectation_makes_a_field_unknown_never_consistent(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    proj = m.get(r.expectation.expectation_id).native_projection()
    outcome, _ = _checkpoint_unknown()
    ok = (proj.evidence_condition == "unknown" and proj.evidence_condition != "conflicting"
          and not outcome.authorized and outcome.step == 4)
    if not ok:
        return CaseResult(False, markers=["### M8 MINTED A GATE DECISION ###"])
    return CaseResult(True, lines=[_SIG["an-undischarged-expectation-makes-a-field-unknown-never-consistent"]])


def case_discharge_and_indeterminate_detection_continue_under_a_brake(w: World) -> CaseResult:
    m = w.machine()
    BrakeStore(w.conn).engage(tenant=m.tenant, actor="rasheed", actor_kind="HUMAN",
                              reason="probe: brake engaged")
    # under a brake, observation continues: a discharge still discharges, and a blind deadline still
    # goes INDETERMINATE.
    r1 = w.raised(m, subject="load:d")
    w.observation(m.tenant, "pod-b", bound="load:d")
    d = m.discharge(r1.expectation.expectation_id, observation_id="pod-b")
    cid = _indeterminate(w, m, health="DOWN", owner=w.human(m.tenant))
    ok = d.to_state is ExState.DISCHARGED and m.get(cid).state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### BRAKE STOPPED INDETERMINATE DETECTION ###"])
    return CaseResult(True, lines=[_SIG["discharge-and-indeterminate-detection-continue-under-a-brake"]])


def case_a_brake_never_fabricates_overdue_state(w: World) -> CaseResult:
    m = w.machine()
    BrakeStore(w.conn).engage(tenant=m.tenant, actor="rasheed", actor_kind="HUMAN",
                              reason="probe: brake engaged")
    # a brake is not a coverage signal: a blind window under a brake is still INDETERMINATE, never
    # OVERDUE.
    cid = _indeterminate(w, m, health="DOWN")
    ok = m.get(cid).state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### BRAKE FABRICATED OVERDUE ###"])
    return CaseResult(True, lines=[_SIG["a-brake-never-fabricates-overdue-state"]])


def case_tenant_isolation(w: World) -> CaseResult:
    a = w.machine("tenant-a")
    b = w.machine("tenant-b")
    ra = w.raised(a)
    rb = w.raised(b)
    ok = a.get(rb.expectation.expectation_id) is None and b.get(ra.expectation.expectation_id) is None
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT OBSERVATION ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["tenant-isolation"]])


def case_cross_tenant_identical_expectation_key(w: World) -> CaseResult:
    a = w.machine("tenant-a")
    b = w.machine("tenant-b")
    ra = w.raised(a, subject="load:4471", etype="POD")
    rb = w.raised(b, subject="load:4471", etype="POD")
    ok = (not ra.coalesced and not rb.coalesced
          and ra.expectation.expectation_id != rb.expectation.expectation_id)
    if not ok:
        return CaseResult(False, markers=["### TWO LIVE RAISED EXPECTATIONS FOR ONE KEY ###"])
    return CaseResult(True, lines=[_SIG["cross-tenant-identical-expectation-key"]])


def case_cross_tenant_observation_cannot_discharge(w: World) -> CaseResult:
    res = case_a_wrong_tenant_observation_cannot_discharge(w)
    if not res.ok:
        return res
    return CaseResult(True, lines=[_SIG["cross-tenant-observation-cannot-discharge"]])


def case_cross_tenant_coverage_record_fails_closed(w: World) -> CaseResult:
    a = w.machine("tenant-a")
    b = w.machine("tenant-b")
    rb = w.raised(b, subject="load:z")
    # a HEALTHY coverage in tenant-a for the same channel must not make tenant-b's window healthy.
    a.record_coverage(coverage_id="cov-a", channel=CHANNEL,
                      window_start=rb.expectation.created_at, window_end=rb.expectation.deadline_utc,
                      health="HEALTHY", probe_source="p")
    m_b = b
    res = m_b.evaluate_deadline(rb.expectation.expectation_id, owner_id=w.human("tenant-b"))
    ok = res.to_state is ExState.INDETERMINATE
    if not ok:
        return CaseResult(False, markers=["### CROSS-TENANT COVERAGE ACCEPTED ###"])
    return CaseResult(True, lines=[_SIG["cross-tenant-coverage-record-fails-closed"]])


def case_cross_tenant_owner_fails_closed(w: World) -> CaseResult:
    a = w.machine("tenant-a")
    w.human("tenant-b", "owner:b")
    refused = False
    try:
        w.raised(a, owner="owner:b")  # owner:b belongs to tenant-b
    except GuardNotSatisfied:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### OWNERLESS HUMAN-OWNED STATE CREATED ###"])
    return CaseResult(True, lines=[_SIG["cross-tenant-owner-fails-closed"]])


def case_occ_on_expectation_version(w: World) -> CaseResult:
    m = w.machine()
    r = w.raised(m)
    stale = m.get(r.expectation.expectation_id)
    m.amend_deadline(r.expectation.expectation_id,
                     new_deadline_utc=datetime(2026, 8, 30, tzinfo=timezone.utc))
    refused = False
    try:
        m.cancel(r.expectation.expectation_id, reason="load cancelled", expected=stale)
    except StateConflict:
        refused = True
    if not refused:
        return CaseResult(False, markers=["### STALE VERSION OVERWROTE NEWER STATE ###"])
    return CaseResult(True, lines=[_SIG["occ-on-expectation-version"]])


def case_inbox_idempotency(w: World) -> CaseResult:
    m = w.machine()
    cid = _indeterminate(w, m, health="DOWN")
    env = [e for e in m._event_stream(cid) if e.event_name == "ExpectationIndeterminate"][0]
    m.consume_event(env)
    second = m.consume_event(env)
    ok = second.consume.is_noop and not second.moved
    if not ok:
        return CaseResult(False, markers=["### MISS ### redelivered event was not a no-op"])
    return CaseResult(True, lines=[_SIG["inbox-idempotency"]])


def case_database_invariants(w: World) -> CaseResult:
    from freight_recon.migrations.phase6_expectations import phase6_expectations_readiness_problems
    ready = (schema_readiness_problems(w.conn) == []
             and phase6_expectations_readiness_problems(w.conn) == [])
    # a legacy database migrates to the same shape.
    from fixtures.legacy_workspace import build_legacy_workspace
    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate
    tmp = Path(tempfile.mkdtemp(prefix="p6m8-mig-"))
    legacy = tmp / "legacy.db"
    build_legacy_workspace(legacy)
    migrate(str(legacy), assertion=OwnerAssertion(
        actor_id="rasheed@neyma", tenant="acme-brokerage", scope="all legacy rows",
        operational_basis="sole workspace onboarded for Acme; verified against record",
        evidence_reference="docs/onboarding/acme.md"), dry_run=False)
    migrated = sqlite3.connect(legacy)
    migrated.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(migrated)
    migrated_ready = phase6_expectations_readiness_problems(migrated) == []
    tables = {t[0] for t in migrated.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    ok = ready and migrated_ready and {"expectations", "observation_coverage"} <= tables
    if not ok:
        return CaseResult(False, markers=[f"### MISS ### ready={ready} migrated={migrated_ready}"])
    return CaseResult(True, lines=[_SIG["database-invariants"],
                                   "A LEGACY DATABASE MIGRATES TO THE CANONICAL EXPECTATION SHAPE"])


def case_malformed_expectation_fails_closed(w: World) -> CaseResult:
    m = w.machine()
    refused = 0
    for kw in ({"subject": ""}, {"etype": ""}, {"source": ""}):
        try:
            w.raised(m, **kw)
        except MalformedExpectation:
            refused += 1
    # an unknown subject_kind fails closed too.
    try:
        w.raised(m, subject_kind="mystery")
    except MalformedExpectation:
        refused += 1
    ok = refused == 4 and w.expectations(m.tenant) == 0
    if not ok:
        return CaseResult(False, markers=[f"### MISS ### malformed inputs not all refused ({refused})"])
    return CaseResult(True, lines=[_SIG["malformed-expectation-fails-closed"]])


def _unchanged(paths: tuple[str, ...]) -> bool:
    import subprocess
    r = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *paths], cwd=ROOT,
                       capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == ""


def case_the_m5_observation_machine_is_not_rewritten(w: World) -> CaseResult:
    ok = _unchanged(("src/freight_recon/observation.py",
                     "src/freight_recon/migrations/phase6_observations.py"))
    if not ok:
        return CaseResult(False, markers=["### M5 OBSERVATION ROW REWRITTEN BY M8 ###"])
    return CaseResult(True, lines=[_SIG["the-m5-observation-machine-is-not-rewritten"]])


def case_the_m3_awaiting_observation_seam_is_unchanged(w: World) -> CaseResult:
    ok = _unchanged(("src/freight_recon/external_effect.py",
                     "src/freight_recon/migrations/phase6_external_effects.py"))
    if not ok:
        return CaseResult(False, markers=["### M3 AWAITING_OBSERVATION SEAM REWRITTEN ###"])
    return CaseResult(True, lines=[_SIG["the-m3-awaiting-observation-seam-is-unchanged"]])


def case_the_m7_conflict_machine_is_not_rewritten(w: World) -> CaseResult:
    ok = _unchanged(("src/freight_recon/conflict.py",
                     "src/freight_recon/migrations/phase6_conflicts.py"))
    if not ok:
        return CaseResult(False, markers=["### M7 CONFLICT ROW REWRITTEN BY M8 ###"])
    return CaseResult(True, lines=[_SIG["the-m7-conflict-machine-is-not-rewritten"]])


def case_an_overdue_expectation_is_not_automatically_a_conflict(w: World) -> CaseResult:
    m = w.machine()
    cid = _overdue(w, m)
    # M8 raises no Conflict, writes no conflicts row, and mints no ConflictRaised.
    conflicts = w.conn.execute("SELECT COUNT(*) FROM conflicts WHERE tenant = ?",
                               (m.tenant,)).fetchone()[0]
    conflict_events = w.events(m.tenant, "ConflictRaised")
    src = (ROOT / "src" / "freight_recon" / "expectation.py").read_text(encoding="utf-8")
    ok = (m.get(cid).state is ExState.OVERDUE and conflicts == 0 and conflict_events == 0
          and "import conflict" not in src and "from .conflict" not in src
          and "ConflictRaised" not in src)
    if not ok:
        return CaseResult(False, markers=["### M7 CONFLICT ROW REWRITTEN BY M8 ###"])
    return CaseResult(True, lines=[_SIG["an-overdue-expectation-is-not-automatically-a-conflict"]])


def case_m9_m10_m11_and_m12_are_not_built(w: World) -> CaseResult:
    tables = {t[0] for t in w.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    forbidden = {"exceptions", "compensations", "policies", "rules", "evidence"}
    src = (ROOT / "src" / "freight_recon" / "expectation.py").read_text(encoding="utf-8")
    import re
    foreign_ids = re.findall(r"\b(?:EC|CM|PO|RU)-\d+[a-z]*\b", src)
    ok = not (forbidden & tables) and not foreign_ids and "ExceptionRaised" not in src
    if not ok:
        return CaseResult(False, markers=["### M9 EVENT MINTED ###"])
    return CaseResult(True, lines=[_SIG["m9-m10-m11-and-m12-are-not-built"]])


CASE_FUNCS = {name: globals()[f"case_{name.replace('-', '_')}"] for name in CASES}


# ---- argument handling & the run --------------------------------------------------------------

_ILLEGAL_FAULTS = {"overdue-without-coverage", "cancel-indeterminate", "expire-raised",
                   "silent-expiry", "sweep-close", "utc-window", "replay-from-live-channel"}


def _run_case(w: World, case: str) -> CaseResult:
    try:
        result = CASE_FUNCS[case](w)
        if not isinstance(result, CaseResult):
            return CaseResult(False, markers=[f"### MISS ### {case} returned no result"])
        return result
    except ProbeExit:
        raise
    except Exception as exc:  # noqa: BLE001 — a case that crashes is a wrong behaviour, not a probe
        return CaseResult(False, markers=[f"### MISS ### {case} raised {type(exc).__name__}: {exc}"])


def _resolve_ctx(args: argparse.Namespace) -> Ctx:
    def bounded_int(name: str, value: int, lo: int, hi: int) -> int:
        if value < lo or value > hi:
            raise ProbeExit(
                f"--{name} {value} is out of range [{lo}, {hi}]. The mutation axis is bounded — a "
                f"probe that accepts anything is a probe whose passing runs mean nothing.")
        return value

    if args.confidence < 0.0 or args.confidence > 1.0:
        raise ProbeExit(
            f"--confidence {args.confidence} is out of range [0.0, 1.0]. Confidence is the negative "
            f"control: it must change NOTHING, at 1.0 or 0.0. An out-of-range value is refused.")
    if args.coverage not in COVERAGE_VALUES:
        raise ProbeExit(
            f"--coverage {args.coverage!r} is not one of {list(COVERAGE_VALUES)}. Coverage is a closed "
            f"health vocabulary; absent means NO ROW and is not a value the machine ever writes.")
    if args.inject in ("reopen-expectation", "reopen"):
        raise ProbeExit(
            "unknown fault 'reopen-expectation' is REFUSED: entity §27 and machine §24 say 'Reopening "
            "rules. N/A'. A probe that accepted it would produce passing evidence for a transition the "
            "corpus states does not exist.")
    if args.inject in ("correct-expectation", "correct"):
        raise ProbeExit(
            "unknown fault 'correct-expectation' is REFUSED: entity §23 and machine §25 say a wrong "
            "expectation is CANCELLED, not corrected. Correction is the tidy-looking thing a build "
            "session adds; it would let a wrong deadline be edited out of history.")
    if args.inject in ("supersede-expectation", "supersede"):
        raise ProbeExit(
            "unknown fault 'supersede-expectation' is REFUSED: entity §24 and machine §26 say a "
            "re-versioned deadline is NOT a supersession; there is no SUPERSEDED state in registry §4's "
            "M8 row and no ExpectationSuperseded event is registered anywhere.")
    if args.inject not in FAULTS:
        raise ProbeExit(
            f"unknown fault {args.inject!r}. The fault vocabulary is CLOSED and BOUNDED: "
            f"{', '.join(FAULTS)}. Closed means closed — an unknown fault is a refusal, never a "
            f"silent fallback to none. This is not fuzzing.")
    ctx = Ctx(
        concurrency=bounded_int("concurrency", args.concurrency, 1, 8),
        delay_ms=bounded_int("delay-ms", args.delay_ms, 0, 5000),
        repeat=bounded_int("repeat", args.repeat, 1, 5),
        tenants=bounded_int("tenants", args.tenants, 1, 3),
        age_ms=bounded_int("age-ms", args.age_ms, 0, 86400000),
        coverage=args.coverage, timezone=args.timezone, confidence=args.confidence, seed=args.seed,
        inject=args.inject)
    ctx.rng = random.Random(args.seed)
    return ctx


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list-cases", action="store_true", help="print the case names and exit")
    p.add_argument("--list-dimensions", action="store_true",
                   help="print the mutation flags and every fault name and exit")
    p.add_argument("--case", default=None, help="run exactly one case")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--delay-ms", type=int, default=0)
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--tenants", type=int, default=1)
    p.add_argument("--age-ms", type=int, default=0)
    p.add_argument("--coverage", default="healthy")
    p.add_argument("--timezone", default="America/Denver")
    p.add_argument("--confidence", type=float, default=0.5)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--inject", default="none")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if args.list_cases:
        for name in CASES:
            print(name)
        return 0
    if args.list_dimensions:
        for flag in DIMENSIONS:
            print(f"--{flag}")
        for fault in FAULTS:
            print(fault)
        return 0

    try:
        ctx = _resolve_ctx(args)
        if args.case is not None:
            if args.case not in CASE_FUNCS:
                raise ProbeExit(f"unknown case {args.case!r}. Run --list-cases for the case names.")
            cases = [args.case]
        else:
            cases = list(CASES)
    except ProbeExit as exc:
        print(f"probe: {exc.message}", file=sys.stderr)
        return 2

    wrong = 0
    printed: set[str] = set()
    for case in cases:
        case_ctx = Ctx(concurrency=ctx.concurrency, delay_ms=ctx.delay_ms, repeat=ctx.repeat,
                       tenants=ctx.tenants, age_ms=ctx.age_ms, coverage=ctx.coverage,
                       timezone=ctx.timezone, confidence=ctx.confidence, seed=ctx.seed,
                       inject=ctx.inject, rng=random.Random(ctx.seed + (abs(hash(case)) % 100000)))
        result = _run_case(_world(case_ctx), case)
        for line in result.lines:
            if line not in printed:
                print(line)
                printed.add(line)
        for marker in result.markers:
            print(marker)
        if not result.ok:
            wrong += 1
            print(f"  case {case}: WRONG")

    if args.case is None:
        for line in _REQUIRED_ON_FULL_RUN:
            if line not in printed:
                print(line)
                printed.add(line)

    print(f"behaviours as specified, {wrong} wrong")
    return 0 if wrong == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
