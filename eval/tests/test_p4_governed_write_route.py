"""P4 EP-1 / F-01 — THE REAL GOVERNED EFFECT CHAIN, entered through the production path.

THE FINDING THIS FILE ANSWERS. The independent hostile review rejected the candidate because the
governed pipeline was two disconnected halves: `build_checkpoint_approval` had zero callers,
`GovernedWriteIntentQueued` had no consumer, and the test that appeared to prove the end-to-end
order authorized its executed grant with an UNRELATED fixture approval (`ap-1` / `owner:rasheed`)
while the governed approval beside it was `appr-9` / `U-OWNER`. Two halves, no shared authority.

WHAT IS DIFFERENT HERE. Every test below enters through the REAL production entry point
(`governed_write_route.handle_governed_write_callback`, which the authenticated Slack callback
handler calls) or through the real consumer. NOTHING in this file mints a grant, a witness or an
ApprovalRecord of its own: the only authority in play is the one the signed human decision carries,
and the tests assert that the SAME identity reaches the adapter, the grant row and the witness row.

The bounded writer is a scripted double whose call log is the negative oracle — never a real
browser, and never a source of authority: it holds no kernel, store, grant or witness.
"""

from __future__ import annotations

import ast
import sys
import threading
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon import browser_use_write as bw  # noqa: E402
from freight_recon import effect_boundary as eb  # noqa: E402
from freight_recon import governed_write_route as gwr  # noqa: E402
from freight_recon.fingerprint import fingerprint  # noqa: E402
from freight_recon.checkpoint import material_fact_set  # noqa: E402
from freight_recon.freight_operations import FreightOperationClass, InvoiceWriteOperation  # noqa: E402
from freight_recon.governed_approval import (  # noqa: E402
    GovernedApprovalError,
    governed_approval_for,
    sign_governed_approval,
)
from phase3_kit import EPOCH, T_A, T_B, make_facts, make_kernel, make_store  # noqa: E402

HANDLE_KEY = b"p4-invoice-write-shared-handle-key"
SECRET = b"governed-approval-hmac-secret"
ACTOR = "U-OWNER"
APPROVAL_ID = "appr-9"
OWNER = "owner:rasheed"
CHANNEL, WORKSPACE, MESSAGE_TS = "C-OPS", "W-ACME", "1720000000.000100"


# ------------------------------------------------------------------ the typed operation and world


def _op(**overrides) -> InvoiceWriteOperation:
    base = dict(
        tenant=T_A, work_item_id="WI-77", pipeline_instance_id="PI-77",
        load_id="load:4471", invoice_ref="INV-req-9", target_integration="tms:truckingoffice",
        target_account="acct-broker", operation_class=FreightOperationClass.RAISE_INVOICE,
        approved_fields={"customer": "Echo", "amount": "2850.00", "load_ref": "4471"},
        approval_id=APPROVAL_ID, approval_revision=0, idempotency_key="idem-9",
        capability_id="A4.raise_invoice", sandbox=True, base_url="http://localhost:9111",
    )
    base.update(overrides)
    return InvoiceWriteOperation(**base)


def _facts_source(op: InvoiceWriteOperation, world: dict | None = None):
    """A live MaterialFactSource over a mutable box — the same shape production supplies. Mutating
    the box models real-world drift, which the checkpoint must then catch at step 2/5."""
    box = world if world is not None else {
        "facts": make_facts(entity_ref=op.load_id),
        "projection": {"status": "DELIVERED"},
        "versions": {op.load_id: 17},
    }
    return box, gwr.MaterialFactSource(
        business_facts=lambda: dict(box["facts"]),
        projected_state=lambda: dict(box["projection"]),
        entity_versions=lambda: dict(box["versions"]),
        projection_assertion={"status": "DELIVERED"},
        policy_version="pv1",
    )


def _expected_fingerprint(op: InvoiceWriteOperation, box: dict) -> str:
    """The material-facts fingerprint the checkpoint will compute, composed through the ONE
    canonical composer — not copied out of the implementation."""
    effect = op.logical_effect()
    return fingerprint(material_fact_set(
        effect=effect, commit_key=effect.key(), business_facts=box["facts"],
        entity_versions=dict(box["versions"]), policy_version="pv1"))


