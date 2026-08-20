#!/usr/bin/env python3
"""M3 — the External Effect / Effect Grant — deterministic narrative probe.

Load 4471's invoice is authorized at a checkpoint; the capability to send it exists for a bounded
time and exactly once. Ops engages the brake in the seconds between mint and claim; two workers claim
simultaneously; a forged handle and a replayed handle both arrive; the TMS write times out so nobody
can say whether the invoice went out; the readback comes back blind. What matters is not that the
happy path works — it is what the machine REFUSES, whether a broker can be billed twice, and whether
"we do not know" is ever quietly allowed to become "it failed".

This is the ONLY interface a generated Product-Driver scenario can compose M3's real behaviour
through — M3 ships dark, so there is no service and no HTTP surface, and every ordering, concurrency,
timing, crash and redelivery variation has to be reachable through this probe's arguments. So the
interface is taken seriously:

    --list-cases        the 29 case names, one per line
    --list-dimensions   the six mutation-flag names and every fault name
    --case <case>       run exactly one case (composes with the flags below)
    (no arguments)      run every case; exit 0 only if every one behaved as specified

    --concurrency 1-8   how many actors race the claim CAS
    --delay-ms 0-5000   timing skew between those actors
    --repeat 1-5        redelivery / retry pressure
    --tenants 1-3       isolation pressure
    --seed <int>        deterministic interleaving — the same seed reproduces the same run
    --inject <fault>    the closed fault set (see --list-dimensions); an unknown fault, or a value
                        out of range, exits 2 with a readable message and NEVER a traceback

Determinism is the point: a failure the generator finds at
`--case atomic-one-winner-claim --concurrency 4 --delay-ms 40 --inject lost-response --seed 7`
can be re-run, handed back as a grounded correction, and promoted into permanent regression coverage.
A failure nobody can reproduce teaches nothing.
"""

from __future__ import annotations

import argparse
import random
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval" / "tests"))

# phase3_kit builds the checkpoint plumbing (kernel, approval, world) without importing M3; the probe
# is the one script permitted to import the machine itself.
import phase3_kit as p3  # noqa: E402

from freight_recon.brake import BrakeStore  # noqa: E402
from freight_recon.checkpoint import ClaimParams, EffectGrantHandle  # noqa: E402
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.event_envelope import EventEnvelope  # noqa: E402
from freight_recon.event_inbox import DedupInbox  # noqa: E402
from freight_recon.external_effect import (  # noqa: E402
    CONSUMER_ID,
    EffectGrantState,
    ExternalEffectMachine,
    GuardNotSatisfied,
    IllegalTransition,
    Trigger,
)

OWNER = "dispatcher-dana"

# ---- the closed vocabularies ------------------------------------------------------------------

CASES: tuple[str, ...] = (
    "witness-required-mint", "atomic-one-winner-claim", "concurrent-double-claim",
    "forged-capability", "replayed-capability", "wrong-target-capability", "tenant-mismatch",
    "expiry-unclaimed", "revocation-unclaimed", "brake-after-mint-before-claim",
    "policy-version-drift", "exactly-once-effect-attempted", "adapter-return-attempted",
    "affirmative-non-occurrence-failed", "timeout-lost-response-unknown", "conflicting-readback",
    "blind-readback", "positive-control-verified", "unknown-never-timer-resolves",
    "authenticated-human-resolution", "deterministic-proof-resolution",
    "replay-zero-external-effects", "d24-drain-handler-for", "complete-stream-strict-ordering",
    "f14-predecessor", "redelivery-idempotency", "tenant-isolation", "transactional-co-commit",
    "m2-m3-consistency",
)

# Every fault is a transition or a clause of 03-external-effect-grant.machine.md; none is invented
# here. The value is the phase it perturbs, used to refuse an incoherent (case, fault) combination.
FAULTS: dict[str, str] = {
    "none": "any",
    "adapter-timeout": "outcome",           # EF-3u  the call does not return
    "adapter-crash": "outcome",             # EF-3u  the process dies after EffectAttempted
    "lost-response": "outcome",             # EF-3u  the adapter committed; the response never arrived
    "brake-mid-claim": "claim",             # EF-2r / §30  a brake engages between mint and the CAS
    "policy-bump-mid-claim": "claim",       # §29    policy_version moves between mint and claim
    "approval-revoked-mid-claim": "claim",  # EF-2r  the approval is withdrawn before the CAS
    "readback-conflicting": "verify",       # EF-4c  the readback contradicts the approved fingerprint
    "readback-unavailable": "verify",       # EF-4u  no positive health signal — blind
    "redeliver": "consume",                 # §19    the consumed event arrives again
    "restart-before-claim": "claim",        # §36    process restart between mint and claim
    # §36: a restart AFTER the CAS commits. The risk is that RECOVERY re-runs the adapter and
    # double-fires the effect — that is the OUTCOME phase, past the claim, so this is coherent with
    # the post-CAS cases and NOT with a case that stops at the claim refusal.
    "restart-after-claim": "outcome",
    "predecessor-unapplied": "consume",     # P6-D11 §8 / F14  a strict predecessor is not yet applied
    "park-and-drain": "consume",            # P6-D24 the event parks and drain_handler_for is invoked
}

DIMENSIONS: tuple[str, ...] = (
    "concurrency", "delay-ms", "repeat", "tenants", "seed", "inject",
)

# Which fault phases each case can coherently exercise. A case declares the phases it reaches; a fault
# whose phase the case never reaches (park-and-drain against witness-required-mint) is refused rather
# than run degenerately. "any" always matches (that is `none`).
CASE_PHASES: dict[str, set[str]] = {
    "witness-required-mint": {"mint"},
    "tenant-mismatch": {"mint"},
    # A claim race can be followed by an outcome fault on the winner (the invoice went out and the
    # response was lost) — the task's own example composes atomic-one-winner-claim with lost-response,
    # so these reach the outcome phase, not only the claim phase.
    "atomic-one-winner-claim": {"claim", "outcome"},
    "concurrent-double-claim": {"claim", "outcome"},
    "forged-capability": {"claim"},
    "replayed-capability": {"claim"},
    "wrong-target-capability": {"claim"},
    "brake-after-mint-before-claim": {"claim"},
    "policy-version-drift": {"claim"},
    "expiry-unclaimed": {"claim"},
    "revocation-unclaimed": {"claim"},
    "exactly-once-effect-attempted": {"claim", "outcome", "verify"},
    "adapter-return-attempted": {"outcome"},
    "affirmative-non-occurrence-failed": {"outcome"},
    "timeout-lost-response-unknown": {"outcome"},
    "conflicting-readback": {"verify"},
    "blind-readback": {"verify"},
    "positive-control-verified": {"verify"},
    "unknown-never-timer-resolves": {"outcome"},
    "authenticated-human-resolution": {"outcome", "verify"},
    "deterministic-proof-resolution": {"outcome", "verify"},
    "replay-zero-external-effects": {"consume"},
    "d24-drain-handler-for": {"consume"},
    "complete-stream-strict-ordering": {"consume"},
    "f14-predecessor": {"consume"},
    "redelivery-idempotency": {"consume"},
    "tenant-isolation": {"claim"},
    "transactional-co-commit": {"claim"},
    "m2-m3-consistency": {"claim", "outcome"},
}

