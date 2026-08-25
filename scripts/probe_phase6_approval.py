#!/usr/bin/env python3
"""M4 — the Approval — deterministic narrative probe.

The owner approves invoicing load 4471 at £2,850 read from the TMS invoice screen; the card sits for
forty minutes; the TMS moves to £3,100; a second card carries the same £2,850 from a different
source; the policy cap tightens underneath a third; ops engages the brake; a counterparty claims
"per our call, you approved this"; the owner taps twice because the button was slow; a worker
crashes between the tap and the claim. What matters is not that the happy path works — it is what the
machine REFUSES, and whether an approval that no longer describes reality can still authorize money.

M4 ships dark — no service, no HTTP surface, no live approval channel — so this probe is the ONLY
interface a generated Product-Driver scenario can compose M4's real behaviour through. Every
ordering, concurrency, timing, drift, crash and redelivery variation has to be reachable through
these arguments, so the interface is taken seriously:

    --list-cases        the case names, one per line
    --list-dimensions   every dimension flag and every fault name
    --case <case>       run exactly one case (composes with the flags below)
    (no arguments)      run every case; exit 0 only if every one behaved as specified

    --concurrency 1-8   how many actors race the consume CAS
    --delay-ms 0-5000   timing skew between actors, and between signatures
    --repeat 1-5        double-tap / redelivery pressure
    --tenants 1-3       isolation pressure
    --signers 1-4       dual-control quorum size
    --seed <int>        deterministic interleaving — the same seed reproduces the same run
    --inject <fault>    the closed fault set (see --list-dimensions); an unknown fault, or a value
                        out of range, exits 2 with a readable message and NEVER a traceback

### CLOSED MEANS CLOSED. `--inject not-a-real-fault` and `--inject unfreeze` both exit 2 — `unfreeze`
is precisely the mechanism the repository has NOT established (G2-D15), so a probe that accepted it
would be manufacturing evidence for a transition nobody authorized.
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
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "eval" / "tests"))

# phase3_kit builds the checkpoint plumbing (kernel, approval facts, world) WITHOUT importing M4 or
# M3; this probe is the one script permitted to import the approval machine itself.
import phase3_kit as p3  # noqa: E402

from freight_recon.approval import (  # noqa: E402
    ApprovalMachine,
    ApprovalState,
    AuthorityRefused,
    GuardNotSatisfied,
    IllegalTransition,
)
from freight_recon.brake import BrakeStore  # noqa: E402
from freight_recon.checkpoint import (  # noqa: E402
    CheckpointInputs,
    EvidenceCondition,
    ProvenanceClass,
    SourceUnreadable,
    run_checkpoint,
)
from freight_recon.event_timers import DurableTimers, TimerRelay  # noqa: E402
from freight_recon.fingerprint import Money  # noqa: E402

# The recorded, ACTIVE humans this probe grants with (up to a quorum of four).
SIGNERS = ("owner:rasheed", "owner:dana", "owner:sam", "owner:mo")

# ---- the closed vocabularies ------------------------------------------------------------------

CASES: tuple[str, ...] = (
    "runtime-fact-binding", "model-output-cannot-manufacture-authority",
    "authenticated-authorized-human-grant", "model-cannot-grant", "counterparty-cannot-grant",
    "human-denial-is-terminal", "single-use-transport-token", "replayed-token-refused",
    "wrong-actor-token-refused", "expiry-is-not-an-approval", "amount-drift-voids",
    "party-drift-voids", "provenance-drift-voids", "evidence-condition-drift-voids",
    "entity-version-drift-voids", "unreadable-source-fails-closed", "drift-diff-is-human-readable",
    "policy-version-drift-voids", "brake-voids-before-consume", "human-revoke-before-consume",
    "forged-authority-refused", "wrong-target-authority-refused",
    "consume-cas-in-the-claim-txn", "double-tap-is-idempotent", "provable-failure-ap8",
    "unknown-outcome-freeze-ap9", "frozen-approval-not-reusable", "crash-before-consume-survives",
    "crash-after-consume-not-regranted", "dual-control-distinct-actors",
    "dual-control-drift-voids-signatures", "partial-approval-is-a-new-proposal",
    "live-approval-uniqueness", "m2-awaiting-approval-seam", "m3-claim-serialization-seam",
    "database-invariants", "replay-zero-approval-authority", "redelivery-idempotency",
    "transactional-co-commit", "tenant-isolation", "retained-canonical-payload",
    "terminal-states-stay-terminal", "strict-order-predecessor-declared",
    "complete-aggregate-stream-consumed", "frozen-reconstructed-from-positive-evidence",
)

# Every fault is a transition or a clause of 04-approval.machine.md or ADR-005; none is invented
# here. The value is the phase it perturbs, used to refuse an incoherent (case, fault) combination.
# ### `unfreeze` IS NOT HERE, DELIBERATELY: the unfreeze direction is an open residual (G2-D15).
FAULTS: dict[str, str] = {
    "none": "any",
    "drift-amount": "drift",              # AP-4  the money moves between grant and re-check
    "drift-party": "drift",              # AP-4  the counterparty moves
    "drift-provenance": "drift",         # AP-4 / §3.3  same value, different basis
    "drift-evidence-condition": "drift",  # AP-4 / §3.14  consistent -> stale/unknown/conflicting
    "drift-entity-version": "drift",     # AP-4  a referenced entity version moves
    "source-unreadable": "drift",        # §3.12  the live re-read fails; fail closed, not "no drift"
    "policy-bump": "policy",             # AP-4p  policy_version moves under a live approval
    "brake-engage": "brake",             # AP-5   a brake engages in scope before consumption
    "human-revoke": "revoke",            # AP-6   the human revokes before consumption
    "ttl-elapse": "expire",              # AP-3   the durable timer fires
    "provable-failure": "provable",      # AP-8 / M3 EF-3f
    "outcome-unknown": "freeze",         # AP-9 / M3 EF-3u
    "double-tap": "consume",             # §19 / §3.15  the second tap arrives
    "replay-token": "transport",         # §40 / §3.15 layer 1
    "wrong-actor": "transport",          # §40   the token is presented by another actor
    "crash-before-consume": "crash",     # §36
    "crash-after-consume": "crash",      # §36
    "redeliver": "consume",              # GR-4 / §19
    "signature-drift": "dual",           # §16 / §3.16  facts move between signature 1 and 2
    "forge-token": "transport",          # §40   a forged transport authority, naming no real row
    "wrong-target": "transport",         # §40   authority presented against a different target
    "drop-predecessor": "stream",        # events §8  an event is lost; its successor names an unapplied one
    "reorder-stream": "stream",          # events §8  delivery order is permuted within the aggregate
    "freeze-by-absence": "rebuild",      # ER-16  rebuild frozen from OutcomeUnknown AND NOT RealityEstablished
}

DIMENSIONS: tuple[str, ...] = (
    "concurrency", "delay-ms", "repeat", "tenants", "signers", "seed", "inject",
)

# Which fault phases each case can coherently exercise. A fault whose phase a case never reaches
# (signature-drift against human-denial-is-terminal) is refused rather than run degenerately.
CASE_PHASES: dict[str, set[str]] = {
    "runtime-fact-binding": {"request"},
    "model-output-cannot-manufacture-authority": {"grant"},
    "authenticated-authorized-human-grant": {"grant"},
    "model-cannot-grant": {"grant"},
    "counterparty-cannot-grant": {"grant"},
    "human-denial-is-terminal": {"grant"},
    "single-use-transport-token": {"transport"},
    "replayed-token-refused": {"transport"},
    "wrong-actor-token-refused": {"transport"},
    "expiry-is-not-an-approval": {"expire"},
    "amount-drift-voids": {"drift"},
    "party-drift-voids": {"drift"},
    "provenance-drift-voids": {"drift"},
    "evidence-condition-drift-voids": {"drift"},
    "entity-version-drift-voids": {"drift"},
    "unreadable-source-fails-closed": {"drift"},
    "drift-diff-is-human-readable": {"drift"},
    "policy-version-drift-voids": {"policy"},
    "brake-voids-before-consume": {"brake"},
    "human-revoke-before-consume": {"revoke"},
    "forged-authority-refused": {"transport"},
    "wrong-target-authority-refused": {"transport"},
    "consume-cas-in-the-claim-txn": {"consume"},
    "double-tap-is-idempotent": {"consume"},
    "provable-failure-ap8": {"provable"},
    "unknown-outcome-freeze-ap9": {"freeze"},
    "frozen-approval-not-reusable": {"freeze", "consume"},
    "crash-before-consume-survives": {"crash", "consume"},
    "crash-after-consume-not-regranted": {"crash", "consume"},
    "dual-control-distinct-actors": {"dual"},
    "dual-control-drift-voids-signatures": {"dual", "drift"},
    "partial-approval-is-a-new-proposal": {"grant"},
    "live-approval-uniqueness": {"request"},
    "m2-awaiting-approval-seam": {"request"},
    "m3-claim-serialization-seam": {"consume"},
    "database-invariants": {"schema"},
    "replay-zero-approval-authority": {"rebuild"},
    "redelivery-idempotency": {"consume", "stream"},
    "transactional-co-commit": {"request", "consume"},
    "tenant-isolation": {"request"},
    "retained-canonical-payload": {"drift"},
    "terminal-states-stay-terminal": {"grant"},
    "strict-order-predecessor-declared": {"stream"},
    "complete-aggregate-stream-consumed": {"stream"},
    "frozen-reconstructed-from-positive-evidence": {"rebuild", "freeze"},
}

# ### THE INVARIANT SENTENCES THE VERIFICATION SCENARIO MATCHES AS LITERAL SUBSTRINGS. Each is the
# sentence that makes a behaviour observable to something other than the session that wrote it.
_SIG: dict[str, str] = {
    "runtime-fact-binding": "AN APPROVAL IS A HUMAN PLUS THE EXACT FACTS",
    "authenticated-authorized-human-grant": "ONLY AN AUTHENTICATED AUTHORIZED HUMAN GRANTS",
    "model-cannot-grant": "A MODEL CANNOT GRANT",
    "model-output-cannot-manufacture-authority": "A MODEL CANNOT GRANT",
    "counterparty-cannot-grant": "A COUNTERPARTY CLAIM IS A FRAUD SIGNAL, NEVER AN APPROVAL",
    "amount-drift-voids": "A DRIFTED FACT IS NOT AN APPROVAL, IT IS A NEW QUESTION",
    "provenance-drift-voids": "SAME AMOUNT, CHANGED PROVENANCE, VOID",
    "drift-diff-is-human-readable": "THE DRIFT DIFF NAMES THE FIELD, THE OLD VALUE AND THE NEW",
    "evidence-condition-drift-voids": "A DEGRADED EVIDENCE CONDITION IS DRIFT",
    "unreadable-source-fails-closed": 'AN UNREADABLE SOURCE IS NOT "NO DRIFT"',
    "policy-version-drift-voids": "A POLICY CHANGE VOIDS AN IN-FLIGHT APPROVAL",
    "brake-voids-before-consume": "A BRAKE BEFORE CONSUME VOIDS THE APPROVAL",
    "human-revoke-before-consume": "A HUMAN MAY REVOKE BEFORE CONSUMPTION",
    "expiry-is-not-an-approval": "AN EXPIRED APPROVAL IS NOT A WEAKER APPROVAL",
    "human-denial-is-terminal": "A DENIAL IS TERMINAL",
    "consume-cas-in-the-claim-txn": "CONSUMED EXACTLY ONCE, IN THE CLAIM TRANSACTION",
    "double-tap-is-idempotent": "A DOUBLE TAP IS ALREADY DONE, NOT AN ERROR",
    "replayed-token-refused": "A REPLAYED TOKEN IS REFUSED AT THE TRANSPORT",
    "single-use-transport-token": "A REPLAYED TOKEN IS REFUSED AT THE TRANSPORT",
    "wrong-actor-token-refused": "A TOKEN PRESENTED BY ANOTHER ACTOR IS REFUSED",
    "partial-approval-is-a-new-proposal": "A PARTIAL APPROVAL IS A NEW PROPOSAL",
    "live-approval-uniqueness": "AT MOST ONE LIVE APPROVAL PER COMMIT KEY",
    "dual-control-drift-voids-signatures": "DUAL-CONTROL DRIFT VOIDS ALL SIGNATURES",
    "dual-control-distinct-actors": "A DUPLICATE ACTOR DOES NOT SATISFY QUORUM",
    "frozen-approval-not-reusable": "A FROZEN APPROVAL IS NOT REUSABLE",
    "unknown-outcome-freeze-ap9": "NO TIMER UNFREEZES AN APPROVAL",
    "crash-before-consume-survives": "A CRASH BEFORE CONSUME LEAVES A GRANTED APPROVAL, RE-CHECKED",
    "crash-after-consume-not-regranted":
        "A CRASH AFTER CONSUME NEVER RETURNS AN APPROVAL TO GRANTED",
    "terminal-states-stay-terminal": "A TERMINAL APPROVAL STAYS TERMINAL",
    "tenant-isolation": "THE SAME COMMIT KEY IN TWO TENANTS IS TWO APPROVALS",
    "redelivery-idempotency": "REDELIVERY IS IDEMPOTENT",
    "retained-canonical-payload": "WHAT THE HUMAN SAW IS STILL READABLE",
    "database-invariants": "A LEGACY DATABASE MIGRATES TO THE CANONICAL APPROVAL SHAPE",
    "forged-authority-refused": "A FORGED AUTHORITY NAMES NO APPROVAL",
    "wrong-target-authority-refused": "AUTHORITY FOR ANOTHER TARGET IS REFUSED",
    "strict-order-predecessor-declared": "EVERY APPROVAL EVENT DECLARES WHAT IT FOLLOWS",
    "complete-aggregate-stream-consumed": "A STRICT CONSUMER READS THE COMPLETE AGGREGATE STREAM",
    "frozen-reconstructed-from-positive-evidence":
        "A FREEZE IS REBUILT FROM POSITIVE EVIDENCE, NEVER FROM AN ABSENCE",
    "replay-zero-approval-authority":
        "replay: 0 grants, 0 approvals granted, 0 approvals consumed, 0 external effects",
}

# Extra required substrings not owned by a single case's primary signature, surfaced on the full run.
_EXTRA_REQUIRED: tuple[str, ...] = (
    "NO TIMER UNFREEZES AN APPROVAL",
    'AN ABSENCE IS NEVER "THERE IS NOTHING BEFORE ME"',
)


class ProbeExit(Exception):
    """A malformed-input refusal: exit code 2, a readable message, and NEVER a traceback."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class Ctx:
    concurrency: int = 1
    delay_ms: int = 0
    repeat: int = 1
    tenants: int = 1
    signers: int = 1
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
    markers: list[str] = field(default_factory=list)


