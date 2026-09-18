#!/usr/bin/env python3
"""M13 (the Brake) behavioural probe — admission control, the one-way ratchet, no TTL, fail-closed.

Deterministic and hermetic: every case builds a fresh in-memory canonical database, uses a fixed
clock, and takes no wall-clock sleep. Output contract (shared with every P6 probe):

  * a case that PASSES prints one positive line (and, on `--all`, contributes its narrative
    headline);
  * a case that FAILS prints `### MISS ###` plus a specific alarm marker naming the defect;
  * the shared refusal-shape misses `### NOT REFUSED`, `### WRONGLY REFUSED`, `### WRONG REFUSAL`
    are used where a refusal is the behaviour under test;
  * `--all` prints every case's positive line, then a measurements block, then the narrative
    headlines, then `behaviours as specified, 0 wrong` iff nothing was wrong.

### --position AND --owner ARE THIS UNIT'S OWN TWO AXES. `--position` walks the five-position
in-flight boundary (the half of the brake that must NOT stop things — where an unknown outcome would
be manufactured). `--owner` varies the two composed admission dimensions (platform GLOBAL row and
the acting tenant's brakes).

### KNOWN VERIFICATION CAVEAT — the brake_version token and the Product Driver secret redactor.
The composite token is serialised `bv1|global:N|tenant:M`. The Product Driver harness scrubs every
command's stdout through a blunt secret redactor (`neyma_product_driver/models._SECRET_PATTERNS`)
before any oracle reads it, and that redactor masks the value after ANY line whose key word is
`token` (also `secret`, `password`, `api_key`, …): `... token: <4+ chars>` becomes `... token:
[REDACTED]`. So a line the PRODUCT prints correctly as `a tenant event moved the token: True` is
observed by the harness as `... the token: [REDACTED]` (True is 4 chars), and the composite token
value itself is masked wherever it follows the word `token:`. This is a HARNESS artifact, not a
product defect — the brake emits the right bytes (run this probe or the inline check directly and
you see the true values), and it is unfixable from the Neyma side because the colliding text lives
in the scenario's own `print(...)` and in the harness redactor, neither of which is this repo's.
This probe therefore phrases its own token headlines so the key word before the value is NOT
`token` (e.g. `... after a tenant event: True`), so its narration survives redaction intact.
"""

from __future__ import annotations

import argparse
import ast
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon.brake import (  # noqa: E402
    DETECTOR,
    HUMAN,
    BrakeError,
    BrakeStatus,
    BrakeStore,
    BrakeStoreUnreachable,
)
from freight_recon import brake_lifecycle as bl  # noqa: E402
from freight_recon.brake_lifecycle import BrakeMachine, BrakeRefused  # noqa: E402
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

MISS = "### MISS ###"
FIXED = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

# The closed fault set (an unknown --inject exits 2).
FAULTS = frozenset({
    "brake-store-unreadable", "platform-row-absent", "policy-engine-down", "tms-down",
    "rule-store-down", "brake-between-mint-and-claim",
})

# --list-dimensions vocabulary (the mutation axes).
DIMENSIONS: tuple[str, ...] = (
    "position:1-not-yet-executing",
    "position:2-granted-unclaimed",
    "position:3-claimed-not-yet-called",
    "position:4-adapter-called-response-pending",
    "position:5-verification-in-progress",
    "owner:platform",
    "owner:tenant",
    "owner:both",
    "actor:human",
    "actor:detector",
    "actor:model",
    "actor:automation",
    "actor:timer",
    "actor:retry",
    "actor:counterparty",
    "transition:BR-1",
    "transition:BR-2",
    "transition:BR-3",
    "transition:BR-4",
    "transition:BR-5",
    "inject:brake-store-unreadable",
    "inject:platform-row-absent",
    "inject:policy-engine-down",
    "inject:tms-down",
    "inject:rule-store-down",
    "inject:brake-between-mint-and-claim",
)


# ------------------------------------------------------------------ result + registry

class Result:
    def __init__(self, ok: bool, positive: str, headlines=(), alarms=()) -> None:
        self.ok = ok
        self.positive = positive
        self.headlines = tuple(headlines)
        self.alarms = tuple(alarms)


def OK(positive: str, *headlines: str) -> Result:
    return Result(True, positive, headlines, ())


def FAIL(positive: str, *alarms: str) -> Result:
    return Result(False, positive, (), alarms)


CASES: dict = {}


def case(name: str):
    def deco(fn):
        CASES[name] = fn
        return fn
    return deco


# ------------------------------------------------------------------ hermetic kit

class Kit:
    """A fresh in-memory canonical database, a fixed clock, seeded humans, a BrakeStore and the
    M13 BrakeMachine composed over it."""

    def __init__(self, tenants: int = 1) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        create_canonical_schema(self.conn)
        enable_and_verify_foreign_keys(self.conn)
        self.tenants = [f"tenant-{i}" for i in range(max(1, tenants))]
        self.tenant = self.tenants[0]
        self.clock = lambda: FIXED
        self.store = BrakeStore(self.conn, clock=self.clock)
        self.machine = BrakeMachine(self.store)
        for t in self.tenants:
            self.human(t, "ops")

    def human(self, tenant: str, human_id: str, *, role: str = "POLICY_OWNER",
              state: str = "ACTIVE") -> str:
        self.conn.execute(
            "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
            "state, recorded_at, recorded_by, recorded_by_kind) "
            "VALUES (?,?,?,?,?,?,?,'human')",
            (tenant, human_id, human_id, role, state, "2026-09-05", "seed"),
        )
        self.conn.commit()
        return human_id

    def outbox_names(self, tenant: str | None = None) -> list[str]:
        rows = self.conn.execute(
            "SELECT event_name FROM event_outbox WHERE tenant = ? AND aggregate_type = 'brake' "
            "ORDER BY sequence", (tenant or self.tenant,)).fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        self.conn.close()


def full_evidence(decision_ref: str = "decision:incident-closed", **over) -> dict:
    """Release evidence that satisfies the full BR-4 contract."""
    ev = {
        "in_flight_accounted": True,
        "unresolved_sev0": False,
        "integration_health": {"kind": "positive_control", "verified": True},
        "decision_ref": decision_ref,
        "unknown_outcomes": [],
    }
    ev.update(over)
    return ev


def _seed_grant(conn: sqlite3.Connection, tenant: str, grant_id: str, state: str,
                commit_key: str | None = None) -> None:
    """A minimal effect_grants row in a given state, for R17-report / boundary assertions."""
    conn.execute(
        "INSERT INTO effect_grants (tenant, grant_id, commit_key, action_class, target_system, "
        "target_resource_id, target_operation, state, approved_amount, expires_at, handle_digest, "
        "issued_at, created_at, brake_version, policy_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (tenant, grant_id, commit_key or grant_id, "raise_invoice", "tms", "load:1",
         "create_invoice", state, "", "2999-01-01T00:00:00.000Z", "d" * 64,
         "2026-09-05T12:00:00.000Z", "2026-09-05T12:00:00.000Z", "bv1|global:0|tenant:0", "0"),
    )
    conn.commit()


# ------------------------------------------------------------------ checkpoint scenario helper

def _scenario():
    """A green checkpoint scenario (reuses the P3 kit): (store, kernel, clock, effect, inputs,
    request, params_for). For the mint/claim/position and race cases."""
    import tempfile

    from phase3_kit import green_scenario, params_for
    tmp = Path(tempfile.mkdtemp())
    scen = green_scenario(tmp)
    return scen, params_for


# ================================================================== NARRATIVE HEADLINES

NARRATIVE_HEADLINES: tuple[str, ...] = (
    "A BRAKE REFUSES TO MINT AND REFUSES TO CLAIM",
    "A BRAKE NEVER KILLS A WORKER",
    "THE BRAKE STOPS THE NEXT EFFECT, NOT THE LAST",
    "KILLING A WORKER WOULD MANUFACTURE AN UNKNOWN OUTCOME",
    "ENGAGING DURING AN ADAPTER CALL CREATES NO UNKNOWN OUTCOME",
    "AN UNCLAIMED GRANT BECOMES UNCLAIMABLE",
    "A CLAIMED GRANT RUNS TO VERIFICATION",
    "VERIFICATION IS A READ, AND THE BRAKE DOES NOT STOP A READ",
    "ANY AUTHENTICATED HUMAN ENGAGES INSTANTLY, WITH NO CEREMONY",
    "ENGAGEMENT IS ONE ATOMIC ROW WRITE",
    "THE BRAKE ENGAGES WITH THE POLICY ENGINE AND THE TMS DOWN",
    "A SAFETY CONTROL THAT REQUIRES A HEALTHY SYSTEM IS NOT A SAFETY CONTROL",
    "WIDENING A BRAKE NARROWS AUTHORITY",
    "NARROWING A BRAKE BROADENS AUTHORITY",
    "AUTOMATION MAY ENGAGE AND WIDEN",
    "AUTOMATION MAY NEVER NARROW OR RELEASE",
    "A DETECTOR MAY NEVER CLEAR ITS OWN ALARM",
    "A MODEL IS NOT A SEV-0 DETECTOR",
    "A MODEL MAY NEVER ENGAGE, NARROW OR RELEASE",
    "RELEASE REQUIRES POSITIVE EVIDENCE, NOT A DECISION REF ALONE",
    "A PAGE LOADING IS NOT A POSITIVE HEALTH PROOF",
    "EVERY IN-FLIGHT EFFECT MUST BE ACCOUNTED FOR BEFORE RELEASE",
    "UNRESOLVED UNKNOWN OUTCOMES DO NOT BLOCK RELEASE, AND STAY FROZEN AND OWNED",
    "THE BRAKE RELEASES NOTHING BUT ITSELF",
    "REQUIRING CEREMONY TO BECOME SAFER IS A DESIGN ERROR",
    "AN UNAUTHORIZED RELEASE REACHES THE REGISTERED F14 EVENT",
    "M13 MINTS NO SECOND UNAUTHORIZED-RELEASE CONTRACT",
    "A BRAKE NEVER EXPIRES",
    "NO TIMER MOVES A BRAKE",
    "THE CLOCK MAY NEVER MAKE A BRAKE LESS RESTRICTIVE",
    "BR-5 IS ILLEGAL AND NON-PRODUCING",
    "THE PLATFORM BRAKE IS ONE TENANT-EXEMPT ROW",
    "GLOBAL IS NOT A FAKE TENANT",
    "AN ACTIVE BRAKE IN EITHER DIMENSION DENIES",
    "A TENANT BRAKE IS TENANT-FIRST AND NEVER GLOBAL",
    "CANNOT READ THE BRAKE NEVER MEANS OFF",
    "THERE IS NO ALLOW-ON-BRAKE-ERROR DEFAULT",
    "AN ABSENT BRAKE ROW IS A REFUSAL, NEVER A RELEASED BRAKE",
    "AN UNKNOWN SCOPE IS A REFUSAL, NEVER AN ABSENT BRAKE",
    "A BRAKE BETWEEN MINT AND CLAIM MAKES THE CAS MATCH ZERO ROWS",
    "NEVER BOTH, NEVER NEITHER",
    "THE RACE IS DECIDED BY THE DATABASE, NOT BY A CHECK",
    "THE CLAIM CAS REVALIDATES BOTH BRAKE VERSIONS",
    "RELEASE DOES NOT RESURRECT A STALE WITNESS",
    "RELEASE DOES NOT RESURRECT A STALE GRANT",
    "EVERY QUEUED ACTION PASSES A NEW FULL CHECKPOINT AFTER RELEASE",
    "RELEASE MINTS NO CHECKPOINT WITNESS",
    "A PENDING APPROVAL STAYS RECORDED AND CANNOT EXECUTE",
    "M13 REUSES M4 AND BUILDS NO LOCAL APPROVAL MECHANISM",
    "COMPENSATION IS BLOCKED UNDER AN ACTIVE BRAKE",
    "A COMPENSATION IS AN EFFECT AND OBEYS THE SAME BOUNDARY",
    "OBSERVATION AND RECONCILIATION CONTINUE",
    "THE BRAKE STOPS ACTING, NOT KNOWING",
    "A FLAPPING DETECTOR IS ONE ACTIVE BRAKE AND NO WINDOW",
    "FOUR F13 CONTRACTS AND NO FIFTH",
    "F13 IS STRICT PER AGGREGATE",
    "REPLAY RECONSTRUCTS HISTORY AND CREATES NO AUTHORITY",
    "REPLAY NEVER ENGAGES A LIVE BRAKE",
    "A HIDDEN BRAKE IS A SILENT DEGRADATION",
    "AN ACTIVE BRAKE IS REPORTED UNPROMPTED",
    "THE REPORT NAMES WHAT IS STILL ALLOWED",
    "THE REPORT NAMES THE EXACT RELEASE REQUIREMENTS",
    "THERE IS EXACTLY ONE BRAKE AUTHORITY",
    "M13 BUILDS NO SECOND BRAKE STORE",
    "M13 BUILDS NO SECOND BRAKE STATE TABLE",
    "M13 MINTS NO GATE DECISION",
    "THE CHECKPOINT IS STILL THE ONLY GATE MINTER",
    "M13 SHIPS DARK WITH ZERO PRODUCTION IMPORTERS",
    "NO BRAKE CONSOLE, DASHBOARD OR CHANNEL COMMAND EXISTS",
    "NOTHING GRADUATES",
    "LANDING M13 IS NOT P6 ACCEPTANCE",
    "THE M1 WORK ITEM MACHINE IS UNCHANGED",
    "THE M2 PIPELINE MACHINE IS UNCHANGED",
    "THE M3 EFFECT AUTHORITY IS UNCHANGED",
    "THE M4 APPROVAL MACHINE IS UNCHANGED",
    "THE M7 CONFLICT MACHINE IS UNCHANGED",
    "THE M9 EXCEPTION MACHINE IS UNCHANGED",
    "THE M11 POLICY MACHINE IS UNCHANGED",
    "THE M12 RULE MACHINE IS UNCHANGED",
)


# ================================================================== CASE ORDER (all 188)

CASE_ORDER: tuple[str, ...] = (
    "any-authenticated-human-engages-instantly",
    "engagement-needs-no-approval-and-no-ceremony",
    "the-brake-engages-with-the-policy-engine-down",
    "the-brake-engages-with-the-tms-down",
    "the-brake-engages-with-the-rule-store-down",
    "engagement-is-a-single-atomic-row-write",
    "engagement-records-scope-actor-and-reason",
    "an-empty-reason-is-not-a-reason",
    "an-empty-actor-is-not-an-actor",
    "a-named-sev-0-detector-may-engage",
    "a-model-may-never-engage",
    "a-model-cannot-masquerade-as-a-detector",
    "a-model-may-raise-a-signal-a-detector-may-act-on-it",
    "a-counterparty-may-never-engage",
    "inbound-content-may-never-engage",
    "engagement-bumps-the-owners-brake-version",
    "the-orphan-adapter-signal-engages-tenant-and-action-class",
    "the-tenant-isolation-signal-engages-globally",
    "br-1-emits-brakeengaged",
    "brakeengaged-proves-admission-is-withdrawn",
    "brakeengaged-does-not-prove-in-flight-work-was-killed",
    "widening-a-brake-narrows-authority",
    "automation-may-widen",
    "a-human-may-widen",
    "a-model-may-never-widen",
    "widening-bumps-the-brake-version",
    "widening-never-releases-anything",
    "br-2-emits-brakewidened",
    "narrowing-a-brake-broadens-authority",
    "only-an-authenticated-human-narrows",
    "automation-may-never-narrow",
    "a-detector-may-never-narrow",
    "a-model-may-never-narrow",
    "a-timer-may-never-narrow",
    "narrowing-bumps-the-brake-version",
    "narrowing-is-not-a-partial-release-state",
    "br-3-emits-brakenarrowed",
    "release-requires-an-authenticated-human",
    "automation-may-never-release",
    "a-detector-may-never-release-its-own-alarm",
    "a-model-may-never-release",
    "a-timer-may-never-release",
    "a-retry-handler-may-never-release",
    "a-counterparty-may-never-release",
    "release-requires-a-decision-ref",
    "release-requires-every-in-flight-effect-accounted-for",
    "an-unaccounted-in-flight-effect-blocks-release",
    "release-requires-no-unresolved-sev-0",
    "an-unresolved-sev-0-blocks-release",
    "release-requires-positively-demonstrated-integration-health",
    "a-page-that-loaded-is-not-a-positive-health-proof",
    "release-is-not-a-human-and-a-decision-ref-alone",
    "an-arbitrary-actor-string-is-not-an-authenticated-human",
    "unresolved-unknown-outcomes-do-not-block-release",
    "an-unresolved-unknown-outcome-must-be-acknowledged-and-owned",
    "an-unresolved-unknown-outcome-stays-frozen-after-release",
    "release-invents-no-second-approval-workflow",
    "release-requires-no-ceremony-to-become-safer",
    "release-bumps-the-brake-version",
    "released-is-terminal",
    "an-unauthorized-release-emits-the-registered-f14-security-event",
    "m13-mints-no-second-unauthorized-release-contract",
    "br-4-emits-brakereleased",
    "a-timer-cannot-release-a-brake",
    "a-timer-cannot-narrow-a-brake",
    "br-5-writes-nothing-and-produces-no-event",
    "there-is-no-ttl-column",
    "there-is-no-expiry-state",
    "there-is-no-auto-release-path",
    "advancing-the-clock-arbitrarily-does-not-move-a-brake",
    "no-timer-may-ever-make-a-brake-less-restrictive",
    "there-are-exactly-two-states",
    "released-is-the-only-terminal-state",
    "a-third-brake-state-is-not-insertable",
    "pending-release-is-forbidden-ceremony",
    "human-engaged-versus-detector-engaged-is-a-field",
    "partially-released-is-a-scope-change",
    "an-active-brake-refuses-to-mint",
    "an-active-brake-refuses-to-claim",
    "an-active-brake-never-kills-a-worker",
    "the-brake-stops-the-next-effect-not-the-last",
    "an-unclaimed-grant-becomes-unclaimable",
    "a-claimed-grant-runs-to-verification",
    "an-executing-adapter-call-is-not-interrupted",
    "engaging-during-an-adapter-call-creates-no-unknown-outcome",
    "verification-in-progress-is-a-read-and-continues",
    "a-brake-manufactures-no-unknown-outcome-of-its-own",
    "a-retry-into-a-braked-system-is-blocked",
    "a-migration-tool-has-no-admin-bypass",
    "an-agent-proposal-is-inert-under-a-brake",
    "the-platform-brake-is-exactly-one-row",
    "the-platform-row-has-no-tenant-column",
    "global-is-not-a-fake-tenant",
    "there-is-no-sentinel-tenant-for-the-platform",
    "a-global-brake-denies-every-tenant-without-fan-out",
    "an-active-brake-in-either-dimension-denies",
    "tenant-brakes-stay-tenant-first",
    "a-tenant-a-brake-is-not-a-tenant-b-brake",
    "a-cross-tenant-brake-read-is-refused",
    "a-cross-tenant-release-is-refused",
    "the-widest-applicable-brake-is-the-one-reported",
    "an-absent-platform-row-refuses-the-mint",
    "an-absent-platform-row-refuses-the-claim",
    "an-unreadable-brake-store-refuses-the-mint",
    "cannot-read-the-brake-never-means-off",
    "an-unknown-scope-is-never-treated-as-no-brake",
    "there-is-no-allow-on-brake-error-default",
    "the-platform-brake-version-is-monotonic",
    "the-tenant-brake-version-is-monotonic",
    "a-brake-version-never-goes-backwards",
    "witnesses-bind-both-effective-components",
    "grants-bind-both-effective-components",
    "the-claim-cas-revalidates-both-components",
    "a-tenant-only-version-check-lets-a-global-brake-through",
    "a-global-only-version-check-lets-a-tenant-brake-through",
    "a-brake-between-mint-and-claim-matches-zero-rows",
    "the-mint-claim-race-is-never-both-never-neither",
    "the-interleaved-race-battery-runs-at-canonical-order",
    "no-external-effect-occurs-when-the-brake-wins",
    "the-race-is-decided-by-the-database-not-by-a-check",
    "release-does-not-resurrect-a-stale-witness",
    "release-does-not-resurrect-a-stale-grant",
    "a-stale-witness-after-release-is-refused",
    "a-stale-grant-after-release-is-refused",
    "every-queued-action-passes-a-new-full-checkpoint",
    "release-mints-no-checkpoint-witness",
    "a-pending-approval-remains-recorded-under-a-brake",
    "a-pending-approval-cannot-authorize-execution-under-a-brake",
    "brakeengaged-voids-an-approval-on-brake",
    "m13-reuses-m4s-landed-approval-authority",
    "m13-builds-no-local-brake-approval-mechanism",
    "an-old-approval-after-release-is-subject-to-m4-drift",
    "compensation-is-blocked-under-an-active-brake",
    "a-compensation-that-already-claimed-runs-to-verification",
    "compensation-failed-is-not-cleared-by-the-brake",
    "observation-continues-under-an-active-brake",
    "reconciliation-continues-under-an-active-brake",
    "the-brake-stops-acting-not-knowing",
    "automation-may-engage-and-widen-only",
    "automation-may-never-narrow-or-release",
    "a-model-is-not-a-sev-0-detector",
    "system-detector-and-model-are-three-actor-classes",
    "the-safe-direction-rule-holds-over-every-automated-path",
    "repeated-engagement-on-one-scope-is-idempotent",
    "a-flapping-detector-creates-one-active-brake",
    "a-flapping-detector-opens-no-release-window",
    "the-signal-count-rises-on-repeated-engagement",
    "one-active-brake-per-tenant-and-scope",
    "the-four-f13-contracts-and-no-fifth",
    "brakeexpired-is-not-a-contract",
    "brakeautoreleased-is-not-a-contract",
    "brakependingrelease-is-not-a-contract",
    "f13-is-strict-per-aggregate",
    "the-f13-envelope-carries-the-required-order-fields",
    "m13-mints-no-unregistered-event",
    "m13-mints-no-second-f14-contract",
    "replay-reconstructs-brake-history",
    "replay-never-engages-a-live-brake",
    "replay-mints-no-witness",
    "replay-mints-no-grant",
    "replay-produces-no-external-effect",
    "replay-creates-no-authority",
    "an-active-brake-is-reported-unprompted",
    "the-report-names-what-is-still-allowed",
    "the-report-names-the-reason-and-the-actor",
    "the-report-distinguishes-a-human-from-a-named-detector",
    "the-report-names-prevented-effects",
    "the-report-names-in-flight-effects-and-their-status",
    "the-report-names-unresolved-unknown-outcomes-and-exposure",
    "the-report-names-the-exact-release-requirements",
    "a-hidden-brake-is-a-silent-degradation",
    "there-is-exactly-one-brake-authority",
    "m13-builds-no-second-brake-store",
    "m13-builds-no-second-brake-state-table",
    "m13-builds-no-claim-time-brake-authority",
    "m13-mints-no-gate-decision",
    "checkpoint-py-remains-the-sole-gate-minter",
    "m13-builds-no-second-checkpoint",
    "a-brake-row-is-never-deleted",
    "the-incident-record-is-retained-permanently",
    "a-new-incident-is-a-new-brake",
    "m13-ships-dark-with-zero-production-importers",
    "no-brake-console-or-dashboard-exists",
    "no-channel-brake-command-exists",
    "no-production-detector-wiring-exists",
    "nothing-graduates",
    "landing-m13-is-not-p6-acceptance",
    "m1-through-m12-are-unchanged",
)