def _token(op: InvoiceWriteOperation, *, actor=ACTOR, issued=EPOCH, ttl=3600,
           channel=CHANNEL, workspace=WORKSPACE, message_ts=MESSAGE_TS, secret=SECRET) -> str:
    approval = governed_approval_for(
        op, actor_id=actor, workspace_id=workspace, channel_id=channel,
        message_ts=message_ts, issued_at=issued, ttl_seconds=ttl)
    return sign_governed_approval(approval, secret)


class RecordingWriter:
    """The scripted bounded writer. It RECORDS THE TYPED OPERATION IT WAS HANDED, so the identity
    that reached the adapter is evidence rather than an assumption. It never decides
    VERIFIED/FAILED, and holds no kernel, store, grant or witness — it cannot mint authority."""

    def __init__(self, *, approved_fp: str, mode: str = "ok", readback: str = "match") -> None:
        self.approved_fp = approved_fp
        self.mode = mode
        self.readback_mode = readback
        self.calls: list[tuple[str, str]] = []
        self.seen_ops: list[InvoiceWriteOperation] = []

    def write(self, op) -> bw.BoundedWriteResult:
        self.seen_ops.append(op)
        if self.mode == "preflight_reject":
            return bw.BoundedWriteResult(outcome="PREFLIGHT_REJECTED",
                                         proof="TMS pre-flight: invoice already exists; no write issued")
        if self.mode == "unknown":
            return bw.BoundedWriteResult(outcome="OUTCOME_UNKNOWN",
                                         detail="browser session dropped mid-submit", exposure="rendered")
        if self.mode == "lost_ack":
            self.calls.append(("write", op.load_id))
            raise RuntimeError("submit clicked; acknowledgement never received")
        self.calls.append(("write", op.load_id))
        return bw.BoundedWriteResult(outcome="ATTEMPTED", external_ref="INV-1001", detail="submitted")

    def readback(self, op) -> bw.BoundedReadback:
        self.calls.append(("readback", op.load_id))
        if self.readback_mode == "blind":
            return bw.BoundedReadback(health_signal=False, observed_fingerprint=None,
                                      detail="logged-out page that loads fine")
        observed = self.approved_fp if self.readback_mode == "match" else "CONFLICTING-FINGERPRINT"
        return bw.BoundedReadback(health_signal=True, observed_fingerprint=observed)

    @property
    def writes(self):
        return [c for c in self.calls if c[0] == "write"]


def _scene(tmp_path, *, op=None, name="p4route.db", tenant=None, mode="ok", readback="match"):
    """One complete production scene: store, kernel, live facts, and a recording writer bound to the
    fingerprint the checkpoint will actually compute."""
    op = op if op is not None else _op()
    store = make_store(tmp_path, tenant or op.tenant, name=name)
    kernel, clock = make_kernel(store, handle_key=HANDLE_KEY)
    box, facts = _facts_source(op)
    writer = RecordingWriter(approved_fp=_expected_fingerprint(op, box), mode=mode, readback=readback)
    return store, kernel, clock, box, facts, writer, op


def _call(kernel, op, facts, writer, *, token=None, now=EPOCH, actors=(ACTOR,),
          channel=CHANNEL, workspace=WORKSPACE, message_ts=MESSAGE_TS, secret=SECRET,
          owner=OWNER):
    """ENTER THROUGH THE REAL PRODUCTION ENTRY POINT. Nothing here mints authority."""
    return gwr.handle_governed_write_callback(
        kernel,
        token=token if token is not None else _token(op),
        op=op, secret=secret, allowed_actors=actors,
        expected_channel_id=channel, expected_workspace_id=workspace,
        expected_message_ts=message_ts,
        facts=facts, accountable_owner=owner, now=now, writer=writer)


def _row(store, table, where, args):
    return store.conn.execute(f"SELECT * FROM {table} WHERE {where}", args).fetchone()


def _events(store, event_type):
    return [e for e in store.security_events() if e["event_type"] == event_type]


# ============================================================ THE FULL ORDER, THROUGH PRODUCTION