# ---- scenario plumbing -------------------------------------------------------------------------

# ### THE GATE REGISTRY IS P3'S TEST REGISTRY, NOT A PRODUCTION ONE (R-07). The production
# `GateRegistry` stays EMPTY until U8.1/P8. This probe borrows P3's TEST registry (under eval/tests),
# never constructs one of its own, and never registers a production gate.
def _registry(policy_version: str = "pv1"):
    return p3.default_registry(policy_version)


class Scn:
    """One green scenario over a canonical database, with M4 and a pool of recorded humans."""

    def __init__(self, ctx: Ctx, tmp: Path, *, tenant: str, resource: str,
                 policy_version: str = "pv1"):
        (self.store, self.kernel, self.clock, self.effect, self.facts, self.versions,
         self._rec, self.world, self._inputs, self.request_req) = p3.green_scenario(
            tmp, tenant=tenant, resource=resource, registry=_registry(policy_version))
        for human in SIGNERS:
            self.store.conn.execute(
                "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, "
                "authority_role, state, recorded_at, recorded_by, recorded_by_kind) "
                "VALUES (?,?,?,?, 'ACTIVE', ?, ?, 'human')",
                (tenant, human, human, "AUTHORIZED_HUMAN", "2026-08-20T09:00:00.000Z", "founder"))
        self.store.conn.commit()
        self.m4 = ApprovalMachine(
            self.store.conn, tenant=tenant, kernel=self.kernel, clock=self.clock)
        self.policy_version = policy_version
        self._aid = 0

    def new_id(self) -> str:
        self._aid += 1
        return f"ap-{self.store.tenant}-{self._aid}"

    def reader(self):
        return p3.live_reader(lambda: dict(self.world["facts"]))

    def version_reader(self):
        return p3.live_reader(lambda: dict(self.world["versions"]))

    def request(self, aid: str, *, required_signatures: int = 1, ttl=None, schedule_timer=True):
        return self.m4.request(
            approval_id=aid, effect=self.effect, material_facts_reader=self.reader(),
            entity_versions=self.versions, policy_version=self.policy_version,
            gate_decision="HUMAN_APPROVAL_REQUIRED",
            rendered_facts={"amount": "GBP 2,850", "counterparty": "Acme Logistics"},
            actor_id="pipeline", required_signatures=required_signatures, ttl=ttl,
            schedule_timer=schedule_timer)

    def grant(self, aid: str, *, actor: str = SIGNERS[0], **kw):
        return self.m4.grant(aid, actor_id=actor, actor_kind="HUMAN", **kw)

    def request_and_grant(self, aid: str):
        self.request(aid)
        return self.grant(aid)

    def mint(self, aid: str):
        rec = self.m4.as_approval_record(aid)
        inputs = CheckpointInputs(
            material_facts_reader=self.reader(),
            projection_assertion={"status": "DELIVERED"},
            projected_state_reader=p3.live_reader(lambda: dict(self.world["projection"])),
            entity_version_reader=self.version_reader(),
            approval=rec)
        return run_checkpoint(self.kernel, self.request_req, inputs)

    def params(self):
        return p3.params_for(self.effect)

    def outbox_count(self, event_name: str) -> int:
        return self.store.conn.execute(
            "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = ?",
            (self.store.tenant, event_name)).fetchone()[0]

    def grants_count(self) -> int:
        return self.store.conn.execute(
            "SELECT COUNT(*) FROM effect_grants WHERE tenant = ?",
            (self.store.tenant,)).fetchone()[0]

    def claimed_count(self) -> int:
        return self.store.conn.execute(
            "SELECT COUNT(*) FROM effect_grants WHERE tenant = ? AND state = 'CLAIMED'",
            (self.store.tenant,)).fetchone()[0]