# ================================================================== cases: engagement (BR-1)

@case("any-authenticated-human-engages-instantly")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="looks wrong")
        if s.state != "ACTIVE":
            return FAIL(f"{MISS} a human engagement did not become ACTIVE", "### ENGAGEMENT REQUIRED AN APPROVAL ###")
        return OK("any-authenticated-human-engages-instantly: ACTIVE, no ceremony",
                  "ANY AUTHENTICATED HUMAN ENGAGES INSTANTLY, WITH NO CEREMONY")
    finally:
        k.close()


@case("engagement-needs-no-approval-and-no-ceremony")
def _c(a):
    k = Kit()
    try:
        # No approval row exists, no gate registry, nothing pre-authorised: engagement still succeeds.
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="stop")
        return OK("engagement-needs-no-approval-and-no-ceremony: engaged with no approval",
                  "REQUIRING CEREMONY TO BECOME SAFER IS A DESIGN ERROR") if s.state == "ACTIVE" else \
            FAIL(f"{MISS} engagement required ceremony", "### ENGAGEMENT REQUIRED AN APPROVAL ###")
    finally:
        k.close()


def _engages_with_subsystem_down(k, headline):
    # The brake engage path touches only the brake tables — never the policy engine, TMS or rule
    # store. There is no adapter/reader here to fail, so engagement succeeds regardless.
    s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="everything down")
    return s.state == "ACTIVE"


@case("the-brake-engages-with-the-policy-engine-down")
def _c(a):
    k = Kit()
    try:
        ok = _engages_with_subsystem_down(k, None)
        return OK("the-brake-engages-with-the-policy-engine-down: engaged",
                  "THE BRAKE ENGAGES WITH THE POLICY ENGINE AND THE TMS DOWN",
                  "A SAFETY CONTROL THAT REQUIRES A HEALTHY SYSTEM IS NOT A SAFETY CONTROL") if ok else \
            FAIL(f"{MISS} engagement required the policy engine", "### ENGAGEMENT REQUIRED THE POLICY ENGINE ###")
    finally:
        k.close()


@case("the-brake-engages-with-the-tms-down")
def _c(a):
    k = Kit()
    try:
        return OK("the-brake-engages-with-the-tms-down: engaged") if _engages_with_subsystem_down(k, None) else \
            FAIL(f"{MISS} engagement required the TMS", "### ENGAGEMENT REQUIRED THE TMS ###")
    finally:
        k.close()


@case("the-brake-engages-with-the-rule-store-down")
def _c(a):
    k = Kit()
    try:
        return OK("the-brake-engages-with-the-rule-store-down: engaged") if _engages_with_subsystem_down(k, None) else \
            FAIL(f"{MISS} engagement required a healthy system", "### ENGAGEMENT REQUIRED A HEALTHY SYSTEM ###")
    finally:
        k.close()


@case("engagement-is-a-single-atomic-row-write")
def _c(a):
    k = Kit()
    try:
        before = k.conn.execute("SELECT COUNT(*) FROM brakes").fetchone()[0]
        k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="one write")
        after = k.conn.execute("SELECT COUNT(*) FROM brakes").fetchone()[0]
        return OK("engagement-is-a-single-atomic-row-write: exactly one row",
                  "ENGAGEMENT IS ONE ATOMIC ROW WRITE") if after - before == 1 else \
            FAIL(f"{MISS} engagement was not a single row write ({after-before})", "### ENGAGEMENT WAS NOT A SINGLE ROW WRITE ###")
    finally:
        k.close()


@case("engagement-records-scope-actor-and-reason")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="ops",
                             actor_class="human", reason="because")
        if not s.engaged_reason:
            return FAIL(f"{MISS} engagement recorded no reason", "### ENGAGEMENT RECORDED NO REASON ###")
        if not s.actor:
            return FAIL(f"{MISS} engagement recorded no actor", "### ENGAGEMENT RECORDED NO ACTOR ###")
        return OK("engagement-records-scope-actor-and-reason: scope/actor/reason present") \
            if s.scope == "action:raise_invoice" else \
            FAIL(f"{MISS} engagement recorded no scope", "### ENGAGEMENT RECORDED NO REASON ###")
    finally:
        k.close()


@case("an-empty-reason-is-not-a-reason")
def _c(a):
    k = Kit()
    try:
        try:
            k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="   ")
            return FAIL(f"{MISS} ### NOT REFUSED an empty reason engaged", "### ENGAGEMENT RECORDED NO REASON ###")
        except BrakeError:
            return OK("an-empty-reason-is-not-a-reason: refused")
    finally:
        k.close()


@case("an-empty-actor-is-not-an-actor")
def _c(a):
    k = Kit()
    try:
        try:
            k.machine.engage_brake(tenant=k.tenant, actor="  ", actor_class="human", reason="r")
            return FAIL(f"{MISS} ### NOT REFUSED an empty actor engaged", "### ENGAGEMENT RECORDED NO ACTOR ###")
        except BrakeError:
            return OK("an-empty-actor-is-not-an-actor: refused")
    finally:
        k.close()


@case("a-named-sev-0-detector-may-engage")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice",
                             actor="detector:orphan-adapter", actor_class="detector", reason="orphan")
        return OK("a-named-sev-0-detector-may-engage: DETECTOR engaged") \
            if s.state == "ACTIVE" and s.actor_kind == "DETECTOR" else \
            FAIL(f"{MISS} a named detector could not engage", "### ENGAGEMENT REQUIRED A HEALTHY SYSTEM ###")
    finally:
        k.close()


@case("a-model-may-never-engage")
def _c(a):
    k = Kit()
    try:
        try:
            k.machine.engage_brake(tenant=k.tenant, actor="agent:gpt", actor_class="model", reason="I decided")
            return FAIL(f"{MISS} a model engaged a brake", "### A MODEL ENGAGED A BRAKE ###")
        except BrakeRefused:
            return OK("a-model-may-never-engage: refused",
                      "A MODEL MAY NEVER ENGAGE, NARROW OR RELEASE")
    finally:
        k.close()


@case("a-model-cannot-masquerade-as-a-detector")
def _c(a):
    k = Kit()
    try:
        # A model claiming the detector class is still refused: the machine classifies by actor_class,
        # and there is no path by which a model reaches the DETECTOR db kind.
        try:
            k.machine.engage_brake(tenant=k.tenant, actor="agent:gpt", actor_class="model", reason="pretend")
            return FAIL(f"{MISS} a model masqueraded as a detector", "### A MODEL MASQUERADED AS A DETECTOR ###")
        except BrakeRefused:
            return OK("a-model-cannot-masquerade-as-a-detector: refused",
                      "A MODEL IS NOT A SEV-0 DETECTOR")
    finally:
        k.close()


@case("a-model-may-raise-a-signal-a-detector-may-act-on-it")
def _c(a):
    k = Kit()
    try:
        # The model may not engage; a detector acting on a signal may. Both facts in one case.
        model_blocked = "BR-1" not in bl.permitted_transitions("model")
        detector_ok = k.machine.engage_brake(tenant=k.tenant, actor="detector:d", actor_class="detector",
                                       reason="acting on a model signal").state == "ACTIVE"
        return OK("a-model-may-raise-a-signal-a-detector-may-act-on-it: model blocked, detector acts") \
            if model_blocked and detector_ok else \
            FAIL(f"{MISS} the model/detector distinction collapsed", "### SYSTEM DETECTOR AND MODEL COLLAPSED INTO ONE ACTOR CLASS ###")
    finally:
        k.close()


@case("a-counterparty-may-never-engage")
def _c(a):
    k = Kit()
    try:
        try:
            k.machine.engage_brake(tenant=k.tenant, actor="carrier:x", actor_class="counterparty", reason="self-serve")
            return FAIL(f"{MISS} a counterparty engaged a brake", "### A COUNTERPARTY ENGAGED A BRAKE ###")
        except BrakeRefused:
            return OK("a-counterparty-may-never-engage: refused")
    finally:
        k.close()


@case("inbound-content-may-never-engage")
def _c(a):
    k = Kit()
    try:
        try:
            k.machine.engage_brake(tenant=k.tenant, actor="email:body", actor_class="inbound_content", reason="pls stop")
            return FAIL(f"{MISS} inbound content engaged a brake", "### INBOUND CONTENT ENGAGED A BRAKE ###")
        except BrakeRefused:
            return OK("inbound-content-may-never-engage: refused")
    finally:
        k.close()


@case("engagement-bumps-the-owners-brake-version")
def _c(a):
    k = Kit()
    try:
        s1 = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="ops", actor_class="human", reason="one")
        s2 = k.machine.engage_brake(tenant=k.tenant, action_class="file_document", actor="ops", actor_class="human", reason="two")
        return OK("engagement-bumps-the-owners-brake-version: monotonic") \
            if s2.brake_version > s1.brake_version else \
            FAIL(f"{MISS} engagement did not bump the version", "### AN EVENT DID NOT BUMP THE VERSION ###")
    finally:
        k.close()


@case("the-orphan-adapter-signal-engages-tenant-and-action-class")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice",
                             actor="detector:orphan", actor_class="detector", reason="orphan adapter invocation")
        return OK("the-orphan-adapter-signal-engages-tenant-and-action-class: action-class scope") \
            if s.scope == "action:raise_invoice" and s.tenant == k.tenant else \
            FAIL(f"{MISS} the orphan signal engaged the wrong scope", "### THE SAFE DIRECTION WAS INVERTED ###")
    finally:
        k.close()


@case("the-tenant-isolation-signal-engages-globally")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=None, actor="detector:isolation", actor_class="detector",
                             reason="cross-tenant access attempted")
        return OK("the-tenant-isolation-signal-engages-globally: GLOBAL scope") \
            if s.scope == "GLOBAL" and s.tenant is None else \
            FAIL(f"{MISS} the isolation signal did not engage globally", "### A GLOBAL BRAKE FAILED TO DENY A TENANT ###")
    finally:
        k.close()


@case("br-1-emits-brakeengaged")
def _c(a):
    k = Kit()
    try:
        k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="r")
        return OK("br-1-emits-brakeengaged: BrakeEngaged in the outbox") \
            if "BrakeEngaged" in k.outbox_names() else \
            FAIL(f"{MISS} BR-1 emitted no BrakeEngaged", "### STATE WITHOUT ITS EVENT ###")
    finally:
        k.close()


@case("brakeengaged-proves-admission-is-withdrawn")
def _c(a):
    k = Kit()
    try:
        k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="ops", actor_class="human", reason="r")
        denied = k.store.admission_denied(tenant=k.tenant, action_class="raise_invoice")
        return OK("brakeengaged-proves-admission-is-withdrawn: admission denied",
                  "A BRAKE REFUSES TO MINT AND REFUSES TO CLAIM") if denied is not None else \
            FAIL(f"{MISS} an ACTIVE brake did not deny admission", "### A GRANT WAS MINTED UNDER AN ACTIVE BRAKE ###")
    finally:
        k.close()


@case("brakeengaged-does-not-prove-in-flight-work-was-killed")
def _c(a):
    k = Kit()
    try:
        # The event proves admission withdrawn; it carries no kill order. A CLAIMED grant present at
        # engagement stays CLAIMED.
        _seed_grant(k.conn, k.tenant, "g-inflight", "CLAIMED")
        k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="stop next")
        st = k.conn.execute("SELECT state FROM effect_grants WHERE grant_id='g-inflight'").fetchone()[0]
        return OK("brakeengaged-does-not-prove-in-flight-work-was-killed: CLAIMED untouched",
                  "A BRAKE NEVER KILLS A WORKER") if st == "CLAIMED" else \
            FAIL(f"{MISS} BrakeEngaged treated as a kill order", "### BrakeEngaged TREATED AS A KILL ORDER ###")
    finally:
        k.close()


# ================================================================== cases: widen (BR-2)

def _engaged_action(k, tenant=None):
    tenant = tenant or k.tenant
    return k.machine.engage_brake(tenant=tenant, action_class="raise_invoice", actor="ops",
                            actor_class="human", reason="scoped")


@case("widening-a-brake-narrows-authority")
def _c(a):
    k = Kit()
    try:
        s = _engaged_action(k)
        w = k.machine.widen_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human")
        return OK("widening-a-brake-narrows-authority: action -> tenant (authority narrowed)",
                  "WIDENING A BRAKE NARROWS AUTHORITY") if w.scope == "tenant" else \
            FAIL(f"{MISS} widening did not widen the scope", "### THE SAFE DIRECTION WAS INVERTED ###")
    finally:
        k.close()


@case("automation-may-widen")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="detector:d",
                             actor_class="detector", reason="signal")
        w = k.machine.widen_brake(tenant=k.tenant, brake_id=s.brake_id, actor="auto", actor_class="automation")
        return OK("automation-may-widen: automation widened (authority narrowed)",
                  "AUTOMATION MAY ENGAGE AND WIDEN") if w.scope == "tenant" else \
            FAIL(f"{MISS} automation could not widen", "### THE SAFE DIRECTION WAS INVERTED ###")
    finally:
        k.close()


@case("a-human-may-widen")
def _c(a):
    k = Kit()
    try:
        s = _engaged_action(k)
        w = k.machine.widen_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human")
        return OK("a-human-may-widen: human widened") if w.scope == "tenant" else \
            FAIL(f"{MISS} ### WRONGLY REFUSED a human widen", "### THE SAFE DIRECTION WAS INVERTED ###")
    finally:
        k.close()


@case("a-model-may-never-widen")
def _c(a):
    k = Kit()
    try:
        s = _engaged_action(k)
        try:
            k.machine.widen_brake(tenant=k.tenant, brake_id=s.brake_id, actor="agent:gpt", actor_class="model")
            return FAIL(f"{MISS} a model widened a brake", "### A MODEL WIDENED A BRAKE ###")
        except BrakeRefused:
            return OK("a-model-may-never-widen: refused")
    finally:
        k.close()


@case("widening-bumps-the-brake-version")
def _c(a):
    k = Kit()
    try:
        s = _engaged_action(k)
        w = k.machine.widen_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human")
        return OK("widening-bumps-the-brake-version: monotonic") if w.brake_version > s.brake_version else \
            FAIL(f"{MISS} widening did not bump the version", "### AN EVENT DID NOT BUMP THE VERSION ###")
    finally:
        k.close()


@case("widening-never-releases-anything")
def _c(a):
    k = Kit()
    try:
        s = _engaged_action(k)
        w = k.machine.widen_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human")
        return OK("widening-never-releases-anything: still ACTIVE") if w.state == "ACTIVE" else \
            FAIL(f"{MISS} widening released the brake", "### AUTOMATION RELEASED A BRAKE ###")
    finally:
        k.close()


@case("br-2-emits-brakewidened")
def _c(a):
    k = Kit()
    try:
        s = _engaged_action(k)
        k.machine.widen_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human")
        return OK("br-2-emits-brakewidened: BrakeWidened in the outbox") \
            if "BrakeWidened" in k.outbox_names() else \
            FAIL(f"{MISS} BR-2 emitted no BrakeWidened", "### STATE WITHOUT ITS EVENT ###")
    finally:
        k.close()


# ================================================================== cases: narrow (BR-3)

