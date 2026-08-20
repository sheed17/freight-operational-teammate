"""Test kit for M3 — the External Effect / Effect Grant.

Composes P3's kit (`phase3_kit`) rather than re-deriving approvals and the checkpoint: the grant is
minted by the real kernel, so a test never fabricates checkpoint authority — the one thing the
machine exists to make unforgeable. What this kit adds is the M3 machine, a named accountable human
for the human-owned `UNKNOWN_OUTCOME`, and a fresh grant already carried to `GRANTED` or `CLAIMED`.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval" / "tests"))

import phase3_kit as p3  # noqa: E402

from freight_recon.checkpoint import ClaimParams  # noqa: E402
from freight_recon.event_envelope import EventEnvelope  # noqa: E402
from freight_recon.event_inbox import DedupInbox  # noqa: E402
from freight_recon.external_effect import (  # noqa: E402
    CONSUMER_ID,
    ExternalEffectMachine,
)
from freight_recon.work_item import record_human_authority  # noqa: E402

T_A = p3.T_A
T_B = p3.T_B
OWNER = "dispatcher-dana"

SYS: dict[str, Any] = {"actor_type": "system", "actor_id": "execution-service"}


def make_store(tmp_path, *, tenant: str = T_A, name: str = "p6m3.db"):
    return p3.make_store(tmp_path, tenant=tenant, name=name)


def a_human(store, human_id: str = OWNER, *, tenant: str = T_A, role: str = "AUTHORIZED_HUMAN",
            recorded_by: str = "founder-sam") -> str:
    record_human_authority(
        store.conn, tenant=tenant, human_id=human_id, display_name=human_id.title(),
        authority_role=role, recorded_by=recorded_by)
    return human_id


def machine(store, *, kernel, clock) -> ExternalEffectMachine:
    return ExternalEffectMachine(store.conn, tenant=store.tenant, kernel=kernel, clock=clock)


def params_for(effect) -> ClaimParams:
    return p3.params_for(effect)


class Scenario:
    """One green mint scenario, fully wired, with the perturbable world P3's kit exposes."""

    def __init__(self, tmp_path, *, tenant: str = T_A, action_class: str = "raise_invoice",
                 resource: str = "load:4471", registry=None, with_owner: bool = True):
        (self.store, self.kernel, self.clock, self.effect, self.facts, self.versions,
         self.approval, self.world, self.inputs, self.request) = p3.green_scenario(
            tmp_path, tenant=tenant, action_class=action_class, resource=resource,
            registry=registry)
        if with_owner:
            a_human(self.store, tenant=tenant)
        self.m3 = machine(self.store, kernel=self.kernel, clock=self.clock)
        self.params = params_for(self.effect)

    def mint(self, **kw):
        kw.setdefault("actor_id", "execution-service")
        return self.m3.mint(self.request, self.inputs, **kw)

    def claimed(self, **kw):
        """Mint, then claim — the grant is CLAIMED, ready for the outcome aspect."""
        mint = self.mint()
        assert mint.authorized, f"green mint refused: {mint.refusal}"
        claim = self.m3.claim(mint.handle, self.params, actor_id="execution-service", **kw)
        assert claim.claimed, f"green claim refused: {claim.cause}"
        return mint, claim

    def approved_fingerprint(self, grant_id: str) -> str:
        return self.m3.require(grant_id).material_facts_fingerprint or ""

    def inbox(self) -> DedupInbox:
        return DedupInbox(
            self.store.conn, tenant=self.store.tenant, consumer_id=CONSUMER_ID, clock=self.clock,
            reference_resolver=self.m3.reference_resolver)


_DUMMY_PINS: dict[str, Any] = {
    "entity_versions": {"load:ghost": 1}, "policy_version": "pv1", "brake_version": "0:0",
    "material_facts_fingerprint": "fp-fabricated",
}


