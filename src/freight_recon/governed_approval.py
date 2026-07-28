"""THE GOVERNED APPROVAL BINDING (P4 adapter containment, EP-1 write-half, R-07 scope).

A Slack button callback is NOT, by itself, authority to perform an arbitrary effect. This module is
what turns a raw human tap into a recorded, bounded, single-use decision that the governed pipeline
can advance — and it draws the hard line the containment requires:

    THE CALLBACK RECORDS THE HUMAN DECISION AND ADVANCES THE GOVERNED PIPELINE.
    THE CALLBACK MUST NOT DIRECTLY INVOKE THE BROWSER ACTUATOR.

So nothing in this module imports an adapter, mints a grant, mints a witness, or touches the effect
boundary. It produces a `GovernedApproval` — a recorded decision bound to exactly one typed
`InvoiceWriteOperation` — and records that the write intent is now QUEUED for the governed route. The
consequential write happens later, through the checkpoint/witness/grant/claim boundary, with no
production caller yet (it ships dark, P12).

WHAT THE BINDING PROVES (each is a distinct, testable refusal):
  * authenticated        — an HMAC signature over the whole bound envelope (a forgery fails)
  * actor-authorized     — the actor is on the operation's allowlist
  * tenant-bound         — the envelope's tenant equals the operation's and the server's
  * context-bound        — workspace / channel / message match where applicable
  * work-item-bound      — the envelope names the operation's Work Item
  * operation-class-bound— the envelope's class equals the operation's class
  * payload-hash-bound   — the envelope's payload hash equals the operation's payload hash
  * revision-bound       — the envelope's revision equals the operation's revision
  * time-bounded         — an expired envelope is refused (staleness is not weakness; it is refusal)
  * single-use           — the decision is claimed once, atomically, per tenant (a replay is refused)

A PREVIOUS APPROVAL THEREFORE CANNOT AUTHORIZE a changed invoice, amount, load, tenant, target
system, operation class, or a later Work Item revision: every one of those changes the payload hash,
the class, the tenant, or the revision, and the binding refuses the mismatch BEFORE any pipeline
advance — and the checkpoint's own material-facts fingerprint refuses it AGAIN at execution.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .freight_operations import InvoiceWriteOperation

GOVERNED_TOKEN_TYPE = "governed_invoice_write_approval"


class GovernedApprovalError(RuntimeError):
    """A governed approval failed to bind. Fail closed: nothing is recorded, no pipeline advances."""


class ForgedApproval(GovernedApprovalError):
    """The signature is missing, malformed or does not verify — the envelope is untrusted."""


class StaleApproval(GovernedApprovalError):
    """The envelope has expired. An approval past its window is not a weaker approval."""


class UnauthorizedActor(GovernedApprovalError):
    """The tapping actor is not on the operation's allowlist."""


class ContextMismatch(GovernedApprovalError):
    """The workspace / channel / message the tap came from is not the one the envelope was bound to."""


class BindingMismatch(GovernedApprovalError):
    """The envelope binds a different tenant, operation class, payload hash, revision or Work Item
    than the typed operation presented — a previous approval for a different effect."""


class AlreadyConsumed(GovernedApprovalError):
    """The decision has already been recorded once. A governed approval is single-use."""


@dataclass(frozen=True, slots=True)
class GovernedApproval:
    """The recorded human decision, bound to ONE typed operation. Every field is a binding the
    verifier revalidates; none of them is executable, and there is no adapter, task or selector
    anywhere in it. Immutable: a decision that can be edited after the fact is not a decision."""

    approval_id: str
    tenant: str
    actor_id: str
    workspace_id: str
    channel_id: str
    message_ts: str
    work_item_id: str
    pipeline_instance_id: str
    operation_class: str
    payload_hash: str
    approval_revision: int
    capability_id: str
    idempotency_key: str
    issued_at: float
    expires_at: float

    def envelope(self) -> dict[str, Any]:
        """The canonical bound envelope that is signed. Deterministic key order so the signature is
        stable and any change to any bound field changes the signature."""
        return {
            "type": GOVERNED_TOKEN_TYPE,
            "approval_id": self.approval_id,
            "tenant": self.tenant,
            "actor_id": self.actor_id,
            "workspace_id": self.workspace_id,
            "channel_id": self.channel_id,
            "message_ts": self.message_ts,
            "work_item_id": self.work_item_id,
            "pipeline_instance_id": self.pipeline_instance_id,
            "operation_class": self.operation_class,
            "payload_hash": self.payload_hash,
            "approval_revision": int(self.approval_revision),
            "capability_id": self.capability_id,
            "idempotency_key": self.idempotency_key,
            "issued_at": float(self.issued_at),
            "expires_at": float(self.expires_at),
        }