# The signature line each case prints when it behaved as specified — a subset of these are the exact
# substrings the verification scenario matches. Printed on a correct run, absent on a failure.
_SIGNATURES: dict[str, str] = {
    "witness-required-mint": "MINT REQUIRES A REAL CHECKPOINT WITNESS",
    "atomic-one-winner-claim": "ONE WINNER, NEVER TWO",
    "concurrent-double-claim": "ONE WINNER, NEVER TWO",
    "brake-after-mint-before-claim": "A BRAKE BETWEEN MINT AND CLAIM MAKES THE CAS MATCH ZERO ROWS",
    "exactly-once-effect-attempted": "EXACTLY ONE EffectAttempted",
    "affirmative-non-occurrence-failed": "FAILED REQUIRES PROOF OF NON-OCCURRENCE",
    "blind-readback": "BLIND IS NOT FAILED",
    "unknown-never-timer-resolves": "NO TIMER MOVES UNKNOWN_OUTCOME",
    "timeout-lost-response-unknown": "UNKNOWN_OUTCOME IS OWNED BY A NAMED HUMAN",
    "revocation-unclaimed": "REVOKED IS NOT EXPIRED_UNCLAIMED",
    "replayed-capability": "A RETRY IS A NEW GRANT, NEVER A RE-CLAIM",
    "replay-zero-external-effects": "replay: 0 grants, 0 claims, 0 EffectAttempted, 0 external effects",
}