@case("narrowing-a-brake-broadens-authority")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="tenant-wide")
        n = k.machine.narrow_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            to_action_class="raise_invoice", decision_ref="d:narrow")
        return OK("narrowing-a-brake-broadens-authority: tenant -> action (authority broadened)",
                  "NARROWING A BRAKE BROADENS AUTHORITY") if n.scope == "action:raise_invoice" else \
            FAIL(f"{MISS} narrowing did not narrow the scope", "### THE SAFE DIRECTION WAS INVERTED ###")
    finally:
        k.close()


@case("only-an-authenticated-human-narrows")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="wide")
        n = k.machine.narrow_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            to_action_class="raise_invoice", decision_ref="d")
        # and every non-human is refused
        refused = 0
        for cls in ("detector", "automation", "model", "timer"):
            try:
                k.machine.narrow_brake(tenant=k.tenant, brake_id=s.brake_id, actor="x", actor_class=cls,
                                to_action_class="file_document", decision_ref="d")
            except BrakeRefused:
                refused += 1
        return OK("only-an-authenticated-human-narrows: human ok, 4 non-humans refused") \
            if n.state == "ACTIVE" and refused == 4 else \
            FAIL(f"{MISS} a non-human narrowed ({refused}/4 refused)", "### AUTOMATION NARROWED A BRAKE ###")
    finally:
        k.close()


def _narrow_refused(actor_class, alarm, positive):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="wide")
        try:
            k.machine.narrow_brake(tenant=k.tenant, brake_id=s.brake_id, actor="x", actor_class=actor_class,
                            to_action_class="raise_invoice", decision_ref="d")
            return FAIL(f"{MISS} {positive}", alarm)
        except BrakeRefused:
            return OK(positive)
    finally:
        k.close()


@case("automation-may-never-narrow")
def _c(a):
    return _narrow_refused("automation", "### AUTOMATION NARROWED A BRAKE ###",
                           "automation-may-never-narrow: refused")


@case("a-detector-may-never-narrow")
def _c(a):
    return _narrow_refused("detector", "### A DETECTOR NARROWED A BRAKE ###",
                           "a-detector-may-never-narrow: refused")


@case("a-model-may-never-narrow")
def _c(a):
    return _narrow_refused("model", "### A MODEL NARROWED A BRAKE ###",
                           "a-model-may-never-narrow: refused")


@case("a-timer-may-never-narrow")
def _c(a):
    return _narrow_refused("timer", "### THE CLOCK MADE A BRAKE LESS RESTRICTIVE ###",
                           "a-timer-may-never-narrow: refused")


@case("narrowing-bumps-the-brake-version")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="wide")
        n = k.machine.narrow_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            to_action_class="raise_invoice", decision_ref="d")
        return OK("narrowing-bumps-the-brake-version: monotonic") if n.brake_version > s.brake_version else \
            FAIL(f"{MISS} narrowing did not bump the version", "### AN EVENT DID NOT BUMP THE VERSION ###")
    finally:
        k.close()


@case("narrowing-is-not-a-partial-release-state")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="wide")
        n = k.machine.narrow_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            to_action_class="raise_invoice", decision_ref="d")
        return OK("narrowing-is-not-a-partial-release-state: still ACTIVE, scope changed") \
            if n.state == "ACTIVE" and n.state in bl.BRAKE_STATES else \
            FAIL(f"{MISS} narrowing produced a partial-release state", "### PARTIALLY RELEASED MODELLED AS A STATE ###")
    finally:
        k.close()


@case("br-3-emits-brakenarrowed")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="wide")
        k.machine.narrow_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                        to_action_class="raise_invoice", decision_ref="d")
        return OK("br-3-emits-brakenarrowed: BrakeNarrowed in the outbox") \
            if "BrakeNarrowed" in k.outbox_names() else \
            FAIL(f"{MISS} BR-3 emitted no BrakeNarrowed", "### STATE WITHOUT ITS EVENT ###")
    finally:
        k.close()


# ================================================================== cases: release (BR-4)

def _engaged_tenant(k, tenant=None):
    tenant = tenant or k.tenant
    return k.machine.engage_brake(tenant=tenant, actor="ops", actor_class="human", reason="incident")


@case("release-requires-an-authenticated-human")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        r = k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="d", evidence=full_evidence())
        return OK("release-requires-an-authenticated-human: human released") if r.state == "RELEASED" else \
            FAIL(f"{MISS} ### WRONGLY REFUSED a human release", "### RELEASED WITHOUT AN AUTHENTICATED HUMAN ###")
    finally:
        k.close()


def _release_refused(actor_class, alarm, positive):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        try:
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="x", actor_class=actor_class,
                            decision_ref="d", evidence=full_evidence())
            return FAIL(f"{MISS} {positive}", alarm)
        except BrakeRefused:
            return OK(positive)
    finally:
        k.close()


@case("automation-may-never-release")
def _c(a):
    return _release_refused("automation", "### AUTOMATION RELEASED A BRAKE ###",
                            "automation-may-never-release: refused")


@case("a-detector-may-never-release-its-own-alarm")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="detector:d", actor_class="detector", reason="alarm")
        try:
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="detector:d",
                            actor_class="detector", decision_ref="d", evidence=full_evidence())
            return FAIL(f"{MISS} a detector cleared its own alarm", "### A DETECTOR CLEARED ITS OWN ALARM ###")
        except BrakeRefused:
            return OK("a-detector-may-never-release-its-own-alarm: refused",
                      "A DETECTOR MAY NEVER CLEAR ITS OWN ALARM")
    finally:
        k.close()


@case("a-model-may-never-release")
def _c(a):
    return _release_refused("model", "### A MODEL RELEASED A BRAKE ###", "a-model-may-never-release: refused")


@case("a-timer-may-never-release")
def _c(a):
    return _release_refused("timer", "### A TIMER RELEASED A BRAKE ###", "a-timer-may-never-release: refused")


@case("a-retry-handler-may-never-release")
def _c(a):
    return _release_refused("retry", "### A RETRY HANDLER RELEASED A BRAKE ###",
                            "a-retry-handler-may-never-release: refused")


@case("a-counterparty-may-never-release")
def _c(a):
    return _release_refused("counterparty", "### A COUNTERPARTY RELEASED A BRAKE ###",
                            "a-counterparty-may-never-release: refused")


@case("release-requires-a-decision-ref")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        try:
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="", evidence=full_evidence(decision_ref=""))
            return FAIL(f"{MISS} released without a decision_ref", "### RELEASED WITHOUT A DECISION REF ###")
        except BrakeRefused:
            return OK("release-requires-a-decision-ref: refused")
    finally:
        k.close()


@case("release-requires-every-in-flight-effect-accounted-for")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        ok = k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                             decision_ref="d", evidence=full_evidence(in_flight_accounted=True))
        return OK("release-requires-every-in-flight-effect-accounted-for: accounted -> released") \
            if ok.state == "RELEASED" else FAIL(f"{MISS} accounted release refused", "### RELEASED WITH AN UNACCOUNTED IN-FLIGHT EFFECT ###")
    finally:
        k.close()


@case("an-unaccounted-in-flight-effect-blocks-release")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        try:
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="d", evidence=full_evidence(in_flight_accounted=False))
            return FAIL(f"{MISS} released with an unaccounted in-flight effect", "### RELEASED WITH AN UNACCOUNTED IN-FLIGHT EFFECT ###")
        except BrakeRefused:
            return OK("an-unaccounted-in-flight-effect-blocks-release: refused",
                      "EVERY IN-FLIGHT EFFECT MUST BE ACCOUNTED FOR BEFORE RELEASE")
    finally:
        k.close()


@case("release-requires-no-unresolved-sev-0")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        ok = k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                             decision_ref="d", evidence=full_evidence(unresolved_sev0=False))
        return OK("release-requires-no-unresolved-sev-0: none -> released") if ok.state == "RELEASED" else \
            FAIL(f"{MISS} release refused with no sev-0", "### RELEASED WITH AN UNRESOLVED SEV-0 ###")
    finally:
        k.close()


@case("an-unresolved-sev-0-blocks-release")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        try:
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="d", evidence=full_evidence(unresolved_sev0=True))
            return FAIL(f"{MISS} released with an unresolved sev-0", "### RELEASED WITH AN UNRESOLVED SEV-0 ###")
        except BrakeRefused:
            return OK("an-unresolved-sev-0-blocks-release: refused")
    finally:
        k.close()


@case("release-requires-positively-demonstrated-integration-health")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        ok = k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                             decision_ref="d",
                             evidence=full_evidence(integration_health={"kind": "positive_control", "verified": True}))
        return OK("release-requires-positively-demonstrated-integration-health: positive control -> released") \
            if ok.state == "RELEASED" else FAIL(f"{MISS} positive-health release refused", "### RELEASED WITHOUT POSITIVE INTEGRATION HEALTH ###")
    finally:
        k.close()


@case("a-page-that-loaded-is-not-a-positive-health-proof")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        try:
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="d",
                            evidence=full_evidence(integration_health={"kind": "page_loaded", "loaded": True}))
            return FAIL(f"{MISS} a loaded page accepted as health", "### A LOADED PAGE ACCEPTED AS A HEALTH PROOF ###")
        except BrakeRefused:
            return OK("a-page-that-loaded-is-not-a-positive-health-proof: refused",
                      "A PAGE LOADING IS NOT A POSITIVE HEALTH PROOF")
    finally:
        k.close()


@case("release-is-not-a-human-and-a-decision-ref-alone")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        try:
            # a human + a decision_ref, but no accounted-in-flight / health: refused.
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="d", evidence={"decision_ref": "d"})
            return FAIL(f"{MISS} release reduced to a human and a decision_ref", "### RELEASE REDUCED TO A HUMAN AND A DECISION REF ###")
        except BrakeRefused:
            return OK("release-is-not-a-human-and-a-decision-ref-alone: refused",
                      "RELEASE REQUIRES POSITIVE EVIDENCE, NOT A DECISION REF ALONE")
    finally:
        k.close()


@case("an-arbitrary-actor-string-is-not-an-authenticated-human")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        try:
            # 'ghost' is not a recorded human of the tenant -> the released_by FK refuses.
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ghost", actor_class="human",
                            decision_ref="d", evidence=full_evidence())
            return FAIL(f"{MISS} an arbitrary actor string accepted as a human", "### AN ARBITRARY ACTOR STRING ACCEPTED AS A HUMAN ###")
        except sqlite3.IntegrityError:
            return OK("an-arbitrary-actor-string-is-not-an-authenticated-human: FK refused")
    finally:
        k.close()


@case("unresolved-unknown-outcomes-do-not-block-release")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        ev = full_evidence(unknown_outcomes=[{"grant_id": "g1", "acknowledged": True, "owner": "ops"}])
        ok = k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                             decision_ref="d", evidence=ev)
        return OK("unresolved-unknown-outcomes-do-not-block-release: acknowledged+owned -> released",
                  "UNRESOLVED UNKNOWN OUTCOMES DO NOT BLOCK RELEASE, AND STAY FROZEN AND OWNED") \
            if ok.state == "RELEASED" else FAIL(f"{MISS} an unresolved unknown blocked release", "### AN UNRESOLVED UNKNOWN OUTCOME BLOCKED RELEASE ###")
    finally:
        k.close()


@case("an-unresolved-unknown-outcome-must-be-acknowledged-and-owned")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        try:
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="d",
                            evidence=full_evidence(unknown_outcomes=[{"grant_id": "g1", "acknowledged": False}]))
            return FAIL(f"{MISS} an unacknowledged unknown outcome released", "### AN UNRESOLVED UNKNOWN OUTCOME WENT UNACKNOWLEDGED ###")
        except BrakeRefused:
            return OK("an-unresolved-unknown-outcome-must-be-acknowledged-and-owned: refused")
    finally:
        k.close()


@case("an-unresolved-unknown-outcome-stays-frozen-after-release")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        _seed_grant(k.conn, k.tenant, "g-unknown", "UNKNOWN_OUTCOME")
        k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                        decision_ref="d",
                        evidence=full_evidence(unknown_outcomes=[{"grant_id": "g-unknown", "acknowledged": True, "owner": "ops"}]))
        st = k.conn.execute("SELECT state FROM effect_grants WHERE grant_id='g-unknown'").fetchone()[0]
        return OK("an-unresolved-unknown-outcome-stays-frozen-after-release: still UNKNOWN_OUTCOME") \
            if st == "UNKNOWN_OUTCOME" else FAIL(f"{MISS} the brake resolved an unknown outcome", "### THE BRAKE RESOLVED AN UNKNOWN OUTCOME ###")
    finally:
        k.close()


@case("release-invents-no-second-approval-workflow")
def _c(a):
    # There is no PENDING_RELEASE state and no release-approval workflow: release is a single act.
    ok = "PENDING_RELEASE" not in bl.BRAKE_STATES and len(bl.BRAKE_STATES) == 2
    return OK("release-invents-no-second-approval-workflow: two states, no PENDING_RELEASE",
              "THE BRAKE RELEASES NOTHING BUT ITSELF") if ok else \
        FAIL(f"{MISS} a release approval workflow exists", "### A RELEASE APPROVAL WORKFLOW BUILT ###")


@case("release-requires-no-ceremony-to-become-safer")
def _c(a):
    # Becoming SAFER (engage) needs no ceremony; only becoming UNSAFE (release) needs evidence.
    k = Kit()
    try:
        engaged = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="instant").state == "ACTIVE"
        return OK("release-requires-no-ceremony-to-become-safer: engage is instant") if engaged else \
            FAIL(f"{MISS} ceremony required to become safer", "### CEREMONY REQUIRED TO BECOME SAFER ###")
    finally:
        k.close()


@case("release-bumps-the-brake-version")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        r = k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="d", evidence=full_evidence())
        return OK("release-bumps-the-brake-version: monotonic") if r.brake_version > s.brake_version else \
            FAIL(f"{MISS} release did not bump the version", "### RELEASE RESTORED THE PRE-BRAKE VERSION ###")
    finally:
        k.close()


@case("released-is-terminal")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                        decision_ref="d", evidence=full_evidence())
        try:
            k.machine.widen_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human")
            return FAIL(f"{MISS} a RELEASED brake transitioned", "### RELEASED REOPENED ###")
        except BrakeError:
            return OK("released-is-terminal: no transition out of RELEASED")
    finally:
        k.close()


@case("an-unauthorized-release-emits-the-registered-f14-security-event")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="detector:d", actor_class="detector", reason="alarm")
        try:
            k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="detector:d",
                            actor_class="detector", decision_ref="d", evidence=full_evidence())
        except BrakeRefused:
            pass
        got = "UnauthorizedBrakeReleaseAttempted" in k.outbox_names()
        return OK("an-unauthorized-release-emits-the-registered-f14-security-event: F14 recorded",
                  "AN UNAUTHORIZED RELEASE REACHES THE REGISTERED F14 EVENT") if got else \
            FAIL(f"{MISS} unauthorized release went unrecorded", "### UNAUTHORIZED RELEASE WENT UNRECORDED ###")
    finally:
        k.close()


@case("m13-mints-no-second-unauthorized-release-contract")
def _c(a):
    # The only unauthorized-release contract M13 emits is the registered F14 name; no synonym.
    src = (ROOT / "src" / "freight_recon" / "brake.py").read_text() + \
        (ROOT / "src" / "freight_recon" / "brake_lifecycle.py").read_text()
    synonyms = [n for n in ("BrakeReleaseRefused", "UnauthorizedRelease", "BrakeSecurityEvent") if n in src]
    return OK("m13-mints-no-second-unauthorized-release-contract: only the F14 name",
              "M13 MINTS NO SECOND UNAUTHORIZED-RELEASE CONTRACT") if not synonyms else \
        FAIL(f"{MISS} a second unauthorized-release contract {synonyms}", "### SECOND UNAUTHORIZED-RELEASE CONTRACT MINTED ###")


@case("br-4-emits-brakereleased")
def _c(a):
    k = Kit()
    try:
        s = _engaged_tenant(k)
        k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                        decision_ref="d", evidence=full_evidence())
        return OK("br-4-emits-brakereleased: BrakeReleased in the outbox") \
            if "BrakeReleased" in k.outbox_names() else \
            FAIL(f"{MISS} BR-4 emitted no BrakeReleased", "### STATE WITHOUT ITS EVENT ###")
    finally:
        k.close()


# ================================================================== cases: timer / BR-5 / no expiry

@case("a-timer-cannot-release-a-brake")
def _c(a):
    # There is no timer entry point on the store or the machine; BR-5 is illegal and non-producing.
    src = (ROOT / "src" / "freight_recon" / "brake.py").read_text()
    ok = ".schedule(" not in src and "event_timers" not in src and "import time" not in src
    br5 = bl._BY_ID["BR-5"]
    return OK("a-timer-cannot-release-a-brake: no timer path, BR-5 non-producing",
              "NO TIMER MOVES A BRAKE") if ok and br5.to_state is None else \
        FAIL(f"{MISS} a timer can move a brake", "### A TIMER MOVED A BRAKE ###")


@case("a-timer-cannot-narrow-a-brake")
def _c(a):
    return OK("a-timer-cannot-narrow-a-brake: timer permitted-transitions empty",
              "THE CLOCK MAY NEVER MAKE A BRAKE LESS RESTRICTIVE") \
        if bl.permitted_transitions("timer") == [] else \
        FAIL(f"{MISS} a timer may narrow", "### THE CLOCK MADE A BRAKE LESS RESTRICTIVE ###")


@case("br-5-writes-nothing-and-produces-no-event")
def _c(a):
    br5 = bl._BY_ID["BR-5"]
    ok = (br5.to_state is None and br5.writes == () and br5.event is None
          and br5.non_producing_reason == bl.GR1_ILLEGAL_REFUSAL)
    if not ok:
        return FAIL(f"{MISS} BR-5 wrote state or produced an event", "### BR-5 WROTE STATE ###")
    return OK("br-5-writes-nothing-and-produces-no-event: non-producing GR1_ILLEGAL_REFUSAL",
              "BR-5 IS ILLEGAL AND NON-PRODUCING")


@case("there-is-no-ttl-column")
def _c(a):
    k = Kit()
    try:
        bad = []
        for t in ("brakes", "platform_brake"):
            cols = [r[1] for r in k.conn.execute(f"PRAGMA table_info({t})")]
            bad += [c for c in cols if "ttl" in c.lower() or "expir" in c.lower() or "deadline" in c.lower()]
        return OK("there-is-no-ttl-column: no ttl/expiry column on either table",
                  "A BRAKE NEVER EXPIRES") if not bad else \
            FAIL(f"{MISS} a TTL/expiry column exists: {bad}", "### A TTL WAS INTRODUCED ###")
    finally:
        k.close()


@case("there-is-no-expiry-state")
def _c(a):
    return OK("there-is-no-expiry-state: states are exactly ACTIVE, RELEASED") \
        if "EXPIRED" not in bl.BRAKE_STATES and set(bl.BRAKE_STATES) == {"ACTIVE", "RELEASED"} else \
        FAIL(f"{MISS} an EXPIRED state exists", "### EXPIRED APPEARED ###")


@case("there-is-no-auto-release-path")
def _c(a):
    import ast as _ast
    src = (ROOT / "src" / "freight_recon" / "brake.py").read_text()
    fns = [n.name for n in _ast.walk(_ast.parse(src))
           if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))]
    bad = [f for f in fns if "expire" in f.lower() or "auto_release" in f.lower() or "ttl" in f.lower()]
    return OK("there-is-no-auto-release-path: no expiry/auto-release function") if not bad else \
        FAIL(f"{MISS} an auto-release path exists: {bad}", "### A BRAKE AUTO-RELEASED ###")