def governed_approval_for(
    op: InvoiceWriteOperation,
    *,
    actor_id: str,
    workspace_id: str,
    channel_id: str,
    message_ts: str,
    issued_at: datetime,
    ttl_seconds: int = 3600,
) -> GovernedApproval:
    """Build the `GovernedApproval` that binds a specific typed operation to a specific human tap.

    The payload hash, operation class, tenant, Work Item, revision and capability id are taken FROM
    the operation, so the envelope cannot bind values the operation does not carry. This is what the
    proposal step issues; the tap returns the signed form of it.
    """
    issued = issued_at.astimezone(timezone.utc).timestamp()
    return GovernedApproval(
        approval_id=op.approval_id,
        tenant=op.tenant,
        actor_id=str(actor_id),
        workspace_id=str(workspace_id),
        channel_id=str(channel_id),
        message_ts=str(message_ts),
        work_item_id=op.work_item_id,
        pipeline_instance_id=op.pipeline_instance_id,
        operation_class=op.operation_class.value,
        payload_hash=op.payload_hash(),
        approval_revision=int(op.approval_revision),
        capability_id=op.capability_id,
        idempotency_key=op.idempotency_key,
        issued_at=issued,
        expires_at=issued + int(ttl_seconds),
    )


def sign_governed_approval(approval: GovernedApproval, secret: bytes | str) -> str:
    """HMAC-sign the bound envelope. `body.signature`, base64url body, hex signature — the same
    shape the existing signed-action tokens use, so the transport is unchanged."""
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    body = base64.urlsafe_b64encode(
        json.dumps(approval.envelope(), sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(key, body, hashlib.sha256).hexdigest()
    return f"{body.decode('ascii')}.{signature}"


def _parse_signed(token: str, secret: bytes | str) -> dict[str, Any]:
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    if not token or token.count(".") != 1:
        raise ForgedApproval("malformed governed approval token")
    body_part, signature = token.split(".", 1)
    body = body_part.encode("ascii")
    expected = hmac.new(key, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ForgedApproval("governed approval signature mismatch — forged or modified")
    try:
        data = json.loads(base64.urlsafe_b64decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ForgedApproval("governed approval payload is not valid JSON") from exc
    if not isinstance(data, dict) or data.get("type") != GOVERNED_TOKEN_TYPE:
        raise ForgedApproval("governed approval token is not a governed-invoice-write approval")
    return data


def verify_governed_approval(
    token: str,
    op: InvoiceWriteOperation,
    *,
    secret: bytes | str,
    server_tenant: str,
    allowed_actors: frozenset[str] | set[str] | tuple[str, ...],
    expected_channel_id: str,
    expected_workspace_id: str = "",
    expected_message_ts: str = "",
    now: datetime,
) -> GovernedApproval:
    """Verify a signed governed approval against the typed operation it must authorize.

    Raises a typed `GovernedApprovalError` subclass for each distinct failure, so a caller (and the
    tests) can prove each barrier independently. Returns the bound `GovernedApproval` on success —
    NOT authority to execute: execution still requires the whole checkpoint/grant/claim chain.
    """
    data = _parse_signed(token, secret)          # authenticated (forgery / modification refused)
    approval = GovernedApproval(
        approval_id=str(data.get("approval_id", "")),
        tenant=str(data.get("tenant", "")),
        actor_id=str(data.get("actor_id", "")),
        workspace_id=str(data.get("workspace_id", "")),
        channel_id=str(data.get("channel_id", "")),
        message_ts=str(data.get("message_ts", "")),
        work_item_id=str(data.get("work_item_id", "")),
        pipeline_instance_id=str(data.get("pipeline_instance_id", "")),
        operation_class=str(data.get("operation_class", "")),
        payload_hash=str(data.get("payload_hash", "")),
        approval_revision=int(data.get("approval_revision", -1)),
        capability_id=str(data.get("capability_id", "")),
        idempotency_key=str(data.get("idempotency_key", "")),
        issued_at=float(data.get("issued_at", 0.0)),
        expires_at=float(data.get("expires_at", 0.0)),
    )

    # time-bounded
    if now.astimezone(timezone.utc).timestamp() > approval.expires_at:
        raise StaleApproval(
            f"governed approval expired at {approval.expires_at} (now "
            f"{now.astimezone(timezone.utc).timestamp()})")

    # tenant-bound: the envelope, the operation, and the server must all name ONE tenant
    if not (_eq(approval.tenant, op.tenant) and _eq(approval.tenant, server_tenant)):
        raise BindingMismatch(
            f"tenant binding mismatch: envelope={approval.tenant!r} op={op.tenant!r} "
            f"server={server_tenant!r}")

    # actor-authorized
    if approval.actor_id not in set(allowed_actors):
        raise UnauthorizedActor(
            f"actor {approval.actor_id!r} is not authorized for this operation")

    # context-bound (workspace / channel / message where applicable)
    if not _eq(approval.channel_id, expected_channel_id):
        raise ContextMismatch(
            f"channel binding mismatch: envelope={approval.channel_id!r} "
            f"clicked-in={expected_channel_id!r}")
    if expected_workspace_id and not _eq(approval.workspace_id, expected_workspace_id):
        raise ContextMismatch("workspace binding mismatch")
    if expected_message_ts and not _eq(approval.message_ts, expected_message_ts):
        raise ContextMismatch("message binding mismatch")

    # work-item-bound
    if not _eq(approval.work_item_id, op.work_item_id):
        raise BindingMismatch(
            f"work-item binding mismatch: envelope={approval.work_item_id!r} op={op.work_item_id!r}")

    # operation-class-bound
    if approval.operation_class != op.operation_class.value:
        raise BindingMismatch(
            f"operation-class mismatch: envelope={approval.operation_class!r} "
            f"op={op.operation_class.value!r}")

    # revision-bound
    if int(approval.approval_revision) != int(op.approval_revision):
        raise BindingMismatch(
            f"revision mismatch: envelope=v{approval.approval_revision} op=v{op.approval_revision} — "
            f"a previous approval does not authorize a later revision of the Work Item")

    # payload-hash-bound: a changed invoice / amount / load / target changes this hash
    if not hmac.compare_digest(approval.payload_hash, op.payload_hash()):
        raise BindingMismatch(
            "payload-hash mismatch: the approved facts are not the facts of the operation presented "
            "— a previous approval does not authorize a changed invoice, amount, load or target")

    # capability id bound (belt and suspenders: the op the boundary will invoke)
    if not _eq(approval.capability_id, op.capability_id):
        raise BindingMismatch("capability-id binding mismatch")

    return approval


@dataclass(frozen=True, slots=True)
class GovernedDecision:
    """The receipt of recording ONE governed decision. `recorded` is False when the decision was
    already recorded (single-use); `advanced` is True when a fresh write intent was queued for the
    governed route. No adapter was touched producing this — a decision, not an effect."""

    approval_id: str
    recorded: bool
    advanced: bool
    commit_key: str
    payload_hash: str
    exposure: str


def record_governed_decision(
    store: Any,
    approval: GovernedApproval,
    op: InvoiceWriteOperation,
    *,
    now: datetime,
) -> GovernedDecision:
    """Record the human decision and ADVANCE THE GOVERNED PIPELINE — and do nothing else.

    Single-use is atomic and tenant-scoped: `store.claim_operation_action` inserts one row per
    (tenant, approval_id); a duplicate tap loses the claim and is recorded as a duplicate, never as a
    second decision. The advance is a durable, tenant-scoped record that a write intent is now QUEUED
    for the checkpoint/grant/claim route — NOT the write itself. No adapter, grant, witness or claim
    is created here; this module cannot reach one.

    Money never lands in the record: only the payload hash and a rendered exposure string
    (action + target), never the raw amount (memory/logs never store money).
    """
    exposure = _rendered_exposure(op)
    claimed = store.claim_operation_action(
        approval.approval_id,
        actor=approval.actor_id,
        payload={
            "kind": "governed_invoice_write_decision",
            "tenant": op.tenant,
            "work_item_id": op.work_item_id,
            "pipeline_instance_id": op.pipeline_instance_id,
            "operation_class": op.operation_class.value,
            "payload_hash": approval.payload_hash,
            "capability_id": op.capability_id,
            "exposure": exposure,
        },
    )
    if not claimed:
        store.add_security_event(
            "GovernedApprovalReplayIgnored", actor=approval.actor_id,
            payload={"approval_id": approval.approval_id, "tenant": op.tenant,
                     "work_item_id": op.work_item_id, "payload_hash": approval.payload_hash})
        return GovernedDecision(
            approval_id=approval.approval_id, recorded=False, advanced=False,
            commit_key=op.effect_key(), payload_hash=approval.payload_hash, exposure=exposure)

    # advance the governed pipeline: a durable record that the write intent is QUEUED for the
    # checkpoint/grant/claim route. This is the human decision advancing the pipeline; it is NOT an
    # external effect and touches no adapter.
    store.add_security_event(
        "GovernedWriteIntentQueued", actor=approval.actor_id,
        payload={"approval_id": approval.approval_id, "tenant": op.tenant,
                 "work_item_id": op.work_item_id, "pipeline_instance_id": op.pipeline_instance_id,
                 "commit_key": op.effect_key(), "operation_class": op.operation_class.value,
                 "payload_hash": approval.payload_hash, "capability_id": op.capability_id,
                 "idempotency_key": op.idempotency_key, "sandbox": bool(op.sandbox),
                 "exposure": exposure,
                 "queued_at": now.astimezone(timezone.utc).isoformat()})
    return GovernedDecision(
        approval_id=approval.approval_id, recorded=True, advanced=True,
        commit_key=op.effect_key(), payload_hash=approval.payload_hash, exposure=exposure)


def build_checkpoint_approval(
    approval: GovernedApproval,
    *,
    material_facts_fingerprint: str,
    canonical_payload: bytes,
    fingerprint_version: str,
    entity_versions: dict[str, int],
    policy_version: str,
    authority: str,
    granted_at: datetime,
    expires_at: datetime,
):
    """Map a bound `GovernedApproval` onto the checkpoint kernel's `ApprovalRecord`.

    The kernel's `ApprovalRecord.fingerprint` is the MATERIAL-FACTS fingerprint (the live-world drift
    barrier), which is distinct from this approval's payload hash (the approved-proposal drift
    barrier). The caller composes the material-facts fingerprint through the ONE canonical composer
    (`checkpoint.material_fact_set`) and passes it here, so the two barriers stay independent and
    neither is reconstructed from the other. `checkpoint` is imported lazily: this module never
    depends on the kernel at import time, and it certainly never creates a grant or witness.
    """
    from .checkpoint import ApprovalRecord  # lazy: no kernel coupling at import time

    return ApprovalRecord(
        approval_id=approval.approval_id,
        tenant=approval.tenant,
        actor_id=approval.actor_id,
        actor_kind="HUMAN",
        authority=authority,
        state="GRANTED",
        fingerprint=material_facts_fingerprint,
        canonical_payload=canonical_payload,
        fingerprint_version=fingerprint_version,
        entity_versions=dict(entity_versions),
        policy_version=policy_version,
        granted_at=granted_at.astimezone(timezone.utc),
        expires_at=expires_at.astimezone(timezone.utc),
    )


def _rendered_exposure(op: InvoiceWriteOperation) -> str:
    """A rendered exposure string for the record — WITHOUT the money value. Memory and logs never
    store money (CLAUDE.md §10): the record says an amount was approved, never what it was. The raw
    figure lives only on the approval/grant, never in this durable record."""
    return (f"operation={op.operation_class.value} target={op.target_integration}:{op.load_id} "
            f"amount_approved={'yes' if op.approved_amount else 'no'}")


def _eq(a: object, b: object) -> bool:
    return str(a or "").strip().lower() == str(b or "").strip().lower()