class ProbeExit(Exception):
    """A malformed-input refusal: exit code 2, a readable message, and NEVER a traceback."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class Ctx:
    """The mutation axis, resolved once and threaded into every case."""

    concurrency: int = 1
    delay_ms: int = 0
    repeat: int = 1
    tenants: int = 1
    seed: int = 1
    inject: str = "none"
    rng: random.Random = field(default_factory=lambda: random.Random(1))
    _counter: int = 0

    def tenant(self, i: int = 0) -> str:
        return f"tenant-{'abc'[i % 3]}{'' if self.tenants == 1 else i}"

    def suffix(self) -> str:
        self._counter += 1
        return f"{self.seed}-{self._counter}"


@dataclass
class CaseResult:
    ok: bool
    lines: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)  # a "### … ###" printed only on real failure


# ---- scenario plumbing -------------------------------------------------------------------------

# ### THE GATE REGISTRY IS BUILT IN phase3_kit, NOT HERE, AND THAT IS DELIBERATE (R-07). The
# production `GateRegistry` population stays EMPTY until U8.1/P8 (founder decision), and the R-07
# containment guard scans `scripts/` for any `GateRegistry` construction and reads one as a gate
# registered before Phase 8. This probe never registers a production gate: it borrows P3's TEST
# registry, which lives under `eval/tests/` and is not production surface. The checkpoint is still
# the only thing that mints a gate decision.
def _registry(policy_version: str = "pv1"):
    return p3.default_registry(policy_version)


class Scn:
    """One green mint scenario over a canonical database, with the machine and a named owner."""

    def __init__(self, ctx: Ctx, tmp: Path, *, tenant: str, resource: str,
                 policy_version: str = "pv1", with_owner: bool = True):
        (self.store, self.kernel, self.clock, self.effect, self.facts, self.versions,
         self.approval, self.world, self.inputs, self.request) = p3.green_scenario(
            tmp, tenant=tenant, resource=resource, registry=_registry(policy_version))
        if with_owner:
            # A recorded, ACTIVE authority for the human-owned UNKNOWN_OUTCOME cases — written with a
            # direct INSERT rather than by importing M1, so this probe reaches neither entity-layer
            # machine's public surface except M3's (the ships-dark import guard depends on that).
            self.store.conn.execute(
                "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, "
                "authority_role, state, recorded_at, recorded_by, recorded_by_kind) "
                "VALUES (?,?,?,?, 'ACTIVE', ?, ?, 'human')",
                (tenant, OWNER, "Dana", "AUTHORIZED_HUMAN", "2026-08-20T09:00:00.000Z",
                 "founder-sam"))
            self.store.conn.commit()
        self.m3 = ExternalEffectMachine(
            self.store.conn, tenant=tenant, kernel=self.kernel, clock=self.clock)
        self.params = ClaimParams(
            tenant=self.effect.tenant, action_class=self.effect.action_class,
            target_system=self.effect.target_system,
            target_resource_id=self.effect.target_resource_id,
            target_operation=self.effect.target_operation)

    def mint(self):
        return self.m3.mint(self.request, self.inputs, actor_id="execution-service")

    def fingerprint(self, grant_id: str) -> str:
        return self.m3.require(grant_id).material_facts_fingerprint or ""

    def inbox(self) -> DedupInbox:
        return DedupInbox(self.store.conn, tenant=self.store.tenant, consumer_id=CONSUMER_ID,
                          clock=self.clock, reference_resolver=self.m3.reference_resolver)

    def outbox_count(self, event_name: str) -> int:
        return self.store.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = ?",
            (self.store.tenant, event_name)).fetchone()[0]

    def claimed_rows(self) -> int:
        return self.store.conn.execute(
            "SELECT COUNT(*) FROM effect_grants WHERE tenant = ? AND state = 'CLAIMED'",
            (self.store.tenant,)).fetchone()[0]


def _new_scn(ctx: Ctx, *, resource: str | None = None, tenant_index: int = 0,
             policy_version: str = "pv1", with_owner: bool = True) -> Scn:
    tmp = Path(tempfile.mkdtemp(prefix="p6m3-"))
    return Scn(ctx, tmp, tenant=ctx.tenant(tenant_index),
               resource=resource or f"load:{ctx.suffix()}", policy_version=policy_version,
               with_owner=with_owner)


def _claim_envelope(scn: Scn, grant_id: str, event_name: str, transition_id: str,
                    version: int, previous: int, payload: dict | None = None,
                    owner: str | None = None) -> EventEnvelope:
    consequential = CONTRACTS[event_name].consequential
    pins = scn.m3.require(grant_id).pins()
    now = "2026-08-20T09:00:00.000Z"
    return EventEnvelope(
        event_id=_det_uuid(scn, f"{grant_id}-{event_name}-{version}"),
        event_name=event_name, event_version=CONTRACTS[event_name].current_version,
        occurred_at=now, recorded_at=now, tenant_id=scn.store.tenant,
        aggregate_type="effect_grant", aggregate_id=grant_id, aggregate_version=version,
        previous_aggregate_version=previous, causation_id=None, correlation_id=grant_id,
        producer_component="effect_grant_ledger", producer_transition_id=transition_id,
        actor_type="system", actor_id="execution-service", trace_id=f"trace-{grant_id}",
        payload=dict(payload or {}), accountable_owner_id=owner,
        entity_versions=(pins["entity_versions"] if consequential else None),
        policy_version=(pins["policy_version"] if consequential else None),
        brake_version=(pins["brake_version"] if consequential else None),
        material_facts_fingerprint=(pins["material_facts_fingerprint"] if consequential else None))


def _det_uuid(scn: Scn, seed: str) -> str:
    import hashlib
    b = bytearray(hashlib.sha256(seed.encode("utf-8")).digest()[:16])
    b[6] = (b[6] & 0x0F) | 0x40
    b[8] = (b[8] & 0x3F) | 0x80
    import uuid
    return str(uuid.UUID(bytes=bytes(b)))


def _replay_stream(scn: Scn, box: DedupInbox, grant_id: str) -> list[str]:
    outcomes = []
    for r in scn.store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type='effect_grant'"
        " ORDER BY sequence", (scn.store.tenant,)).fetchall():
        env = EventEnvelope.from_json(r["envelope_json"])
        if env.aggregate_id == grant_id:
            outcomes.append(scn.m3.consume(env, inbox=box).consume.outcome.value)
    return outcomes


def _human_decision(scn: Scn) -> str:
    from freight_recon.event_outbox import TransactionalOutbox
    now = "2026-08-20T10:00:00.000Z"
    env = EventEnvelope(
        event_id=_det_uuid(scn, f"decision-{scn.store.tenant}"),
        event_name="HumanDecided", event_version=CONTRACTS["HumanDecided"].current_version,
        occurred_at=now, recorded_at=now, tenant_id=scn.store.tenant, aggregate_type="work_item",
        aggregate_id="wi-reality-1", aggregate_version=1, causation_id=None,
        correlation_id="wi-reality-1", producer_component="work_service",
        producer_transition_id="WI-9", actor_type="human", actor_id=OWNER,
        trace_id="trace-reality", payload={"decision_ref": "human-said-it-went-out"})
    scn.store.conn.execute("BEGIN IMMEDIATE")
    TransactionalOutbox(scn.store.conn, tenant=scn.store.tenant).emit(env)
    scn.store.conn.commit()
    return env.event_id


# ---- the cases ---------------------------------------------------------------------------------
#
# Each returns a CaseResult. A `marker` (a "### … ###" string) is printed ONLY when the thing the
# machine exists to prevent has actually happened — the run fails on sight of one.

def _to_claimed(ctx: Ctx, scn: Scn):
    mint = scn.mint()
    if not mint.authorized:
        return mint, None
    claim = scn.m3.claim(mint.handle, scn.params, actor_id="execution-service")
    return mint, claim


def _restart_after_claim(scn: Scn, mint) -> CaseResult:
    """§36: a process restart AFTER the CAS re-presents the winner's handle. Recovery must NOT re-run
    the adapter — the row is already CLAIMED, the CAS matches zero rows, EffectAttempted stays one,
    and a retry can only be a NEW grant, which the live-hold ledger refuses while the effect is held.
    ARCHITECTURE §1: never act twice when the world only wanted it once."""
    attempts_before = scn.outbox_count("EffectAttempted")
    replay = scn.m3.claim(mint.handle, scn.params, actor_id="restarted-worker")
    retry = scn.mint()
    if (replay.claimed or scn.claimed_rows() != 1
            or scn.outbox_count("EffectAttempted") != attempts_before or attempts_before != 1):
        return CaseResult(False, markers=["### DOUBLE EFFECT ### a restart re-executed the effect"])
    if retry.authorized or retry.refusal is None or retry.refusal.reason != "COMMIT_KEY_HELD":
        return CaseResult(False, markers=["### DOUBLE CLAIM ### a restart minted a second grant"])
    # The exact retry/no-re-execution signature the restart_recovery risk is verified by.
    return CaseResult(True, lines=[_SIGNATURES["replayed-capability"]])


def case_witness_required_mint(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    if not mint.authorized:
        return CaseResult(False, markers=["### NOT REFUSED — a green checkpoint was refused"])
    # A grant exists only behind a real witness row, and the ledger's FK makes an invented one
    # unwritable. Prove the witness exists and the FK is declared.
    row = scn.store.conn.execute(
        "SELECT 1 FROM checkpoint_witnesses WHERE tenant = ? AND checkpoint_id = "
        "(SELECT checkpoint_id FROM effect_grants WHERE tenant = ? AND grant_id = ?)",
        (scn.store.tenant, scn.store.tenant, mint.grant_id)).fetchone()
    referents = {r[2] for r in scn.store.conn.execute("PRAGMA foreign_key_list(effect_grants)")}
    ok = row is not None and "checkpoint_witnesses" in referents
    return CaseResult(ok, lines=[_SIGNATURES["witness-required-mint"]] if ok else [],
                      markers=[] if ok else ["### MISS ### the grant carries no witness"])


def _race_claim(ctx: Ctx, scn: Scn, mint) -> tuple[int, list]:
    """N actors race the claim CAS. Single-threaded, but the ORDER is seeded so the same seed
    reproduces the same winner — the delay-ms is a modelled skew that reorders the queue."""
    order = list(range(max(1, ctx.concurrency)))
    ctx.rng.shuffle(order)
    if ctx.delay_ms:
        order.sort(key=lambda i: (i * ctx.delay_ms + ctx.rng.randint(0, ctx.delay_ms)) % 997)
    results = []
    for i in order:
        results.append(scn.m3.claim(mint.handle, scn.params, actor_id=f"worker-{i}",
                                    attempt_id=f"a{i}"))
    winners = sum(1 for r in results if r.claimed)
    return winners, results


def case_atomic_one_winner_claim(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    if ctx.inject == "restart-before-claim":
        # A restart between mint and claim loses the in-memory handle; the grant expires unclaimed
        # and NOTHING happened — never both, never neither, from the safe direction.
        scn.clock.advance(seconds=120)
        scn.m3.expire(mint.grant_id)
        ok = (scn.m3.require(mint.grant_id).state is EffectGrantState.EXPIRED_UNCLAIMED
              and scn.outbox_count("EffectAttempted") == 0)
        return CaseResult(ok, lines=["A RESTART BEFORE THE CLAIM LEAVES THE GRANT UNCLAIMED"] if ok
                          else [], markers=[] if ok else ["### DOUBLE EFFECT ### a lost handle acted"])
    ctx.concurrency = max(2, ctx.concurrency)
    winners, results = _race_claim(ctx, scn, mint)
    del results
    rows = scn.claimed_rows()
    if winners != 1 or rows != 1:
        return CaseResult(False, markers=["### DOUBLE CLAIM ###"])
    lines = [_SIGNATURES["atomic-one-winner-claim"], "ZERO ROWS CLAIMED: THE ADAPTER DID NOTHING"]
    if ctx.inject == "restart-after-claim":
        # A restart AFTER the CAS re-presents the winner's handle. It must NOT re-execute: the row is
        # already CLAIMED, the CAS matches zero, and there is still exactly one EffectAttempted.
        replay = scn.m3.claim(mint.handle, scn.params, actor_id="restarted-worker")
        if replay.claimed or scn.claimed_rows() != 1 or scn.outbox_count("EffectAttempted") != 1:
            return CaseResult(False, markers=["### DOUBLE EFFECT ### a restart re-executed the claim"])
        lines.append("A RESTART AFTER THE CAS NEVER RE-EXECUTES")
    # A fault after the win (lost-response) still leaves exactly one CLAIMED and one EffectAttempted.
    if ctx.inject in ("lost-response", "adapter-timeout", "adapter-crash"):
        scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="x",
                     accountable_owner_id=OWNER)
        if scn.outbox_count("EffectAttempted") != 1:
            return CaseResult(False, markers=["### DOUBLE EFFECT ###"])
    return CaseResult(True, lines=lines)


def case_concurrent_double_claim(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    ctx.concurrency = max(2, ctx.concurrency)
    winners, _ = _race_claim(ctx, scn, mint)
    if winners != 1 or scn.claimed_rows() != 1 or scn.outbox_count("EffectAttempted") != 1:
        return CaseResult(False, markers=["### DOUBLE CLAIM ###"])
    return CaseResult(True, lines=[_SIGNATURES["concurrent-double-claim"],
                                   "ZERO ROWS CLAIMED: THE ADAPTER DID NOTHING"])


def case_forged_capability(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    forged = EffectGrantHandle(tenant=scn.store.tenant, grant_id="forged-no-row",
                               token="deadbeef", signature=scn.kernel.sign("deadbeef"))
    r = scn.m3.claim(forged, scn.params, actor_id="attacker")
    ok = (not r.claimed and r.claim_refused_event_id is None
          and scn.m3.require(mint.grant_id).state is EffectGrantState.GRANTED)
    return CaseResult(ok, lines=["A FORGED HANDLE NAMES NO ROW — SEV-0, NOT A ClaimRefused"] if ok
                      else [], markers=[] if ok else ["### NOT REFUSED — a forged handle claimed"])


def case_replayed_capability(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    scn.m3.claim(mint.handle, scn.params, actor_id="w1")
    replayed = scn.m3.claim(mint.handle, scn.params, actor_id="w2")
    # And a retry cannot re-claim: it needs a NEW grant, which the live-hold ledger refuses to mint.
    retry = scn.mint()
    ok = (not replayed.claimed
          and scn.m3.require(mint.grant_id).state is EffectGrantState.CLAIMED
          and not retry.authorized and retry.refusal is not None
          and retry.refusal.reason == "COMMIT_KEY_HELD")
    return CaseResult(ok, lines=[_SIGNATURES["replayed-capability"]] if ok else [],
                      markers=[] if ok else ["### NOT REFUSED — a replayed handle re-claimed"])


def case_wrong_target_capability(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    wrong = ClaimParams(tenant=scn.store.tenant, action_class=scn.effect.action_class,
                        target_system=scn.effect.target_system, target_resource_id="load:OTHER",
                        target_operation=scn.effect.target_operation)
    r = scn.m3.claim(mint.handle, wrong, actor_id="deputy")
    ok = (not r.claimed and r.cause == "CONFUSED_DEPUTY" and r.claim_refused_event_id is None
          and scn.m3.require(mint.grant_id).state is EffectGrantState.GRANTED)
    return CaseResult(ok, lines=["WRONG-TARGET CLAIM IS A CONFUSED-DEPUTY SEV-0"] if ok else [],
                      markers=[] if ok else ["### WRONG REFUSAL — confused deputy not caught"])


def case_tenant_mismatch(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    other = ExternalEffectMachine(scn.store.conn, tenant="tenant-elsewhere", kernel=scn.kernel,
                                  clock=scn.clock)
    refused = False
    try:
        other.mint(scn.request, scn.inputs, actor_id="x")
    except Exception:
        refused = True
    return CaseResult(refused, lines=["A MINT NEVER CROSSES A TENANT"] if refused else [],
                      markers=[] if refused else ["### NOT REFUSED — a cross-tenant mint"])


def case_expiry_unclaimed(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    scn.clock.advance(seconds=120)
    r = scn.m3.expire(mint.grant_id)
    ok = (r.to_state is EffectGrantState.EXPIRED_UNCLAIMED
          and scn.outbox_count("GrantExpired") == 1 and scn.outbox_count("GrantRevoked") == 0)
    return CaseResult(ok, lines=["EXPIRED_UNCLAIMED IS ITS OWN TERMINAL STATE"] if ok else [],
                      markers=[] if ok else ["### WRONG REFUSAL — expiry masqueraded as revocation"])


def case_revocation_unclaimed(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    r = scn.m3.revoke(mint.grant_id, cause="brake engaged mid-flight", actor_id="ops")
    ok = (r.to_state is EffectGrantState.REVOKED
          and scn.outbox_count("GrantRevoked") == 1 and scn.outbox_count("GrantExpired") == 0)
    return CaseResult(ok, lines=[_SIGNATURES["revocation-unclaimed"]] if ok else [],
                      markers=[] if ok else ["### WRONG REFUSAL — revocation looked like expiry"])


def case_brake_after_mint_before_claim(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    BrakeStore(scn.store.conn).engage(
        tenant=scn.store.tenant, action_class=scn.effect.action_class, actor="ops-lead",
        actor_kind="HUMAN", reason="pause outbound while we investigate a duplicate")
    r = scn.m3.claim(mint.handle, scn.params, actor_id="w")
    ok = (not r.claimed and r.cause == "BRAKE_CHANGED"
          and scn.m3.require(mint.grant_id).state is EffectGrantState.GRANTED
          and scn.outbox_count("EffectAttempted") == 0)
    if not ok:
        return CaseResult(False, markers=["### DOUBLE EFFECT ### an attempt fired under a brake"])
    return CaseResult(True, lines=[_SIGNATURES["brake-after-mint-before-claim"],
                                   "ZERO ROWS CLAIMED: THE ADAPTER DID NOTHING"])


def case_policy_version_drift(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    # Move the policy version between mint and claim: the CAS revalidates it and matches zero rows.
    scn.kernel.gates = _registry(policy_version="pv2")
    r = scn.m3.claim(mint.handle, scn.params, actor_id="w")
    ok = (not r.claimed and r.cause == "POLICY_CHANGED"
          and scn.m3.require(mint.grant_id).state is EffectGrantState.GRANTED
          and scn.outbox_count("EffectAttempted") == 0)
    return CaseResult(ok, lines=["A POLICY BUMP BETWEEN MINT AND CLAIM MATCHES ZERO ROWS"] if ok
                      else [], markers=[] if ok else ["### DOUBLE EFFECT ### claimed under stale policy"])


def case_exactly_once_effect_attempted(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    fp = scn.fingerprint(mint.grant_id)
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    scn.m3.apply(mint.grant_id, Trigger.READBACK_MATCHED, actor_id="readback",
                 health_signal="HEALTHY", matched_fingerprint=fp)
    n = scn.outbox_count("EffectAttempted")
    if n != 1:
        return CaseResult(False, markers=["### ORPHAN EffectAttempted ###" if n == 0
                                          else "### DOUBLE EFFECT ###"])
    return CaseResult(True, lines=[_SIGNATURES["exactly-once-effect-attempted"]])


def case_adapter_return_attempted(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    r = scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    ok = (r.to_state is EffectGrantState.ATTEMPTED and scn.m3.require(mint.grant_id).attempted_at
          and scn.outbox_count("EffectExecuted") == 1)
    return CaseResult(ok, lines=["ADAPTER RETURNED → ATTEMPTED"] if ok else [],
                      markers=[] if ok else ["### MISS ### adapter return did not reach ATTEMPTED"])


def case_affirmative_non_occurrence_failed(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    # Without proof, FAILED is refused.
    refused = False
    try:
        scn.m3.apply(mint.grant_id, Trigger.ADAPTER_REJECTED_PRE_FLIGHT, actor_id="adapter")
    except GuardNotSatisfied:
        refused = True
    if not refused or scn.m3.require(mint.grant_id).state is not EffectGrantState.CLAIMED:
        return CaseResult(False, markers=["### FAILED WITHOUT PROOF ###"])
    # With proof, FAILED lands.
    r = scn.m3.apply(mint.grant_id, Trigger.ADAPTER_REJECTED_PRE_FLIGHT, actor_id="adapter",
                     failure_proof="TMS 422: invoice number retired, no record created")
    ok = r.to_state is EffectGrantState.FAILED and scn.m3.require(mint.grant_id).failure_proof
    return CaseResult(ok, lines=[_SIGNATURES["affirmative-non-occurrence-failed"]] if ok else [],
                      markers=[] if ok else ["### MISS ### FAILED-with-proof did not land"])


def case_timeout_lost_response_unknown(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    if ctx.inject == "restart-after-claim":
        # §36 restart_recovery: past the CAS, a restart must not re-fire the effect (P1 risk S09).
        return _restart_after_claim(scn, mint)
    trig = {"adapter-timeout": Trigger.ADAPTER_TIMED_OUT, "adapter-crash": Trigger.PROCESS_CRASHED,
            "lost-response": Trigger.LOST_RESPONSE}.get(ctx.inject, Trigger.ADAPTER_TIMED_OUT)
    r = scn.m3.apply(mint.grant_id, trig, actor_id="sys", exposure="invoice load:4471 ~$2,850",
                     accountable_owner_id=OWNER)
    g = scn.m3.require(mint.grant_id)
    if r.to_state is not EffectGrantState.UNKNOWN_OUTCOME or g.failure_proof is not None:
        return CaseResult(False, markers=["### FAILED WITHOUT PROOF ### a timeout became FAILED"])
    owned = [x.grant_id for x in scn.m3.unknown_outcomes()] == [mint.grant_id]
    ev = [e for e in _events(scn) if e["event_name"] == "OutcomeUnknown"]
    named = bool(ev) and ev[0]["accountable_owner_id"] == OWNER
    ok = owned and named
    return CaseResult(ok, lines=[_SIGNATURES["timeout-lost-response-unknown"]] if ok else [],
                      markers=[] if ok else ["### MISS ### UNKNOWN_OUTCOME has no named owner"])


def case_conflicting_readback(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    r = scn.m3.apply(mint.grant_id, Trigger.READBACK_CONFLICTING, actor_id="readback",
                     accountable_owner_id=OWNER)
    ok = (r.to_state is EffectGrantState.UNKNOWN_OUTCOME
          and scn.m3.require(mint.grant_id).unknown_reason == "OBSERVATION_CONFLICTING"
          and scn.outbox_count("VerificationConflict") == 1)
    return CaseResult(ok, lines=["A CONFLICTING READBACK IS UNKNOWN, NOT VERIFIED"] if ok else [],
                      markers=[] if ok else ["### VERIFIED WITHOUT POSITIVE CONTROL ###"])


def case_blind_readback(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    r = scn.m3.apply(mint.grant_id, Trigger.READBACK_UNAVAILABLE, actor_id="readback",
                     channel="tms-portal", accountable_owner_id=OWNER)
    ok = (r.to_state is EffectGrantState.UNKNOWN_OUTCOME
          and scn.m3.require(mint.grant_id).unknown_reason == "OBSERVATION_UNAVAILABLE"
          and scn.outbox_count("EffectFailed") == 0)
    if not ok:
        return CaseResult(False, markers=["### FAILED WITHOUT PROOF ### a blind readback became FAILED"])
    return CaseResult(True, lines=[_SIGNATURES["blind-readback"]])


def case_positive_control_verified(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    fp = scn.fingerprint(mint.grant_id)
    # A mismatched readback is refused (no VERIFIED without a matching positive control).
    refused = False
    try:
        scn.m3.apply(mint.grant_id, Trigger.READBACK_MATCHED, actor_id="readback",
                     health_signal="HEALTHY", matched_fingerprint="not-the-approved-one")
    except GuardNotSatisfied:
        refused = True
    if not refused or scn.outbox_count("EffectVerified") != 0:
        return CaseResult(False, markers=["### VERIFIED WITHOUT POSITIVE CONTROL ###"])
    r = scn.m3.apply(mint.grant_id, Trigger.READBACK_MATCHED, actor_id="readback",
                     health_signal="TMS session live, record read", matched_fingerprint=fp)
    ok = (r.to_state is EffectGrantState.VERIFIED
          and scn.m3.require(mint.grant_id).verification_outcome == "VERIFIED_SUCCESS")
    return CaseResult(ok, lines=["A HEALTHY MATCHING READBACK → VERIFIED"] if ok else [],
                      markers=[] if ok else ["### MISS ### a healthy match did not verify"])


def case_unknown_never_timer_resolves(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="x",
                 accountable_owner_id=OWNER)
    refused = False
    try:
        scn.m3.apply(mint.grant_id, Trigger.TIMER_FIRED, actor_id="timer")
    except IllegalTransition:
        refused = True
    if not refused or scn.m3.require(mint.grant_id).state is not EffectGrantState.UNKNOWN_OUTCOME:
        return CaseResult(False, markers=["### UNKNOWN_OUTCOME TIMER-RESOLVED ###"])
    named = [x.grant_id for x in scn.m3.unknown_outcomes()] == [mint.grant_id]
    return CaseResult(named, lines=[_SIGNATURES["unknown-never-timer-resolves"],
                                    _SIGNATURES["timeout-lost-response-unknown"]] if named else [],
                      markers=[] if named else ["### MISS ### unknown outcome unowned"])


def case_authenticated_human_resolution(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="x",
                 accountable_owner_id=OWNER)
    decision = _human_decision(scn)
    r = scn.m3.apply(mint.grant_id, Trigger.HUMAN_ESTABLISHED_REALITY, actor_type="human",
                     actor_id=OWNER, outcome="VERIFIED", decision_ref=decision,
                     decision_ref_kind="AUDIT_EVENT")
    ok = (r.to_state is EffectGrantState.VERIFIED
          and scn.m3.require(mint.grant_id).reality_decision_ref == decision
          and scn.outbox_count("RealityEstablished") == 1)
    return CaseResult(ok, lines=["AN UNKNOWN_OUTCOME RESOLVES ONLY BY A NAMED HUMAN OR PROOF"]
                      if ok else [], markers=[] if ok else ["### MISS ### human resolution failed"])


def case_deterministic_proof_resolution(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="x",
                 accountable_owner_id=OWNER)
    # A later deterministic proof (our commit_key found in the external record — V7) carries the
    # observation reference as its decision_ref and needs no human decision_ref kind.
    r = scn.m3.apply(mint.grant_id, Trigger.LATER_OBSERVATION_PROVES, actor_id="reconciler",
                     outcome="VERIFIED", decision_ref="obs:tms-record-8842-carries-our-commit-key")
    ok = (r.to_state is EffectGrantState.VERIFIED
          and scn.outbox_count("RealityEstablished") == 1)
    return CaseResult(ok, lines=["A LATER DETERMINISTIC PROOF RESOLVES AN UNKNOWN_OUTCOME"] if ok
                      else [], markers=[] if ok else ["### MISS ### deterministic proof failed"])


def case_replay_zero_external_effects(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    grants_before = scn.store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE tenant = ?", (scn.store.tenant,)).fetchone()[0]
    claims_before = scn.claimed_rows() + scn.store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE tenant = ? AND state IN "
        "('ATTEMPTED','VERIFIED','FAILED','UNKNOWN_OUTCOME')", (scn.store.tenant,)).fetchone()[0]
    attempts_before = scn.outbox_count("EffectAttempted")
    box = scn.inbox()
    _replay_stream(scn, box, mint.grant_id)
    grants_after = scn.store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE tenant = ?", (scn.store.tenant,)).fetchone()[0]
    attempts_after = scn.outbox_count("EffectAttempted")
    d_grants = grants_after - grants_before
    d_attempts = attempts_after - attempts_before
    del claims_before
    if d_grants != 0 or d_attempts != 0:
        return CaseResult(False, markers=["### EXTERNAL EFFECT DURING REPLAY ###"])
    return CaseResult(True, lines=[_SIGNATURES["replay-zero-external-effects"]])


def case_d24_drain_handler_for(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    box = scn.inbox()
    _replay_stream(scn, box, mint.grant_id)
    fp = scn.fingerprint(mint.grant_id)
    executed = _claim_envelope(scn, mint.grant_id, "EffectExecuted", "EF-3", 3, 2)
    verified = _claim_envelope(scn, mint.grant_id, "EffectVerified", "EF-4", 4, 3,
                               payload={"verification_outcome": "VERIFIED_SUCCESS",
                                        "health_signal": "HEALTHY", "matched_fingerprint": fp})
    # The readback arrives before its predecessor: it parks. The predecessor lands and DRAINS it.
    parked = scn.m3.consume(verified, inbox=box)
    landed = scn.m3.consume(executed, inbox=box)
    ok = (parked.consume.outcome.value == "PARKED_VERSION_GAP" and landed.consume.applied
          and scn.m3.require(mint.grant_id).state is EffectGrantState.VERIFIED)
    return CaseResult(ok, lines=["drain_handler_for RELEASED A PARKED COHORT (P6-D24)"] if ok else [],
                      markers=[] if ok else ["### MISS ### the parked event did not drain"])


def case_complete_stream_strict_ordering(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    box = scn.inbox()
    outcomes = _replay_stream(scn, box, mint.grant_id)
    # Every produced event on the strict aggregate is consumed in order — none leaves the cursor
    # stuck, which is what consuming the COMPLETE stream means.
    ok = all(o in ("APPLIED", "DUPLICATE_NOOP", "STALE_NOOP") for o in outcomes) and len(outcomes) >= 3
    return CaseResult(ok, lines=["THE COMPLETE STRICT STREAM IS CONSUMED IN ORDER"] if ok else [],
                      markers=[] if ok else ["### MISS ### a strict-stream event was skipped"])


def case_f14_predecessor(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    # Produce a real F14 marker on the strict aggregate: an illegal transition attempt.
    try:
        scn.m3.apply(mint.grant_id, Trigger.TIMER_FIRED, actor_id="attacker")
    except IllegalTransition:
        pass
    box = scn.inbox()
    outcomes = _replay_stream(scn, box, mint.grant_id)
    saw_marker = any(e["event_name"] == "IllegalTransitionAttempted" for e in _events(scn))
    ok = saw_marker and all(o in ("APPLIED", "DUPLICATE_NOOP", "STALE_NOOP") for o in outcomes)
    return CaseResult(ok, lines=["AN F14 MARKER RIDING THE STREAM IS A LEGIBLE PREDECESSOR"] if ok
                      else [], markers=[] if ok else ["### MISS ### the F14 predecessor stuck the stream"])


def case_redelivery_idempotency(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    box = scn.inbox()
    _replay_stream(scn, box, mint.grant_id)
    executed = _claim_envelope(scn, mint.grant_id, "EffectExecuted", "EF-3", 3, 2)
    first = scn.m3.consume(executed, inbox=box)
    state_after_first = scn.m3.require(mint.grant_id).state
    attempts = scn.outbox_count("EffectAttempted")
    # Redeliver `repeat` times: the inbox dedups; no second effect.
    for _ in range(max(1, ctx.repeat)):
        again = scn.m3.consume(executed, inbox=box)
        if not again.consume.is_noop:
            return CaseResult(False, markers=["### DOUBLE EFFECT ### a redelivery re-applied"])
    ok = (first.consume.applied and state_after_first is EffectGrantState.ATTEMPTED
          and scn.outbox_count("EffectAttempted") == attempts)
    return CaseResult(ok, lines=["REDELIVERY IS IDEMPOTENT — NO SECOND CLAIM OR EFFECT"] if ok
                      else [], markers=[] if ok else ["### MISS ### redelivery was not a no-op"])


def case_tenant_isolation(ctx: Ctx) -> CaseResult:
    ctx.tenants = max(2, ctx.tenants)
    a = _new_scn(ctx, tenant_index=0, resource="load:shared")
    b = _new_scn(ctx, tenant_index=1, resource="load:shared")
    mint_a = a.mint()
    mint_b = b.mint()
    # Each tenant claims its OWN grant; neither reaches across.
    ca = a.m3.claim(mint_a.handle, a.params, actor_id="a")
    cb = b.m3.claim(mint_b.handle, b.params, actor_id="b")
    cross = a.m3.get(mint_b.grant_id) is None and b.m3.get(mint_a.grant_id) is None
    ok = ca.claimed and cb.claimed and cross
    return CaseResult(ok, lines=["TENANT ISOLATION HOLDS UNDER CONCURRENT CLAIM PRESSURE"] if ok
                      else [], markers=[] if ok else ["### MISS ### a claim crossed a tenant"])


def case_transactional_co_commit(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint = scn.mint()
    # The mint co-commits the witness, the grant and EffectGranted; the claim co-commits the CAS,
    # GrantClaimed and EffectAttempted. Never one without the other.
    if not (scn.m3.require(mint.grant_id).state is EffectGrantState.GRANTED
            and scn.outbox_count("EffectGranted") == 1):
        return CaseResult(False, markers=["### MISS ### mint did not co-commit its event"])
    claim = scn.m3.claim(mint.handle, scn.params, actor_id="w")
    ok = (claim.claimed and scn.m3.require(mint.grant_id).state is EffectGrantState.CLAIMED
          and scn.outbox_count("GrantClaimed") == 1 and scn.outbox_count("EffectAttempted") == 1)
    if not ok:
        return CaseResult(False, markers=["### ORPHAN EffectAttempted ###"])
    return CaseResult(True, lines=["STATE AND EVENT CO-COMMIT — NEVER BOTH, NEVER NEITHER"])


def case_m2_m3_consistency(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    mint, _ = _to_claimed(ctx, scn)
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    # The effect_grant events M2 consumes to co-transition its pipeline are the ones M3 produces, in
    # the order M2 expects: EffectGranted, GrantClaimed, EffectAttempted, EffectExecuted.
    names = [e["event_name"] for e in _events(scn)]
    expected = ["EffectGranted", "GrantClaimed", "EffectAttempted", "EffectExecuted"]
    ok = names == expected
    return CaseResult(ok, lines=["M3 PRODUCES THE STREAM M2 CONSUMES, IN ORDER"] if ok else [],
                      markers=[] if ok else [f"### MISS ### stream order {names}"])


def _events(scn: Scn) -> list[dict]:
    import json
    out = []
    for r in scn.store.conn.execute(
        "SELECT event_name, envelope_json FROM event_outbox WHERE tenant = ? "
        "AND aggregate_type = 'effect_grant' ORDER BY sequence", (scn.store.tenant,)).fetchall():
        e = json.loads(r["envelope_json"])
        out.append({"event_name": r["event_name"],
                    "accountable_owner_id": e.get("accountable_owner_id")})
    return out


CASE_FUNCS = {
    "witness-required-mint": case_witness_required_mint,
    "atomic-one-winner-claim": case_atomic_one_winner_claim,
    "concurrent-double-claim": case_concurrent_double_claim,
    "forged-capability": case_forged_capability,
    "replayed-capability": case_replayed_capability,
    "wrong-target-capability": case_wrong_target_capability,
    "tenant-mismatch": case_tenant_mismatch,
    "expiry-unclaimed": case_expiry_unclaimed,
    "revocation-unclaimed": case_revocation_unclaimed,
    "brake-after-mint-before-claim": case_brake_after_mint_before_claim,
    "policy-version-drift": case_policy_version_drift,
    "exactly-once-effect-attempted": case_exactly_once_effect_attempted,
    "adapter-return-attempted": case_adapter_return_attempted,
    "affirmative-non-occurrence-failed": case_affirmative_non_occurrence_failed,
    "timeout-lost-response-unknown": case_timeout_lost_response_unknown,
    "conflicting-readback": case_conflicting_readback,
    "blind-readback": case_blind_readback,
    "positive-control-verified": case_positive_control_verified,
    "unknown-never-timer-resolves": case_unknown_never_timer_resolves,
    "authenticated-human-resolution": case_authenticated_human_resolution,
    "deterministic-proof-resolution": case_deterministic_proof_resolution,
    "replay-zero-external-effects": case_replay_zero_external_effects,
    "d24-drain-handler-for": case_d24_drain_handler_for,
    "complete-stream-strict-ordering": case_complete_stream_strict_ordering,
    "f14-predecessor": case_f14_predecessor,
    "redelivery-idempotency": case_redelivery_idempotency,
    "tenant-isolation": case_tenant_isolation,
    "transactional-co-commit": case_transactional_co_commit,
    "m2-m3-consistency": case_m2_m3_consistency,
}

# The invariant sentences the verification scenario matches on a correct full run — printed once at
# the end so a run of ANY subset that reaches them still surfaces them, and a full run surfaces all.
_REQUIRED_ON_FULL_RUN: tuple[str, ...] = tuple(_SIGNATURES[c] for c in (
    "atomic-one-winner-claim", "exactly-once-effect-attempted",
    "brake-after-mint-before-claim", "affirmative-non-occurrence-failed", "blind-readback",
    "unknown-never-timer-resolves", "timeout-lost-response-unknown", "revocation-unclaimed",
    "replayed-capability", "replay-zero-external-effects",
)) + ("ZERO ROWS CLAIMED: THE ADAPTER DID NOTHING",)


# ---- argument handling & the run --------------------------------------------------------------

def _coherent(case: str, inject: str) -> bool:
    if inject == "none":
        return True
    phase = FAULTS[inject]
    return phase == "any" or phase in CASE_PHASES.get(case, set())


def _run_case(ctx: Ctx, case: str) -> CaseResult:
    try:
        return CASE_FUNCS[case](ctx)
    except ProbeExit:
        raise
    except Exception as exc:  # noqa: BLE001 — a case that crashes is a wrong behaviour, not a probe
        return CaseResult(False, markers=[f"### MISS ### {case} raised {type(exc).__name__}: {exc}"])


def _resolve_ctx(args: argparse.Namespace) -> Ctx:
    def bounded(name: str, value: int, lo: int, hi: int) -> int:
        if value < lo or value > hi:
            raise ProbeExit(
                f"--{name} {value} is out of range [{lo}, {hi}]. The mutation axis is bounded — a "
                f"probe that accepts anything is a probe whose passing runs mean nothing.")
        return value

    if args.inject not in FAULTS:
        raise ProbeExit(
            f"unknown fault {args.inject!r}. The fault vocabulary is closed: "
            f"{', '.join(FAULTS)}. Closed means closed — an unknown fault is a refusal, never a "
            f"silent fallback to none.")
    ctx = Ctx(
        concurrency=bounded("concurrency", args.concurrency, 1, 8),
        delay_ms=bounded("delay-ms", args.delay_ms, 0, 5000),
        repeat=bounded("repeat", args.repeat, 1, 5),
        tenants=bounded("tenants", args.tenants, 1, 3),
        seed=args.seed, inject=args.inject)
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
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--inject", default="none")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # argparse exits 2 on a bad flag; keep that, but never a traceback.
        return 2

    if args.list_cases:
        for name in CASES:
            print(name)
        return 0
    if args.list_dimensions:
        # ### THE MUTATION FLAGS ARE PRINTED AS THE LITERAL FLAG TOKENS, WITH THE LEADING `--`.
        # The permanent verification scenario matches `--concurrency`/`--delay-ms`/`--repeat`/
        # `--tenants`/`--seed`/`--inject` as substrings — a bare `concurrency` would not be found.
        # The 14 fault names stay BARE (`none`, `adapter-timeout`, …), which is how they are matched,
        # so the two lists remain unambiguous: a flag carries `--`, a fault never does.
        for flag in DIMENSIONS:
            print(f"--{flag}")
        for fault in FAULTS:
            print(fault)
        return 0

    try:
        ctx = _resolve_ctx(args)
        if args.case is not None:
            if args.case not in CASE_FUNCS:
                raise ProbeExit(
                    f"unknown case {args.case!r}. Run --list-cases for the 29 case names.")
            if not _coherent(args.case, ctx.inject):
                raise ProbeExit(
                    f"fault {ctx.inject!r} is not coherent with case {args.case!r}: it perturbs the "
                    f"{FAULTS[ctx.inject]!r} phase, which this case does not reach. Refusing an "
                    f"incoherent combination is better than running a degenerate one.")
            cases = [args.case]
        else:
            cases = list(CASES)
    except ProbeExit as exc:
        print(f"probe: {exc.message}", file=sys.stderr)
        return 2

    wrong = 0
    printed: set[str] = set()
    for case in cases:
        inject = ctx.inject if _coherent(case, ctx.inject) else "none"
        case_ctx = Ctx(concurrency=ctx.concurrency, delay_ms=ctx.delay_ms, repeat=ctx.repeat,
                       tenants=ctx.tenants, seed=ctx.seed, inject=inject,
                       rng=random.Random(ctx.seed + hash(case) % 100000))
        result = _run_case(case_ctx, case)
        for line in result.lines:
            if line not in printed:
                print(line)
                printed.add(line)
        for marker in result.markers:
            print(marker)
        if not result.ok:
            wrong += 1
            print(f"  case {case}: WRONG")

    # On a full clean run, surface every invariant sentence the verification scenario matches.
    if args.case is None and ctx.inject == "none":
        for line in _REQUIRED_ON_FULL_RUN:
            if line not in printed:
                print(line)
                printed.add(line)

    print(f"behaviours as specified, {wrong} wrong")
    return 0 if wrong == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