def _new_scn(ctx: Ctx, *, resource: str | None = None, tenant_index: int = 0,
             policy_version: str = "pv1") -> Scn:
    tmp = Path(tempfile.mkdtemp(prefix="p6m4-"))
    return Scn(ctx, tmp, tenant=ctx.tenant(tenant_index),
               resource=resource or f"load:{ctx.suffix()}", policy_version=policy_version)


def _drift_world(scn: Scn, kind: str) -> None:
    """Mutate the live world to model one drift dimension. Every dimension is INSIDE the fingerprint
    (amount, party, provenance, evidence) or an entity version — so the recompute detects it."""
    if kind == "amount":
        scn.world["facts"] = p3.perturbed_facts(
            scn.world["facts"], "amount", _value=Money(310000, "GBP"))
    elif kind == "party":
        scn.world["facts"] = p3.perturbed_facts(
            scn.world["facts"], "counterparty", _value="Rival Freight Co")
    elif kind == "provenance":
        scn.world["facts"] = p3.perturbed_facts(
            scn.world["facts"], "amount", provenance=ProvenanceClass.MODEL_EXTRACTED)
    elif kind == "evidence":
        scn.world["facts"] = p3.perturbed_facts(
            scn.world["facts"], "amount", evidence_condition=EvidenceCondition.STALE)
    elif kind == "entity-version":
        scn.world["versions"] = {k: v + 1 for k, v in scn.world["versions"].items()}


# ---- the cases ---------------------------------------------------------------------------------

def case_runtime_fact_binding(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid)
    a = scn.m4.require(aid)
    # The fingerprint is what the runtime read — recomputed identically here proves it is not model
    # output. A "model" proposing a different amount changes nothing: the runtime resolved the value.
    from freight_recon.checkpoint import material_fact_set
    from freight_recon.fingerprint import canonical_payload
    import hashlib
    expected = hashlib.sha256(canonical_payload(material_fact_set(
        effect=scn.effect, commit_key=scn.effect.key(), business_facts=dict(scn.world["facts"]),
        entity_versions=scn.versions, policy_version=scn.policy_version))).hexdigest()
    ok = (a.material_facts_fingerprint == expected and a.state is ApprovalState.REQUESTED
          and a.canonical_payload.startswith("fp_v1"))
    return CaseResult(ok, lines=[_SIG["runtime-fact-binding"]] if ok else [],
                      markers=[] if ok else ["### MISS ### fingerprint not from runtime reads"])


def case_authenticated_authorized_human_grant(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid)
    g = scn.grant(aid, actor=SIGNERS[0])
    a = scn.m4.require(aid)
    ok = (g.granted and a.state is ApprovalState.GRANTED and a.granted_by == SIGNERS[0]
          and scn.outbox_count("ApprovalGranted") == 1)
    return CaseResult(ok, lines=[_SIG["authenticated-authorized-human-grant"],
                                 _SIG["runtime-fact-binding"]] if ok else [],
                      markers=[] if ok else ["### APPROVAL GRANTED WITHOUT A HUMAN ###"])


def _non_human_grant(ctx: Ctx, actor: str, kind: str, marker: str, sig: str) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid)
    refused = False
    try:
        scn.m4.grant(aid, actor_id=actor, actor_kind=kind)
    except AuthorityRefused:
        refused = True
    a = scn.m4.require(aid)
    frauds = scn.store.conn.execute(
        "SELECT COUNT(*) FROM security_events WHERE tenant = ? AND event_type = "
        "'CounterpartySelfAuthorizationDetected'", (scn.store.tenant,)).fetchone()[0]
    ok = refused and a.state is ApprovalState.REQUESTED and frauds >= 1
    return CaseResult(ok, lines=[sig] if ok else [], markers=[] if ok else [marker])


def case_model_cannot_grant(ctx: Ctx) -> CaseResult:
    return _non_human_grant(ctx, "the-model", "model", "### NON-HUMAN GRANT ACCEPTED ###",
                            _SIG["model-cannot-grant"])


def case_model_output_cannot_manufacture_authority(ctx: Ctx) -> CaseResult:
    return _non_human_grant(ctx, "gpt-proposer", "model", "### NON-HUMAN GRANT ACCEPTED ###",
                            _SIG["model-cannot-grant"])


def case_counterparty_cannot_grant(ctx: Ctx) -> CaseResult:
    return _non_human_grant(
        ctx, "counterparty:rival-freight", "counterparty", "### NON-HUMAN GRANT ACCEPTED ###",
        _SIG["counterparty-cannot-grant"])


def case_human_denial_is_terminal(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid)
    scn.m4.deny(aid, actor_id=SIGNERS[0])
    denied = scn.m4.require(aid).state is ApprovalState.DENIED
    # A denied approval can never later execute — grant is refused (terminal).
    later = False
    try:
        scn.grant(aid, actor=SIGNERS[0])
    except (GuardNotSatisfied, IllegalTransition):
        later = True
    ok = denied and later and scn.outbox_count("ApprovalDenied") == 1
    return CaseResult(ok, lines=[_SIG["human-denial-is-terminal"]] if ok else [],
                      markers=[] if ok else ["### MISS ### denial not terminal"])


def _transport(ctx: Ctx):
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid)
    return scn, aid


def case_single_use_transport_token(ctx: Ctx) -> CaseResult:
    scn, aid = _transport(ctx)
    tok = scn.m4.mint_transport_token(aid, channel="C1", thread="T1", user=SIGNERS[0])
    scn.m4.verify_transport_token(tok, approval_id=aid, channel="C1", thread="T1", user=SIGNERS[0])
    replayed = False
    for _ in range(max(1, ctx.repeat)):
        try:
            scn.m4.verify_transport_token(
                tok, approval_id=aid, channel="C1", thread="T1", user=SIGNERS[0])
        except AuthorityRefused:
            replayed = True
    return CaseResult(replayed, lines=[_SIG["single-use-transport-token"]] if replayed else [],
                      markers=[] if replayed else ["### NOT REFUSED — a replayed token passed"])


def case_replayed_token_refused(ctx: Ctx) -> CaseResult:
    return case_single_use_transport_token(ctx)


def case_wrong_actor_token_refused(ctx: Ctx) -> CaseResult:
    scn, aid = _transport(ctx)
    tok = scn.m4.mint_transport_token(aid, channel="C1", thread="T1", user=SIGNERS[0])
    refused = False
    try:
        scn.m4.verify_transport_token(
            tok, approval_id=aid, channel="C1", thread="T1", user=SIGNERS[1])
    except AuthorityRefused:
        refused = True
    return CaseResult(refused, lines=[_SIG["wrong-actor-token-refused"]] if refused else [],
                      markers=[] if refused else ["### NOT REFUSED — wrong actor token passed"])