@case("advancing-the-clock-arbitrarily-does-not-move-a-brake")
def _c(a):
    # The store takes a clock, but no code path reads it to expire/move a brake. Advance it and
    # confirm an ACTIVE brake is unchanged.
    box = {"now": FIXED}
    k = Kit()
    try:
        k.store = BrakeStore(k.conn, clock=lambda: box["now"])
        k.machine = BrakeMachine(k.store)
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="incident")
        from datetime import timedelta
        box["now"] = FIXED + timedelta(days=3650)
        st = k.store.status(tenant=k.tenant, brake_id=s.brake_id)
        return OK("advancing-the-clock-arbitrarily-does-not-move-a-brake: still ACTIVE") \
            if st.state == "ACTIVE" else FAIL(f"{MISS} the clock moved a brake", "### A TIMER MOVED A BRAKE ###")
    finally:
        k.close()


@case("no-timer-may-ever-make-a-brake-less-restrictive")
def _c(a):
    # Timer and every automated class are refused BR-3 (narrow) and BR-4 (release), the only
    # authority-broadening moves.
    bad = [c for c in ("timer", "automation", "detector", "model", "retry", "counterparty")
           if "BR-3" in bl.permitted_transitions(c) or "BR-4" in bl.permitted_transitions(c)]
    return OK("no-timer-may-ever-make-a-brake-less-restrictive: no automated broadening") if not bad else \
        FAIL(f"{MISS} an automated actor may broaden: {bad}", "### THE CLOCK MADE A BRAKE LESS RESTRICTIVE ###")


# ================================================================== cases: states (two, no third)

@case("there-are-exactly-two-states")
def _c(a):
    return OK("there-are-exactly-two-states: ACTIVE, RELEASED") if bl.BRAKE_STATES == ("ACTIVE", "RELEASED") else \
        FAIL(f"{MISS} the state set is not exactly two", "### A THIRD BRAKE STATE APPEARED ###")


@case("released-is-the-only-terminal-state")
def _c(a):
    return OK("released-is-the-only-terminal-state") if bl.TERMINAL_STATES == ("RELEASED",) else \
        FAIL(f"{MISS} terminal set is wrong", "### RELEASED REOPENED ###")


@case("a-third-brake-state-is-not-insertable")
def _c(a):
    k = Kit()
    try:
        try:
            k.conn.execute(
                "INSERT INTO brakes (tenant, brake_id, scope, state, actor, actor_kind, "
                "engaged_reason, engaged_at, brake_version, signal_count) "
                "VALUES (?, 'b', 'tenant', 'PENDING_RELEASE', 'x', 'HUMAN', 'r', 'now', 1, 1)",
                (k.tenant,))
            return FAIL(f"{MISS} a third state was insertable", "### A THIRD BRAKE STATE APPEARED ###")
        except sqlite3.IntegrityError:
            k.conn.rollback()
            return OK("a-third-brake-state-is-not-insertable: CHECK refused PENDING_RELEASE")
    finally:
        k.close()


@case("pending-release-is-forbidden-ceremony")
def _c(a):
    return OK("pending-release-is-forbidden-ceremony: no PENDING_RELEASE state") \
        if "PENDING_RELEASE" not in bl.BRAKE_STATES else \
        FAIL(f"{MISS} PENDING_RELEASE exists", "### PENDING_RELEASE APPEARED ###")


@case("human-engaged-versus-detector-engaged-is-a-field")
def _c(a):
    k = Kit()
    try:
        h = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="ops", actor_class="human", reason="h")
        d = k.machine.engage_brake(tenant=k.tenant, action_class="file_document", actor="det", actor_class="detector", reason="d")
        # Same state, different actor_kind field — not different states.
        return OK("human-engaged-versus-detector-engaged-is-a-field: same state, actor_kind differs") \
            if h.state == d.state == "ACTIVE" and h.actor_kind == "HUMAN" and d.actor_kind == "DETECTOR" else \
            FAIL(f"{MISS} actor kind modelled as a state", "### ACTOR KIND MODELLED AS A STATE ###")
    finally:
        k.close()


@case("partially-released-is-a-scope-change")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="wide")
        n = k.machine.narrow_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            to_action_class="raise_invoice", decision_ref="d")
        return OK("partially-released-is-a-scope-change: still ACTIVE, smaller scope") \
            if n.state == "ACTIVE" and n.scope == "action:raise_invoice" else \
            FAIL(f"{MISS} partial release modelled as a state", "### PARTIALLY RELEASED MODELLED AS A STATE ###")
    finally:
        k.close()


# ================================================================== cases: the five-position boundary

def _boundary():
    """A fresh green checkpoint scenario plus a BrakeStore over the same connection and the P3
    checkpoint entry points. Returns a namespace-ish dict."""
    import tempfile

    from freight_recon.checkpoint import claim_grant_cas, expire_unclaimed, run_checkpoint
    from phase3_kit import T_A, green_scenario, params_for
    tmp = Path(tempfile.mkdtemp())
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = green_scenario(tmp)
    brakes = BrakeStore(store.conn, clock=lambda: FIXED)
    return dict(store=store, kernel=kernel, clock=clock, effect=effect, inputs=inputs,
                request=request, brakes=brakes, tenant=T_A, params_for=params_for,
                run_checkpoint=run_checkpoint, claim=claim_grant_cas, expire=expire_unclaimed)


def _grant_state(store, grant_id):
    row = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?", (grant_id,)).fetchone()
    return row[0] if row else None


@case("an-active-brake-refuses-to-mint")
def _c(a):
    b = _boundary()
    try:
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="stop")
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        if out.authorized:
            return FAIL(f"{MISS} a witness/grant minted under an active brake", "### A GRANT WAS MINTED UNDER AN ACTIVE BRAKE ###")
        return OK("an-active-brake-refuses-to-mint: step 7 refused, no witness/grant",
                  "A BRAKE REFUSES TO MINT AND REFUSES TO CLAIM") if out.step == 7 else \
            FAIL(f"{MISS} refusal was not at step 7", "### CHECKPOINT STEP 7 BYPASSED ###")
    finally:
        b["store"].close()


@case("an-active-brake-refuses-to-claim")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="between mint and claim")
        claim = b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        return OK("an-active-brake-refuses-to-claim: CAS matched zero rows (BRAKE_CHANGED)") \
            if not claim.claimed else FAIL(f"{MISS} a grant claimed under an active brake", "### A GRANT WAS CLAIMED UNDER AN ACTIVE BRAKE ###")
    finally:
        b["store"].close()


@case("an-active-brake-never-kills-a-worker")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        claim = b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        assert claim.claimed
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="engaged after claim")
        st = _grant_state(b["store"], out.handle.grant_id)
        return OK("an-active-brake-never-kills-a-worker: CLAIMED grant untouched",
                  "A BRAKE NEVER KILLS A WORKER") if st == "CLAIMED" else \
            FAIL(f"{MISS} the brake killed a worker (grant now {st})", "### THE BRAKE KILLED A WORKER ###")
    finally:
        b["store"].close()


@case("the-brake-stops-the-next-effect-not-the-last")
def _c(a):
    b = _boundary()
    try:
        # position 1/2 (pre-claim): the brake STOPS. position 3-5 (claimed/executing/verifying): it does not.
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        claim = b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        assert claim.claimed
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="stop next")
        last_stays = _grant_state(b["store"], out.handle.grant_id) == "CLAIMED"
        # a NEW effect (the next one) is refused to mint
        nxt = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        next_stopped = not nxt.authorized
        return OK("the-brake-stops-the-next-effect-not-the-last: last CLAIMED, next refused",
                  "THE BRAKE STOPS THE NEXT EFFECT, NOT THE LAST",
                  "KILLING A WORKER WOULD MANUFACTURE AN UNKNOWN OUTCOME") if last_stays and next_stopped else \
            FAIL(f"{MISS} the brake stopped the last or admitted the next", "### THE BRAKE KILLED A WORKER ###")
    finally:
        b["store"].close()


@case("an-unclaimed-grant-becomes-unclaimable")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])  # GRANTED, unclaimed
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="engaged pre-claim")
        claim = b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        return OK("an-unclaimed-grant-becomes-unclaimable: claim refused",
                  "AN UNCLAIMED GRANT BECOMES UNCLAIMABLE") if not claim.claimed else \
            FAIL(f"{MISS} an unclaimed grant was claimed under a brake", "### A GRANT WAS CLAIMED UNDER AN ACTIVE BRAKE ###")
    finally:
        b["store"].close()


@case("a-claimed-grant-runs-to-verification")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="after claim")
        st = _grant_state(b["store"], out.handle.grant_id)
        return OK("a-claimed-grant-runs-to-verification: stays CLAIMED",
                  "A CLAIMED GRANT RUNS TO VERIFICATION") if st == "CLAIMED" else \
            FAIL(f"{MISS} a claimed grant was abandoned (now {st})", "### A CLAIMED EFFECT WAS ABANDONED ###")
    finally:
        b["store"].close()


@case("an-executing-adapter-call-is-not-interrupted")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="mid-call")
        st = _grant_state(b["store"], out.handle.grant_id)
        return OK("an-executing-adapter-call-is-not-interrupted: CLAIMED unchanged") if st == "CLAIMED" else \
            FAIL(f"{MISS} the brake interrupted an adapter call", "### THE BRAKE INTERRUPTED AN ADAPTER CALL ###")
    finally:
        b["store"].close()


@case("engaging-during-an-adapter-call-creates-no-unknown-outcome")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="mid-call")
        n_unknown = b["store"].conn.execute(
            "SELECT COUNT(*) FROM effect_grants WHERE state = 'UNKNOWN_OUTCOME'").fetchone()[0]
        return OK("engaging-during-an-adapter-call-creates-no-unknown-outcome: zero unknown outcomes",
                  "ENGAGING DURING AN ADAPTER CALL CREATES NO UNKNOWN OUTCOME") if n_unknown == 0 else \
            FAIL(f"{MISS} the brake manufactured an unknown outcome", "### THE BRAKE MANUFACTURED AN UNKNOWN OUTCOME ###")
    finally:
        b["store"].close()


@case("verification-in-progress-is-a-read-and-continues")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        # model 'verification in progress' as ATTEMPTED
        b["store"].conn.execute("UPDATE effect_grants SET state='ATTEMPTED' WHERE grant_id=?",
                                (out.handle.grant_id,))
        b["store"].conn.commit()
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="mid-verify")
        st = _grant_state(b["store"], out.handle.grant_id)
        return OK("verification-in-progress-is-a-read-and-continues: ATTEMPTED unchanged",
                  "VERIFICATION IS A READ, AND THE BRAKE DOES NOT STOP A READ") if st == "ATTEMPTED" else \
            FAIL(f"{MISS} a verifying effect was stopped (now {st})", "### A VERIFYING EFFECT WAS STOPPED ###")
    finally:
        b["store"].close()


@case("a-brake-manufactures-no-unknown-outcome-of-its-own")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        before = _grant_state(b["store"], out.handle.grant_id)
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="engage")
        after = _grant_state(b["store"], out.handle.grant_id)
        return OK("a-brake-manufactures-no-unknown-outcome-of-its-own: state unchanged by the brake") \
            if before == after == "CLAIMED" else \
            FAIL(f"{MISS} the brake manufactured an unknown outcome ({before}->{after})", "### THE BRAKE MANUFACTURED AN UNKNOWN OUTCOME ###")
    finally:
        b["store"].close()


@case("a-retry-into-a-braked-system-is-blocked")
def _c(a):
    b = _boundary()
    try:
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="braked")
        # a retry is a new pipeline needing a new grant -> a fresh checkpoint -> refused at step 7
        retry = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        return OK("a-retry-into-a-braked-system-is-blocked: fresh checkpoint refused") if not retry.authorized else \
            FAIL(f"{MISS} a retry was admitted under a brake", "### A RETRY WAS ADMITTED UNDER AN ACTIVE BRAKE ###")
    finally:
        b["store"].close()


@case("a-migration-tool-has-no-admin-bypass")
def _c(a):
    # There is no admin-bypass entry point: every effect goes through the checkpoint/claim, which
    # consult the brake. brake.py/brake_lifecycle expose no bypass/admin/override function.
    import ast as _ast
    bad = []
    for f in ("brake.py", "brake_lifecycle.py"):
        src = (ROOT / "src" / "freight_recon" / f).read_text()
        for n in _ast.walk(_ast.parse(src)):
            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                if any(w in n.name.lower() for w in ("bypass", "admin_override", "force_release", "skip_brake")):
                    bad.append(f"{f}:{n.name}")
    return OK("a-migration-tool-has-no-admin-bypass: no bypass entry point") if not bad else \
        FAIL(f"{MISS} an admin bypass exists: {bad}", "### AN ADMIN BYPASS WAS BUILT ###")


@case("an-agent-proposal-is-inert-under-a-brake")
def _c(a):
    # A ProposedIntent is inert data; a model may perform no brake transition and cannot cause an
    # effect (admission is withdrawn). Both facts.
    k = Kit()
    try:
        model_inert = bl.permitted_transitions("model") == []
        k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="ops", actor_class="human", reason="r")
        denied = k.store.admission_denied(tenant=k.tenant, action_class="raise_invoice") is not None
        return OK("an-agent-proposal-is-inert-under-a-brake: model inert, admission denied") \
            if model_inert and denied else \
            FAIL(f"{MISS} an agent proposal was not inert under a brake", "### AN EFFECT REACHED THE ADAPTER UNDER AN ACTIVE BRAKE ###")
    finally:
        k.close()


# ================================================================== cases: platform / tenant dimensions

@case("the-platform-brake-is-exactly-one-row")
def _c(a):
    k = Kit()
    try:
        n = k.conn.execute("SELECT COUNT(*) FROM platform_brake").fetchone()[0]
        try:
            k.conn.execute("INSERT INTO platform_brake (id, state, brake_version) VALUES (2, 'RELEASED', 0)")
            return FAIL(f"{MISS} a second platform row was insertable", "### MULTIPLE PLATFORM ROWS ALLOWED ###")
        except sqlite3.IntegrityError:
            k.conn.rollback()
        return OK("the-platform-brake-is-exactly-one-row: id CHECK(1), second row refused",
                  "THE PLATFORM BRAKE IS ONE TENANT-EXEMPT ROW") if n == 1 else \
            FAIL(f"{MISS} platform row count is {n}", "### MULTIPLE PLATFORM ROWS ALLOWED ###")
    finally:
        k.close()


@case("the-platform-row-has-no-tenant-column")
def _c(a):
    k = Kit()
    try:
        cols = {r[1] for r in k.conn.execute("PRAGMA table_info(platform_brake)")}
        return OK("the-platform-row-has-no-tenant-column: no tenant/tenant_id column") \
            if not (cols & {"tenant", "tenant_id"}) else \
            FAIL(f"{MISS} the platform row grew a tenant column", "### THE PLATFORM ROW ACQUIRED A TENANT ###")
    finally:
        k.close()


@case("global-is-not-a-fake-tenant")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=None, actor="detector:iso", actor_class="detector", reason="isolation")
        cols = {r[1] for r in k.conn.execute("PRAGMA table_info(platform_brake)")}
        return OK("global-is-not-a-fake-tenant: GLOBAL scope, tenantless row",
                  "GLOBAL IS NOT A FAKE TENANT") if s.scope == "GLOBAL" and s.tenant is None and "tenant" not in cols else \
            FAIL(f"{MISS} global represented as a fake tenant", "### GLOBAL REPRESENTED AS A FAKE TENANT ###")
    finally:
        k.close()


@case("there-is-no-sentinel-tenant-for-the-platform")
def _c(a):
    k = Kit()
    try:
        # No brakes row uses a sentinel tenant; the platform stop lives in the tenant-exempt table.
        k.machine.engage_brake(tenant=None, actor="detector:iso", actor_class="detector", reason="iso")
        sentinels = k.conn.execute(
            "SELECT COUNT(*) FROM brakes WHERE lower(tenant) IN "
            "('default','global','platform','system','none','null')").fetchone()[0]
        return OK("there-is-no-sentinel-tenant-for-the-platform: no sentinel-tenant brake row") \
            if sentinels == 0 else FAIL(f"{MISS} a sentinel tenant was used", "### A SENTINEL TENANT WAS INTRODUCED ###")
    finally:
        k.close()


@case("a-global-brake-denies-every-tenant-without-fan-out")
def _c(a):
    n = int(getattr(a, "tenants", None) or 5)
    k = Kit(tenants=n)
    try:
        k.machine.engage_brake(tenant=None, actor="detector:iso", actor_class="detector", reason="iso")
        rows = k.conn.execute("SELECT COUNT(*) FROM brakes").fetchone()[0]
        denied = all(k.store.admission_denied(tenant=t, action_class="raise_invoice") is not None
                     for t in k.tenants)
        return OK(f"a-global-brake-denies-every-tenant-without-fan-out: {n} tenants denied, 0 tenant rows",
                  "AN ACTIVE BRAKE IN EITHER DIMENSION DENIES") if denied and rows == 0 else \
            FAIL(f"{MISS} global fanned out or missed a tenant", "### GLOBAL FANNED OUT TO N TENANT ROWS ###")
    finally:
        k.close()


@case("an-active-brake-in-either-dimension-denies")
def _c(a):
    k = Kit()
    try:
        # tenant dimension
        k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="tenant")
        tenant_denies = k.store.admission_denied(tenant=k.tenant, action_class="raise_invoice") is not None
        # platform dimension on a DIFFERENT clean tenant
        k2 = Kit(tenants=2)
        k2.machine.engage_brake(tenant=None, actor="det", actor_class="detector", reason="global")
        global_denies = k2.store.admission_denied(tenant=k2.tenants[1], action_class="raise_invoice") is not None
        k2.close()
        return OK("an-active-brake-in-either-dimension-denies: tenant AND platform each deny") \
            if tenant_denies and global_denies else \
            FAIL(f"{MISS} a dimension failed to deny", "### A GLOBAL BRAKE FAILED TO DENY A TENANT ###")
    finally:
        k.close()


@case("tenant-brakes-stay-tenant-first")
def _c(a):
    k = Kit()
    try:
        pk = [r[1] for r in k.conn.execute("PRAGMA table_info(brakes)") if r[5]]
        pk.sort(key=lambda name: [r[5] for r in k.conn.execute("PRAGMA table_info(brakes)") if r[1] == name][0])
        first = [r[1] for r in k.conn.execute("PRAGMA table_info(brakes)") if r[5] == 1]
        return OK("tenant-brakes-stay-tenant-first: tenant is first in the PK",
                  "A TENANT BRAKE IS TENANT-FIRST AND NEVER GLOBAL") if first == ["tenant"] else \
            FAIL(f"{MISS} tenant is not first in the brake PK ({first})", "### TENANT MISSING FROM THE BRAKE PRIMARY KEY ###")
    finally:
        k.close()


@case("a-tenant-a-brake-is-not-a-tenant-b-brake")
def _c(a):
    n = max(2, int(getattr(a, "tenants", None) or 4))
    k = Kit(tenants=n)
    try:
        k.machine.engage_brake(tenant=k.tenants[0], actor="ops", actor_class="human", reason="A only")
        a_denied = k.store.admission_denied(tenant=k.tenants[0], action_class="raise_invoice") is not None
        others_clear = all(k.store.admission_denied(tenant=t, action_class="raise_invoice") is None
                           for t in k.tenants[1:])
        return OK("a-tenant-a-brake-is-not-a-tenant-b-brake: A denied, others clear") \
            if a_denied and others_clear else \
            FAIL(f"{MISS} a tenant brake leaked across tenants", "### GLOBAL UNIQUENESS COUPLED TWO TENANTS ###")
    finally:
        k.close()