def test_the_full_order_runs_through_the_real_entry_point_with_one_identity(tmp_path):
    """THE F-01 ACCEPTANCE. One authenticated decision drives the whole chain, and the SAME approval
    identity is present at every stage: the queued intent, the checkpoint's ApprovalRecord, the
    witness row, the Effect Grant row, and the typed operation the ADAPTER received.

    There is no `ap-1` anywhere. Nothing in this test mints a grant or an approval record."""
    store, kernel, _clock, _box, facts, writer, op = _scene(tmp_path)

    outcome = _call(kernel, op, facts, writer)

    # -- it reached the intended real entry point and the intended adapter --------------------
    assert outcome.consumed and outcome.executed, outcome.reason
    assert outcome.state == "VERIFIED", f"{outcome.state}: {outcome.reason}"
    assert len(writer.writes) == 1, "the world must be touched exactly once"
    assert writer.seen_ops, "the ADAPTER was never reached — this proves nothing about the chain"

    # -- ONE IDENTITY LINEAGE, asserted at every stage ---------------------------------------
    assert writer.seen_ops[0].approval_id == APPROVAL_ID, (
        "the adapter received an operation carrying a DIFFERENT approval identity than the human "
        "signed — this is exactly F-01")
    assert writer.seen_ops[0].tenant == T_A
    assert writer.seen_ops[0].work_item_id == "WI-77"
    assert writer.seen_ops[0].pipeline_instance_id == "PI-77"
    assert writer.seen_ops[0].capability_id == "A4.raise_invoice"
    assert writer.seen_ops[0].payload_hash() == op.payload_hash()

    grant = _row(store, "effect_grants", "tenant = ? AND grant_id = ?", (T_A, outcome.grant_id))
    assert grant["approval_id"] == APPROVAL_ID, (
        f"the Effect Grant is authorized by {grant['approval_id']!r}, not by the human's approval")
    assert grant["state"] == "VERIFIED"
    assert grant["commit_key"] == op.effect_key()

    witness = _row(store, "checkpoint_witnesses", "tenant = ? AND checkpoint_id = ?",
                   (T_A, outcome.checkpoint_id))
    assert witness is not None, "no witness row — the checkpoint did not run"
    assert witness["approval_id"] == APPROVAL_ID
    assert witness["grant_id"] == outcome.grant_id
    assert witness["accountable_owner"] == OWNER

    # -- the decision half and the execution half are ONE pipeline ---------------------------
    queued = _events(store, gwr.QUEUED_EVENT)
    assert len(queued) == 1, "the decision did not advance the pipeline exactly once"
    assert queued[0]["payload"]["approval_id"] == APPROVAL_ID
    assert queued[0]["actor"] == ACTOR
    completed = _events(store, "GovernedWriteCompleted")
    assert len(completed) == 1, "the queued intent was never consumed to completion"
    assert completed[0]["payload"]["approval_id"] == APPROVAL_ID
    assert completed[0]["payload"]["grant_id"] == outcome.grant_id
    assert completed[0]["payload"]["actor_id"] == ACTOR
    assert _events(store, "EffectAttempted"), "EffectAttempted must be recorded before the call"

    # -- no money value is written into memory or logs ---------------------------------------
    for event in queued + completed:
        assert "2850.00" not in str(event["payload"]), "a money value reached a durable record"


def test_the_queued_intent_is_really_consumed_not_merely_written(tmp_path):
    """`GovernedWriteIntentQueued` has a REAL consumer: the queue is readable, the consumer reads
    it, and refusing to queue makes the consumer refuse."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path)

    intents = gwr.queued_write_intents(store)
    assert intents == [], "the queue is not empty before the decision"

    _call(kernel, op, facts, writer)
    intents = gwr.queued_write_intents(store, approval_id=APPROVAL_ID)
    assert len(intents) == 1, "the consumer's read side sees no queued intent"
    assert intents[0].approval_id == APPROVAL_ID
    assert intents[0].commit_key == op.effect_key()
    assert intents[0].payload_hash == op.payload_hash()


def test_the_consumer_refuses_when_nothing_was_queued(tmp_path):
    """The consumer never invents an intent: with no queued advance there is nothing to consume."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path)
    approval = governed_approval_for(
        op, actor_id=ACTOR, workspace_id=WORKSPACE, channel_id=CHANNEL,
        message_ts=MESSAGE_TS, issued_at=EPOCH)
    with pytest.raises(gwr.GovernedWriteRouteError, match="no queued write intent"):
        gwr.consume_governed_write_intent(
            kernel, approval, op, facts=facts, accountable_owner=OWNER, now=EPOCH, writer=writer)
    assert len(writer.writes) == 0


# ============================================================ HOSTILE: the binding attacks


def _hostile(tmp_path, **kw):
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path, **kw)
    return store, kernel, facts, writer, op