def canonical_effect_envelope(
    *,
    tenant: str,
    grant_id: str,
    event_name: str,
    producer_transition_id: str,
    aggregate_version: int,
    previous_aggregate_version: int,
    payload: dict[str, Any] | None = None,
    accountable_owner_id: str | None = None,
    seed: str | None = None,
    actor_type: str = "system",
    actor_id: str = "execution-service",
    pins: dict[str, Any] | None = None,
) -> EventEnvelope:
    """A contract-valid `effect_grant` envelope built by hand — for exercising M3's CONSUMER on a
    stream this test authored, exactly the way the M2 test fabricates M3's events. Not emitted; it is
    delivered straight into `consume`.

    A CONSEQUENTIAL event (EffectExecuted, EffectVerified, …) must pin its decision context or the
    consumer's contract gate refuses it as malformed before it can even park — so `pins` carries the
    grant's real `entity_versions`/`policy_version`/`brake_version`, or a fabricated set for the
    ghost-grant park test where there is no real grant to read them from.
    """
    from freight_recon.event_contracts import CONTRACTS

    p = pins if pins is not None else _DUMMY_PINS
    now = "2026-08-20T09:00:00.000Z"
    consequential = CONTRACTS[event_name].consequential
    return EventEnvelope(
        event_id=_seeded_uuid(seed or f"{grant_id}-{event_name}-{aggregate_version}"),
        event_name=event_name,
        event_version=CONTRACTS[event_name].current_version,
        occurred_at=now, recorded_at=now, tenant_id=tenant,
        aggregate_type="effect_grant", aggregate_id=grant_id,
        aggregate_version=aggregate_version,
        previous_aggregate_version=previous_aggregate_version,
        causation_id=None, correlation_id=grant_id,
        producer_component="effect_grant_ledger",
        producer_transition_id=producer_transition_id,
        actor_type=actor_type, actor_id=actor_id, trace_id=f"trace-{grant_id}",
        payload=dict(payload or {}),
        accountable_owner_id=accountable_owner_id,
        entity_versions=(p.get("entity_versions") if consequential else None),
        policy_version=(p.get("policy_version") if consequential else None),
        brake_version=(p.get("brake_version") if consequential else None),
        material_facts_fingerprint=(p.get("material_facts_fingerprint") if consequential else None),
    )


def grant_pins(scn: "Scenario", grant_id: str) -> dict[str, Any]:
    return scn.m3.require(grant_id).pins()


def _seeded_uuid(seed: str) -> str:
    """A deterministic, v4-SHAPED UUID: reproducible across runs (a discovered failure must re-run),
    and valid where the envelope requires v4 (§1 forbids a v1/v5 id leaking a MAC or a namespace)."""
    import hashlib

    b = bytearray(hashlib.sha256(seed.encode("utf-8")).digest()[:16])
    b[6] = (b[6] & 0x0F) | 0x40   # version 4
    b[8] = (b[8] & 0x3F) | 0x80   # RFC-4122 variant
    return str(uuid.UUID(bytes=bytes(b)))


def replay_produced_stream(scn: "Scenario", box: DedupInbox, grant_id: str) -> list[str]:
    """Feed M3's own produced `effect_grant` events into its consumer, in order.

    They are no-op markers — the producer path already advanced the ledger past them — which is
    exactly a strict consumer catching up to a stream it did not itself apply, so the cursor reaches
    the producer's high-water mark and a later out-of-order event can be shown to park on a genuine
    gap rather than on the consumer simply being behind.
    """
    outcomes: list[str] = []
    rows = scn.store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = 'effect_grant'"
        " ORDER BY sequence", (scn.store.tenant,),
    ).fetchall()
    for r in rows:
        env = EventEnvelope.from_json(r["envelope_json"])
        if env.aggregate_id != grant_id:
            continue
        outcomes.append(scn.m3.consume(env, inbox=box).consume.outcome.value)
    return outcomes


# --- oracles ------------------------------------------------------------------------------------

def ledger(store, *, tenant: str = T_A) -> list[dict[str, Any]]:
    return [
        {"grant_id": r["grant_id"], "state": r["state"], "commit_key": r["commit_key"]}
        for r in store.conn.execute(
            "SELECT grant_id, state, commit_key FROM effect_grants WHERE tenant = ? "
            " ORDER BY grant_id", (tenant,),
        ).fetchall()
    ]


def effect_grant_events(store, *, tenant: str = T_A) -> list[dict[str, Any]]:
    import json
    out = []
    for r in store.conn.execute(
        "SELECT event_name, producer_transition_id, envelope_json FROM event_outbox "
        " WHERE tenant = ? AND aggregate_type = 'effect_grant' ORDER BY sequence", (tenant,),
    ).fetchall():
        e = json.loads(r["envelope_json"])
        out.append({
            "event_name": r["event_name"], "producer": r["producer_transition_id"],
            "version": e["aggregate_version"], "previous": e.get("previous_aggregate_version"),
            "payload": e.get("payload", {}),
            "accountable_owner_id": e.get("accountable_owner_id"),
        })
    return out


def event_names(store, *, tenant: str = T_A) -> list[str]:
    return [e["event_name"] for e in effect_grant_events(store, tenant=tenant)]


def count_event(store, event_name: str, *, tenant: str = T_A) -> int:
    return store.conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = ?",
        (tenant, event_name),
    ).fetchone()[0]


def security_rows(store, *, tenant: str = T_A) -> list[dict[str, Any]]:
    return [
        {"event_type": r["event_type"], "actor": r["actor"]}
        for r in store.conn.execute(
            "SELECT event_type, actor FROM security_events WHERE tenant = ? ORDER BY id", (tenant,),
        ).fetchall()
    ]