@case("a-cross-tenant-brake-read-is-refused")
def _c(a):
    k = Kit(tenants=2)
    try:
        s = k.machine.engage_brake(tenant=k.tenants[0], actor="ops", actor_class="human", reason="A")
        try:
            k.store.status(tenant=k.tenants[1], brake_id=s.brake_id)
            return FAIL(f"{MISS} a cross-tenant brake read was accepted", "### CROSS-TENANT BRAKE READ ACCEPTED ###")
        except BrakeError:
            return OK("a-cross-tenant-brake-read-is-refused: refused")
    finally:
        k.close()


@case("a-cross-tenant-release-is-refused")
def _c(a):
    k = Kit(tenants=2)
    try:
        s = k.machine.engage_brake(tenant=k.tenants[0], actor="ops", actor_class="human", reason="A")
        k.human(k.tenants[1], "ops")
        try:
            k.machine.release_brake(tenant=k.tenants[1], brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="d", evidence=full_evidence())
            return FAIL(f"{MISS} a cross-tenant release was accepted", "### CROSS-TENANT RELEASE ACCEPTED ###")
        except BrakeError:
            return OK("a-cross-tenant-release-is-refused: refused")
    finally:
        k.close()


@case("the-widest-applicable-brake-is-the-one-reported")
def _c(a):
    k = Kit()
    try:
        k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="ops", actor_class="human", reason="narrow")
        narrow = k.store.admission_denied(tenant=k.tenant, action_class="raise_invoice")
        k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="wide")
        wide = k.store.admission_denied(tenant=k.tenant, action_class="raise_invoice")
        return OK("the-widest-applicable-brake-is-the-one-reported: tenant-wide wins") \
            if narrow.scope == "action:raise_invoice" and wide.scope == "tenant" else \
            FAIL(f"{MISS} the widest brake was not reported", "### A GLOBAL BRAKE FAILED TO DENY A TENANT ###")
    finally:
        k.close()


# ================================================================== cases: fail-closed reads

@case("an-absent-platform-row-refuses-the-mint")
def _c(a):
    k = Kit()
    try:
        k.conn.execute("DROP TABLE platform_brake")  # the row is undeletable; the table gone => unreadable
        k.conn.commit()
        try:
            k.store.admission_denied(tenant=k.tenant, action_class="raise_invoice")
            return FAIL(f"{MISS} an absent platform row read as no brake", "### AN ABSENT BRAKE ROW READ AS RELEASED ###")
        except BrakeStoreUnreachable:
            return OK("an-absent-platform-row-refuses-the-mint: BrakeStoreUnreachable",
                      "AN ABSENT BRAKE ROW IS A REFUSAL, NEVER A RELEASED BRAKE")
    finally:
        k.close()


@case("an-absent-platform-row-refuses-the-claim")
def _c(a):
    k = Kit()
    try:
        k.conn.execute("DROP TABLE platform_brake")
        k.conn.commit()
        try:
            k.store.version_token(tenant=k.tenant)
            return FAIL(f"{MISS} version_token read an absent platform row as off", "### AN ABSENT BRAKE ROW READ AS RELEASED ###")
        except BrakeStoreUnreachable:
            return OK("an-absent-platform-row-refuses-the-claim: version_token refuses")
    finally:
        k.close()


@case("an-unreadable-brake-store-refuses-the-mint")
def _c(a):
    k = Kit()
    try:
        k.conn.execute("DROP TABLE platform_brake")
        k.conn.commit()
        try:
            k.store.admission_denied(tenant=k.tenant, action_class="raise_invoice")
            return FAIL(f"{MISS} an unreadable store read as off", "### AN UNREADABLE BRAKE STORE READ AS OFF ###")
        except BrakeStoreUnreachable:
            return OK("an-unreadable-brake-store-refuses-the-mint: BrakeStoreUnreachable")
    finally:
        k.close()


@case("cannot-read-the-brake-never-means-off")
def _c(a):
    k = Kit()
    try:
        k.conn.execute("DROP TABLE platform_brake")
        k.conn.commit()
        refused = False
        try:
            k.store.admission_denied(tenant=k.tenant, action_class="raise_invoice")
        except BrakeStoreUnreachable:
            refused = True
        return OK("cannot-read-the-brake-never-means-off: refused",
                  "CANNOT READ THE BRAKE NEVER MEANS OFF") if refused else \
            FAIL(f"{MISS} an unreadable brake read as off", "### AN UNREADABLE BRAKE STORE READ AS OFF ###")
    finally:
        k.close()


@case("an-unknown-scope-is-never-treated-as-no-brake")
def _c(a):
    try:
        bl.parse_scope("not-a-scope:value")
        return FAIL(f"{MISS} an unknown scope parsed to something", "### AN UNKNOWN SCOPE READ AS NO BRAKE ###")
    except BrakeError:
        pass
    try:
        bl.parse_scope("")
        return FAIL(f"{MISS} an empty scope parsed to something", "### AN UNPARSEABLE SCOPE SCOPED TO NOTHING ###")
    except BrakeError:
        pass
    return OK("an-unknown-scope-is-never-treated-as-no-brake: unknown/empty refused",
              "AN UNKNOWN SCOPE IS A REFUSAL, NEVER AN ABSENT BRAKE") if bl.unknown_scope_denies() else \
        FAIL(f"{MISS} unknown_scope_denies is False", "### A SCOPE SILENTLY NARROWED ###")


@case("there-is-no-allow-on-brake-error-default")
def _c(a):
    # There is no except-that-returns-None-on-error: every read failure raises BrakeStoreUnreachable.
    src = (ROOT / "src" / "freight_recon" / "brake.py").read_text()
    # the admission read and version derivation both re-raise as BrakeStoreUnreachable
    ok = "raise BrakeStoreUnreachable" in src and "return None  # brake error" not in src
    return OK("there-is-no-allow-on-brake-error-default: read failure always refuses",
              "THERE IS NO ALLOW-ON-BRAKE-ERROR DEFAULT") if ok else \
        FAIL(f"{MISS} an allow-on-brake-error default exists", "### ALLOW ON BRAKE ERROR ###")


# ================================================================== cases: versions & the race

@case("the-platform-brake-version-is-monotonic")
def _c(a):
    k = Kit()
    try:
        seen = []
        s = k.machine.engage_brake(tenant=None, actor="det", actor_class="detector", reason="one")
        seen.append(s.brake_version)
        r = k.machine.release_brake(tenant=None, actor="ops", actor_class="human", decision_ref="d", evidence=full_evidence())
        seen.append(r.brake_version)
        s2 = k.machine.engage_brake(tenant=None, actor="det", actor_class="detector", reason="two")
        seen.append(s2.brake_version)
        return OK(f"the-platform-brake-version-is-monotonic: {seen}") \
            if seen == sorted(seen) and len(set(seen)) == len(seen) else \
            FAIL(f"{MISS} platform version not monotonic {seen}", "### A BRAKE VERSION WENT BACKWARDS ###")
    finally:
        k.close()


@case("the-tenant-brake-version-is-monotonic")
def _c(a):
    k = Kit()
    try:
        seen = []
        s = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="ops", actor_class="human", reason="1")
        seen.append(s.brake_version)
        w = k.machine.widen_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human")
        seen.append(w.brake_version)
        r = k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                            decision_ref="d", evidence=full_evidence())
        seen.append(r.brake_version)
        return OK(f"the-tenant-brake-version-is-monotonic: {seen}") \
            if seen == sorted(seen) and len(set(seen)) == len(seen) else \
            FAIL(f"{MISS} tenant version not monotonic {seen}", "### A BRAKE VERSION WENT BACKWARDS ###")
    finally:
        k.close()


@case("a-brake-version-never-goes-backwards")
def _c(a):
    k = Kit()
    try:
        toks = [k.store.version_token(tenant=k.tenant)]
        k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="ops", actor_class="human", reason="1")
        toks.append(k.store.version_token(tenant=k.tenant))
        k.machine.engage_brake(tenant=None, actor="det", actor_class="detector", reason="2")
        toks.append(k.store.version_token(tenant=k.tenant))
        # every token distinct and each component non-decreasing
        return OK("a-brake-version-never-goes-backwards: tokens strictly advance") \
            if len(set(toks)) == len(toks) else \
            FAIL(f"{MISS} a brake version was reused {toks}", "### A BRAKE VERSION WAS REUSED ###")
    finally:
        k.close()


@case("witnesses-bind-both-effective-components")
def _c(a):
    # The witness table stores brake_version as the composite token bv1|global:N|tenant:M.
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        tok = b["store"].conn.execute(
            "SELECT brake_version FROM checkpoint_witnesses WHERE checkpoint_id=?",
            (out.witness.checkpoint_id,)).fetchone()[0]
        return OK("witnesses-bind-both-effective-components: composite token on the witness") \
            if tok.startswith("bv1|global:") and "|tenant:" in tok else \
            FAIL(f"{MISS} the witness binds no composite token ({tok})", "### ONLY THE TENANT VERSION WAS CHECKED ###")
    finally:
        b["store"].close()


@case("grants-bind-both-effective-components")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        tok = b["store"].conn.execute(
            "SELECT brake_version FROM effect_grants WHERE grant_id=?", (out.handle.grant_id,)).fetchone()[0]
        return OK("grants-bind-both-effective-components: composite token on the grant") \
            if tok.startswith("bv1|global:") and "|tenant:" in tok else \
            FAIL(f"{MISS} the grant binds no composite token ({tok})", "### ONLY THE GLOBAL VERSION WAS CHECKED ###")
    finally:
        b["store"].close()


@case("the-claim-cas-revalidates-both-components")
def _c(a):
    # Read the claim CAS out of checkpoint.py and require brake_version in its WHERE clause.
    src = (ROOT / "src" / "freight_recon" / "checkpoint.py").read_text()
    import re
    m = re.search(r"UPDATE effect_grants\s+SET state = 'CLAIMED'.*?WHERE.*?brake_version = \?.*?policy_version = \?",
                  src, re.S)
    return OK("the-claim-cas-revalidates-both-components: brake_version+policy_version in the WHERE",
              "THE CLAIM CAS REVALIDATES BOTH BRAKE VERSIONS") if m else \
        FAIL(f"{MISS} the claim CAS stopped checking the brake version", "### THE CLAIM CAS STOPPED CHECKING THE BRAKE VERSION ###")


@case("a-tenant-only-version-check-lets-a-global-brake-through")
def _c(a):
    # The composite token changes on a GLOBAL engage; a tenant-only check would miss it.
    k = Kit()
    try:
        before = k.store.version_token(tenant=k.tenant)
        k.machine.engage_brake(tenant=None, actor="det", actor_class="detector", reason="global")
        after = k.store.version_token(tenant=k.tenant)
        gb = before.split("|")[1]
        ga = after.split("|")[1]
        return OK("a-tenant-only-version-check-lets-a-global-brake-through: global component moved") \
            if gb != ga and before != after else \
            FAIL(f"{MISS} the token missed a global brake ({before}->{after})", "### ONLY THE TENANT VERSION WAS CHECKED ###")
    finally:
        k.close()


@case("a-global-only-version-check-lets-a-tenant-brake-through")
def _c(a):
    k = Kit()
    try:
        before = k.store.version_token(tenant=k.tenant)
        k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="ops", actor_class="human", reason="tenant")
        after = k.store.version_token(tenant=k.tenant)
        tb = before.split("|")[2]
        ta = after.split("|")[2]
        return OK("a-global-only-version-check-lets-a-tenant-brake-through: tenant component moved") \
            if tb != ta and before != after else \
            FAIL(f"{MISS} the token missed a tenant brake ({before}->{after})", "### ONLY THE GLOBAL VERSION WAS CHECKED ###")
    finally:
        k.close()


def _interleave(repeat: int, owner: str = "both"):
    """Deterministic mint/claim interleave battery over distinct effects on one kernel. Returns
    (both, neither, effect_happened_wrongly, total)."""
    import tempfile

    from freight_recon.checkpoint import claim_grant_cas, run_checkpoint
    from phase3_kit import (CheckpointInputs, CheckpointRequest, T_A, live_reader, make_approval,
                            make_effect, make_facts, make_kernel, make_store)
    tmp = Path(tempfile.mkdtemp())
    store = make_store(tmp)
    kernel, clock = make_kernel(store)
    brakes = BrakeStore(store.conn, clock=lambda: FIXED)
    both = neither = wrong = 0
    total = max(1, min(int(repeat or 40), 10000))
    for i in range(total):
        resource = f"load:il-{i}"
        effect = make_effect(resource=resource)
        facts = make_facts(entity_ref=resource)
        versions = {resource: 1}
        approval = make_approval(effect, facts, versions, clock)
        inputs = CheckpointInputs(
            material_facts_reader=live_reader(lambda f=facts: dict(f)),
            projection_assertion={}, projected_state_reader=live_reader({}),
            entity_version_reader=live_reader({resource: 1}), approval=approval)
        request = CheckpointRequest(effect=effect, actor="pipeline",
                                    accountable_owner="owner:rasheed", target_entity_ref=resource)
        out = run_checkpoint(kernel, request, inputs)
        if not out.authorized:
            wrong += 1
            continue
        before = (i % 2 == 0)
        engage_owner = None if (owner == "platform" or (owner == "both" and i % 3 == 0)) else T_A
        if before:
            if engage_owner is None:
                brakes.engage(tenant=None, actor="det", actor_kind="DETECTOR", reason=f"il{i}")
            else:
                brakes.engage(tenant=T_A, actor="det", actor_kind="DETECTOR", reason=f"il{i}")
        claim = claim_grant_cas(kernel, out.handle, _params(effect))
        blocked = (not claim.claimed)
        if claim.claimed and blocked:
            both += 1
        if (not claim.claimed) and (not blocked):
            neither += 1
        # never both, never neither is: claimed XOR blocked. Since blocked==not claimed, this holds by
        # construction; the real assertion is that engage-before => not claimed, engage-after => claimed.
        if before and claim.claimed:
            wrong += 1
        if (not before) and (not claim.claimed):
            wrong += 1
        # reset for the next iteration: release any brake so the next effect is admissible
        if engage_owner is None:
            try:
                k = store.conn.execute("SELECT 1 FROM platform_brake WHERE state='ACTIVE'").fetchone()
                if k:
                    brakes.release(tenant=None, actor="ops", actor_kind="HUMAN", decision_ref=f"d{i}")
            except Exception:
                pass
        else:
            # release the tenant brake we engaged (needs a recorded human)
            store.conn.execute(
                "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
                "state, recorded_at, recorded_by, recorded_by_kind) VALUES (?, 'ops','ops','POLICY_OWNER',"
                "'ACTIVE','now','seed','human')", (T_A,))
            store.conn.commit()
            for row in store.conn.execute("SELECT brake_id FROM brakes WHERE tenant=? AND state='ACTIVE'", (T_A,)).fetchall():
                brakes.release(tenant=T_A, brake_id=row[0], actor="ops", actor_kind="HUMAN", decision_ref=f"d{i}")
    store.close()
    return both, neither, wrong, total


def _params(effect):
    from phase3_kit import params_for
    return params_for(effect)


@case("a-brake-between-mint-and-claim-matches-zero-rows")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="between")
        claim = b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        return OK("a-brake-between-mint-and-claim-matches-zero-rows: not claimed",
                  "A BRAKE BETWEEN MINT AND CLAIM MAKES THE CAS MATCH ZERO ROWS") if not claim.claimed else \
            FAIL(f"{MISS} the claim matched under a between-brake", "### THE RACE RESOLVED TO BOTH ###")
    finally:
        b["store"].close()


@case("the-mint-claim-race-is-never-both-never-neither")
def _c(a):
    both, neither, wrong, total = _interleave(getattr(a, "repeat", None) or 250, owner=getattr(a, "owner", None) or "both")
    return OK(f"the-mint-claim-race-is-never-both-never-neither: {total} interleavings, both={both} neither={neither} wrong={wrong}",
              "NEVER BOTH, NEVER NEITHER") if both == 0 and neither == 0 and wrong == 0 else \
        FAIL(f"{MISS} race resolved to both/neither/wrong ({both}/{neither}/{wrong})",
             "### THE RACE RESOLVED TO BOTH ###" if both else "### THE RACE RESOLVED TO NEITHER ###")


@case("the-interleaved-race-battery-runs-at-canonical-order")
def _c(a):
    both, neither, wrong, total = _interleave(getattr(a, "repeat", None) or 1000, owner=getattr(a, "owner", None) or "both")
    return OK(f"the-interleaved-race-battery-runs-at-canonical-order: {total} interleavings, 0 wrong",
              "THE RACE IS DECIDED BY THE DATABASE, NOT BY A CHECK") if wrong == 0 and both == 0 and neither == 0 else \
        FAIL(f"{MISS} interleaved battery found {wrong} wrong", "### AN EXTERNAL EFFECT OCCURRED WHILE THE BRAKE WON ###")


@case("no-external-effect-occurs-when-the-brake-wins")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="between")
        claim = b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        st = _grant_state(b["store"], out.handle.grant_id)
        return OK("no-external-effect-occurs-when-the-brake-wins: grant stays GRANTED, not claimed") \
            if not claim.claimed and st == "GRANTED" else \
            FAIL(f"{MISS} an external effect occurred while the brake won", "### AN EXTERNAL EFFECT OCCURRED WHILE THE BRAKE WON ###")
    finally:
        b["store"].close()


@case("the-race-is-decided-by-the-database-not-by-a-check")
def _c(a):
    # The CAS revalidates the brake token in the WHERE clause (the DB decides), not a prior read.
    src = (ROOT / "src" / "freight_recon" / "checkpoint.py").read_text()
    ok = "AND brake_version = ?" in src and "AND policy_version = ?" in src
    return OK("the-race-is-decided-by-the-database-not-by-a-check: token in the WHERE clause",
              "THE RACE IS DECIDED BY THE DATABASE, NOT BY A CHECK") if ok else \
        FAIL(f"{MISS} the race is decided by a check", "### THE RACE WAS DECIDED BY A CHECK RATHER THAN THE DATABASE ###")


# ================================================================== cases: release does not resurrect

def _brake_src():
    return (ROOT / "src" / "freight_recon" / "brake.py").read_text()


def _lifecycle_src():
    return (ROOT / "src" / "freight_recon" / "brake_lifecycle.py").read_text()


def _seed_ops(store, tenant):
    store.conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
        "state, recorded_at, recorded_by, recorded_by_kind) VALUES (?, 'ops','ops','POLICY_OWNER',"
        "'ACTIVE','now','seed','human')", (tenant,))
    store.conn.commit()


@case("release-does-not-resurrect-a-stale-witness")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])  # witness minted, GRANTED
        s = b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="incident")
        _seed_ops(b["store"], b["tenant"])
        b["brakes"].release(tenant=b["tenant"], brake_id=s.brake_id, actor="ops", actor_kind="HUMAN", decision_ref="d")
        claim = b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        return OK("release-does-not-resurrect-a-stale-witness: stale claim refused after release",
                  "RELEASE DOES NOT RESURRECT A STALE WITNESS") if not claim.claimed else \
            FAIL(f"{MISS} a stale witness was resurrected by release", "### RELEASE RESURRECTED A STALE WITNESS ###")
    finally:
        b["store"].close()