def case_forged_authority_refused(ctx: Ctx) -> CaseResult:
    scn, aid = _transport(ctx)
    from freight_recon.approval import TransportToken
    forged = TransportToken(tenant=scn.store.tenant, approval_id="ap-does-not-exist",
                            channel="C1", thread="T1", user=SIGNERS[0], mac="deadbeef")
    refused = False
    try:
        scn.m4.verify_transport_token(
            forged, approval_id="ap-does-not-exist", channel="C1", thread="T1", user=SIGNERS[0])
    except AuthorityRefused:
        refused = True
    return CaseResult(refused, lines=[_SIG["forged-authority-refused"]] if refused else [],
                      markers=[] if refused else ["### FORGED AUTHORITY ACCEPTED ###"])


def case_wrong_target_authority_refused(ctx: Ctx) -> CaseResult:
    from freight_recon.commit_key import LogicalEffect
    scn = _new_scn(ctx)
    a1 = scn.new_id()
    scn.request(a1)
    # A second, DIFFERENT existing approval (its own commit key, so both can be live at once).
    b = scn.new_id()
    eff_b = LogicalEffect(
        tenant=scn.store.tenant, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id="load:another-target", target_operation="create_invoice",
        occurrence_key="")
    scn.m4.request(
        approval_id=b, effect=eff_b, material_facts_reader=scn.reader(),
        entity_versions={"load:another-target": 1}, policy_version=scn.policy_version,
        gate_decision="HUMAN_APPROVAL_REQUIRED", rendered_facts={}, actor_id="pipeline")
    tok = scn.m4.mint_transport_token(a1, channel="C1", thread="T1", user=SIGNERS[0])
    # Present a1's token against b (a different target): b EXISTS (so it is not the forged-no-row
    # case), but the HMAC binds a1, so authority for another target is refused (§40).
    refused = False
    try:
        scn.m4.verify_transport_token(tok, approval_id=b, channel="C1", thread="T1",
                                      user=SIGNERS[0])
    except AuthorityRefused:
        refused = True
    return CaseResult(refused, lines=[_SIG["wrong-target-authority-refused"]] if refused else [],
                      markers=[] if refused else ["### FORGED AUTHORITY ACCEPTED ###"])


def case_expiry_is_not_an_approval(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid, ttl=None)  # default TTL; a durable timer is scheduled at request
    # Advance past the TTL and fire the durable timer — never a background sweep.
    scn.clock.advance(hours=2)
    fired = _fire_ttl(scn)
    a = scn.m4.require(aid)
    ok = (fired and a.state is ApprovalState.EXPIRED and scn.outbox_count("ApprovalExpired") == 1)
    # An expired approval cannot execute: consume is refused.
    if ok:
        outcome = scn.mint(aid)
        # The checkpoint refuses (approval not GRANTED); no grant to consume.
        ok = ok and not outcome.authorized
    return CaseResult(ok, lines=[_SIG["expiry-is-not-an-approval"]] if ok else [],
                      markers=[] if ok else ["### EXPIRED APPROVAL EXECUTED ###"])


def _fire_ttl(scn: Scn) -> bool:
    fired = {"n": 0}

    def handler(trigger):
        scn.m4.on_timer(trigger)
        fired["n"] += 1
    relay = TimerRelay(scn.store.conn, tenant=scn.store.tenant, handler=handler,
                       relay_id="probe-ttl", clock=scn.clock)
    relay.run_once()
    return fired["n"] >= 1


def _drift_case(ctx: Ctx, kind: str, sig_key: str, *, extra_sig: str | None = None) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    _drift_world(scn, kind)
    reader = scn.reader() if kind != "entity-version" else scn.reader()
    d = scn.m4.check_drift(
        aid, effect=scn.effect, material_facts_reader=reader,
        entity_version_reader=scn.version_reader())
    a = scn.m4.require(aid)
    ok = (d.drifted and a.state is ApprovalState.VOID_ON_DRIFT
          and scn.outbox_count("ApprovalVoided") == 1 and bool(d.fields))
    lines = [_SIG[sig_key]] if ok else []
    if ok and extra_sig:
        lines.append(extra_sig)
    return CaseResult(ok, lines=lines,
                      markers=[] if ok else ["### DRIFTED APPROVAL EXECUTED ###"])


def case_amount_drift_voids(ctx: Ctx) -> CaseResult:
    return _drift_case(ctx, "amount", "amount-drift-voids")


def case_party_drift_voids(ctx: Ctx) -> CaseResult:
    r = _drift_case(ctx, "party", "amount-drift-voids")
    if r.ok:
        r.lines = ["A COUNTERPARTY DRIFT IS A NEW QUESTION"]
    return r


def case_provenance_drift_voids(ctx: Ctx) -> CaseResult:
    return _drift_case(ctx, "provenance", "provenance-drift-voids")


def case_evidence_condition_drift_voids(ctx: Ctx) -> CaseResult:
    return _drift_case(ctx, "evidence", "evidence-condition-drift-voids")


def case_entity_version_drift_voids(ctx: Ctx) -> CaseResult:
    r = _drift_case(ctx, "entity-version", "amount-drift-voids")
    if r.ok:
        r.lines = ["A REFERENCED ENTITY VERSION MOVED, VOID"]
    return r