def test_a_mismatched_approval_id_is_refused(tmp_path):
    """A token signed for a DIFFERENT approval cannot authorize this operation."""
    store, kernel, facts, writer, op = _hostile(tmp_path)
    other = _op(approval_id="appr-OTHER")
    with pytest.raises(GovernedApprovalError):
        _call(kernel, op, facts, writer, token=_token(other))
    assert len(writer.writes) == 0
    assert _events(store, gwr.QUEUED_EVENT) == []


def test_a_mismatched_actor_is_refused(tmp_path):
    """The tapping actor must be on the operation's allowlist."""
    store, kernel, facts, writer, op = _hostile(tmp_path)
    with pytest.raises(GovernedApprovalError):
        _call(kernel, op, facts, writer, token=_token(op, actor="U-INTRUDER"))
    assert len(writer.writes) == 0


def test_a_tenant_mismatch_is_refused(tmp_path):
    """The envelope, the operation and the KERNEL must all name one tenant."""
    op = _op(tenant=T_A)
    store = make_store(tmp_path, T_B, name="beta.db")          # a kernel bound to another tenant
    kernel, _ = make_kernel(store, handle_key=HANDLE_KEY)
    box, facts = _facts_source(op)
    writer = RecordingWriter(approved_fp=_expected_fingerprint(op, box))
    with pytest.raises(GovernedApprovalError):
        _call(kernel, op, facts, writer)
    assert len(writer.writes) == 0


def test_a_work_item_mismatch_is_refused(tmp_path):
    store, kernel, facts, writer, op = _hostile(tmp_path)
    with pytest.raises(GovernedApprovalError):
        _call(kernel, op, facts, writer, token=_token(_op(work_item_id="WI-OTHER")))
    assert len(writer.writes) == 0


def test_a_revision_mismatch_is_refused(tmp_path):
    """A previous approval does not authorize a later revision of the Work Item."""
    store, kernel, facts, writer, op = _hostile(tmp_path)
    with pytest.raises(GovernedApprovalError, match="revision"):
        _call(kernel, op, facts, writer, token=_token(_op(approval_revision=1)))
    assert len(writer.writes) == 0


def test_payload_substitution_is_refused(tmp_path):
    """The approved AMOUNT is changed after signing. The payload hash refuses it — the model never
    chooses an amount, and a signed approval covers exactly the facts it was shown."""
    store, kernel, facts, writer, op = _hostile(tmp_path)
    substituted = _op(approved_fields={"customer": "Echo", "amount": "9999.00", "load_ref": "4471"})
    with pytest.raises(GovernedApprovalError, match="payload-hash"):
        _call(kernel, substituted, facts, writer, token=_token(op))
    assert len(writer.writes) == 0


def test_a_capability_mismatch_is_refused(tmp_path):
    store, kernel, facts, writer, op = _hostile(tmp_path)
    with pytest.raises(GovernedApprovalError, match="capability"):
        _call(kernel, op, facts, writer, token=_token(_op(capability_id="A4.pay_carrier")))
    assert len(writer.writes) == 0


def test_an_adapter_mismatch_cannot_be_reached(tmp_path):
    """The adapter is chosen by the OPERATION's capability id, never by the caller. A capability the
    boundary was not handed cannot perform, so an adapter substitution has nowhere to land."""
    store, kernel, facts, writer, op = _hostile(tmp_path)
    operation = eb.build_invoice_write_operation(op, writer=writer)
    assert operation.adapter == "A4"
    assert operation.op_id == op.capability_id
    from freight_recon.checkpoint import ClaimParams
    params = ClaimParams(tenant=op.tenant, action_class="raise_invoice",
                         target_system=op.target_integration, target_resource_id=op.load_id,
                         target_operation="raise_invoice")
    with pytest.raises(eb.OrphanEffectDetected):
        operation.perform(object(), params)
    assert len(writer.writes) == 0


def test_a_stale_approval_is_refused(tmp_path):
    """Staleness is not weakness; it is refusal."""
    store, kernel, facts, writer, op = _hostile(tmp_path)
    with pytest.raises(GovernedApprovalError, match="expired"):
        _call(kernel, op, facts, writer,
              token=_token(op, ttl=60), now=EPOCH + timedelta(hours=2))
    assert len(writer.writes) == 0