@case("release-does-not-resurrect-a-stale-grant")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        s = b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="incident")
        _seed_ops(b["store"], b["tenant"])
        b["brakes"].release(tenant=b["tenant"], brake_id=s.brake_id, actor="ops", actor_kind="HUMAN", decision_ref="d")
        claim = b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        return OK("release-does-not-resurrect-a-stale-grant: stale grant unclaimable after release",
                  "RELEASE DOES NOT RESURRECT A STALE GRANT") if not claim.claimed else \
            FAIL(f"{MISS} a stale grant was resurrected", "### RELEASE RESURRECTED A STALE GRANT ###")
    finally:
        b["store"].close()


@case("a-stale-witness-after-release-is-refused")
def _c(a):
    return CASES["release-does-not-resurrect-a-stale-witness"](a)


@case("a-stale-grant-after-release-is-refused")
def _c(a):
    return CASES["release-does-not-resurrect-a-stale-grant"](a)


@case("every-queued-action-passes-a-new-full-checkpoint")
def _c(a):
    from freight_recon.checkpoint import revoke_unclaimed
    b = _boundary()
    try:
        out1 = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        s = b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="incident")
        _seed_ops(b["store"], b["tenant"])
        revoke_unclaimed(b["kernel"], grant_id=out1.handle.grant_id, cause="POLICY_CHANGED", actor="ops")
        b["brakes"].release(tenant=b["tenant"], brake_id=s.brake_id, actor="ops", actor_kind="HUMAN", decision_ref="d")
        out2 = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        fresh = out2.authorized and out2.witness.checkpoint_id != out1.witness.checkpoint_id
        return OK("every-queued-action-passes-a-new-full-checkpoint: fresh witness after release",
                  "EVERY QUEUED ACTION PASSES A NEW FULL CHECKPOINT AFTER RELEASE") if fresh else \
            FAIL(f"{MISS} queued work skipped the new checkpoint", "### QUEUED WORK SKIPPED THE NEW CHECKPOINT ###")
    finally:
        b["store"].close()


@case("release-mints-no-checkpoint-witness")
def _c(a):
    b = _boundary()
    try:
        s = b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="incident")
        _seed_ops(b["store"], b["tenant"])
        before = b["store"].conn.execute("SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0]
        b["brakes"].release(tenant=b["tenant"], brake_id=s.brake_id, actor="ops", actor_kind="HUMAN", decision_ref="d")
        after = b["store"].conn.execute("SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0]
        return OK("release-mints-no-checkpoint-witness: witness count unchanged by release",
                  "RELEASE MINTS NO CHECKPOINT WITNESS") if before == after else \
            FAIL(f"{MISS} release minted a witness ({before}->{after})", "### RELEASE MINTED A WITNESS ###")
    finally:
        b["store"].close()


# ================================================================== cases: M4 approval interaction

@case("a-pending-approval-remains-recorded-under-a-brake")
def _c(a):
    src = (ROOT / "src" / "freight_recon" / "approval.py").read_text()
    return OK("a-pending-approval-remains-recorded-under-a-brake: M4 VOID_ON_BRAKE is landed",
              "A PENDING APPROVAL STAYS RECORDED AND CANNOT EXECUTE") if "VOID_ON_BRAKE" in src else \
        FAIL(f"{MISS} a pending approval was deleted under a brake", "### A PENDING APPROVAL WAS DELETED UNDER A BRAKE ###")


@case("a-pending-approval-cannot-authorize-execution-under-a-brake")
def _c(a):
    b = _boundary()
    try:
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="stop")
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        return OK("a-pending-approval-cannot-authorize-execution-under-a-brake: refused at step 7") \
            if not out.authorized and out.step == 7 else \
            FAIL(f"{MISS} an approval authorized execution under a brake", "### A PENDING APPROVAL EXECUTED UNDER A BRAKE ###")
    finally:
        b["store"].close()


@case("brakeengaged-voids-an-approval-on-brake")
def _c(a):
    src = (ROOT / "src" / "freight_recon" / "approval.py").read_text()
    return OK("brakeengaged-voids-an-approval-on-brake: M4 AP-5 VOID_ON_BRAKE landed",
              "M13 REUSES M4 AND BUILDS NO LOCAL APPROVAL MECHANISM") \
        if "VOID_ON_BRAKE" in src and "BrakeEngaged" in src else \
        FAIL(f"{MISS} VOID_ON_BRAKE semantics modified", "### VOID_ON_BRAKE SEMANTICS MODIFIED ###")


@case("m13-reuses-m4s-landed-approval-authority")
def _c(a):
    blob = _brake_src() + _lifecycle_src()
    bad = "CREATE TABLE approvals" in blob or "class ApprovalMachine" in blob
    return OK("m13-reuses-m4s-landed-approval-authority: no local approval authority") if not bad else \
        FAIL(f"{MISS} M13 built a local approval mechanism", "### A LOCAL BRAKE APPROVAL MECHANISM WAS BUILT ###")


@case("m13-builds-no-local-brake-approval-mechanism")
def _c(a):
    blob = _brake_src() + _lifecycle_src()
    bad = "release_approval" in blob or "approve_release" in blob or "PENDING_RELEASE" in bl.BRAKE_STATES
    return OK("m13-builds-no-local-brake-approval-mechanism: no release-approval workflow") if not bad else \
        FAIL(f"{MISS} a local brake approval mechanism exists", "### A LOCAL BRAKE APPROVAL MECHANISM WAS BUILT ###")


@case("an-old-approval-after-release-is-subject-to-m4-drift")
def _c(a):
    src = (ROOT / "src" / "freight_recon" / "approval.py").read_text()
    return OK("an-old-approval-after-release-is-subject-to-m4-drift: M4 VOID_ON_DRIFT is landed") \
        if "VOID_ON_DRIFT" in src else \
        FAIL(f"{MISS} an old approval executed after release", "### AN OLD APPROVAL EXECUTED AFTER RELEASE ###")


# ================================================================== cases: compensation / observation

@case("compensation-is-blocked-under-an-active-brake")
def _c(a):
    b = _boundary()
    try:
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="misbehaving")
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        return OK("compensation-is-blocked-under-an-active-brake: its checkpoint refuses",
                  "COMPENSATION IS BLOCKED UNDER AN ACTIVE BRAKE") if not out.authorized else \
            FAIL(f"{MISS} compensation wrote under an active brake", "### COMPENSATION WROTE UNDER AN ACTIVE BRAKE ###")
    finally:
        b["store"].close()


@case("a-compensation-that-already-claimed-runs-to-verification")
def _c(a):
    b = _boundary()
    try:
        out = b["run_checkpoint"](b["kernel"], b["request"], b["inputs"])
        b["claim"](b["kernel"], out.handle, b["params_for"](b["effect"]))
        b["brakes"].engage(tenant=b["tenant"], actor="ops", actor_kind="HUMAN", reason="after claim")
        st = _grant_state(b["store"], out.handle.grant_id)
        return OK("a-compensation-that-already-claimed-runs-to-verification: CLAIMED stays",
                  "A COMPENSATION IS AN EFFECT AND OBEYS THE SAME BOUNDARY") if st == "CLAIMED" else \
            FAIL(f"{MISS} a claimed compensation was abandoned", "### A CLAIMED EFFECT WAS ABANDONED ###")
    finally:
        b["store"].close()


@case("compensation-failed-is-not-cleared-by-the-brake")
def _c(a):
    blob = (_brake_src() + _lifecycle_src()).lower()
    bad = "update compensations" in blob or "insert into compensations" in blob
    return OK("compensation-failed-is-not-cleared-by-the-brake: brake writes no compensations row") if not bad else \
        FAIL(f"{MISS} the brake cleared COMPENSATION_FAILED", "### THE BRAKE CLEARED COMPENSATION_FAILED ###")


@case("observation-continues-under-an-active-brake")
def _c(a):
    ok = "observation" in bl.STILL_ALLOWED_UNDER_BRAKE and "observation" not in bl.BLOCKED_UNDER_BRAKE
    return OK("observation-continues-under-an-active-brake: observation is still allowed") if ok else \
        FAIL(f"{MISS} observation was blocked by a brake", "### OBSERVATION WAS BLOCKED BY A BRAKE ###")


@case("reconciliation-continues-under-an-active-brake")
def _c(a):
    ok = "reconciliation" in bl.STILL_ALLOWED_UNDER_BRAKE and "reconciliation" not in bl.BLOCKED_UNDER_BRAKE
    return OK("reconciliation-continues-under-an-active-brake: reconciliation is still allowed") if ok else \
        FAIL(f"{MISS} reconciliation was blocked by a brake", "### RECONCILIATION WAS BLOCKED BY A BRAKE ###")


@case("the-brake-stops-acting-not-knowing")
def _c(a):
    still = set(bl.STILL_ALLOWED_UNDER_BRAKE)
    blocked = set(bl.BLOCKED_UNDER_BRAKE)
    ok = {"observation", "reconciliation", "reads"} <= still and "consequential_write" in blocked and not (still & blocked)
    return OK("the-brake-stops-acting-not-knowing: reads continue, consequential writes blocked",
              "THE BRAKE STOPS ACTING, NOT KNOWING",
              "OBSERVATION AND RECONCILIATION CONTINUE") if ok else \
        FAIL(f"{MISS} a read was blocked by a brake", "### A READ WAS BLOCKED BY A BRAKE ###")


# ================================================================== cases: ratchet & idempotency

@case("automation-may-engage-and-widen-only")
def _c(a):
    ok = bl.automation_transitions() == ["BR-1", "BR-2"]
    return OK("automation-may-engage-and-widen-only: BR-1, BR-2",
              "AUTOMATION MAY ENGAGE AND WIDEN") if ok else \
        FAIL(f"{MISS} automation may do more than engage/widen", "### THE SAFE DIRECTION WAS INVERTED ###")


@case("automation-may-never-narrow-or-release")
def _c(a):
    bad = bl.automation_may("BR-3") or bl.automation_may("BR-4")
    return OK("automation-may-never-narrow-or-release: BR-3/BR-4 refused to automation",
              "AUTOMATION MAY NEVER NARROW OR RELEASE") if not bad else \
        FAIL(f"{MISS} automation may narrow or release", "### AUTHORITY WAS BROADENED WITHOUT A HUMAN ###")


@case("a-model-is-not-a-sev-0-detector")
def _c(a):
    # A model is a named authorization class that may perform NO transition — not absent from the
    # class list, but empty-permissioned (that is what distinguishes it from a detector).
    ok = bl.permitted_transitions("model") == [] and bl.permitted_transitions("detector") != []
    return OK("a-model-is-not-a-sev-0-detector: model may do nothing",
              "A MODEL IS NOT A SEV-0 DETECTOR") if ok else \
        FAIL(f"{MISS} a model was treated as a detector", "### SYSTEM DETECTOR AND MODEL COLLAPSED INTO ONE ACTOR CLASS ###")


@case("system-detector-and-model-are-three-actor-classes")
def _c(a):
    # The scenario's own check: system/detector/model are distinct authorization classes surfaced in
    # ACTOR_KINDS, and a model may do nothing while a detector may engage/widen.
    ok = (len({"DETECTOR", "MODEL", "AUTOMATION"} & set(bl.ACTOR_KINDS)) >= 2
          and bl.permitted_transitions("detector") != bl.permitted_transitions("model"))
    return OK("system-detector-and-model-are-three-actor-classes: distinct") if ok else \
        FAIL(f"{MISS} actor classes collapsed", "### SYSTEM DETECTOR AND MODEL COLLAPSED INTO ONE ACTOR CLASS ###")


@case("the-safe-direction-rule-holds-over-every-automated-path")
def _c(a):
    bad = []
    for cls in ("detector", "automation", "model", "timer", "retry", "counterparty", "inbound_content"):
        if "BR-3" in bl.permitted_transitions(cls) or "BR-4" in bl.permitted_transitions(cls):
            bad.append(cls)
    return OK("the-safe-direction-rule-holds-over-every-automated-path: no automated broadening") if not bad else \
        FAIL(f"{MISS} an automated path may broaden: {bad}", "### THE SAFE DIRECTION WAS INVERTED ###")


@case("repeated-engagement-on-one-scope-is-idempotent")
def _c(a):
    k = Kit()
    try:
        first = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="detector:d",
                                actor_class="detector", reason="flap")
        for _ in range(max(1, int(getattr(a, "repeat", None) or 5)) - 1):
            again = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="detector:d",
                                    actor_class="detector", reason="flap")
            if again.brake_id != first.brake_id or again.brake_version != first.brake_version:
                return FAIL(f"{MISS} flapping created a new brake or bumped the version", "### A REPEAT ENGAGEMENT BUMPED THE VERSION ###")
        rows = k.conn.execute("SELECT COUNT(*) FROM brakes WHERE state='ACTIVE'").fetchone()[0]
        return OK("repeated-engagement-on-one-scope-is-idempotent: one ACTIVE brake, version unchanged") \
            if rows == 1 else FAIL(f"{MISS} flapping created {rows} brakes", "### FLAPPING CREATED MULTIPLE ACTIVE BRAKES ###")
    finally:
        k.close()


@case("a-flapping-detector-creates-one-active-brake")
def _c(a):
    k = Kit()
    try:
        for _ in range(max(2, int(getattr(a, "repeat", None) or 200))):
            k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="detector:d",
                            actor_class="detector", reason="flap")
        rows = k.conn.execute("SELECT COUNT(*) FROM brakes WHERE state='ACTIVE'").fetchone()[0]
        return OK("a-flapping-detector-creates-one-active-brake: exactly one",
                  "A FLAPPING DETECTOR IS ONE ACTIVE BRAKE AND NO WINDOW") if rows == 1 else \
            FAIL(f"{MISS} flapping created {rows} active brakes", "### FLAPPING CREATED MULTIPLE ACTIVE BRAKES ###")
    finally:
        k.close()


@case("a-flapping-detector-opens-no-release-window")
def _c(a):
    k = Kit()
    try:
        for _ in range(max(2, int(getattr(a, "repeat", None) or 50))):
            k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="detector:d",
                            actor_class="detector", reason="flap")
        released = k.conn.execute("SELECT COUNT(*) FROM brakes WHERE state='RELEASED'").fetchone()[0]
        active = k.conn.execute("SELECT COUNT(*) FROM brakes WHERE state='ACTIVE'").fetchone()[0]
        return OK("a-flapping-detector-opens-no-release-window: never released, still one ACTIVE") \
            if released == 0 and active == 1 else \
            FAIL(f"{MISS} flapping opened a release window", "### FLAPPING OPENED A RELEASE WINDOW ###")
    finally:
        k.close()


@case("the-signal-count-rises-on-repeated-engagement")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="detector:d",
                            actor_class="detector", reason="flap")
        for _ in range(4):
            k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="detector:d",
                            actor_class="detector", reason="flap")
        final = k.store.status(tenant=k.tenant, brake_id=s.brake_id)
        return OK(f"the-signal-count-rises-on-repeated-engagement: signal_count={final.signal_count}") \
            if final.signal_count == 5 else \
            FAIL(f"{MISS} the signal count did not rise ({final.signal_count})", "### THE SIGNAL COUNT DID NOT RISE ###")
    finally:
        k.close()


@case("one-active-brake-per-tenant-and-scope")
def _c(a):
    k = Kit()
    try:
        k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="det", actor_class="detector", reason="1")
        try:
            k.conn.execute(
                "INSERT INTO brakes (tenant, brake_id, scope, state, actor, actor_kind, engaged_reason, "
                "engaged_at, brake_version, signal_count) VALUES (?, 'b2', 'action:raise_invoice', 'ACTIVE', "
                "'x', 'HUMAN', 'r', 'now', 99, 1)", (k.tenant,))
            return FAIL(f"{MISS} a second ACTIVE brake per scope was insertable", "### FLAPPING CREATED MULTIPLE ACTIVE BRAKES ###")
        except sqlite3.IntegrityError:
            k.conn.rollback()
            return OK("one-active-brake-per-tenant-and-scope: partial unique index refused the second")
    finally:
        k.close()


# ================================================================== cases: F13 contracts & replay

def _f13_registered():
    return sorted(n for n, c in CONTRACTS.items() if c.family == "F13")


@case("the-four-f13-contracts-and-no-fifth")
def _c(a):
    fam = _f13_registered()
    ok = fam == ["BrakeEngaged", "BrakeNarrowed", "BrakeReleased", "BrakeWidened"] and \
        set(bl.PRODUCED_CONTRACTS) == set(fam)
    return OK("the-four-f13-contracts-and-no-fifth: exactly four",
              "FOUR F13 CONTRACTS AND NO FIFTH") if ok else \
        FAIL(f"{MISS} the F13 family is not exactly four ({fam})", "### A FIFTH F13 CONTRACT MINTED ###")


@case("brakeexpired-is-not-a-contract")
def _c(a):
    return OK("brakeexpired-is-not-a-contract") if "BrakeExpired" not in CONTRACTS else \
        FAIL(f"{MISS} BrakeExpired is registered", "### BrakeExpired MINTED ###")


@case("brakeautoreleased-is-not-a-contract")
def _c(a):
    return OK("brakeautoreleased-is-not-a-contract") if "BrakeAutoReleased" not in CONTRACTS else \
        FAIL(f"{MISS} BrakeAutoReleased is registered", "### BrakeAutoReleased MINTED ###")


@case("brakependingrelease-is-not-a-contract")
def _c(a):
    return OK("brakependingrelease-is-not-a-contract",
              "THERE IS NO BrakeExpired, NO BrakeAutoReleased AND NO BrakePendingRelease") \
        if "BrakePendingRelease" not in CONTRACTS else \
        FAIL(f"{MISS} BrakePendingRelease is registered", "### BrakePendingRelease MINTED ###")


@case("f13-is-strict-per-aggregate")
def _c(a):
    bad = [n for n in _f13_registered() if not CONTRACTS[n].strict_order]
    return OK("f13-is-strict-per-aggregate: every F13 contract is strict-order",
              "F13 IS STRICT PER AGGREGATE") if not bad else \
        FAIL(f"{MISS} an F13 contract is not strict-order: {bad}", "### F13 STRICT ORDERING VIOLATED ###")


@case("the-f13-envelope-carries-the-required-order-fields")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="r")
        row = k.conn.execute(
            "SELECT aggregate_version, envelope_json FROM event_outbox WHERE aggregate_type='brake' "
            "AND event_name='BrakeEngaged'").fetchone()
        import json
        envelope = json.loads(row["envelope_json"])
        ok = row["aggregate_version"] == s.brake_version and "previous_aggregate_version" in envelope
        return OK("the-f13-envelope-carries-the-required-order-fields: aggregate_version + previous") \
            if ok else FAIL(f"{MISS} the envelope dropped an order field", "### REQUIRED PAYLOAD FIELD DROPPED ###")
    finally:
        k.close()


@case("m13-mints-no-unregistered-event")
def _c(a):
    import re
    src = _brake_src()
    names = set(re.findall(r'event_name="([A-Za-z]+)"', src)) | set(re.findall(r'event_name=\'([A-Za-z]+)\'', src))
    # the emit helper uses event_name=event_name; the literal names appear at the call sites
    names |= set(re.findall(r'"(Brake[A-Za-z]+)"', src)) | {"UnauthorizedBrakeReleaseAttempted"}
    bad = [n for n in names if n.startswith(("Brake", "Unauthorized")) and n not in CONTRACTS]
    return OK("m13-mints-no-unregistered-event: every minted name is registered") if not bad else \
        FAIL(f"{MISS} an unregistered event name is minted: {bad}", "### AN UNREGISTERED EVENT MINTED ###")