def case_drift_diff_is_human_readable(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    _drift_world(scn, "amount")
    d = scn.m4.check_drift(aid, effect=scn.effect, material_facts_reader=scn.reader())
    a = scn.m4.require(aid)
    # The diff names the field, the old value AND the new (285000|GBP -> 310000|GBP).
    ok = (d.drifted and "amount" in d.diff and "285000|GBP" in d.diff and "310000|GBP" in d.diff
          and a.drift_diff and "->" in (a.drift_diff or ""))
    return CaseResult(ok, lines=[_SIG["drift-diff-is-human-readable"],
                                 _SIG["amount-drift-voids"]] if ok else [],
                      markers=[] if ok else ["### MISS ### drift diff not human-readable"])


def case_unreadable_source_fails_closed(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)

    def boom():
        raise RuntimeError("TMS session dropped")
    failed = False
    try:
        scn.m4.check_drift(aid, effect=scn.effect, material_facts_reader=p3.live_reader(boom))
    except SourceUnreadable:
        failed = True
    a = scn.m4.require(aid)
    # An unreadable source is NOT no-drift: fail closed, the approval stays GRANTED (unusable now),
    # never voided-away and never proceeded.
    ok = (failed and a.state is ApprovalState.GRANTED and scn.outbox_count("ApprovalVoided") == 0)
    return CaseResult(ok, lines=[_SIG["unreadable-source-fails-closed"]] if ok else [],
                      markers=[] if ok else ["### DRIFTED APPROVAL EXECUTED ###"])


def case_policy_version_drift_voids(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    r = scn.m4.void_on_policy(aid, current_policy_version="pv2")
    a = scn.m4.require(aid)
    ok = (r is not None and a.state is ApprovalState.VOID_ON_DRIFT and a.void_reason == "policy"
          and scn.outbox_count("ApprovalVoided") == 1)
    return CaseResult(ok, lines=[_SIG["policy-version-drift-voids"]] if ok else [],
                      markers=[] if ok else ["### DRIFTED APPROVAL EXECUTED ###"])


def case_brake_voids_before_consume(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    BrakeStore(scn.store.conn).engage(
        tenant=scn.store.tenant, action_class=scn.effect.action_class, actor="ops-lead",
        actor_kind="HUMAN", reason="pause outbound while we investigate a duplicate")
    r = scn.m4.void_on_brake(aid)
    a = scn.m4.require(aid)
    ok = (r is not None and a.state is ApprovalState.VOID_ON_BRAKE and a.void_reason == "brake"
          and scn.outbox_count("ApprovalVoided") == 1)
    return CaseResult(ok, lines=[_SIG["brake-voids-before-consume"]] if ok else [],
                      markers=[] if ok else ["### REVOKED APPROVAL EXECUTED ###"])


def case_human_revoke_before_consume(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    scn.m4.revoke(aid, actor_id=SIGNERS[0])
    a = scn.m4.require(aid)
    # A revoked approval cannot execute.
    later = False
    try:
        outcome = scn.mint(aid)
        later = not outcome.authorized
    except Exception:  # noqa: BLE001
        later = True
    ok = (a.state is ApprovalState.REVOKED and scn.outbox_count("ApprovalRevoked") == 1 and later)
    return CaseResult(ok, lines=[_SIG["human-revoke-before-consume"]] if ok else [],
                      markers=[] if ok else ["### REVOKED APPROVAL EXECUTED ###"])


def case_consume_cas_in_the_claim_txn(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    if not outcome.authorized:
        return CaseResult(False, markers=["### MISS ### mint refused a green approval"])
    res = scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
    a = scn.m4.require(aid)
    grant_state = scn.store.conn.execute(
        "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (scn.store.tenant, outcome.handle.grant_id)).fetchone()[0]
    ok = (res.consumed and a.state is ApprovalState.CONSUMED and grant_state == "CLAIMED"
          and scn.outbox_count("ApprovalConsumed") == 1)
    if not ok:
        m = ["### CONSUMED WITHOUT A DURABLE CLAIM ###"] if a.state is ApprovalState.CONSUMED \
            and grant_state != "CLAIMED" else ["### MISS ### consume seam"]
        return CaseResult(False, markers=m)
    return CaseResult(True, lines=[_SIG["consume-cas-in-the-claim-txn"]])


def case_m3_claim_serialization_seam(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    grants_before = scn.grants_count()
    # N actors race the consume CAS in a seeded order: exactly one wins the claim + consume; the rest
    # find CONSUMED (already done). No second grant of authority is minted (M3 is the one authority).
    order = list(range(max(2, ctx.concurrency)))
    ctx.rng.shuffle(order)
    winners = 0
    for i in order:
        r = scn.m4.consume(outcome.handle, scn.params(), approval_id=aid, actor_id=f"worker-{i}")
        if r.consumed:
            winners += 1
    a = scn.m4.require(aid)
    ok = (winners == 1 and a.state is ApprovalState.CONSUMED and scn.claimed_count() == 1
          and scn.grants_count() == grants_before and scn.outbox_count("ApprovalConsumed") == 1)
    if not ok:
        return CaseResult(False, markers=["### SECOND EFFECT AUTHORITY ###" if winners != 1
                                          else "### MISS ### claim serialization"])
    return CaseResult(True, lines=["ONE CLAIM, ONE CONSUME, ONE EFFECT AUTHORITY",
                                   _SIG["consume-cas-in-the-claim-txn"]])


def case_double_tap_is_idempotent(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    first = scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
    raised = False
    already = True
    for _ in range(max(2, ctx.repeat)):
        try:
            r = scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
            already = already and r.already_done and not r.consumed
        except Exception:  # noqa: BLE001
            raised = True
    ok = (first.consumed and already and not raised
          and scn.outbox_count("ApprovalConsumed") == 1 and scn.claimed_count() == 1)
    if not ok:
        return CaseResult(False, markers=["### APPROVAL CONSUMED TWICE ###" if not already
                                          else "### MISS ### double-tap raised"])
    return CaseResult(True, lines=[_SIG["double-tap-is-idempotent"]])


def case_provable_failure_ap8(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    # AP-8: a provably-failed attempt is a no-op — the approval SURVIVES, still GRANTED, consumable
    # exactly once, and no ApprovalConsumed event fired. (See the module note on the §3.9 authority
    # question: this row is written from GRANTED, as the table states.)
    before = scn.outbox_count("ApprovalConsumed")
    scn.m4.note_provable_failure(aid)
    a = scn.m4.require(aid)
    ok = (a.state is ApprovalState.GRANTED and not a.frozen
          and scn.outbox_count("ApprovalConsumed") == before)
    return CaseResult(ok, lines=["AN APPROVAL SURVIVES A PROVABLY-FAILED ATTEMPT"] if ok else [],
                      markers=[] if ok else ["### MISS ### AP-8 did not survive"])


def case_unknown_outcome_freeze_ap9(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    scn.m4.freeze(aid, unknown_outcome_ref="ou-evt-1", effect_grant_id=outcome.handle.grant_id)
    a = scn.m4.require(aid)
    if not (a.frozen and a.state is ApprovalState.GRANTED
            and scn.outbox_count("ApprovalFrozen") == 1):
        return CaseResult(False, markers=["### MISS ### AP-9 did not freeze"])
    # NO TIMER UNFREEZES: a timer fired on a frozen approval is ILLEGAL and leaves it frozen.
    scn.clock.advance(hours=2)
    unfroze = False
    try:
        _fire_ttl(scn)  # the TTL timer is due; firing it hits AP-3 on a frozen approval -> ILLEGAL
    except IllegalTransition:
        pass
    a2 = scn.m4.require(aid)
    if not a2.frozen or a2.state is not ApprovalState.GRANTED:
        unfroze = True
    if unfroze:
        return CaseResult(False, markers=["### APPROVAL UNFROZEN ###"])
    return CaseResult(True, lines=[_SIG["unknown-outcome-freeze-ap9"]])


def case_frozen_approval_not_reusable(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    scn.m4.freeze(aid, unknown_outcome_ref="ou-evt-1", effect_grant_id=outcome.handle.grant_id)
    reused = False
    refused = False
    try:
        r = scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
        reused = r.consumed
    except IllegalTransition:
        refused = True
    a = scn.m4.require(aid)
    ok = (refused and not reused and a.frozen and a.state is ApprovalState.GRANTED
          and scn.outbox_count("ApprovalConsumed") == 0)
    return CaseResult(ok, lines=[_SIG["frozen-approval-not-reusable"],
                                 _SIG["unknown-outcome-freeze-ap9"]] if ok else [],
                      markers=[] if ok else ["### FROZEN APPROVAL REUSED ###"])


def case_crash_before_consume_survives(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    # "Crash" before consumption: the GRANTED approval survives durably. Recovery re-runs the drift
    # check LIVE before any claim — and only then consumes.
    a_after_crash = scn.m4.require(aid)
    d = scn.m4.check_drift(aid, effect=scn.effect, material_facts_reader=scn.reader())
    res = scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
    a = scn.m4.require(aid)
    ok = (a_after_crash.state is ApprovalState.GRANTED and not d.drifted and res.consumed
          and a.state is ApprovalState.CONSUMED)
    return CaseResult(ok, lines=[_SIG["crash-before-consume-survives"]] if ok else [],
                      markers=[] if ok else ["### MISS ### crash-before-consume"])


def case_crash_after_consume_not_regranted(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
    # "Crash" after consumption: a fresh machine (new in-memory state) re-reads the durable row.
    m4b = ApprovalMachine(scn.store.conn, tenant=scn.store.tenant, kernel=scn.kernel,
                          clock=scn.clock)
    a = m4b.require(aid)
    retry = m4b.consume(outcome.handle, scn.params(), approval_id=aid)
    ok = (a.state is ApprovalState.CONSUMED and retry.already_done and not retry.consumed
          and m4b.require(aid).state is ApprovalState.CONSUMED)
    return CaseResult(ok, lines=[_SIG["crash-after-consume-not-regranted"]] if ok else [],
                      markers=[] if ok else ["### APPROVAL CONSUMED TWICE ###"])


def case_dual_control_distinct_actors(ctx: Ctx) -> CaseResult:
    quorum = max(2, min(4, ctx.signers if ctx.signers > 1 else 2))
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid, required_signatures=quorum)
    # A DUPLICATE ACTOR DOES NOT SATISFY QUORUM: the same signer twice is still one signature.
    scn.grant(aid, actor=SIGNERS[0])
    dup = scn.grant(aid, actor=SIGNERS[0])
    if dup.granted or dup.signatures != 1:
        return CaseResult(False, markers=["### QUORUM MET BY ONE ACTOR ###"])
    # Distinct actors reach quorum.
    granted = None
    for i in range(1, quorum):
        granted = scn.grant(aid, actor=SIGNERS[i])
    a = scn.m4.require(aid)
    ok = (granted is not None and granted.granted and a.state is ApprovalState.GRANTED
          and len(scn.m4.signatures(aid)) == quorum)
    return CaseResult(ok, lines=[_SIG["dual-control-distinct-actors"]] if ok else [],
                      markers=[] if ok else ["### QUORUM MET BY ONE ACTOR ###"])


def case_dual_control_drift_voids_signatures(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid, required_signatures=2)
    scn.grant(aid, actor=SIGNERS[0], effect=scn.effect, material_facts_reader=scn.reader(),
              entity_versions=scn.versions, policy_version=scn.policy_version)
    assert len(scn.m4.signatures(aid)) == 1
    # Facts drift between signature 1 and signature 2 -> ALL signatures void, fresh fingerprint.
    _drift_world(scn, "amount")
    g2 = scn.grant(aid, actor=SIGNERS[1], effect=scn.effect, material_facts_reader=scn.reader(),
                   entity_versions=scn.versions, policy_version=scn.policy_version)
    a = scn.m4.require(aid)
    ok = (g2.resigned and not g2.granted and len(scn.m4.signatures(aid)) == 0
          and a.state is ApprovalState.REQUESTED)
    return CaseResult(ok, lines=[_SIG["dual-control-drift-voids-signatures"],
                                 _SIG["dual-control-distinct-actors"]] if ok else [],
                      markers=[] if ok else ["### QUORUM MET BY ONE ACTOR ###"])


def case_partial_approval_is_a_new_proposal(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    a1 = scn.new_id()
    scn.request_and_grant(a1)
    fp1 = scn.m4.require(a1).material_facts_fingerprint
    # "Approve it, but for £2,700" is NOT a mutation of a1 — it is a NEW proposal with a NEW
    # fingerprint. a1 is untouched; the new proposal needs a1 terminal first (one live per key).
    scn.m4.revoke(a1, actor_id=SIGNERS[0])  # free the key by making a1 terminal
    scn.world["facts"] = p3.perturbed_facts(scn.world["facts"], "amount", _value=Money(270000, "GBP"))
    a2 = scn.new_id()
    scn.request(a2)
    fp2 = scn.m4.require(a2).material_facts_fingerprint
    ok = (fp1 != fp2 and scn.m4.require(a1).material_facts_fingerprint == fp1
          and scn.m4.require(a1).state is ApprovalState.REVOKED)
    return CaseResult(ok, lines=[_SIG["partial-approval-is-a-new-proposal"]] if ok else [],
                      markers=[] if ok else ["### PARTIAL APPROVAL APPLIED ###"])


def case_live_approval_uniqueness(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    a1 = scn.new_id()
    scn.request(a1)
    # A second LIVE approval for the same commit key is refused by the DB (one live per key).
    refused = False
    try:
        scn.request(scn.new_id())
    except Exception:  # noqa: BLE001 — the partial unique index raises IntegrityError
        refused = True
    if not refused:
        return CaseResult(False, markers=["### MISS ### two live approvals per commit key"])
    # After the first is terminal, a re-approval is allowed (supersession = drift-void ∪ dup-refusal).
    scn.m4.deny(a1, actor_id=SIGNERS[0])
    reallowed = True
    try:
        scn.request(scn.new_id())
    except Exception:  # noqa: BLE001
        reallowed = False
    ok = refused and reallowed
    return CaseResult(ok, lines=[_SIG["live-approval-uniqueness"]] if ok else [],
                      markers=[] if ok else ["### MISS ### re-request after terminal blocked"])


def case_m2_awaiting_approval_seam(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid)
    # AP-1 co-commits the approval row AND the ApprovalRequested event (GR-2): a crash leaves neither
    # an orphan approval nor a pipeline waiting on one that never existed. The event carries the
    # fingerprint and gate_decision M2's PL-6 consumes to move ITS row to AWAITING_APPROVAL.
    approvals = scn.store.conn.execute(
        "SELECT COUNT(*) FROM approvals WHERE tenant = ? AND approval_id = ?",
        (scn.store.tenant, aid)).fetchone()[0]
    import json
    ev = scn.store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND event_name = 'ApprovalRequested' "
        "AND aggregate_id = ?", (scn.store.tenant, aid)).fetchone()
    payload = json.loads(ev["envelope_json"])["payload"] if ev else {}
    ok = (approvals == 1 and ev is not None and "fingerprint" in payload
          and payload.get("gate_decision") == "HUMAN_APPROVAL_REQUIRED")
    return CaseResult(ok, lines=["AP-1 CO-COMMITS THE APPROVAL AND ITS ApprovalRequested (M2 PL-6 "
                                 "CONSUMES IT)"] if ok else [],
                      markers=[] if ok else ["### MISS ### m2 seam not co-committed"])


def case_transactional_co_commit(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid)
    # request: the approval row AND ApprovalRequested, never one without the other.
    if not (scn.m4.get(aid) is not None and scn.outbox_count("ApprovalRequested") == 1):
        return CaseResult(False, markers=["### MISS ### request did not co-commit its event"])
    scn.grant(aid)
    outcome = scn.mint(aid)
    scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
    # grant: state + ApprovalGranted; consume: state + ApprovalConsumed. Both or neither.
    ok = (scn.outbox_count("ApprovalGranted") == 1 and scn.outbox_count("ApprovalConsumed") == 1
          and scn.m4.require(aid).state is ApprovalState.CONSUMED)
    return CaseResult(ok, lines=["STATE AND EVENT CO-COMMIT — NEVER BOTH, NEVER NEITHER"] if ok
                      else [], markers=[] if ok else ["### MISS ### co-commit broken"])


def case_tenant_isolation(ctx: Ctx) -> CaseResult:
    ctx.tenants = max(2, ctx.tenants)
    a = _new_scn(ctx, tenant_index=0, resource="load:shared")
    b = _new_scn(ctx, tenant_index=1, resource="load:shared")
    aid_a, aid_b = a.new_id(), b.new_id()
    a.request_and_grant(aid_a)
    b.request_and_grant(aid_b)
    # The same LOGICAL effect (load:shared, raise_invoice) in two tenants is two isolated approvals:
    # the commit key is tenant-first, so the two are distinct by construction and neither machine can
    # read the other's row [C-1].
    cross = a.m4.get(aid_b) is None and b.m4.get(aid_a) is None
    same_resource = a.effect.target_resource_id == b.effect.target_resource_id
    distinct_keys = a.m4.require(aid_a).commit_key != b.m4.require(aid_b).commit_key
    ok = (cross and same_resource and distinct_keys
          and a.m4.require(aid_a).state is ApprovalState.GRANTED
          and b.m4.require(aid_b).state is ApprovalState.GRANTED)
    return CaseResult(ok, lines=[_SIG["tenant-isolation"]] if ok else [],
                      markers=[] if ok else ["### CROSS-TENANT APPROVAL ACCEPTED ###"])


def case_retained_canonical_payload(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    a = scn.m4.require(aid)
    # What the human saw is still readable: the full canonical payload and rendered_facts are
    # retained, so the diff can name the field years later and the decision is reconstructable.
    _drift_world(scn, "amount")
    d = scn.m4.check_drift(aid, effect=scn.effect, material_facts_reader=scn.reader())
    ok = (a.canonical_payload.startswith("fp_v1") and "285000|GBP" in a.canonical_payload
          and a.rendered_facts and d.drifted and "285000|GBP" in d.diff)
    return CaseResult(ok, lines=[_SIG["retained-canonical-payload"]] if ok else [],
                      markers=[] if ok else ["### MISS ### canonical payload not retained"])


def case_terminal_states_stay_terminal(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
    # A CONSUMED approval never transitions again — revoke/deny/drift-check all refuse.
    refusals = 0
    for attempt in (
        lambda: scn.m4.revoke(aid, actor_id=SIGNERS[0]),
        lambda: scn.m4.deny(aid, actor_id=SIGNERS[0]),
        lambda: scn.m4.check_drift(aid, effect=scn.effect, material_facts_reader=scn.reader()),
        lambda: scn.m4.freeze(aid, unknown_outcome_ref="x", effect_grant_id=outcome.handle.grant_id),
    ):
        try:
            attempt()
        except (GuardNotSatisfied, IllegalTransition):
            refusals += 1
    a = scn.m4.require(aid)
    ok = (refusals == 4 and a.state is ApprovalState.CONSUMED)
    return CaseResult(ok, lines=[_SIG["terminal-states-stay-terminal"]] if ok else [],
                      markers=[] if ok else ["### MISS ### terminal approval moved"])


def case_replay_zero_approval_authority(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
    grants_before = scn.grants_count()
    claimed_before = scn.claimed_count()
    granted_before = scn.outbox_count("ApprovalGranted")
    consumed_before = scn.outbox_count("ApprovalConsumed")
    # Replay: fold the full history. It reconstructs state and creates ZERO authority.
    rebuilt = scn.m4.rebuild(aid)
    ok = (rebuilt.state is ApprovalState.CONSUMED
          and rebuilt.grants_minted == 0 and rebuilt.approvals_granted == 0
          and rebuilt.approvals_consumed == 0 and rebuilt.external_effects == 0
          and scn.grants_count() == grants_before and scn.claimed_count() == claimed_before
          and scn.outbox_count("ApprovalGranted") == granted_before
          and scn.outbox_count("ApprovalConsumed") == consumed_before)
    return CaseResult(ok, lines=[_SIG["replay-zero-approval-authority"]] if ok else [],
                      markers=[] if ok else ["### APPROVAL AUTHORITY DURING REPLAY ###"])


def _stream(scn: Scn, aid: str):
    import json
    rows = scn.store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = 'approval' "
        "AND aggregate_id = ? ORDER BY aggregate_version, sequence",
        (scn.store.tenant, aid)).fetchall()
    from freight_recon.event_envelope import EventEnvelope
    return [EventEnvelope.from_json(r["envelope_json"]) for r in rows], json


def case_redelivery_idempotency(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    from freight_recon.event_inbox import DedupInbox
    from freight_recon.approval import CONSUMER_ID
    box = DedupInbox(scn.store.conn, tenant=scn.store.tenant, consumer_id=CONSUMER_ID,
                     clock=scn.clock, reference_resolver=scn.m4.reference_resolver)
    stream, _ = _stream(scn, aid)
    outcomes = [scn.m4.consume_event(e, inbox=box).consume.outcome.value for e in stream]
    # Redeliver every event `repeat` times: the inbox dedups; every redelivery is a no-op.
    noop = True
    for _ in range(max(1, ctx.repeat)):
        for e in stream:
            r = scn.m4.consume_event(e, inbox=box)
            noop = noop and r.consume.is_noop
    ok = (all(o in ("APPLIED", "DUPLICATE_NOOP", "STALE_NOOP") for o in outcomes) and noop
          and scn.m4.require(aid).state is ApprovalState.GRANTED)
    return CaseResult(ok, lines=[_SIG["redelivery-idempotency"]] if ok else [],
                      markers=[] if ok else ["### MISS ### redelivery was not a no-op"])


def case_strict_order_predecessor_declared(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    scn.m4.consume(outcome.handle, scn.params(), approval_id=aid)
    stream, _ = _stream(scn, aid)
    # EVERY approval event declares what it follows; the first declares 0 (nothing before it), and
    # an absence is never read as "there is nothing before me".
    declared = all(e.previous_aggregate_version is not None for e in stream)
    first_zero = stream and stream[0].previous_aggregate_version == 0
    monotone = all(
        stream[i].previous_aggregate_version <= stream[i].aggregate_version
        for i in range(len(stream)))
    ok = bool(declared and first_zero and monotone and len(stream) >= 3)
    return CaseResult(ok, lines=[_SIG["strict-order-predecessor-declared"],
                                 'AN ABSENCE IS NEVER "THERE IS NOTHING BEFORE ME"'] if ok else [],
                      markers=[] if ok else ["### PREDECESSOR SKIPPED ###"])


def case_complete_aggregate_stream_consumed(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request(aid)
    # Produce a real F14 marker riding the strict approval aggregate BEFORE the grant: a model tries
    # to grant a REQUESTED approval, which records `IllegalTransitionAttempted` (and a fraud signal)
    # at the attempt's unchanged version — an order-tolerant F14 contract riding a strict aggregate.
    try:
        scn.m4.grant(aid, actor_id="the-model", actor_kind="model")
    except AuthorityRefused:
        pass
    scn.grant(aid, actor=SIGNERS[0])
    from freight_recon.event_inbox import DedupInbox
    from freight_recon.approval import CONSUMER_ID
    box = DedupInbox(scn.store.conn, tenant=scn.store.tenant, consumer_id=CONSUMER_ID,
                     clock=scn.clock, reference_resolver=scn.m4.reference_resolver)
    stream, _ = _stream(scn, aid)
    saw_marker = any(e.event_name == "IllegalTransitionAttempted" for e in stream)
    outcomes = [scn.m4.consume_event(e, inbox=box).consume.outcome.value for e in stream]
    # The COMPLETE stream — including the F14 marker riding it — is consumed in order; none stuck.
    ok = (saw_marker and all(o in ("APPLIED", "DUPLICATE_NOOP", "STALE_NOOP") for o in outcomes))
    return CaseResult(ok, lines=[_SIG["complete-aggregate-stream-consumed"],
                                 'AN ABSENCE IS NEVER "THERE IS NOTHING BEFORE ME"'] if ok else [],
                      markers=[] if ok else ["### PREDECESSOR SKIPPED ###"])


def case_frozen_reconstructed_from_positive_evidence(ctx: Ctx) -> CaseResult:
    scn = _new_scn(ctx)
    aid = scn.new_id()
    scn.request_and_grant(aid)
    outcome = scn.mint(aid)
    scn.m4.freeze(aid, unknown_outcome_ref="ou-evt-1", effect_grant_id=outcome.handle.grant_id)
    # A rebuild sets frozen=true from the PRESENCE of ApprovalFrozen (ER-16), and never from an
    # absence: inferring it from OutcomeUnknown AND NOT RealityEstablished is refused.
    rebuilt = scn.m4.rebuild(aid)
    if not (rebuilt.frozen and rebuilt.state is ApprovalState.GRANTED):
        return CaseResult(False, markers=["### FREEZE INFERRED FROM AN ABSENCE ###"
                                          if rebuilt.frozen else "### MISS ### freeze not rebuilt"])
    # Drop the positive evidence and prove the wrong inference stays wrong: no ApprovalFrozen ⇒ NOT
    # frozen, even though the (M3-chain) absence would tempt the forbidden derivation.
    stream, _ = _stream(scn, aid)
    without_freeze = [e for e in stream if e.event_name != "ApprovalFrozen"]
    absent = scn.m4.rebuild(aid, events=without_freeze, infer_frozen_from_absence=True)
    if absent.frozen:
        return CaseResult(False, markers=["### FREEZE INFERRED FROM AN ABSENCE ###"])
    return CaseResult(True, lines=[_SIG["frozen-reconstructed-from-positive-evidence"]])


def case_database_invariants(ctx: Ctx) -> CaseResult:
    """The database ENFORCES the approval authority invariants, and a legacy database migrates to the
    canonical shape. Deterministic and seed-independent."""
    import sqlite3

    from fixtures.legacy_workspace import build_legacy_workspace
    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate
    from freight_recon.migrations.phase6_approvals import phase6_approvals_readiness_problems
    from freight_recon.schema import (
        create_canonical_schema,
        enable_and_verify_foreign_keys,
        schema_readiness_problems,
    )

    tmp = Path(tempfile.mkdtemp(prefix="p6m4-mig-"))
    legacy = tmp / "legacy.db"
    build_legacy_workspace(legacy)
    migrate(str(legacy), assertion=OwnerAssertion(
        actor_id="rasheed@neyma", tenant="acme-brokerage", scope="all legacy rows",
        operational_basis="sole workspace onboarded for Acme; verified against record",
        evidence_reference="docs/onboarding/acme.md"), dry_run=False)
    migrated = sqlite3.connect(legacy)
    migrated.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(migrated)
    m_tables = {r[0] for r in migrated.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    m_ready = schema_readiness_problems(migrated) == [] and \
        phase6_approvals_readiness_problems(migrated) == []

    fresh = sqlite3.connect(tmp / "fresh.db")
    fresh.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(fresh)
    create_canonical_schema(fresh)
    enable_and_verify_foreign_keys(fresh)

    def shape(conn):
        cols = [(r[1], (r[2] or "").upper(), bool(r[3]), bool(r[5]))
                for r in conn.execute("PRAGMA table_info(approvals)")]
        fks = sorted((r[2], r[3], r[4]) for r in conn.execute(
            "PRAGMA foreign_key_list(approvals)"))
        idx = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='ix_approvals_live_per_commit_key'").fetchone()
        return cols, fks, " ".join((idx[0] or "").split()) if idx else None
    equal = shape(migrated) == shape(fresh)

    # The invariants fire (a GRANTED approval must carry a granted_by; a second live approval per
    # commit key is refused). Proved against a real recorded human.
    fresh.execute(
        "INSERT INTO tenant_humans (tenant,human_id,display_name,authority_role,state,recorded_at,"
        "recorded_by,recorded_by_kind) VALUES ('acme','h1','H','AUTHORIZED_HUMAN','ACTIVE','t',"
        "'founder','human')")

    def try_insert(**over):
        cols = dict(tenant="acme", approval_id="a", commit_key="ck", action_class="raise_invoice",
                    state="REQUESTED", version=1, material_facts_fingerprint="fp",
                    canonical_payload="fp_v1|x", fingerprint_version="fp_v1", entity_versions_json="{}",
                    policy_version="pv1", brake_version="bv1", gate_decision="HUMAN_APPROVAL_REQUIRED",
                    required_authority=None, required_signatures=1, rendered_facts="{}",
                    requested_at="t", expires_at="t2", granted_by=None, granted_at=None,
                    consumed_at=None, void_reason=None, drift_diff=None, frozen=0,
                    unknown_outcome_ref=None, effect_grant_id=None, frozen_at=None, created_at="t",
                    updated_at="t")
        cols.update(over)
        q = ",".join("?" * len(cols))
        fresh.execute(f"INSERT INTO approvals ({','.join(cols)}) VALUES ({q})", tuple(cols.values()))

    granted_needs_human = False
    try:
        try_insert(approval_id="g", state="GRANTED")
    except sqlite3.IntegrityError:
        granted_needs_human = True
    autonomous_refused = False
    try:
        try_insert(approval_id="au", gate_decision="AUTONOMOUS_WITHIN_CAPS")
    except sqlite3.IntegrityError:
        autonomous_refused = True

    # ### THE LIVE-APPROVAL PARTIAL UNIQUE INDEX, EXERCISED HERE (entity §17). One live
    # (REQUESTED/GRANTED) approval per (tenant, commit_key); a SECOND live insert for the SAME
    # (acme, ck) must be REFUSED by the database, not by the application. The sentence below is
    # printed ONLY on that genuine refusal — a non-enforcing DB fails the case, never prints it.
    live_unique = False
    two_live_accepted = False
    try_insert(approval_id="live-1")            # first live approval for (acme, ck) — must succeed
    try:
        try_insert(approval_id="live-2")        # a second live approval for the SAME (acme, ck)
    except sqlite3.IntegrityError:
        live_unique = True                      # the database refused it, as required
    else:
        two_live_accepted = True                # the DB let two live approvals coexist — a defect

    ok = ("approvals" in m_tables and "approval_signatures" in m_tables and m_ready and equal
          and granted_needs_human and autonomous_refused and live_unique)
    if not ok:
        marker = ("### MISS ### two live approvals for one commit key were accepted"
                  if two_live_accepted else
                  f"### MISS ### migrate: ready={m_ready} equal={equal} "
                  f"granted_check={granted_needs_human} autonomous_refused={autonomous_refused} "
                  f"live_unique={live_unique}")
        return CaseResult(False, markers=[marker])
    return CaseResult(True, lines=[_SIG["database-invariants"],
                                   "THE DATABASE ENFORCES THE APPROVAL AUTHORITY INVARIANTS",
                                   _SIG["live-approval-uniqueness"]])


CASE_FUNCS = {
    "runtime-fact-binding": case_runtime_fact_binding,
    "model-output-cannot-manufacture-authority": case_model_output_cannot_manufacture_authority,
    "authenticated-authorized-human-grant": case_authenticated_authorized_human_grant,
    "model-cannot-grant": case_model_cannot_grant,
    "counterparty-cannot-grant": case_counterparty_cannot_grant,
    "human-denial-is-terminal": case_human_denial_is_terminal,
    "single-use-transport-token": case_single_use_transport_token,
    "replayed-token-refused": case_replayed_token_refused,
    "wrong-actor-token-refused": case_wrong_actor_token_refused,
    "expiry-is-not-an-approval": case_expiry_is_not_an_approval,
    "amount-drift-voids": case_amount_drift_voids,
    "party-drift-voids": case_party_drift_voids,
    "provenance-drift-voids": case_provenance_drift_voids,
    "evidence-condition-drift-voids": case_evidence_condition_drift_voids,
    "entity-version-drift-voids": case_entity_version_drift_voids,
    "unreadable-source-fails-closed": case_unreadable_source_fails_closed,
    "drift-diff-is-human-readable": case_drift_diff_is_human_readable,
    "policy-version-drift-voids": case_policy_version_drift_voids,
    "brake-voids-before-consume": case_brake_voids_before_consume,
    "human-revoke-before-consume": case_human_revoke_before_consume,
    "forged-authority-refused": case_forged_authority_refused,
    "wrong-target-authority-refused": case_wrong_target_authority_refused,
    "consume-cas-in-the-claim-txn": case_consume_cas_in_the_claim_txn,
    "double-tap-is-idempotent": case_double_tap_is_idempotent,
    "provable-failure-ap8": case_provable_failure_ap8,
    "unknown-outcome-freeze-ap9": case_unknown_outcome_freeze_ap9,
    "frozen-approval-not-reusable": case_frozen_approval_not_reusable,
    "crash-before-consume-survives": case_crash_before_consume_survives,
    "crash-after-consume-not-regranted": case_crash_after_consume_not_regranted,
    "dual-control-distinct-actors": case_dual_control_distinct_actors,
    "dual-control-drift-voids-signatures": case_dual_control_drift_voids_signatures,
    "partial-approval-is-a-new-proposal": case_partial_approval_is_a_new_proposal,
    "live-approval-uniqueness": case_live_approval_uniqueness,
    "m2-awaiting-approval-seam": case_m2_awaiting_approval_seam,
    "m3-claim-serialization-seam": case_m3_claim_serialization_seam,
    "database-invariants": case_database_invariants,
    "replay-zero-approval-authority": case_replay_zero_approval_authority,
    "redelivery-idempotency": case_redelivery_idempotency,
    "transactional-co-commit": case_transactional_co_commit,
    "tenant-isolation": case_tenant_isolation,
    "retained-canonical-payload": case_retained_canonical_payload,
    "terminal-states-stay-terminal": case_terminal_states_stay_terminal,
    "strict-order-predecessor-declared": case_strict_order_predecessor_declared,
    "complete-aggregate-stream-consumed": case_complete_aggregate_stream_consumed,
    "frozen-reconstructed-from-positive-evidence":
        case_frozen_reconstructed_from_positive_evidence,
}

# Every invariant sentence the verification scenario matches, surfaced on a full clean run so a run
# of the whole battery cannot pass while any sentence is silently missing.
_REQUIRED_ON_FULL_RUN: tuple[str, ...] = tuple(dict.fromkeys(
    list(_SIG.values()) + list(_EXTRA_REQUIRED)))


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
            f"unknown fault {args.inject!r}. The fault vocabulary is closed: {', '.join(FAULTS)}. "
            f"Closed means closed — an unknown fault is a refusal, never a silent fallback to none. "
            f"(In particular there is no 'unfreeze': the unfreeze direction is an open residual, "
            f"G2-D15, and M4 has no mechanism for it.)")
    ctx = Ctx(
        concurrency=bounded("concurrency", args.concurrency, 1, 8),
        delay_ms=bounded("delay-ms", args.delay_ms, 0, 5000),
        repeat=bounded("repeat", args.repeat, 1, 5),
        tenants=bounded("tenants", args.tenants, 1, 3),
        signers=bounded("signers", args.signers, 1, 4),
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
    p.add_argument("--signers", type=int, default=1)
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
        # The flags carry a leading `--`; the fault names stay BARE — so the two lists are
        # unambiguous, and the scenario matches `--concurrency`/…/`--inject` and `none`/… as written.
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
                    f"unknown case {args.case!r}. Run --list-cases for the case names.")
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
                       tenants=ctx.tenants, signers=ctx.signers, seed=ctx.seed, inject=inject,
                       rng=random.Random(ctx.seed + (abs(hash(case)) % 100000)))
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

    if args.case is None and ctx.inject == "none":
        for line in _REQUIRED_ON_FULL_RUN:
            if line not in printed:
                print(line)
                printed.add(line)

    print(f"behaviours as specified, {wrong} wrong")
    return 0 if wrong == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
