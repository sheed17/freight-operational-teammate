"""THE PENDING GOVERNED WRITE REPOSITORY — the minimum bounded lookup the P4 route needs.

WHY THIS EXISTS, AND WHY IT IS DELIBERATELY SMALL. The governed write route needs ONE thing the
authenticated callback must never provide: the typed `InvoiceWriteOperation` itself. A callback that
could BUILD the operation could choose its amount, counterparty, load, destination system, adapter
and capability — and permanent human authority (CLAUDE.md §5 rules 5/6) requires that it cannot. So
the operation is written down when it is PROPOSED, and the callback may only LOOK IT UP.

    THE CALLBACK SUPPLIES IDENTITY. THE REPOSITORY SUPPLIES THE OPERATION.

The callback contributes only authenticated, immutable lookup and decision material — approval id,
Work Item, pipeline instance, tenant/workspace identity, revision, and the signed channel receipt —
all of which are re-verified against the stored record and against the human's signed envelope.
Nothing a caller sends can add, replace or edit an operation field.

### THIS IS NOT P6. It is the smallest interface that makes the P4 authority boundary real.
`PendingGovernedWriteRepository` is the boundary; `WorkflowStorePendingWrites` is one storage
implementation of it. **A later phase may replace the storage entirely — a real Work Item /
Pipeline Instance store, Postgres, an outbox — without changing the authority boundary**, because
every rule that matters (what may be looked up, what must match, what fails closed) lives in the
interface and in the checks below, not in where the bytes sit.

HOW IT STORES, AND WHY THAT SHAPE. It reuses the repository's established pattern rather than
inventing one: `thread_reply.find_resumable_operation` already retrieves a pending operation by
reading identity from the durable security-event log and then re-verifying the APPROVED AMOUNT
against the dedicated `operation_token_amounts` table, refusing when the two disagree. The same
split is used here, for the same reason — **memory and logs never store a money value**
(CLAUDE.md §10):

  * identity and the non-money approved fields  -> the `GovernedWriteOperationProposed` event
  * the approved AMOUNT                          -> `operation_token_amounts` (the money table)

INTEGRITY IS PROVED, NOT ASSUMED. Reconstruction is checked against the `payload_hash` recorded at
proposal time — the same hash the human's signature binds. If the stored record, the money table and
the recorded hash do not agree exactly, `pending_for` returns **None** and the route fails closed.
A tampered row cannot produce a different operation; it can only produce no operation.

DARKNESS. This module registers no adapter and injects no writer: `PendingGovernedWrite.writer` is
left `None`, so the effect boundary uses its own default bounded writer, which performs no real
external write. Nothing here can enable one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from .checkpoint import EvidenceCondition, ProvenanceClass, ProvenancedFact
from .fingerprint import Money
from .freight_operations import FreightOperationClass, InvoiceWriteOperation
from .governed_write_route import MaterialFactSource, PendingGovernedWrite

#: The canonical durable record of a PROPOSED governed write. Written at proposal time, read by the
#: repository at tap time. Identity and non-money fields only.
PROPOSED_EVENT = "GovernedWriteOperationProposed"

#: Approved-field keys whose values are MONEY and therefore never enter the event log. They are
#: stored in, and re-read from, `operation_token_amounts`.
MONEY_FIELDS: frozenset[str] = frozenset({"amount"})

#: The adapter the P4 boundary invokes for this operation class. Recorded so a stored record naming
#: a different adapter is refused rather than silently routed.
GOVERNED_ADAPTER = "A4"


class PendingWriteRepositoryError(RuntimeError):
    """A pending governed write could not be recorded. Fail closed: nothing is proposed."""


# ------------------------------------------------------------------ the authority boundary


class PendingGovernedWriteRepository(Protocol):
    """THE AUTHORITY BOUNDARY. Exactly one capability: given an approval id, return the
    already-authorized pending write, or None.

    There is deliberately no method that CREATES, EDITS or COMPLETES an operation from caller input.
    That absence is the containment: a callback holding this interface can look one up and nothing
    else. A later phase may implement this over real P6 entities; the boundary does not change.
    """

    def pending_for(self, approval_id: str) -> PendingGovernedWrite | None:
        """The pending governed write for `approval_id`, or None when there is none, when it has
        expired, or when its stored form fails its own integrity check. None means FAIL CLOSED."""
        ...


# ------------------------------------------------------------------ writing the proposal down


def record_proposed_governed_write(
    store: Any,
    op: InvoiceWriteOperation,
    *,
    allowed_actors: tuple[str, ...] | list[str],
    workspace_id: str,
    channel_id: str,
    message_ts: str,
    token_fingerprint: str,
    accountable_owner: str,
    entity_versions: dict[str, int],
    expires_at: datetime,
    currency: str = "USD",
    policy_version: str = "pv1",
    counterparty: str = "",
) -> None:
    """Write down ONE proposed governed write, at proposal time, so the tap can only look it up.

    This is the ONLY way an operation enters the repository. It is called by the proposal step —
    the place where a human is shown exact facts — never by the callback.

    The approved AMOUNT goes to the money table, never into the event payload.
    """
    if not isinstance(op, InvoiceWriteOperation):
        raise PendingWriteRepositoryError("only a typed InvoiceWriteOperation may be proposed")
    if not str(token_fingerprint or "").strip():
        raise PendingWriteRepositoryError(
            "a proposed governed write is bound to the signed token's fingerprint; blank is not one")
    if not str(accountable_owner or "").strip():
        raise PendingWriteRepositoryError(
            "every consequential operation has one accountable human owner (CLAUDE.md §5 rule 13)")
    actors = tuple(str(a).strip() for a in allowed_actors if str(a).strip())
    if not actors:
        raise PendingWriteRepositoryError(
            "a proposed governed write names the actors permitted to approve it; an empty allowlist "
            "would authorize everyone, so it is refused")

    amount = str(op.approved_fields.get("amount", "") or "")
    if amount:
        # MONEY GOES HERE, AND ONLY HERE.
        store.record_operation_token_amount(
            token_fingerprint=token_fingerprint,
            action_id=op.approval_id,
            approved_amount=amount,
            payload={"kind": "governed_invoice_write_proposal", "approval_id": op.approval_id},
        )

    store.add_security_event(
        PROPOSED_EVENT,
        actor=accountable_owner,
        payload={
            # -- lookup identity ---------------------------------------------------------------
            "approval_id": op.approval_id,
            "tenant": op.tenant,
            "work_item_id": op.work_item_id,
            "pipeline_instance_id": op.pipeline_instance_id,
            "revision": int(op.approval_revision),
            # -- the signed channel receipt ----------------------------------------------------
            "workspace_id": str(workspace_id),
            "channel_id": str(channel_id),
            "message_ts": str(message_ts),
            "token_fingerprint": str(token_fingerprint),
            # -- the bounded operation, minus money --------------------------------------------
            "load_id": op.load_id,
            "invoice_ref": op.invoice_ref,
            "target_integration": op.target_integration,
            "target_account": op.target_account,
            "operation_class": op.operation_class.value,
            "capability_id": op.capability_id,
            "adapter": GOVERNED_ADAPTER,
            "idempotency_key": op.idempotency_key,
            "sandbox": bool(op.sandbox),
            "base_url": op.base_url,
            "expected_preconditions": list(op.expected_preconditions),
            "verification_mode": op.verification_mode,
            "approved_fields_nonmoney": {
                k: str(v) for k, v in sorted(op.approved_fields.items()) if k not in MONEY_FIELDS},
            "money_fields_withheld": sorted(k for k in op.approved_fields if k in MONEY_FIELDS),
            "currency": str(currency),
            # -- what the tap must satisfy ------------------------------------------------------
            "allowed_actors": list(actors),
            "accountable_owner": str(accountable_owner),
            "entity_versions": {str(k): int(v) for k, v in dict(entity_versions).items()},
            "policy_version": str(policy_version),
            "counterparty": str(counterparty),
            "expires_at": _utc(expires_at).isoformat(),
            # -- the integrity anchor -----------------------------------------------------------
            # The hash the HUMAN's signature binds. Reconstruction must reproduce it exactly.
            "payload_hash": op.payload_hash(),
        },
    )


# ------------------------------------------------------------------ reading it back


class WorkflowStorePendingWrites:
    """ONE implementation of `PendingGovernedWriteRepository`, over the tenant-bound WorkflowStore.

    ### STORAGE DETAIL, NOT AUTHORITY. Everything that decides whether a write may proceed lives in
    the interface contract and in `pending_for`'s integrity checks. A later phase may swap this for
    real Work Item / Pipeline Instance entities, a relational store or an outbox **without changing
    the authority boundary** — the route will still receive a `PendingGovernedWrite` or `None`, and
    `None` will still mean fail closed.
    """

    __slots__ = ("_open", "_owns_store", "_secret", "_source", "_writer")

    def __init__(self, store_factory: Any, *, secret: bytes | str,
                 source: str = "tms:truckingoffice", writer: Any = None) -> None:
        """`store_factory` is a ZERO-ARGUMENT callable returning a tenant-bound WorkflowStore.

        A factory, not a live store, for two reasons that both matter in the deployed server:
        SQLite connections are not shareable across a threading HTTP server's request threads, and
        the material-fact readers must perform a LIVE read at CHECKPOINT time — long after the
        lookup returned. Handing them a connection the lookup had already closed is exactly the
        defect this shape removes: every read opens, and closes, its own connection.

        A live `WorkflowStore` is also accepted, for tests and short-lived callers. It is then
        reused as-is and never closed by this class, because this class does not own it.
        """
        self._owns_store = callable(store_factory)
        if self._owns_store:
            self._open = store_factory
        else:
            existing = store_factory
            self._open = lambda: existing
        self._secret = secret
        self._source = source
        # DARK BY DEFAULT. None => the effect boundary's own bounded writer, which performs no real
        # external write. A live writer is injected at P12, never here.
        self._writer = writer

    def _with_store(self, fn):
        """Run `fn(store)`, closing the store only when this class opened it."""
        store = self._open()
        try:
            return fn(store)
        finally:
            if self._owns_store:
                try:
                    store.close()
                except Exception:  # noqa: BLE001 — a close failure must not mask the result
                    pass

    # -- the one capability ---------------------------------------------------------------------

    def pending_for(self, approval_id: str) -> PendingGovernedWrite | None:
        wanted = str(approval_id or "").strip()
        if not wanted:
            return None
        record = self._latest_proposal(wanted)
        if record is None:
            return None
        try:
            return self._rebuild(record)
        except (PendingWriteRepositoryError, ValueError, TypeError, KeyError):
            # FAIL CLOSED. A record that cannot be rebuilt exactly is not a weaker authorization;
            # it is no authorization. The route then produces an explicit governed refusal.
            return None

    # -- internals ------------------------------------------------------------------------------

    def _latest_proposal(self, approval_id: str) -> dict | None:
        def read(store):
            found = None
            for event in store.security_events():            # tenant-scoped by construction
                if event.get("event_type") != PROPOSED_EVENT:
                    continue
                payload = event.get("payload") or {}
                if str(payload.get("approval_id", "")) == approval_id:
                    found = payload                          # newest wins
            return found

        return self._with_store(read)

    def _rebuild(self, record: dict) -> PendingGovernedWrite | None:
        # -- expiry / single-use state -----------------------------------------------------------
        expires_at = _parse_iso(str(record.get("expires_at", "")))
        if expires_at is None or datetime.now(timezone.utc) > expires_at:
            return None
        # SINGLE-USE is enforced by the route's own atomic, tenant-scoped claims — the decision
        # claim and the consumer claim — not by a lookup-time pre-check. A pre-check here would be a
        # second, weaker answer to a question the claim already answers atomically, and two answers
        # to one question is how a race gets a foothold.

        # -- the adapter must be the one the boundary actually invokes ---------------------------
        if str(record.get("adapter", "")) != GOVERNED_ADAPTER:
            return None

        # -- money comes from the money table, never from the log --------------------------------
        approved_fields = {str(k): str(v)
                           for k, v in dict(record.get("approved_fields_nonmoney") or {}).items()}
        for key in sorted(record.get("money_fields_withheld") or []):
            if key != "amount":
                return None                                   # only `amount` is a known money field
            fingerprint_ref = str(record.get("token_fingerprint", ""))
            amount = self._with_store(lambda s: s.operation_token_amount(fingerprint_ref))
            if not amount:
                return None                                   # the money row is gone -> fail closed
            approved_fields["amount"] = str(amount)

        op = InvoiceWriteOperation(
            tenant=str(record["tenant"]),
            work_item_id=str(record["work_item_id"]),
            pipeline_instance_id=str(record["pipeline_instance_id"]),
            load_id=str(record["load_id"]),
            invoice_ref=str(record["invoice_ref"]),
            target_integration=str(record["target_integration"]),
            target_account=str(record["target_account"]),
            operation_class=FreightOperationClass(str(record["operation_class"])),
            approved_fields=approved_fields,
            approval_id=str(record["approval_id"]),
            approval_revision=int(record["revision"]),
            idempotency_key=str(record["idempotency_key"]),
            capability_id=str(record["capability_id"]),
            expected_preconditions=tuple(record.get("expected_preconditions") or ()),
            verification_mode=str(record.get("verification_mode", "READBACK_VERIFIABLE")),
            sandbox=bool(record.get("sandbox", True)),
            base_url=str(record.get("base_url", "")),
        )

        # -- THE INTEGRITY ANCHOR ----------------------------------------------------------------
        # The rebuilt operation must hash to exactly what was recorded when the human was shown it —
        # which is also what their signature binds. One changed byte anywhere (the event row, the
        # money table, this reconstruction) yields a different hash and no authorization at all.
        if op.payload_hash() != str(record.get("payload_hash", "")):
            return None

        actors = tuple(str(a) for a in (record.get("allowed_actors") or ()) if str(a).strip())
        if not actors:
            return None

        return PendingGovernedWrite(
            op=op,
            facts=self._facts_for(op, record),
            accountable_owner=str(record["accountable_owner"]),
            allowed_actors=actors,
            secret=self._secret,
            expected_channel_id=str(record.get("channel_id", "")),
            expected_workspace_id=str(record.get("workspace_id", "")),
            expected_message_ts=str(record.get("message_ts", "")),
            writer=self._writer,                              # None => dark
        )

    def _facts_for(self, op: InvoiceWriteOperation, record: dict) -> MaterialFactSource:
        """The material facts the checkpoint reads live.

        ### STATED LIMITATION, DELIBERATELY NOT HIDDEN. Until P12 wires a real TMS read, these
        readers perform a LIVE read of THIS REPOSITORY'S OWN recorded proposal, not of the external
        authoritative source. That means the checkpoint's step-2/step-5 drift barrier currently
        detects drift in the repository's record, NOT drift in the outside world. It is a genuine
        live read (no cache, re-evaluated per call) and it is genuinely load-bearing, but it is not
        yet the external-world barrier ADR-001 C4 ultimately requires.
        ### THIS IS ONE OF THE REASONS THE ROUTE MUST STAY DARK. Replacing this one method with a
        real authoritative read is a P12 obligation, and it changes no other part of the boundary.
        """
        approval_id = str(record.get("approval_id", ""))
        fingerprint_ref = str(record.get("token_fingerprint", ""))
        currency = str(record.get("currency", "USD"))
        counterparty = str(record.get("counterparty", ""))
        versions = {str(k): int(v) for k, v in dict(record.get("entity_versions") or {}).items()}
        with_store = self._with_store

        def business_facts() -> dict:
            # LIVE: re-read per call, on this thread's OWN connection, money re-fetched from the
            # money table every time. Never a value remembered from lookup time.
            amount = with_store(lambda s: s.operation_token_amount(fingerprint_ref)) or ""
            facts = {
                "amount": ProvenancedFact(
                    field="amount",
                    provenance=ProvenanceClass.OWNER_ASSERTED,
                    evidence_condition=EvidenceCondition.CONSISTENT,
                    entity_ref=op.load_id,
                    _value=_money(amount, currency)),
            }
            if counterparty:
                facts["counterparty"] = ProvenancedFact(
                    field="counterparty",
                    provenance=ProvenanceClass.SYSTEM_IMPORTED,
                    evidence_condition=EvidenceCondition.CONSISTENT,
                    entity_ref=op.load_id,
                    _value=counterparty)
            return facts

        def projected_state() -> dict:
            return {"status": with_store(lambda s: _projected_status(s, approval_id))}

        def entity_versions() -> dict:
            return dict(versions)

        return MaterialFactSource(
            business_facts=business_facts,
            projected_state=projected_state,
            entity_versions=entity_versions,
            projection_assertion={"status": "DELIVERED"},
            policy_version=str(record.get("policy_version", "pv1")),
            source=self._source,
        )


# ------------------------------------------------------------------ THE GATE REGISTRY IS BLOCKED
#
# A `GateRegistry` construction belonged here. It is REMOVED, and deliberately not relocated.
#
# `CheckpointKernel` cannot exist without one (F-20: "a gate expressible as an absence is not a
# gate"), so the deployed governed route cannot run without production gate registration. But
# repository authority assigns that work elsewhere and reserves the decision:
#
#   * phase-0-baseline-manifest.yaml records AC-CKPT-6-missing as
#     "DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8", green_at_phase P8, accountable_unit U8.1;
#   * pr-sequence.md assigns "typed policy + Action Class gate registration" to U8.1, and states
#     that they "do not exist until P8";
#   * test_phase0_null_gate.py proves the production registration population is EMPTY and says, in
#     terms, that if it stops being empty the deferral must be RE-ADJUDICATED rather than inherited;
#   * CLAUDE.md sec 7 makes this tier 1: an explicit acceptance-contract revision with FOUNDER
#     APPROVAL before a frozen acceptance case changes.
#
# Registering gates here would therefore implement U8.1 inside P4 and silently invalidate a frozen,
# adjudicated deferral. A remediation builder may not do either, and may not adjudicate the case
# itself. The seam is left BLOCKED and named, which is the fail-closed direction: the deployed route
# has its lookup boundary and no kernel, so it refuses.
#
# TO UNBLOCK, ONCE ADJUDICATED: register the freight action classes under ADR-010's gate ladder in
# the module that OWNS policy (the checkpoint kernel), and hand the resulting registry to
# `_build_governed_write_route`. This module deliberately names no gate decision of its own —
# test_phase0_null_gate.py requires policy to be evaluated at the boundary that owns it, never
# carried by a workflow, adapter or callback, and this module is none of those three but is not the
# kernel either. Nothing else on this boundary changes.

# ------------------------------------------------------------------ helpers


def _projected_status(store: Any, approval_id: str) -> str:
    """The projected state this operation was proposed against, re-read live."""
    for event in store.security_events():
        if event.get("event_type") != PROPOSED_EVENT:
            continue
        payload = event.get("payload") or {}
        if str(payload.get("approval_id", "")) == approval_id:
            return "DELIVERED"
    return "UNKNOWN"


def _money(amount: str, currency: str) -> Money:
    """`"2850.00"` -> `Money(285000, "USD")`. Integer minor units only: a float in a fingerprint is
    a double payment waiting to happen, and `Money` refuses one at construction."""
    text = str(amount or "").strip().replace(",", "")
    if not text:
        raise PendingWriteRepositoryError("an approved money value is required")
    negative = text.startswith("-")
    text = text.lstrip("+-")
    whole, _, frac = text.partition(".")
    frac = (frac + "00")[:2]
    if not whole.isdigit() or not frac.isdigit():
        raise PendingWriteRepositoryError(f"{amount!r} is not a decimal money value")
    minor = int(whole) * 100 + int(frac)
    return Money(-minor if negative else minor, str(currency or "USD").upper())


def _parse_iso(text: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _utc(when: datetime) -> datetime:
    return when.astimezone(timezone.utc)


__all__ = [
    "GOVERNED_ADAPTER",
    "MONEY_FIELDS",
    "PROPOSED_EVENT",
    "PendingGovernedWriteRepository",
    "PendingWriteRepositoryError",
    "WorkflowStorePendingWrites",
    "record_proposed_governed_write",
]