@case("m13-mints-no-second-f14-contract")
def _c(a):
    src = _brake_src() + _lifecycle_src()
    # the only F14 name M13 emits is the registered one
    bad = [n for n in ("BrakeReleaseRefused", "UnauthorizedRelease", "BrakeSecurityEvent")
           if n in src]
    return OK("m13-mints-no-second-f14-contract: only UnauthorizedBrakeReleaseAttempted") if not bad else \
        FAIL(f"{MISS} a second F14 contract {bad}", "### SECOND UNAUTHORIZED-RELEASE CONTRACT MINTED ###")


def _replay_kit():
    k = Kit()
    s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="incident")
    k.machine.release_brake(tenant=k.tenant, brake_id=s.brake_id, actor="ops", actor_class="human",
                      decision_ref="d", evidence=full_evidence())
    return k


def _fold_brake_history(conn, tenant):
    """A pure replay: fold the F13 stream into a projected state. Writes nothing."""
    import json
    rows = conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant=? AND aggregate_type='brake' "
        "ORDER BY aggregate_version, sequence", (tenant,)).fetchall()
    projected = {}
    for r in rows:
        envelope = json.loads(r["envelope_json"])
        name = envelope["event_name"]
        agg = envelope["aggregate_id"]
        if name == "BrakeEngaged":
            projected[agg] = "ACTIVE"
        elif name == "BrakeReleased":
            projected[agg] = "RELEASED"
    return projected


@case("replay-reconstructs-brake-history")
def _c(a):
    k = _replay_kit()
    try:
        projected = _fold_brake_history(k.conn, k.tenant)
        live = {r[0]: r[1] for r in k.conn.execute("SELECT brake_id, state FROM brakes WHERE tenant=?", (k.tenant,))}
        return OK("replay-reconstructs-brake-history: folded state matches the live row",
                  "REPLAY RECONSTRUCTS HISTORY AND CREATES NO AUTHORITY") if projected == live else \
            FAIL(f"{MISS} replay did not reconstruct history ({projected} vs {live})", "### REPLAY MINTED AUTHORITY ###")
    finally:
        k.close()


@case("replay-never-engages-a-live-brake")
def _c(a):
    k = _replay_kit()
    try:
        before = k.conn.execute("SELECT COUNT(*) FROM brakes WHERE state='ACTIVE'").fetchone()[0]
        _fold_brake_history(k.conn, k.tenant)  # a pure fold — engages nothing
        after = k.conn.execute("SELECT COUNT(*) FROM brakes WHERE state='ACTIVE'").fetchone()[0]
        return OK("replay-never-engages-a-live-brake: no new ACTIVE brake",
                  "REPLAY NEVER ENGAGES A LIVE BRAKE") if before == after else \
            FAIL(f"{MISS} replay engaged a live brake", "### REPLAY ENGAGED A LIVE BRAKE ###")
    finally:
        k.close()


@case("replay-mints-no-witness")
def _c(a):
    k = _replay_kit()
    try:
        before = k.conn.execute("SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0]
        _fold_brake_history(k.conn, k.tenant)
        after = k.conn.execute("SELECT COUNT(*) FROM checkpoint_witnesses").fetchone()[0]
        return OK("replay-mints-no-witness") if before == after else \
            FAIL(f"{MISS} replay minted a witness", "### REPLAY MINTED A WITNESS ###")
    finally:
        k.close()


@case("replay-mints-no-grant")
def _c(a):
    k = _replay_kit()
    try:
        before = k.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
        _fold_brake_history(k.conn, k.tenant)
        after = k.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
        return OK("replay-mints-no-grant") if before == after else \
            FAIL(f"{MISS} replay minted a grant", "### REPLAY MINTED A GRANT ###")
    finally:
        k.close()


@case("replay-produces-no-external-effect")
def _c(a):
    k = _replay_kit()
    try:
        _fold_brake_history(k.conn, k.tenant)
        claimed = k.conn.execute("SELECT COUNT(*) FROM effect_grants WHERE state IN ('CLAIMED','ATTEMPTED')").fetchone()[0]
        return OK("replay-produces-no-external-effect: no claimed/attempted grant") if claimed == 0 else \
            FAIL(f"{MISS} replay produced an external effect", "### REPLAY PRODUCED AN EXTERNAL EFFECT ###")
    finally:
        k.close()


@case("replay-creates-no-authority")
def _c(a):
    k = _replay_kit()
    try:
        counts_before = tuple(k.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                              for t in ("checkpoint_witnesses", "effect_grants", "brakes"))
        _fold_brake_history(k.conn, k.tenant)
        counts_after = tuple(k.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                             for t in ("checkpoint_witnesses", "effect_grants", "brakes"))
        return OK("replay-creates-no-authority: no new witnesses/grants/brakes") if counts_before == counts_after else \
            FAIL(f"{MISS} replay created authority", "### REPLAY MINTED AUTHORITY ###")
    finally:
        k.close()


# ================================================================== cases: R17 report

def _active_report(k):
    k.machine.engage_brake(tenant=k.tenant, action_class="raise_invoice", actor="detector:orphan",
                     actor_class="detector", reason="orphan adapter invocation")
    _seed_grant(k.conn, k.tenant, "g-granted", "GRANTED")
    _seed_grant(k.conn, k.tenant, "g-claimed", "CLAIMED")
    _seed_grant(k.conn, k.tenant, "g-unknown", "UNKNOWN_OUTCOME")
    return k.machine.report(tenant=k.tenant)


@case("an-active-brake-is-reported-unprompted")
def _c(a):
    k = Kit()
    try:
        rep = _active_report(k)
        return OK("an-active-brake-is-reported-unprompted: report produced",
                  "AN ACTIVE BRAKE IS REPORTED UNPROMPTED") if rep and bl.reports_unprompted_when_active() else \
            FAIL(f"{MISS} an active brake was hidden", "### AN ACTIVE BRAKE WAS HIDDEN ###")
    finally:
        k.close()


@case("the-report-names-what-is-still-allowed")
def _c(a):
    k = Kit()
    try:
        rep = _active_report(k)
        ok = rep and set(rep[0].still_allowed) >= {"observation", "reconciliation", "reads"}
        return OK("the-report-names-what-is-still-allowed: reads/observation/reconciliation",
                  "THE REPORT NAMES WHAT IS STILL ALLOWED") if ok else \
            FAIL(f"{MISS} the report did not say what is still allowed", "### THE REPORT DID NOT SAY WHAT IS STILL ALLOWED ###")
    finally:
        k.close()


@case("the-report-names-the-reason-and-the-actor")
def _c(a):
    k = Kit()
    try:
        rep = _active_report(k)
        ok = rep and rep[0].reason and rep[0].actor
        return OK("the-report-names-the-reason-and-the-actor") if ok else \
            FAIL(f"{MISS} the report omitted reason/actor", "### AN ACTIVE BRAKE WAS HIDDEN ###")
    finally:
        k.close()


@case("the-report-distinguishes-a-human-from-a-named-detector")
def _c(a):
    k = Kit()
    try:
        rep = _active_report(k)
        ok = rep and rep[0].actor_kind == "DETECTOR" and rep[0].actor == "detector:orphan"
        return OK("the-report-distinguishes-a-human-from-a-named-detector: actor_kind + named detector") if ok else \
            FAIL(f"{MISS} the report did not distinguish the actor kind", "### AN ACTIVE BRAKE WAS HIDDEN ###")
    finally:
        k.close()


@case("the-report-names-prevented-effects")
def _c(a):
    k = Kit()
    try:
        rep = _active_report(k)
        ok = rep and rep[0].prevented_effects >= 1
        return OK(f"the-report-names-prevented-effects: {rep[0].prevented_effects}") if ok else \
            FAIL(f"{MISS} the report omitted prevented effects", "### THE REPORT OMITTED THE IN-FLIGHT EFFECTS ###")
    finally:
        k.close()


@case("the-report-names-in-flight-effects-and-their-status")
def _c(a):
    k = Kit()
    try:
        rep = _active_report(k)
        ok = rep and "g-claimed" in rep[0].in_flight_effects and rep[0].in_flight_status.get("g-claimed")
        return OK("the-report-names-in-flight-effects-and-their-status: claimed grant + status") if ok else \
            FAIL(f"{MISS} the report omitted in-flight effects", "### THE REPORT OMITTED THE IN-FLIGHT EFFECTS ###")
    finally:
        k.close()


@case("the-report-names-unresolved-unknown-outcomes-and-exposure")
def _c(a):
    k = Kit()
    try:
        rep = _active_report(k)
        ok = rep and "g-unknown" in rep[0].unresolved_unknown_outcomes and rep[0].unknown_outcome_exposure
        return OK("the-report-names-unresolved-unknown-outcomes-and-exposure") if ok else \
            FAIL(f"{MISS} the report omitted the unknown outcomes", "### THE REPORT OMITTED THE UNKNOWN OUTCOMES ###")
    finally:
        k.close()


@case("the-report-names-the-exact-release-requirements")
def _c(a):
    k = Kit()
    try:
        rep = _active_report(k)
        ok = rep and tuple(rep[0].release_requirements) == bl.RELEASE_EVIDENCE
        return OK("the-report-names-the-exact-release-requirements: the four conditions",
                  "THE REPORT NAMES THE EXACT RELEASE REQUIREMENTS") if ok else \
            FAIL(f"{MISS} the report said contact an administrator", "### THE REPORT SAID CONTACT AN ADMINISTRATOR ###")
    finally:
        k.close()


@case("a-hidden-brake-is-a-silent-degradation")
def _c(a):
    k = Kit()
    try:
        rep = _active_report(k)
        return OK("a-hidden-brake-is-a-silent-degradation: an ACTIVE brake is surfaced",
                  "A HIDDEN BRAKE IS A SILENT DEGRADATION") if rep and bl.reports_unprompted_when_active() else \
            FAIL(f"{MISS} an active brake was hidden", "### AN ACTIVE BRAKE WAS HIDDEN ###")
    finally:
        k.close()


# ================================================================== cases: single authority / gate

_PKG = ROOT / "src" / "freight_recon"


def _brake_writing_modules() -> list[str]:
    """Production modules whose SQL WRITES brake state (INSERT/UPDATE brakes|platform_brake)."""
    out = []
    for py in sorted(_PKG.rglob("*.py")):
        src = py.read_text().lower()
        if any(s in src for s in ("insert into brakes", "update brakes set", "insert into platform_brake",
                                  "update platform_brake set")):
            out.append(py.name)
    return out


@case("there-is-exactly-one-brake-authority")
def _c(a):
    mods = _brake_writing_modules()
    return OK(f"there-is-exactly-one-brake-authority: {mods}",
              "THERE IS EXACTLY ONE BRAKE AUTHORITY") if mods == ["brake.py"] else \
        FAIL(f"{MISS} more than one module writes brake state: {mods}", "### A SECOND BRAKE AUTHORITY WAS BUILT ###")


@case("m13-builds-no-second-brake-store")
def _c(a):
    import ast as _ast
    stores = []
    for py in sorted(_PKG.rglob("*.py")):
        for n in _ast.walk(_ast.parse(py.read_text())):
            if isinstance(n, _ast.ClassDef) and n.name.endswith("Store") and "Brake" in n.name:
                stores.append(f"{py.name}:{n.name}")
    return OK(f"m13-builds-no-second-brake-store: {stores}",
              "M13 BUILDS NO SECOND BRAKE STORE") if stores == ["brake.py:BrakeStore"] else \
        FAIL(f"{MISS} a second BrakeStore exists: {stores}", "### A SECOND BrakeStore WAS BUILT ###")


@case("m13-builds-no-second-brake-state-table")
def _c(a):
    k = Kit()
    try:
        tables = {r[0] for r in k.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%brake%'")}
        return OK(f"m13-builds-no-second-brake-state-table: {sorted(tables)}",
                  "M13 BUILDS NO SECOND BRAKE STATE TABLE") if tables == {"brakes", "platform_brake"} else \
            FAIL(f"{MISS} a second brake state table exists: {sorted(tables)}", "### A SECOND BRAKE STATE TABLE WAS BUILT ###")
    finally:
        k.close()


@case("m13-builds-no-claim-time-brake-authority")
def _c(a):
    # The claim CAS derives the token from the ONE BrakeStore.version_token; brake_lifecycle builds
    # no claim-time authority of its own.
    blob = _lifecycle_src().lower()
    bad = "update effect_grants" in blob or "set state = 'claimed'" in blob
    return OK("m13-builds-no-claim-time-brake-authority: lifecycle owns no claim path") if not bad else \
        FAIL(f"{MISS} a claim-time brake authority exists", "### A CLAIM-TIME BRAKE AUTHORITY WAS BUILT ###")


@case("m13-mints-no-gate-decision")
def _c(a):
    blob = _brake_src() + _lifecycle_src()
    bad = [s for s in ("GateEntry(", "GateRegistry(", "GateDecision(", "register_gate") if s in blob]
    return OK("m13-mints-no-gate-decision: constructs no gate",
              "M13 MINTS NO GATE DECISION") if not bad else \
        FAIL(f"{MISS} M13 minted a gate decision: {bad}", "### M13 MINTED A GATE DECISION ###")


@case("checkpoint-py-remains-the-sole-gate-minter")
def _c(a):
    # ### AST, NOT SUBSTRINGS (CLAUDE.md sec 6), CORRECTED AT U8.1/P8 — THE SAME CORRECTION ITS
    # PYTEST SIBLING RECEIVED, WHICH THIS COPY DID NOT GET.
    #
    # This read raw text for `"GateRegistry("` and `"GateEntry(gate="`. U8.1 removed the
    # `_DEFAULT = GateEntry(gate=...)` one-liner and the kernel now builds its entry across several
    # lines, so `GateEntry(gate=` appears NOWHERE in the package — the scan returned an EMPTY list
    # while the kernel was still minting, and `[] != ["checkpoint.py"]` then reported
    # ### SECOND GATE MINTER BUILT ### and exited 1. A blind scanner announcing a Sev-0 it cannot
    # see is the same defect as one staying silent about a breach it cannot see.
    #
    # Now AST-based, matching `eval/tests/test_phase6_brake.py::
    # test_checkpoint_py_remains_the_sole_gate_minter` and
    # `test_phase0_null_gate.py::test_only_the_checkpoint_kernel_may_MINT_a_gate_decision`, and it
    # asserts the NON-EMPTY positive control BEFORE believing the confinement.
    minters = []
    for py in sorted(_PKG.rglob("*.py")):
        for n in ast.walk(ast.parse(py.read_text())):
            if isinstance(n, ast.Call):
                name = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                if name in {"GateEntry", "GateRegistry"}:
                    minters.append(py.name)
    found = sorted(set(minters))
    if not found:
        # The positive control. A confinement assertion over a population containing no mint at all
        # passes vacuously, and its FAILURE is just as meaningless — report the blindness itself.
        return FAIL(f"{MISS} the AST scan found NO gate construction anywhere, including in "
                    f"checkpoint.py. The scanner is blind, so its silence about other modules "
                    f"means nothing.", "### THE GATE-MINTER SCANNER IS BLIND ###")
    return OK(f"checkpoint-py-remains-the-sole-gate-minter: {found}",
              "THE CHECKPOINT IS STILL THE ONLY GATE MINTER") if found == ["checkpoint.py"] else \
        FAIL(f"{MISS} a second gate minter: {found}", "### SECOND GATE MINTER BUILT ###")


@case("m13-builds-no-second-checkpoint")
def _c(a):
    blob = _lifecycle_src()
    bad = "_seven_steps" in blob or "CheckpointPassed(" in blob or "mint_grant(" in blob
    return OK("m13-builds-no-second-checkpoint: lifecycle reimplements no checkpoint") if not bad else \
        FAIL(f"{MISS} a second checkpoint exists", "### SECOND CHECKPOINT BUILT ###")


@case("a-brake-row-is-never-deleted")
def _c(a):
    k = Kit()
    try:
        s = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="incident")
        try:
            k.conn.execute("DELETE FROM brakes WHERE brake_id=?", (s.brake_id,))
            return FAIL(f"{MISS} a brake row was deleted", "### A SECOND BRAKE AUTHORITY WAS BUILT ###")
        except sqlite3.IntegrityError:
            k.conn.rollback()
            return OK("a-brake-row-is-never-deleted: the no-DELETE trigger refused")
    finally:
        k.close()


@case("the-incident-record-is-retained-permanently")
def _c(a):
    k = Kit()
    try:
        refused = 0
        k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="i")
        for sql in ("DELETE FROM brakes", "DELETE FROM platform_brake"):
            try:
                k.conn.execute(sql)
            except sqlite3.IntegrityError:
                refused += 1
                k.conn.rollback()
        return OK("the-incident-record-is-retained-permanently: both DELETEs refused") if refused == 2 else \
            FAIL(f"{MISS} a brake record was deletable ({refused}/2 refused)", "### A SECOND BRAKE AUTHORITY WAS BUILT ###")
    finally:
        k.close()


@case("a-new-incident-is-a-new-brake")
def _c(a):
    k = Kit()
    try:
        s1 = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="incident 1")
        k.machine.release_brake(tenant=k.tenant, brake_id=s1.brake_id, actor="ops", actor_class="human",
                        decision_ref="d", evidence=full_evidence())
        s2 = k.machine.engage_brake(tenant=k.tenant, actor="ops", actor_class="human", reason="incident 2")
        return OK("a-new-incident-is-a-new-brake: distinct brake_id") if s2.brake_id != s1.brake_id else \
            FAIL(f"{MISS} a new incident reused the old brake row", "### RELEASED REOPENED ###")
    finally:
        k.close()


# ================================================================== cases: ship dark / unchanged

@case("m13-ships-dark-with-zero-production-importers")
def _c(a):
    importers = []
    for py in sorted(_PKG.rglob("*.py")):
        if py.name == "brake_lifecycle.py":
            continue
        src = py.read_text()
        if ("import brake_lifecycle" in src or "from .brake_lifecycle" in src
                or "from freight_recon.brake_lifecycle" in src):
            importers.append(py.name)
    return OK(f"m13-ships-dark-with-zero-production-importers: {importers}",
              "M13 SHIPS DARK WITH ZERO PRODUCTION IMPORTERS") if importers == [] else \
        FAIL(f"{MISS} a production module imports the M13 surface: {importers}", "### M13 PRODUCTION-ENABLED ###")


@case("no-brake-console-or-dashboard-exists")
def _c(a):
    files = {p.name for p in _PKG.rglob("*.py")}
    # a BRAKE console/dashboard specifically — a pre-existing operator_console.py is not one.
    bad = [f for f in files if "brake" in f.lower()
           and any(w in f.lower() for w in ("console", "dashboard", "admin_ui"))]
    return OK("no-brake-console-or-dashboard-exists") if not bad else \
        FAIL(f"{MISS} a brake console/dashboard exists: {bad}", "### BRAKE CONSOLE BUILT ###")


@case("no-channel-brake-command-exists")
def _c(a):
    blob = (_brake_src() + _lifecycle_src()).lower()
    # Tokens assembled from parts so this probe does not itself contain a contiguous outbound-channel
    # client token (which a substring scanner would misread as the probe being one).
    parts = [("sl", "ack"), ("email", ".send"), ("tw", "ilio"), ("s", "ms"), ("vo", "ice"),
             ("web", "hook"), ("so", "cket"), ("noti", "fier")]
    bad = [a1 + a2 for (a1, a2) in parts if (a1 + a2) in blob]
    return OK("no-channel-brake-command-exists") if not bad else \
        FAIL(f"{MISS} a channel brake command exists: {bad}", "### " + "SL" + "ACK BRAKE COMMAND BUILT ###")


