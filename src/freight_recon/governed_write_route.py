"""THE GOVERNED WRITE ROUTE — the production join between decision and effect (P4 EP-1, R-07).

WHY THIS MODULE EXISTS. The independent hostile review (F-01) found the governed pipeline split into
two halves that shared no authority:

  * `governed_approval.build_checkpoint_approval` — the ONLY function mapping a `GovernedApproval`
    onto the checkpoint kernel's `ApprovalRecord` — had **zero callers anywhere**;
  * `GovernedWriteIntentQueued` — the event the decision half calls "advancing the governed
    pipeline" — had **no consumer**; it was written and only ever read back by test assertions;
  * the test that appeared to prove the end-to-end order authorized its executed grant with an
    UNRELATED fixture approval (`ap-1` / `owner:rasheed`) while the governed approval beside it was
    `appr-9` / `U-OWNER`.

So the chain the completion boundary requires did not exist as code. THIS MODULE IS THAT CHAIN. It
is production code — not a test fixture, not a wrapper, not a bridge — and it is reachable from the
authenticated Slack callback path:

    authenticated channel decision            action_callback -> handle_governed_write_callback
      -> canonical ApprovalDecision           verify_governed_approval  (HMAC over the envelope)
      -> exact tenant and actor binding       tenant/actor/workspace/channel/message checks
      -> exact Work Item and pipeline         work_item_id / pipeline_instance_id
      -> exact revision and payload hash      approval_revision / payload_hash
      -> policy and validation                the typed InvoiceWriteOperation + the gate registry
      -> build_checkpoint_approval            THE JOIN  (this module is its production caller)
      -> checkpoint                           run_checkpoint, seven steps, one transaction
      -> checkpoint witness                   minted inside that transaction
      -> Effect Grant                         minted inside that transaction
      -> atomic claim                         the claim CAS, inside execute_effect
      -> narrowly typed AdapterOperation      build_invoice_write_operation
      -> adapter execution                    the bounded writer
      -> readback verification                the adapter's own readback
      -> explicit outcome                     VERIFIED / FAILED / UNKNOWN_OUTCOME
      -> evidence and closure or escalation   GovernedWriteCompleted / GovernedWriteEscalated

ONE IDENTITY LINEAGE. The `approval_id` the human's authenticated tap carried is the `approval_id`
on the `ApprovalRecord`, on the checkpoint witness row, on the Effect Grant row, and on the typed
operation the adapter receives. There is no second identity anywhere on this path, and no place a
caller could substitute one: every binding is re-derived from the SAME `GovernedApproval` and the
SAME `InvoiceWriteOperation`, and a mismatch between them is refused before any checkpoint runs.

IT SHIPS DARK, AND DARKNESS IS THE ADAPTER'S PROPERTY, NOT THE CHAIN'S. The chain is real and fully
reachable; what it reaches is a bounded writer that performs no real external write. The default is
`browser_use_write.SandboxInvoiceWriteAdapter` with no runner injected — a PROVEN non-occurrence,
never a laundered success — and `effect_boundary.execute_invoice_write` refuses a non-sandbox
operation BEFORE any claim. This module registers no credentialed adapter, constructs no browser
session, imports no actuator, and has no fallback to `OperatorAgent` or `CdpActuator`. Enabling a
live supervised write is P12.

PERMANENT HUMAN AUTHORITY. This module executes the exact bounded operation a human already
approved. It chooses no price, carrier, payment, claim, banking or other consequential value: every
such value arrives inside the approved payload, is covered by the payload hash the human's signature
binds, and is refused if it differs by a single byte. There is no branch here that selects an
amount, a counterparty or a target.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .checkpoint import (
    AuthoritativeSourceReader,
    CheckpointInputs,
    CheckpointRefused,
    CheckpointRequest,
    material_fact_set,
    run_checkpoint,
)
from .fingerprint import canonical_payload, fingerprint
from .freight_operations import InvoiceWriteOperation
from .governed_approval import (
    GOVERNED_TOKEN_TYPE,
    GovernedApproval,
    GovernedDecision,
    build_checkpoint_approval,
    record_governed_decision,
    verify_governed_approval,
)

#: The durable queue's event type. The decision half writes it; this module is its consumer.
QUEUED_EVENT = "GovernedWriteIntentQueued"

#: The consumer's own claim namespace. A queued intent is consumed ONCE: the claim is taken through
#: the same atomic, tenant-scoped primitive the decision half uses (`claim_operation_action`), so
#: two simultaneous consumers cannot both proceed and a restart cannot re-consume.
CONSUMER_CLAIM_PREFIX = "governed-write-consume:"


class GovernedWriteRouteError(RuntimeError):
    """The governed write route refused to proceed. Fail closed: nothing is claimed, nothing is
    written, and the refusal names which binding or stage refused."""


# ------------------------------------------------------------------ the live material-fact source


@dataclass(frozen=True, slots=True)
class MaterialFactSource:
    """WHERE THE CHECKPOINT'S LIVE READS COME FROM, supplied by the caller that owns the freight
    state (P6 owns the entities; P4 owns the route).

    Every field is a zero-argument callable performing a LIVE read of the authoritative source. They
    are wrapped in `AuthoritativeSourceReader` at the checkpoint boundary, which is final and refuses
    anything that is not exactly that type — so a cache cannot be threaded through here either.

    `policy_version` is pinned by the caller and travels into the material-fact set, so a policy
    change voids in-flight approvals at checkpoint step 2 rather than being silently tolerated.
    """

    business_facts: Callable[[], dict]
    projected_state: Callable[[], dict]
    entity_versions: Callable[[], dict]
    projection_assertion: dict
    policy_version: str = "pv1"
    source: str = "tms:truckingoffice"

    def __post_init__(self) -> None:
        for name in ("business_facts", "projected_state", "entity_versions"):
            if not callable(getattr(self, name)):
                raise GovernedWriteRouteError(
                    f"MaterialFactSource.{name} must be a zero-argument LIVE read, not a value — a "
                    "consequential freshness read is structurally forbidden a cache (ADR-001 C4)")
        if not isinstance(self.projection_assertion, dict):
            raise GovernedWriteRouteError("projection_assertion must be a mapping")


# ------------------------------------------------------------------ the queue, read back


@dataclass(frozen=True, slots=True)
class GovernedWriteIntent:
    """ONE queued write intent, read back from the durable queue.

    It carries only IDENTITY and BINDINGS — never behaviour and never a money value. It is not
    authority: consuming it still requires the whole checkpoint/witness/grant/claim chain, and every
    field here is re-checked against the typed operation before that chain is entered.
    """

    approval_id: str
    tenant: str
    actor_id: str
    work_item_id: str
    pipeline_instance_id: str
    commit_key: str
    operation_class: str
    payload_hash: str
    capability_id: str
    idempotency_key: str
    sandbox: bool
    queued_at: str


def queued_write_intents(store: Any, *, approval_id: str = "") -> list[GovernedWriteIntent]:
    """THE CONSUMER'S READ SIDE — the queue `GovernedWriteIntentQueued` writes into.

    Tenant-scoped by construction: `store.security_events()` returns only this tenant's rows, so one
    tenant's queued intent is not visible to another tenant's consumer. Returns them in the order
    they were queued.
    """
    wanted = str(approval_id or "").strip()
    out: list[GovernedWriteIntent] = []
    for event in store.security_events():
        if event.get("event_type") != QUEUED_EVENT:
            continue
        payload = event.get("payload") or {}
        if wanted and str(payload.get("approval_id", "")) != wanted:
            continue
        out.append(GovernedWriteIntent(
            approval_id=str(payload.get("approval_id", "")),
            tenant=str(payload.get("tenant", "")),
            actor_id=str(event.get("actor", "")),
            work_item_id=str(payload.get("work_item_id", "")),
            pipeline_instance_id=str(payload.get("pipeline_instance_id", "")),
            commit_key=str(payload.get("commit_key", "")),
            operation_class=str(payload.get("operation_class", "")),
            payload_hash=str(payload.get("payload_hash", "")),
            capability_id=str(payload.get("capability_id", "")),
            idempotency_key=str(payload.get("idempotency_key", "")),
            sandbox=bool(payload.get("sandbox", False)),
            queued_at=str(payload.get("queued_at", "")),
        ))
    return out


# ------------------------------------------------------------------ the outcome of one consumption


@dataclass(frozen=True, slots=True)
class GovernedWriteOutcome:
    """The explicit outcome of consuming ONE queued write intent. Every field is a fact, not a
    summary: `executed` says whether the adapter was reached, `state` is the canonical effect state,
    and `escalated` says a human owns an unresolved ambiguity."""

    approval_id: str
    consumed: bool
    executed: bool
    state: str
    cause: str
    reason: str
    grant_id: str = ""
    checkpoint_id: str = ""
    commit_key: str = ""
    escalated: bool = False

    @property
    def verified(self) -> bool:
        return self.state == "VERIFIED"


# ------------------------------------------------------------------ THE CONSUMER


def consume_governed_write_intent(
    kernel: Any,
    approval: GovernedApproval,
    op: InvoiceWriteOperation,
    *,
    facts: MaterialFactSource,
    accountable_owner: str,
    authority: str = "owner",
    now: datetime,
    approval_ttl: timedelta = timedelta(hours=1),
    writer: Any = None,
) -> GovernedWriteOutcome:
    """CONSUME one queued governed write intent, and drive the whole governed chain.

    This is the bounded consumer F-01 requires, and the ONLY production caller of
    `build_checkpoint_approval`. It is bounded in every sense that matters:

      * it consumes EXACTLY ONE intent, named by `approval.approval_id`;
      * it takes an atomic, tenant-scoped consumer claim FIRST, so two simultaneous consumers and a
        restarted consumer cannot both proceed;
      * it mints AT MOST ONE grant — a second attempt for the same logical effect is refused by the
        ledger's own unique commit-key index as `COMMIT_KEY_HELD`, never by a check here;
      * it NEVER retries an ambiguous outcome. `UNKNOWN_OUTCOME` is escalated to the accountable
        human and left unresolved; only `effect_boundary.resolve_unknown_outcome` — a named human
        decision, never a timer — can move it.

    It writes nothing to the outside world itself: the adapter does, behind the claim, and the
    default adapter is dark.
    """
    if not isinstance(approval, GovernedApproval):
        raise GovernedWriteRouteError("the governed write route consumes a GovernedApproval")
    if not isinstance(op, InvoiceWriteOperation):
        raise GovernedWriteRouteError("the governed write route consumes an InvoiceWriteOperation")
    if not isinstance(facts, MaterialFactSource):
        raise GovernedWriteRouteError(
            "a MaterialFactSource is required: the checkpoint performs LIVE reads and will not "
            "accept remembered values")

    store = kernel.store

    # ---- 0. THE IDENTITY LINEAGE IS RE-PROVED HERE, not assumed from the caller ------------------
    # The verifier already bound the approval to this operation. Re-checking at the consumption
    # boundary is deliberate: this function is separately reachable, and a consumer that trusted its
    # arguments would be exactly the seam F-01 describes — two halves that share no authority.
    mismatch = approval_operation_mismatch(approval, op, server_tenant=store.tenant)
    if mismatch:
        store.add_security_event(
            "GovernedWriteIntentRefused", actor=approval.actor_id,
            payload={"approval_id": approval.approval_id, "tenant": op.tenant,
                     "work_item_id": op.work_item_id, "reason": mismatch})
        raise GovernedWriteRouteError(f"governed write intent refused: {mismatch}")

    # ---- 1. the intent must actually be QUEUED -------------------------------------------------
    intents = queued_write_intents(store, approval_id=approval.approval_id)
    if not intents:
        raise GovernedWriteRouteError(
            f"no queued write intent for approval {approval.approval_id!r}: the decision half did "
            "not advance the pipeline, so there is nothing to consume. The consumer never invents "
            "an intent.")
    intent = intents[-1]
    if not _same(intent.payload_hash, approval.payload_hash) or \
            not _same(intent.commit_key, op.effect_key()):
        raise GovernedWriteRouteError(
            "the queued intent does not describe this operation (payload hash or commit key "
            "differs) — refusing rather than executing a different effect")

    # ---- 2. SINGLE CONSUMPTION, atomically ------------------------------------------------------
    claim_id = CONSUMER_CLAIM_PREFIX + approval.approval_id
    if not store.claim_operation_action(
            claim_id, actor=approval.actor_id,
            payload={"kind": "governed_write_intent_consumption",
                     "tenant": op.tenant, "approval_id": approval.approval_id,
                     "commit_key": op.effect_key(), "payload_hash": approval.payload_hash}):
        store.add_security_event(
            "GovernedWriteIntentAlreadyConsumed", actor=approval.actor_id,
            payload={"approval_id": approval.approval_id, "tenant": op.tenant,
                     "commit_key": op.effect_key()})
        return GovernedWriteOutcome(
            approval_id=approval.approval_id, consumed=False, executed=False,
            state="REFUSED", cause="ALREADY_CONSUMED", commit_key=op.effect_key(),
            reason="this queued intent was already consumed; a governed write intent is consumed "
                   "exactly once, so no second external attempt can follow from it")

    # ---- 3. THE JOIN: the human's decision becomes the checkpoint's ApprovalRecord ---------------
    # The material-facts fingerprint is composed through the ONE canonical composer, so the approval
    # the checkpoint revalidates at step 2 and the checkpoint's own recomputation cannot disagree by
    # construction. It is INDEPENDENT of the approval's payload hash: two drift barriers, not one.
    effect = op.logical_effect()
    versions = dict(facts.entity_versions())
    fact_set = material_fact_set(
        effect=effect, commit_key=effect.key(), business_facts=facts.business_facts(),
        entity_versions=versions, policy_version=facts.policy_version)
    payload_bytes = canonical_payload(fact_set)
    checkpoint_approval = build_checkpoint_approval(          # <-- THE PRODUCTION CALLER (F-01)
        approval,
        material_facts_fingerprint=fingerprint(fact_set),
        canonical_payload=payload_bytes,
        fingerprint_version="fp_v1",
        entity_versions=versions,
        policy_version=facts.policy_version,
        authority=authority,
        granted_at=_utc(now),
        expires_at=_utc(now) + approval_ttl,
    )
    # The join must not silently rename the human. If these ever diverge, the grant would be
    # authorized by an identity the human never held — which is precisely F-01's defect.
    if checkpoint_approval.approval_id != approval.approval_id or \
            checkpoint_approval.actor_id != approval.actor_id:
        raise GovernedWriteRouteError(
            "the checkpoint approval does not carry the governed approval's identity — refusing")

    # ---- 4. the seven-step checkpoint: witness + grant, in one transaction -----------------------
    inputs = CheckpointInputs(
        material_facts_reader=AuthoritativeSourceReader(
            lambda: dict(facts.business_facts()), source=facts.source),
        projection_assertion=dict(facts.projection_assertion),
        projected_state_reader=AuthoritativeSourceReader(
            lambda: dict(facts.projected_state()), source=facts.source),
        entity_version_reader=AuthoritativeSourceReader(
            lambda: dict(facts.entity_versions()), source=facts.source),
        approval=checkpoint_approval,
    )
    request = CheckpointRequest(
        effect=effect,
        actor=f"pipeline:{op.pipeline_instance_id}",
        accountable_owner=accountable_owner,
        target_entity_ref=op.load_id,
    )
    outcome = run_checkpoint(kernel, request, inputs)
    if isinstance(outcome, CheckpointRefused) or not getattr(outcome, "authorized", False):
        reason = getattr(outcome, "reason", "REFUSED")
        detail = getattr(outcome, "detail", "")
        store.add_security_event(
            "GovernedWriteCheckpointRefused", actor=approval.actor_id,
            payload={"approval_id": approval.approval_id, "tenant": op.tenant,
                     "commit_key": effect.key(), "reason": reason,
                     "step": getattr(outcome, "step", None)})
        return GovernedWriteOutcome(
            approval_id=approval.approval_id, consumed=True, executed=False,
            state="REFUSED", cause=str(reason), commit_key=effect.key(),
            reason=f"the checkpoint refused this effect: {reason} {detail}".strip())

    # ---- 5. claim -> typed AdapterOperation -> adapter -> readback -> outcome --------------------
    # Imported lazily and used ONLY here: the boundary is the one door to an effect-capable adapter,
    # and this module holds no adapter of its own.
    from . import effect_boundary as eb

    try:
        execution = eb.execute_invoice_write(kernel, outcome.handle, op, writer=writer, now=_utc(now))
    except eb.BoundaryError as exc:
        # The boundary refused BEFORE any claim — the darkness refusal for a non-sandbox target is
        # the canonical case. That is a governed REFUSAL with an explicit outcome, not an exception
        # for the callback layer to interpret: translating it here keeps the typed contract whole
        # and keeps every caller free of an effect-boundary import.
        store.add_security_event(
            "GovernedWriteRefused", actor=approval.actor_id,
            payload={"approval_id": approval.approval_id, "tenant": op.tenant,
                     "commit_key": effect.key(), "grant_id": outcome.handle.grant_id,
                     "reason": "BOUNDARY_REFUSED", "detail": str(exc)[:400]})
        return GovernedWriteOutcome(
            approval_id=approval.approval_id, consumed=True, executed=False,
            state="REFUSED", cause="BOUNDARY_REFUSED",
            grant_id=outcome.handle.grant_id, checkpoint_id=outcome.witness.checkpoint_id,
            commit_key=effect.key(),
            reason=f"the effect boundary refused before any claim: {exc}")

    # ---- 6. evidence and closure, or governed escalation ----------------------------------------
    state = str(execution.state)
    escalated = state == "UNKNOWN_OUTCOME"
    store.add_security_event(
        "GovernedWriteEscalated" if escalated else "GovernedWriteCompleted",
        actor=approval.actor_id,
        payload={
            "approval_id": approval.approval_id,          # the SAME identity the human's tap carried
            "tenant": op.tenant,
            "actor_id": approval.actor_id,
            "work_item_id": op.work_item_id,
            "pipeline_instance_id": op.pipeline_instance_id,
            "commit_key": effect.key(),
            "checkpoint_id": outcome.witness.checkpoint_id,
            "grant_id": outcome.handle.grant_id,
            "capability_id": op.capability_id,
            "payload_hash": approval.payload_hash,
            "revision": int(op.approval_revision),
            "state": state,
            "cause": str(getattr(execution, "cause", "") or ""),
            "accountable_owner": accountable_owner,
            # An ambiguous outcome NEVER auto-resolves and NEVER auto-retries: it is owned by a
            # named human until `resolve_unknown_outcome` records their decision.
            "requires_reconciliation": escalated,
            "exposure": _exposure(op),
        })
    return GovernedWriteOutcome(
        approval_id=approval.approval_id,
        consumed=True,
        executed=True,
        state=state,
        cause=str(getattr(execution, "cause", "") or ""),
        grant_id=outcome.handle.grant_id,
        checkpoint_id=outcome.witness.checkpoint_id,
        commit_key=effect.key(),
        escalated=escalated,
        reason=("the outcome is UNKNOWN and is owned by a named human for reconciliation; it will "
                "not be retried automatically because the write may already have landed"
                if escalated else f"governed write completed with state {state}"),
    )


# ------------------------------------------------------------------ what the callback path resolves


@dataclass(frozen=True, slots=True)
class PendingGovernedWrite:
    """Everything the authenticated callback needs to drive ONE governed write, resolved by the
    pipeline that proposed it (P6 owns the entities; this is the P4 route's input contract).

    The callback layer does not BUILD any of this — it looks it up by approval id and hands it
    straight to the route. That matters: a callback that could construct the typed operation could
    also choose its amount, target or counterparty, and permanent human authority requires that it
    cannot. Every consequential value here was fixed when the proposal was made and signed.
    """

    op: InvoiceWriteOperation
    facts: MaterialFactSource
    accountable_owner: str
    allowed_actors: tuple[str, ...]
    secret: bytes
    expected_channel_id: str
    expected_workspace_id: str = ""
    expected_message_ts: str = ""
    #: DARKNESS. Left None, the effect boundary uses its default bounded writer, which performs no
    #: real external write. A live writer is injected at P12, never here.
    writer: Any = None


def peek_approval_id(token: str) -> str:
    """The approval id inside a governed token, WITHOUT verifying it — for ROUTING ONLY.

    This reads an UNTRUSTED field to decide which pending write to look up. Nothing is trusted from
    it: the looked-up `PendingGovernedWrite` carries its own operation and secret, and
    `verify_governed_approval` then re-checks the signature and every binding against that
    operation. A forged id therefore selects either nothing or a pending write whose secret will not
    verify the forged token. Returns "" for anything that is not a governed token.
    """
    import base64
    import json as _json

    raw = str(token or "")
    if raw.count(".") != 1:
        return ""
    body_part, _sig = raw.split(".", 1)
    try:
        data = _json.loads(base64.urlsafe_b64decode(body_part.encode("ascii")).decode("utf-8"))
    except Exception:  # noqa: BLE001 — an unparseable token simply is not routable
        return ""
    if not isinstance(data, dict) or data.get("type") != GOVERNED_TOKEN_TYPE:
        return ""
    return str(data.get("approval_id", ""))


# ------------------------------------------------------------------ THE AUTHENTICATED ENTRY POINT


def handle_governed_write_callback(
    kernel: Any,
    *,
    token: str,
    op: InvoiceWriteOperation,
    secret: bytes | str,
    allowed_actors: Any,
    expected_channel_id: str,
    expected_workspace_id: str,
    expected_message_ts: str,
    facts: MaterialFactSource,
    accountable_owner: str,
    now: datetime,
    writer: Any = None,
    authority: str = "owner",
) -> GovernedWriteOutcome:
    """THE PRODUCTION ENTRY POINT, called from the authenticated Slack callback path.

    One function, the whole order: authenticate the decision, bind it to the typed operation, record
    it once, advance the pipeline, consume that advance, and drive checkpoint -> witness -> grant ->
    claim -> adapter -> readback -> outcome.

    THE CALLBACK STILL NEVER TOUCHES AN ACTUATOR. Nothing on this path imports `cdp_actuator`,
    `cdp_session`, `operation_router` or `operator_agent`; the only effect-capable adapter reachable
    from here is the one the effect boundary itself owns, behind a claimed grant, and it is dark.

    Every failure is a typed refusal that leaves the world untouched: a forged signature, a stale
    envelope, an unauthorized actor, a tenant/work-item/revision/payload/capability mismatch and a
    duplicate tap all fail BEFORE any checkpoint runs.
    """
    approval = verify_governed_approval(                    # authenticated + fully bound
        token, op,
        secret=secret,
        server_tenant=kernel.store.tenant,
        allowed_actors=allowed_actors,
        expected_channel_id=expected_channel_id,
        expected_workspace_id=expected_workspace_id,
        expected_message_ts=expected_message_ts,
        now=now,
    )
    decision: GovernedDecision = record_governed_decision(kernel.store, approval, op, now=now)
    if not decision.recorded:
        # A duplicate delivery of the same approved intent. The decision was already recorded, so no
        # second intent was queued and no second external attempt can follow.
        return GovernedWriteOutcome(
            approval_id=approval.approval_id, consumed=False, executed=False,
            state="REFUSED", cause="DUPLICATE_CALLBACK", commit_key=op.effect_key(),
            reason="this governed approval was already recorded; a duplicate callback records no "
                   "second decision and queues no second write intent")
    return consume_governed_write_intent(
        kernel, approval, op,
        facts=facts, accountable_owner=accountable_owner, authority=authority,
        now=now, writer=writer,
    )


# ------------------------------------------------------------------ helpers


def approval_operation_mismatch(
    approval: GovernedApproval, op: InvoiceWriteOperation, *, server_tenant: str
) -> str:
    """"" when every binding agrees, else the FIRST disagreement, named.

    This is the same binding set `verify_governed_approval` enforces, re-expressed as a pure
    predicate so the consumption boundary can refuse independently of the transport. Substituting an
    approval identity, actor, tenant, Work Item, revision, payload or capability is refused here
    even by a caller that never went through the signed envelope at all.
    """
    if not _same(approval.tenant, op.tenant):
        return f"tenant mismatch: approval={approval.tenant!r} operation={op.tenant!r}"
    if not _same(approval.tenant, server_tenant):
        return f"tenant mismatch: approval={approval.tenant!r} kernel={server_tenant!r}"
    if not _same(approval.approval_id, op.approval_id):
        return (f"approval-id mismatch: approval={approval.approval_id!r} "
                f"operation={op.approval_id!r} — a grant may not be authorized by a different "
                f"approval than the one the human signed")
    if not _same(approval.work_item_id, op.work_item_id):
        return f"work-item mismatch: {approval.work_item_id!r} != {op.work_item_id!r}"
    if not _same(approval.pipeline_instance_id, op.pipeline_instance_id):
        return f"pipeline-instance mismatch: {approval.pipeline_instance_id!r} != {op.pipeline_instance_id!r}"
    if approval.operation_class != op.operation_class.value:
        return f"operation-class mismatch: {approval.operation_class!r} != {op.operation_class.value!r}"
    if int(approval.approval_revision) != int(op.approval_revision):
        return (f"revision mismatch: v{approval.approval_revision} != v{op.approval_revision} — a "
                f"previous approval does not authorize a later revision of the Work Item")
    if approval.payload_hash != op.payload_hash():
        return ("payload-hash mismatch: the approved facts are not the facts of the operation "
                "presented")
    if not _same(approval.capability_id, op.capability_id):
        return f"capability mismatch: {approval.capability_id!r} != {op.capability_id!r}"
    if not _same(approval.idempotency_key, op.idempotency_key):
        return f"idempotency-key mismatch: {approval.idempotency_key!r} != {op.idempotency_key!r}"
    return ""


def _exposure(op: InvoiceWriteOperation) -> str:
    """A money-free exposure string. Memory and logs never store a money value (CLAUDE.md §10)."""
    return (f"operation={op.operation_class.value} target={op.target_integration}:{op.load_id} "
            f"amount_approved={'yes' if op.approved_amount else 'no'}")


def _same(a: object, b: object) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def _utc(when: datetime) -> datetime:
    return when.astimezone(timezone.utc)


__all__ = [
    "QUEUED_EVENT",
    "PendingGovernedWrite",
    "peek_approval_id",
    "GovernedWriteIntent",
    "GovernedWriteOutcome",
    "GovernedWriteRouteError",
    "MaterialFactSource",
    "approval_operation_mismatch",
    "consume_governed_write_intent",
    "handle_governed_write_callback",
    "queued_write_intents",
]