def test_a_reused_approval_produces_no_second_effect(tmp_path):
    """Single-use. The second delivery of the SAME approved intent records no second decision, so
    it queues no second intent and cannot reach the adapter."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path)
    first = _call(kernel, op, facts, writer)
    assert first.state == "VERIFIED"

    second_writer = RecordingWriter(approved_fp=writer.approved_fp)
    second = _call(kernel, op, facts, second_writer)
    assert second.consumed is False
    assert second.cause == "DUPLICATE_CALLBACK"
    assert len(second_writer.writes) == 0, "a reused approval wrote a second effect"
    assert len(_events(store, gwr.QUEUED_EVENT)) == 1


def test_a_duplicate_callback_produces_exactly_one_external_attempt(tmp_path):
    """OBLIGATION 10, the delivery-duplication half: five identical deliveries of one approved
    intent produce exactly ONE external attempt."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path)
    writers = [writer] + [RecordingWriter(approved_fp=writer.approved_fp) for _ in range(4)]
    for w in writers:
        _call(kernel, op, facts, w)
    total = sum(len(w.writes) for w in writers)
    assert total == 1, f"{len(writers)} duplicate deliveries produced {total} external attempts"
    assert len(_events(store, "GovernedWriteCompleted")) == 1


def test_two_simultaneous_consumers_produce_exactly_one_external_attempt(tmp_path):
    """OBLIGATION 10, the concurrency half. The queued intent is consumed once: the consumer claim
    is atomic and tenant-scoped, and the ledger's unique commit-key index is the second barrier."""
    store, kernel, _c, _b, facts, seed_writer, op = _scene(tmp_path)

    # queue the intent through the real authenticated path, but do not let it be consumed yet:
    # a decision is recorded, then two consumers race for it.
    approval = governed_approval_for(
        op, actor_id=ACTOR, workspace_id=WORKSPACE, channel_id=CHANNEL,
        message_ts=MESSAGE_TS, issued_at=EPOCH)
    from freight_recon.governed_approval import record_governed_decision
    decision = record_governed_decision(store, approval, op, now=EPOCH)
    assert decision.recorded and decision.advanced

    store_b = make_store(tmp_path, op.tenant, name="p4route.db")
    kernel_b, _ = make_kernel(store_b, handle_key=HANDLE_KEY)
    writers = [RecordingWriter(approved_fp=seed_writer.approved_fp),
               RecordingWriter(approved_fp=seed_writer.approved_fp)]
    results: list = [None, None]
    barrier = threading.Barrier(2)

    def worker(i, k):
        barrier.wait()
        try:
            results[i] = gwr.consume_governed_write_intent(
                k, approval, op, facts=facts, accountable_owner=OWNER, now=EPOCH,
                writer=writers[i])
        except Exception as exc:  # noqa: BLE001 — a raised race loser is still "did nothing"
            results[i] = exc

    threads = [threading.Thread(target=worker, args=(i, k))
               for i, k in enumerate((kernel, kernel_b))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total = sum(len(w.writes) for w in writers)
    assert total == 1, f"two simultaneous consumers produced {total} external attempts"
    grants = store.conn.execute(
        "SELECT COUNT(*) c FROM effect_grants WHERE tenant = ? AND commit_key = ?",
        (op.tenant, op.effect_key())).fetchone()["c"]
    assert grants == 1, f"{grants} grants were minted for one logical effect"


def test_a_restart_before_the_claim_does_not_double_write(tmp_path):
    """Interrupted after the intent was queued but before anything was claimed: a fresh consumer
    resumes and writes exactly once."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path)
    approval = governed_approval_for(
        op, actor_id=ACTOR, workspace_id=WORKSPACE, channel_id=CHANNEL,
        message_ts=MESSAGE_TS, issued_at=EPOCH)
    from freight_recon.governed_approval import record_governed_decision
    record_governed_decision(store, approval, op, now=EPOCH)          # queued, then "crash"

    store_b = make_store(tmp_path, op.tenant, name="p4route.db")      # restart
    kernel_b, _ = make_kernel(store_b, handle_key=HANDLE_KEY)
    resumed = gwr.consume_governed_write_intent(
        kernel_b, approval, op, facts=facts, accountable_owner=OWNER, now=EPOCH, writer=writer)
    assert resumed.state == "VERIFIED"
    assert len(writer.writes) == 1


def test_a_restart_after_the_claim_cannot_blind_duplicate(tmp_path):
    """Interrupted AFTER the claim: the restarted consumer must not re-run the effect. The intent is
    already consumed, so no second attempt is possible."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path, mode="lost_ack")
    first = _call(kernel, op, facts, writer)
    assert first.state == "UNKNOWN_OUTCOME"
    assert len(writer.writes) == 1

    store_b = make_store(tmp_path, op.tenant, name="p4route.db")      # restart
    kernel_b, _ = make_kernel(store_b, handle_key=HANDLE_KEY)
    approval = governed_approval_for(
        op, actor_id=ACTOR, workspace_id=WORKSPACE, channel_id=CHANNEL,
        message_ts=MESSAGE_TS, issued_at=EPOCH)
    second_writer = RecordingWriter(approved_fp=writer.approved_fp)
    resumed = gwr.consume_governed_write_intent(
        kernel_b, approval, op, facts=facts, accountable_owner=OWNER, now=EPOCH,
        writer=second_writer)
    assert resumed.consumed is False and resumed.cause == "ALREADY_CONSUMED"
    assert len(second_writer.writes) == 0, "a restart blind-duplicated a claimed effect"


# ============================================================ UNKNOWN_OUTCOME


def test_external_success_with_a_lost_acknowledgement_becomes_unknown_never_failed(tmp_path):
    """The write LANDED and the acknowledgement was lost. That ambiguity must be preserved: never
    FAILED (which would assert non-occurrence we cannot prove), never a silent retry."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path, mode="lost_ack")
    outcome = _call(kernel, op, facts, writer)
    assert outcome.state == "UNKNOWN_OUTCOME"
    assert outcome.state != "FAILED"
    assert outcome.escalated is True
    assert len(writer.writes) == 1, "the write may have landed; the ambiguity must be preserved"
    grant = _row(store, "effect_grants", "tenant = ? AND grant_id = ?", (T_A, outcome.grant_id))
    assert grant["state"] == "UNKNOWN_OUTCOME"


def test_unknown_outcome_requires_reconciliation_and_never_auto_retries(tmp_path):
    """OBLIGATION 11. An ambiguous outcome is escalated to a NAMED human and owns a reconciliation
    obligation. Nothing retries it — not this route, not a timer."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path, mode="unknown")
    outcome = _call(kernel, op, facts, writer)
    assert outcome.state == "UNKNOWN_OUTCOME" and outcome.escalated

    escalations = _events(store, "GovernedWriteEscalated")
    assert len(escalations) == 1
    assert escalations[0]["payload"]["requires_reconciliation"] is True
    assert escalations[0]["payload"]["accountable_owner"] == OWNER
    assert escalations[0]["payload"]["approval_id"] == APPROVAL_ID

    # re-delivering the same approved intent does NOT retry the potentially-completed write
    retry_writer = RecordingWriter(approved_fp=writer.approved_fp)
    again = _call(kernel, op, facts, retry_writer)
    assert again.consumed is False
    assert len(retry_writer.writes) == 0, "an UNKNOWN outcome was automatically retried"
    grant = _row(store, "effect_grants", "tenant = ? AND grant_id = ?", (T_A, outcome.grant_id))
    assert grant["state"] == "UNKNOWN_OUTCOME"

    # it resolves ONLY by a named human decision (never a timer)
    assert eb.resolve_unknown_outcome(kernel, outcome.grant_id, to="VERIFIED",
                                      decision_ref="INC-42", established_by=OWNER)


def test_a_conflicting_readback_blocks_closure(tmp_path):
    """Readback verification is load-bearing: an observation that disagrees with the approved facts
    cannot close the effect as verified."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path, readback="conflict")
    outcome = _call(kernel, op, facts, writer)
    assert outcome.state == "UNKNOWN_OUTCOME"
    assert outcome.escalated


# ============================================================ DARKNESS


def test_the_route_performs_no_real_write_with_the_default_adapter(tmp_path):
    """SHIPS DARK. Driven end to end through production with NO writer injected, the effect reaches
    the default bounded adapter, which performs nothing and records a PROVEN non-occurrence."""
    store, kernel, _c, _b, facts, _writer, op = _scene(tmp_path)
    outcome = _call(kernel, op, facts, None)          # writer=None -> the dark default
    assert outcome.executed is True, "the chain must still be reachable — darkness is the adapter's"
    assert outcome.state == "FAILED"
    assert outcome.cause == "PROVEN_NON_OCCURRENCE"


def test_a_non_sandbox_operation_is_refused_before_any_claim(tmp_path):
    """A real target is refused BEFORE any claim, so no real external write is reachable even with a
    fully valid human approval and a genuine grant."""
    op = _op(sandbox=False)
    store, kernel, _c, _b, facts, writer, _ = _scene(tmp_path, op=op)
    # The boundary's darkness refusal is translated into an EXPLICIT governed outcome rather than
    # raised at the caller: a refusal is a recorded governed result with a named cause, not an
    # exception for the callback layer to interpret.
    outcome = _call(kernel, op, facts, writer)
    assert outcome.executed is False
    assert outcome.state == "REFUSED"
    assert outcome.cause == "BOUNDARY_REFUSED"
    assert "DARK" in outcome.reason
    assert len(writer.writes) == 0
    assert _events(store, "InvoiceWriteRefusedNotSandbox")
    assert _events(store, "GovernedWriteRefused")


def test_the_route_registers_no_credentialed_adapter():
    """The route imports no adapter, no browser session and no actuator, and has no fallback to the
    legacy OperatorAgent / CdpActuator path."""
    src = (ROOT / "src/freight_recon/governed_write_route.py").read_text(encoding="utf-8")
    assert "handle_governed_write_callback" in src, (
        "the governed route module does not contain its own entry point — the read is degenerate, "
        "so the absence assertions below would be vacuously true")
    # AST, never substrings: this module's own prose NAMES the actuators it must not reach, and a
    # substring guard would fire on its documentation instead of on its dependencies.
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imported.add(base)
            imported.update(f"{base}.{a.name}" for a in node.names)
    assert imported, "no imports parsed — the AST read is degenerate"
    joined = " ".join(imported)
    for forbidden in ("cdp_actuator", "cdp_session", "operator_agent", "operation_router",
                      "browser_use_adapter", "browser_use_write"):
        assert forbidden not in joined, f"the governed route imports {forbidden!r}"


# ============================================================ THE LEGACY ROUTE STAYS UNREACHABLE


def test_the_legacy_callback_to_actuator_route_remains_unreachable():
    """OBLIGATION 12. The callback layer must not import or construct an effect-capable actuator,
    and the governed handler must not be a way back to one."""
    src = (ROOT / "src/freight_recon/action_callback.py").read_text(encoding="utf-8")
    assert "_maybe_handle_governed_write_approval" in src, (
        "action_callback does not contain the governed handler — the read is degenerate, so the "
        "absence assertions below would be vacuously true")
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imported.add(base)
            imported.update(f"{base}.{a.name}" for a in node.names)
    joined = " ".join(imported)
    for forbidden in ("cdp_actuator", "cdp_session", "operator_agent", "browser_use_write"):
        assert forbidden not in joined, (
            f"action_callback imports {forbidden!r} — the deleted live-write route is reachable again")


def test_the_callback_server_entry_point_constructs_no_actuator():
    src = (ROOT / "scripts/run_action_callback_server.py").read_text(encoding="utf-8")
    assert "run_callback_server" in src, "degenerate read"
    for forbidden in ("CdpActuator(", "CdpBrowserSession(", "OperatorAgent(", "OperationRouter("):
        assert forbidden not in src, f"the entry point constructs {forbidden}"


# ============================================================ FALSE-GREEN DEFENCES (F-01 itself)


def _production_sources() -> dict[str, str]:
    """Every production module, read once. The population is ASSERTED non-empty by the callers."""
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted((ROOT / "src/freight_recon").glob("*.py"))}


def test_build_checkpoint_approval_has_a_real_production_caller():
    """THIS TEST MUST FAIL IF THE DECISION-TO-CHECKPOINT CALLER IS REMOVED.

    `build_checkpoint_approval` is the ONE join between the authenticated decision and the execution
    half. The review found it with zero callers. A CALL node — not an import, not a mention in a
    comment or docstring — must exist in production code outside its own defining module.
    """
    sources = _production_sources()
    assert len(sources) > 50, f"degenerate source population: {len(sources)} modules"
    assert "governed_approval.py" in sources, "the defining module is missing — degenerate read"

    callers = []
    for name, src in sources.items():
        if name == "governed_approval.py":
            continue
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call):
                func = node.func
                called = (func.id if isinstance(func, ast.Name)
                          else func.attr if isinstance(func, ast.Attribute) else "")
                if called == "build_checkpoint_approval":
                    callers.append(name)
    assert callers, (
        "build_checkpoint_approval has NO production caller. The authenticated decision and the "
        "effect execution do not share one authority lineage — this is finding F-01, unremediated.")
    assert "governed_write_route.py" in callers, callers


def test_the_queued_write_intent_has_a_real_production_consumer():
    """THIS TEST MUST FAIL IF THE QUEUED-INTENT CONSUMER IS REMOVED.

    `GovernedWriteIntentQueued` was written and never read. A production module other than the
    writer must READ it back, and that reader must be reachable from the governed route.
    """
    sources = _production_sources()
    assert "governed_approval.py" in sources, "degenerate read"
    assert gwr.QUEUED_EVENT in sources["governed_approval.py"], (
        "the producer no longer emits the queued event — the corpus is degenerate")

    consumers = [name for name, src in sources.items()
                 if name != "governed_approval.py" and gwr.QUEUED_EVENT in src]
    assert consumers, (
        f"{gwr.QUEUED_EVENT} has no production consumer — the 'pipeline advance' terminates in an "
        "unread log event, which is finding F-01, unremediated.")
    assert "governed_write_route.py" in consumers, consumers

    # and the consumer is genuinely wired to the queue's READ side, not merely naming the constant
    assert "queued_write_intents" in sources["governed_write_route.py"]
    assert "security_events" in sources["governed_write_route.py"]


def test_the_authenticated_callback_path_reaches_the_governed_route():
    """THIS TEST MUST FAIL IF THE PRODUCTION CALL SITE IS REMOVED. The route must be reachable from
    the authenticated callback handler, not merely importable."""
    src = (ROOT / "src/freight_recon/action_callback.py").read_text(encoding="utf-8")
    assert "verify_slack_signature" in src, "degenerate read"
    assert "governed_write_route" in src, (
        "the authenticated callback path does not reach the governed write route")
    assert "handle_governed_write_callback" in src, (
        "the callback path imports the route module but never calls its entry point — a "
        "wrapper-only import is exactly what the review refused to accept")
    assert "_maybe_handle_governed_write_approval" in src


def test_identity_substitution_is_refused_at_the_consumption_boundary(tmp_path):
    """THIS TEST MUST FAIL IF APPROVAL IDENTITY IS SUBSTITUTED. The consumer re-proves the lineage
    itself, so even a caller that bypasses the signed envelope entirely cannot pair an approval with
    a foreign operation."""
    store, kernel, _c, _b, facts, writer, op = _scene(tmp_path)
    foreign = governed_approval_for(
        _op(approval_id="ap-1", work_item_id="WI-OTHER"),
        actor_id="owner:rasheed", workspace_id=WORKSPACE, channel_id=CHANNEL,
        message_ts=MESSAGE_TS, issued_at=EPOCH)
    with pytest.raises(gwr.GovernedWriteRouteError, match="mismatch"):
        gwr.consume_governed_write_intent(
            kernel, foreign, op, facts=facts, accountable_owner=OWNER, now=EPOCH, writer=writer)
    assert len(writer.writes) == 0
    assert _events(store, "GovernedWriteIntentRefused")


@pytest.mark.parametrize("field,value", [
    ("approval_id", "ap-1"),
    ("work_item_id", "WI-OTHER"),
    ("pipeline_instance_id", "PI-OTHER"),
    ("capability_id", "A4.pay_carrier"),
    ("idempotency_key", "idem-OTHER"),
    ("approval_revision", 3),
])
def test_every_binding_is_load_bearing_at_the_consumption_boundary(field, value):
    """Each binding refuses INDEPENDENTLY. A pure predicate, so the population is exact and the
    corpus cannot be empty: the matching pair must return "" or the negatives prove nothing."""
    op = _op()
    good = governed_approval_for(op, actor_id=ACTOR, workspace_id=WORKSPACE, channel_id=CHANNEL,
                                 message_ts=MESSAGE_TS, issued_at=EPOCH)
    assert gwr.approval_operation_mismatch(good, op, server_tenant=op.tenant) == "", (
        "the MATCHING pair is reported as a mismatch — the predicate is degenerate and every "
        "negative below would pass vacuously")
    other = governed_approval_for(_op(**{field: value}), actor_id=ACTOR, workspace_id=WORKSPACE,
                                  channel_id=CHANNEL, message_ts=MESSAGE_TS, issued_at=EPOCH)
    assert gwr.approval_operation_mismatch(other, op, server_tenant=op.tenant) != "", (
        f"substituting {field!r} was NOT refused")