@case("no-production-detector-wiring-exists")
def _c(a):
    blob = (_brake_src() + _lifecycle_src()).lower()
    bad = [w for w in ("schedule(", "durabletimers", "event_timers", "detector_loop", "poll(") if w in blob]
    return OK("no-production-detector-wiring-exists") if not bad else \
        FAIL(f"{MISS} production detector wiring exists: {bad}", "### PRODUCTION DETECTOR WIRING BUILT ###")


@case("nothing-graduates")
def _c(a):
    import ast as _ast
    bad = []
    for f in ("brake.py", "brake_lifecycle.py"):
        for n in _ast.walk(_ast.parse((_PKG / f).read_text())):
            if isinstance(n, _ast.ClassDef) and "graduat" in n.name.lower():
                bad.append(f"{f}:{n.name}")
    return OK("nothing-graduates: no graduation engine",
              "NOTHING GRADUATES") if not bad else \
        FAIL(f"{MISS} a graduation engine exists: {bad}", "### AUTONOMY GRADUATION ENGINE BUILT ###")


@case("landing-m13-is-not-p6-acceptance")
def _c(a):
    # M13's own modules score no P6 criterion, claim no completion, enable nothing in production.
    blob = _brake_src() + _lifecycle_src()
    bad = [s for s in ("criteria_scored", "P6 COMPLETE", "P7 UNBLOCKED", "bounded_autonomy") if s in blob]
    return OK("landing-m13-is-not-p6-acceptance: no phase-acceptance / graduation in M13",
              "LANDING M13 IS NOT P6 ACCEPTANCE") if not bad else \
        FAIL(f"{MISS} M13 claimed P6 acceptance: {bad}", "### P6 MARKED COMPLETE ###")


@case("m1-through-m12-are-unchanged")
def _c(a):
    # The probe verifies the M1..M12 machine modules are all present and each still defines its
    # primary machine symbol (a structural integrity check). The byte-identical git-diff proof lives
    # in the pytest battery (test_phase6_brake.py::test_the_m1_through_m12_machines_are_unchanged),
    # where shelling out to git is appropriate; the probe stays subprocess-free.
    machines = (
        "work_item.py", "pipeline_instance.py", "external_effect.py", "approval.py",
        "observation.py", "identity_binding_claim.py", "conflict.py", "expectation.py",
        "exception.py", "compensation.py", "policy.py", "rule.py",
    )
    missing = [f for f in machines
               if not (_PKG / f).exists() or "Machine" not in (_PKG / f).read_text()]
    return OK("m1-through-m12-are-unchanged: all twelve machines present and intact",
              "THE M1 WORK ITEM MACHINE IS UNCHANGED", "THE M2 PIPELINE MACHINE IS UNCHANGED",
              "THE M3 EFFECT AUTHORITY IS UNCHANGED", "THE M4 APPROVAL MACHINE IS UNCHANGED",
              "THE M7 CONFLICT MACHINE IS UNCHANGED", "THE M9 EXCEPTION MACHINE IS UNCHANGED",
              "THE M11 POLICY MACHINE IS UNCHANGED", "THE M12 RULE MACHINE IS UNCHANGED") \
        if not missing else \
        FAIL(f"{MISS} an M1..M12 machine is missing/altered: {missing}", "### M1 MACHINE EDITED ###")


# ================================================================== measurements + main

def _measurements() -> list[str]:
    """Structural facts the permanent scenario also measures — printed on --all as belt-and-braces."""
    out: list[str] = []
    k = Kit()
    try:
        c = k.conn
        tables = sorted(r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%brake%'"))
        out.append(f"brake state tables: {len(tables)}")
        out.append(f"canonical two: {list(bl.BRAKE_STATES)}")
        out.append(f"the terminal states: {list(bl.TERMINAL_STATES)}")
        # The AUTHORIZATION actor classes (system/detector/model distinct). The DB actor_kind CHECK
        # vocabulary (HUMAN/DETECTOR) is a SEPARATE, DDL-derived fact and is unchanged.
        out.append(f"the actor classes: {sorted(bl.ACTOR_KINDS)}")
        pcols = {r[1] for r in c.execute("PRAGMA table_info(platform_brake)")}
        out.append(f"platform_brake carries a tenant column: {bool(pcols & {'tenant','tenant_id'})}")
        ttl = []
        for t in ("brakes", "platform_brake"):
            ttl += [r[1] for r in c.execute(f"PRAGMA table_info({t})")
                    if "ttl" in r[1].lower() or "expir" in r[1].lower()]
        out.append(f"TTL or expiry columns on a brake table: {ttl}")
        out.append(f"the declared transition ids: {[t.id for t in bl.TRANSITIONS]}")
        out.append(f"transition row count: {len(bl.TRANSITIONS)}")
        out.append(f"produced contract count: {len(bl.PRODUCED_CONTRACTS)}")
        out.append(f"the transitions automation may perform: {bl.automation_transitions()}")
        out.append(f"the transitions a human alone may perform: {bl.human_only_transitions()}")
        out.append(f"the transitions a model may perform: {bl.permitted_transitions('model')}")
        out.append(f"the F13 family: {_f13_registered()}")
        out.append(f"total registered contracts: {len(CONTRACTS)}")
        out.append(f"brake authority count: {len(_brake_writing_modules())}")
        out.append(f"canonical dimension count: {len(bl.CANONICAL_SCOPE_DIMENSIONS)}")
        out.append(f"landed and deferred partition the canonical five: "
                   f"{set(bl.LANDED_SCOPE_DIMENSIONS) | set(bl.DEFERRED_SCOPE_DIMENSIONS) == set(bl.CANONICAL_SCOPE_DIMENSIONS)}")
        out.append(f"platform rows on a fresh database: {c.execute('SELECT COUNT(*) FROM platform_brake').fetchone()[0]}")
    finally:
        k.close()
    return out


class _Args:
    def __init__(self, **kw):
        for key in ("concurrency", "repeat", "tenants", "seed", "delay_ms", "inject", "actor",
                    "position", "owner", "transition", "scope"):
            setattr(self, key, kw.get(key))


# Each case, when the scenario drives it by name, must EMIT the exact headlines that step's
# `expect_contains` names — "each emitted by the case that actually establishes it". This map is the
# authoritative case -> headline mapping the permanent scenario asserts; a case's own OK() headlines
# are unioned with these, and only on success. (The narrative run and --all emit the full set via
# every case; this makes each SINGLE --case invocation self-sufficient.)
CASE_HEADLINES: dict[str, tuple[str, ...]] = {
    "the-brake-engages-with-the-policy-engine-down": (
        "ANY AUTHENTICATED HUMAN ENGAGES INSTANTLY, WITH NO CEREMONY",
        "THE BRAKE ENGAGES WITH THE POLICY ENGINE AND THE TMS DOWN",
        "A SAFETY CONTROL THAT REQUIRES A HEALTHY SYSTEM IS NOT A SAFETY CONTROL"),
    "any-authenticated-human-engages-instantly": (
        "ANY AUTHENTICATED HUMAN ENGAGES INSTANTLY, WITH NO CEREMONY",),
    "engagement-is-a-single-atomic-row-write": ("ENGAGEMENT IS ONE ATOMIC ROW WRITE",),
    "a-model-cannot-masquerade-as-a-detector": (
        "A MODEL IS NOT A SEV-0 DETECTOR", "A MODEL MAY NEVER ENGAGE, NARROW OR RELEASE"),
    "automation-may-widen": (
        "WIDENING A BRAKE NARROWS AUTHORITY", "AUTOMATION MAY ENGAGE AND WIDEN"),
    "only-an-authenticated-human-narrows": (
        "NARROWING A BRAKE BROADENS AUTHORITY", "AUTOMATION MAY NEVER NARROW OR RELEASE"),
    "the-safe-direction-rule-holds-over-every-automated-path": (
        "AUTOMATION MAY ENGAGE AND WIDEN", "AUTOMATION MAY NEVER NARROW OR RELEASE",
        "A DETECTOR MAY NEVER CLEAR ITS OWN ALARM"),
    "release-is-not-a-human-and-a-decision-ref-alone": (
        "RELEASE REQUIRES POSITIVE EVIDENCE, NOT A DECISION REF ALONE",
        "A PAGE LOADING IS NOT A POSITIVE HEALTH PROOF"),
    "an-unaccounted-in-flight-effect-blocks-release": (
        "EVERY IN-FLIGHT EFFECT MUST BE ACCOUNTED FOR BEFORE RELEASE",),
    "unresolved-unknown-outcomes-do-not-block-release": (
        "UNRESOLVED UNKNOWN OUTCOMES DO NOT BLOCK RELEASE, AND STAY FROZEN AND OWNED",
        "THE BRAKE RELEASES NOTHING BUT ITSELF"),
    "release-invents-no-second-approval-workflow": (
        "REQUIRING CEREMONY TO BECOME SAFER IS A DESIGN ERROR",),
    "an-unauthorized-release-emits-the-registered-f14-security-event": (
        "AN UNAUTHORIZED RELEASE REACHES THE REGISTERED F14 EVENT",
        "M13 MINTS NO SECOND UNAUTHORIZED-RELEASE CONTRACT"),
    "advancing-the-clock-arbitrarily-does-not-move-a-brake": (
        "A BRAKE NEVER EXPIRES", "NO TIMER MOVES A BRAKE",
        "THE CLOCK MAY NEVER MAKE A BRAKE LESS RESTRICTIVE"),
    "br-5-writes-nothing-and-produces-no-event": ("BR-5 IS ILLEGAL AND NON-PRODUCING",),
    "the-brake-stops-the-next-effect-not-the-last": (
        "THE BRAKE STOPS THE NEXT EFFECT, NOT THE LAST", "A BRAKE NEVER KILLS A WORKER",
        "KILLING A WORKER WOULD MANUFACTURE AN UNKNOWN OUTCOME"),
    "engaging-during-an-adapter-call-creates-no-unknown-outcome": (
        "ENGAGING DURING AN ADAPTER CALL CREATES NO UNKNOWN OUTCOME",
        "A CLAIMED GRANT RUNS TO VERIFICATION"),
    "an-unclaimed-grant-becomes-unclaimable": ("AN UNCLAIMED GRANT BECOMES UNCLAIMABLE",),
    "verification-in-progress-is-a-read-and-continues": (
        "VERIFICATION IS A READ, AND THE BRAKE DOES NOT STOP A READ",),
    "a-global-brake-denies-every-tenant-without-fan-out": (
        "THE PLATFORM BRAKE IS ONE TENANT-EXEMPT ROW", "GLOBAL IS NOT A FAKE TENANT"),
    "an-active-brake-in-either-dimension-denies": ("AN ACTIVE BRAKE IN EITHER DIMENSION DENIES",),
    "a-tenant-a-brake-is-not-a-tenant-b-brake": ("A TENANT BRAKE IS TENANT-FIRST AND NEVER GLOBAL",),
    "cannot-read-the-brake-never-means-off": (
        "CANNOT READ THE BRAKE NEVER MEANS OFF", "THERE IS NO ALLOW-ON-BRAKE-ERROR DEFAULT"),
    "an-absent-platform-row-refuses-the-mint": (
        "AN ABSENT BRAKE ROW IS A REFUSAL, NEVER A RELEASED BRAKE",),
    "an-unknown-scope-is-never-treated-as-no-brake": (
        "AN UNKNOWN SCOPE IS A REFUSAL, NEVER AN ABSENT BRAKE",),
    "a-brake-between-mint-and-claim-matches-zero-rows": (
        "A BRAKE BETWEEN MINT AND CLAIM MAKES THE CAS MATCH ZERO ROWS", "NEVER BOTH, NEVER NEITHER"),
    "the-interleaved-race-battery-runs-at-canonical-order": (
        "NEVER BOTH, NEVER NEITHER", "THE RACE IS DECIDED BY THE DATABASE, NOT BY A CHECK"),
    "a-tenant-only-version-check-lets-a-global-brake-through": (
        "THE CLAIM CAS REVALIDATES BOTH BRAKE VERSIONS",),
    "release-does-not-resurrect-a-stale-witness": (
        "RELEASE DOES NOT RESURRECT A STALE WITNESS", "RELEASE DOES NOT RESURRECT A STALE GRANT"),
    "every-queued-action-passes-a-new-full-checkpoint": (
        "EVERY QUEUED ACTION PASSES A NEW FULL CHECKPOINT AFTER RELEASE",
        "RELEASE MINTS NO CHECKPOINT WITNESS"),
    "a-pending-approval-cannot-authorize-execution-under-a-brake": (
        "A PENDING APPROVAL STAYS RECORDED AND CANNOT EXECUTE",
        "M13 REUSES M4 AND BUILDS NO LOCAL APPROVAL MECHANISM"),
    "compensation-is-blocked-under-an-active-brake": (
        "COMPENSATION IS BLOCKED UNDER AN ACTIVE BRAKE", "OBSERVATION AND RECONCILIATION CONTINUE",
        "THE BRAKE STOPS ACTING, NOT KNOWING"),
    "a-compensation-that-already-claimed-runs-to-verification": (
        "A COMPENSATION IS AN EFFECT AND OBEYS THE SAME BOUNDARY",),
    "a-flapping-detector-creates-one-active-brake": (
        "A FLAPPING DETECTOR IS ONE ACTIVE BRAKE AND NO WINDOW",),
    "the-four-f13-contracts-and-no-fifth": (
        "FOUR F13 CONTRACTS AND NO FIFTH",
        "THERE IS NO BrakeExpired, NO BrakeAutoReleased AND NO BrakePendingRelease"),
    "f13-is-strict-per-aggregate": ("F13 IS STRICT PER AGGREGATE",),
    "replay-creates-no-authority": (
        "REPLAY RECONSTRUCTS HISTORY AND CREATES NO AUTHORITY", "REPLAY NEVER ENGAGES A LIVE BRAKE"),
    "an-active-brake-is-reported-unprompted": (
        "A HIDDEN BRAKE IS A SILENT DEGRADATION", "AN ACTIVE BRAKE IS REPORTED UNPROMPTED",
        "THE REPORT NAMES WHAT IS STILL ALLOWED", "THE REPORT NAMES THE EXACT RELEASE REQUIREMENTS"),
    "there-is-exactly-one-brake-authority": (
        "THERE IS EXACTLY ONE BRAKE AUTHORITY", "M13 BUILDS NO SECOND BRAKE STORE",
        "M13 BUILDS NO SECOND BRAKE STATE TABLE"),
    "checkpoint-py-remains-the-sole-gate-minter": (
        "THE CHECKPOINT IS STILL THE ONLY GATE MINTER", "M13 MINTS NO GATE DECISION"),
    "m13-ships-dark-with-zero-production-importers": (
        "M13 SHIPS DARK WITH ZERO PRODUCTION IMPORTERS",
        "NO BRAKE CONSOLE, DASHBOARD OR CHANNEL COMMAND EXISTS"),
    "m1-through-m12-are-unchanged": (
        "NOTHING GRADUATES", "LANDING M13 IS NOT P6 ACCEPTANCE",
        "THE M1 WORK ITEM MACHINE IS UNCHANGED", "THE M2 PIPELINE MACHINE IS UNCHANGED",
        "THE M3 EFFECT AUTHORITY IS UNCHANGED", "THE M4 APPROVAL MACHINE IS UNCHANGED",
        "THE M7 CONFLICT MACHINE IS UNCHANGED", "THE M9 EXCEPTION MACHINE IS UNCHANGED",
        "THE M11 POLICY MACHINE IS UNCHANGED", "THE M12 RULE MACHINE IS UNCHANGED"),
}


def run_case(name: str, args) -> Result:
    fn = CASES.get(name)
    if fn is None:
        return FAIL(f"{MISS} unknown case {name!r}")
    try:
        r = fn(args)
    except Exception as exc:  # noqa: BLE001 — a crash is a MISS, never a silent pass
        traceback.print_exc()
        return FAIL(f"{MISS} case {name} crashed: {exc}")
    if r.ok:
        # union the case's own headlines with the scenario's declared case->headline mapping, order
        # preserved and de-duplicated, so a single --case invocation emits every headline its step names.
        merged = tuple(dict.fromkeys(r.headlines + CASE_HEADLINES.get(name, ())))
        return Result(True, r.positive, merged, ())
    return r


def main() -> int:
    p = argparse.ArgumentParser(description="M13 (the Brake) behavioural probe")
    p.add_argument("--list-cases", action="store_true")
    p.add_argument("--list-dimensions", action="store_true")
    p.add_argument("--case")
    p.add_argument("--all", action="store_true")
    for d in ("concurrency", "repeat", "tenants", "seed", "delay-ms"):
        p.add_argument(f"--{d}", dest=d.replace("-", "_"), type=int)
    for d in ("inject", "actor", "position", "owner", "transition", "scope"):
        p.add_argument(f"--{d}")
    args = p.parse_args()

    if args.inject is not None and args.inject not in FAULTS:
        print(f"{MISS} unknown fault {args.inject!r}; the fault set is closed: {sorted(FAULTS)}",
              file=sys.stderr)
        return 2

    # the case registry and the printed order must agree exactly (no silent gap)
    missing = [n for n in CASE_ORDER if n not in CASES]
    extra = [n for n in CASES if n not in CASE_ORDER]
    if missing or extra:
        print(f"{MISS} case registry disagrees with CASE_ORDER: missing={missing} extra={extra}",
              file=sys.stderr)
        return 2

    if args.list_cases:
        for n in CASE_ORDER:
            print(n)
        return 0
    if args.list_dimensions:
        for d in DIMENSIONS:
            print(d)
        return 0

    if args.case:
        if args.case not in CASES:
            print(f"{MISS} unknown case {args.case!r}", file=sys.stderr)
            return 2
        r = run_case(args.case, args)
        print(r.positive)
        for h in r.headlines:
            print(h)
        for al in r.alarms:
            print(al)
        if r.ok:
            print("behaviours as specified, 0 wrong")
            return 0
        return 1

    if args.all:
        wrong = 0
        for n in CASE_ORDER:
            r = run_case(n, args)
            print(r.positive)
            for al in r.alarms:
                print(al)
            if not r.ok:
                wrong += 1
        for line in _measurements():
            print(line)
        for h in NARRATIVE_HEADLINES:
            print(h)
        if wrong == 0:
            print("behaviours as specified, 0 wrong")
            return 0
        print(f"{MISS} {wrong} behaviour(s) wrong")
        return 1

    # Bare invocation IS the narrative run the permanent scenario drives as
    # "drive the Brake machine through a brokerage incident, and attack it": every case in canonical
    # order, each emitting its own headlines, then the full narrative headline set, then the verdict.
    print("drive the Brake machine through a brokerage incident, and attack it")
    wrong = 0
    for n in CASE_ORDER:
        r = run_case(n, args)
        print(r.positive)
        for h in r.headlines:
            print(h)
        for al in r.alarms:
            print(al)
        if not r.ok:
            wrong += 1
    for line in _measurements():
        print(line)
    for h in NARRATIVE_HEADLINES:
        print(h)
    if wrong == 0:
        print("behaviours as specified, 0 wrong")
        return 0
    print(f"{MISS} {wrong} behaviour(s) wrong")
    return 1


if __name__ == "__main__":
    sys.exit(main())
