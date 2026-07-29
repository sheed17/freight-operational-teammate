"""P4 EP-1 — THE GOVERNED INVOICE-WRITE ROUTE, end to end and under attack (R-07 scope).

The typed operation is routed through the whole adapter algorithm — Work Item / Pipeline identity
-> policy -> recorded approval -> checkpoint -> witness -> grant -> atomic claim -> bounded
AdapterOperation -> adapter -> readback -> outcome -> closure — and every concurrency, replay,
UNKNOWN_OUTCOME and tenant/capability/operation attack the completion boundary names is proved to
fail closed. The capability is DARK throughout: with the default adapter no real write happens, and a
non-sandbox operation is refused before any claim.

The bounded writer is a scripted double whose call log is the negative oracle — never the real
browser. A double written from the implementation would be a false pass (L-9), so it is driven by
the frozen outcome vocabulary (ATTEMPTED / PREFLIGHT_REJECTED / OUTCOME_UNKNOWN) and a scripted
readback (match / conflict / blind), exactly like phase4_kit's FakeTmsAdapter.
"""

from __future__ import annotations

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
from freight_recon import governed_approval as gov  # noqa: E402
from freight_recon.checkpoint import (  # noqa: E402
    CheckpointInputs,
    CheckpointRequest,
    run_checkpoint,
)
from freight_recon.freight_operations import FreightOperationClass, InvoiceWriteOperation  # noqa: E402
from phase3_kit import (  # noqa: E402
    EPOCH,
    T_A,
    T_B,
    Clock,
    live_reader,
    make_approval,
    make_facts,
    make_kernel,
    make_store,
)
from phase4_kit import approved_fingerprint  # noqa: E402

HANDLE_KEY = b"p4-invoice-write-shared-handle-key"


def _op(**overrides) -> InvoiceWriteOperation:
    base = dict(
        tenant=T_A, work_item_id="WI-77", pipeline_instance_id="PI-77",
        load_id="load:4471", invoice_ref="INV-req-9", target_integration="tms:truckingoffice",
        target_account="acct-broker", operation_class=FreightOperationClass.RAISE_INVOICE,
        approved_fields={"customer": "Echo", "amount": "2850.00", "load_ref": "4471"},
        approval_id="appr-9", approval_revision=0, idempotency_key="idem-9",
        capability_id="A4.raise_invoice", sandbox=True, base_url="http://localhost:9111",
    )
    base.update(overrides)
    return InvoiceWriteOperation(**base)


def _mint(tmp_path, op, *, name="p4inv.db", handle_key=HANDLE_KEY, clock=None):
    """Mint a genuine grant+witness+handle for THIS typed operation's canonical effect, WITHOUT
    claiming (the boundary claims). The grant is minted from op.logical_effect(), so the confusion
    check binds the operation to its grant by construction."""
    store = make_store(tmp_path, op.tenant, name=name)
    kernel, clk = make_kernel(store, handle_key=handle_key, clock=clock)
    effect = op.logical_effect()
    facts = make_facts(entity_ref=op.load_id)
    versions = {op.load_id: 17}
    approval = make_approval(effect, facts, versions, clk)
    world = {"facts": dict(facts), "projection": {"status": "DELIVERED"}, "versions": dict(versions)}
    inputs = CheckpointInputs(
        material_facts_reader=live_reader(lambda: dict(world["facts"])),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=live_reader(lambda: dict(world["projection"])),
        entity_version_reader=live_reader(lambda: dict(world["versions"])),
        approval=approval)
    request = CheckpointRequest(effect=effect, actor="pipeline", accountable_owner="owner:rasheed",
                                target_entity_ref=op.load_id)
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, f"mint failed: {outcome}"
    fp = approved_fingerprint(store, effect.key())
    return store, kernel, clk, outcome.handle, fp


class FakeInvoiceWriter:
    """The scripted bounded writer. Records every call; NEVER decides VERIFIED/FAILED. It has NO
    reference to the kernel, the store, a grant or a witness — it cannot mint or alter authority."""

    def __init__(self, *, approved_fp: str, mode: str = "ok", readback: str = "match") -> None:
        self.approved_fp = approved_fp
        self.mode = mode
        self.readback_mode = readback
        self.calls: list[tuple[str, str]] = []

    def write(self, op) -> bw.BoundedWriteResult:
        if self.mode == "preflight_reject":
            return bw.BoundedWriteResult(outcome="PREFLIGHT_REJECTED",
                                         proof="TMS pre-flight: invoice already exists; no write issued")
        if self.mode == "unknown":
            return bw.BoundedWriteResult(outcome="OUTCOME_UNKNOWN",
                                         detail="browser session dropped mid-submit", exposure="rendered")
        if self.mode == "lost_ack":
            # the write LANDED, then the acknowledgement was lost (a generic crash after submit). The
            # call is logged BEFORE the raise so the ambiguity is real for the negative oracle.
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


def _grant_state(store, grant_id: str) -> str:
    row = store.conn.execute(
        "SELECT state FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (store.tenant, grant_id)).fetchone()
    return row["state"] if row else "ABSENT"


def _security(store, event_type: str):
    return [e for e in store.security_events() if e["event_type"] == event_type]


# ============================================================ the execution order, end to end

def test_the_execution_half_verifies_given_an_already_minted_grant(tmp_path):
    """THE EXECUTION HALF ONLY, given a grant this test minted itself.

    SCOPE, STATED HONESTLY — this test does NOT prove the governed approval chain. The independent
    hostile review (F-01) found that the test formerly standing here was named
    `…executes_the_full_order…` and claimed "approval -> checkpoint -> witness -> grant -> claim ->
    … -> closure" while it did two unrelated things against one store: it recorded a governed
    approval (`appr-9` / `U-OWNER`) and it separately executed a grant minted by `phase3_kit`'s
    fixture approval (`ap-1` / `owner:rasheed`). The two halves shared no identifier, no actor and
    no fingerprint, so the name materially over-read the evidence.

    What this test proves is real and worth keeping: given a genuine claimable grant, the boundary
    performs claim -> bounded op -> adapter -> readback -> VERIFIED with exactly one external
    attempt. The grant here is a FIXTURE, and its identity is deliberately unrelated.

    THE ACTUAL END-TO-END CHAIN — one authenticated decision whose approval identity reaches the
    checkpoint, the witness, the grant and the adapter — is proved in
    `test_p4_governed_write_route.py`, which enters through the production entry point and mints no
    authority of its own.
    """
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)

    writer = FakeInvoiceWriter(approved_fp=fp, mode="ok", readback="match")
    result = eb.execute_invoice_write(kernel, handle, op, writer=writer)

    assert result.state == "VERIFIED"
    assert result.verification_outcome is eb.VerificationOutcome.VERIFIED_SUCCESS
    assert len(writer.writes) == 1, "the world must be touched exactly once"
    assert _grant_state(store, handle.grant_id) == "VERIFIED"
    assert _security(store, "EffectAttempted"), "EffectAttempted must be recorded before the call"
    # The fixture grant's authority is NOT the governed approval's. Asserted, so the disconnection
    # this test deliberately retains can never again be mistaken for an end-to-end proof.
    grant = store.conn.execute(
        "SELECT approval_id FROM effect_grants WHERE tenant = ? AND grant_id = ?",
        (store.tenant, handle.grant_id)).fetchone()
    assert grant["approval_id"] == "ap-1", (
        "this test's grant is a fixture; if it ever carries the governed approval's identity, the "
        "end-to-end claim belongs in test_p4_governed_write_route.py, not here")


def test_the_decision_half_advances_the_pipeline_without_touching_an_actuator(tmp_path):
    """THE DECISION HALF ONLY: a recorded governed decision queues a write intent and touches no
    adapter. Its CONSUMPTION — and the identity lineage from here into the grant — is proved in
    `test_p4_governed_write_route.py`."""
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    approval = gov.GovernedApproval(
        approval_id=op.approval_id, tenant=op.tenant, actor_id="U-OWNER", workspace_id="W",
        channel_id="C", message_ts="1.1", work_item_id=op.work_item_id,
        pipeline_instance_id=op.pipeline_instance_id, operation_class=op.operation_class.value,
        payload_hash=op.payload_hash(), approval_revision=op.approval_revision,
        capability_id=op.capability_id, idempotency_key=op.idempotency_key,
        issued_at=EPOCH.timestamp(), expires_at=EPOCH.timestamp() + 3600)
    decision = gov.record_governed_decision(store, approval, op, now=EPOCH)
    assert decision.recorded and decision.advanced
    queued = _security(store, "GovernedWriteIntentQueued")
    assert queued, "the pipeline did not advance"
    assert queued[0]["payload"]["approval_id"] == op.approval_id


# ============================================================ duplicate callbacks / one effect

def test_duplicate_execution_on_one_grant_produces_one_effect(tmp_path):
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    w1 = FakeInvoiceWriter(approved_fp=fp)
    w2 = FakeInvoiceWriter(approved_fp=fp)
    first = eb.execute_invoice_write(kernel, handle, op, writer=w1)
    second = eb.execute_invoice_write(kernel, handle, op, writer=w2)
    assert first.state == "VERIFIED"
    assert second.claimed is False and second.state == "REFUSED"
    assert second.cause.startswith("ALREADY_")
    assert len(w1.writes) == 1 and len(w2.writes) == 0, "a duplicate callback wrote a second effect"


# ============================================================ two workers cannot both claim

def test_two_workers_cannot_both_claim_the_same_effect(tmp_path):
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    # a second kernel on the SAME db file, sharing the handle key so the signature verifies
    store_b = make_store(tmp_path, op.tenant, name="p4inv.db")
    kernel_b, _ = make_kernel(store_b, handle_key=HANDLE_KEY)
    writers = [FakeInvoiceWriter(approved_fp=fp), FakeInvoiceWriter(approved_fp=fp)]
    results: list = [None, None]
    barrier = threading.Barrier(2)

    def worker(i, k):
        barrier.wait()
        try:
            results[i] = eb.execute_invoice_write(k, handle, op, writer=writers[i])
        except Exception as exc:  # noqa: BLE001 — a raised race loser is still "did nothing"
            results[i] = exc

    threads = [threading.Thread(target=worker, args=(i, k)) for i, k in enumerate((kernel, kernel_b))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_writes = sum(len(w.writes) for w in writers)
    assert total_writes == 1, f"exactly one worker may write, got {total_writes}"


# ============================================================ resumable before claim

def test_interruption_before_claim_is_safely_resumable(tmp_path):
    """A crash after mint but before claim leaves a GRANTED grant and nothing touched. A fresh
    execute later claims it and writes exactly once — resuming, not double-writing."""
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    assert _grant_state(store, handle.grant_id) == "GRANTED"  # interrupted before claim
    writer = FakeInvoiceWriter(approved_fp=fp)
    result = eb.execute_invoice_write(kernel, handle, op, writer=writer)  # resume
    assert result.state == "VERIFIED"
    assert len(writer.writes) == 1


# ============================================================ no blind duplicate after claim

def test_interruption_after_claim_does_not_allow_a_blind_duplicate(tmp_path):
    """Once claimed (here: attempted and left ambiguous), the SAME grant cannot be re-run: a second
    execute is refused, so an interrupted-after-claim run never blind-duplicates the effect."""
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    w1 = FakeInvoiceWriter(approved_fp=fp, mode="lost_ack")
    first = eb.execute_invoice_write(kernel, handle, op, writer=w1)
    assert first.state == "UNKNOWN_OUTCOME"
    w2 = FakeInvoiceWriter(approved_fp=fp)
    second = eb.execute_invoice_write(kernel, handle, op, writer=w2)
    assert second.claimed is False and second.cause.startswith("ALREADY_")
    assert len(w2.writes) == 0, "a claimed-then-ambiguous grant was blind-retried"


# ============================================================ lost ack -> UNKNOWN, never FAILED

def test_write_then_lost_ack_becomes_unknown_never_failed(tmp_path):
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    writer = FakeInvoiceWriter(approved_fp=fp, mode="lost_ack")
    result = eb.execute_invoice_write(kernel, handle, op, writer=writer)
    assert result.state == "UNKNOWN_OUTCOME"
    assert result.state != "FAILED"
    assert _grant_state(store, handle.grant_id) == "UNKNOWN_OUTCOME"
    assert len(writer.writes) == 1, "the write may have landed; the ambiguity must be preserved"


# ============================================================ UNKNOWN does not auto-retry

def test_unknown_outcome_does_not_auto_retry(tmp_path):
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    w1 = FakeInvoiceWriter(approved_fp=fp, mode="unknown")
    first = eb.execute_invoice_write(kernel, handle, op, writer=w1)
    assert first.state == "UNKNOWN_OUTCOME"
    # a re-execute does NOT silently retry: the grant is UNKNOWN_OUTCOME, not GRANTED.
    w2 = FakeInvoiceWriter(approved_fp=fp, mode="ok")
    second = eb.execute_invoice_write(kernel, handle, op, writer=w2)
    assert second.claimed is False and len(w2.writes) == 0
    assert _grant_state(store, handle.grant_id) == "UNKNOWN_OUTCOME"
    # it resolves ONLY by a named human decision (never a timer)
    resolved = eb.resolve_unknown_outcome(
        kernel, handle.grant_id, to="VERIFIED", decision_ref="INC-42",
        established_by="owner:rasheed")
    assert resolved and _grant_state(store, handle.grant_id) == "VERIFIED"


# ============================================================ stale callback cannot reopen closed work

def test_a_stale_callback_cannot_reopen_completed_work(tmp_path):
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    done = eb.execute_invoice_write(kernel, handle, op, writer=FakeInvoiceWriter(approved_fp=fp))
    assert done.state == "VERIFIED"
    # a stale retry of the same signed callback: refused, and the completed grant is untouched
    stale_writer = FakeInvoiceWriter(approved_fp=fp)
    stale = eb.execute_invoice_write(kernel, handle, op, writer=stale_writer)
    assert stale.claimed is False and stale.cause.startswith("ALREADY_")
    assert len(stale_writer.writes) == 0
    assert _grant_state(store, handle.grant_id) == "VERIFIED"


# ============================================================ readback disagreement blocks closure

def test_readback_disagreement_prevents_ordinary_closure(tmp_path):
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    writer = FakeInvoiceWriter(approved_fp=fp, mode="ok", readback="conflict")
    result = eb.execute_invoice_write(kernel, handle, op, writer=writer)
    assert result.state == "UNKNOWN_OUTCOME"
    assert result.verification_outcome is eb.VerificationOutcome.OBSERVATION_CONFLICTING
    assert _grant_state(store, handle.grant_id) == "UNKNOWN_OUTCOME"


def test_blind_readback_is_unavailable_never_verified(tmp_path):
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    writer = FakeInvoiceWriter(approved_fp=fp, mode="ok", readback="blind")
    result = eb.execute_invoice_write(kernel, handle, op, writer=writer)
    assert result.state == "UNKNOWN_OUTCOME"
    assert result.verification_outcome is eb.VerificationOutcome.OBSERVATION_UNAVAILABLE


# ============================================================ tenant / operation / capability mismatch

def test_a_cross_tenant_handle_fails_closed(tmp_path):
    op = _op(tenant=T_A)
    store_a, kernel_a, clock, handle_a, fp = _mint(tmp_path, op, name="a.db")
    store_b = make_store(tmp_path, T_B, name="b.db")
    kernel_b, _ = make_kernel(store_b, handle_key=HANDLE_KEY)
    writer = FakeInvoiceWriter(approved_fp=fp)
    with pytest.raises(eb.BoundaryError):
        eb.execute_invoice_write(kernel_b, handle_a, op, writer=writer)
    assert len(writer.writes) == 0
    assert [e for e in store_b.security_events() if e["event_type"] == "CrossTenantAccessAttempted"]
    assert kernel_b.brakes.platform_status().state == "ACTIVE", "the GLOBAL brake must engage"


def test_an_operation_mismatch_fails_the_confusion_check(tmp_path):
    """A grant minted for one load, presented with a typed operation for a DIFFERENT load, is a
    confused deputy: the claim CAS refuses on the confusion check and nothing is written."""
    minted = _op(load_id="load:4471")
    store, kernel, clock, handle, fp = _mint(tmp_path, minted)
    substituted = _op(load_id="load:9999")   # a different target smuggled onto the same handle
    writer = FakeInvoiceWriter(approved_fp=fp)
    result = eb.execute_invoice_write(kernel, handle, substituted, writer=writer)
    assert result.claimed is False and result.cause == "CONFUSED_DEPUTY"
    assert len(writer.writes) == 0


def test_the_bounded_perform_refuses_a_capability_it_was_not_handed(tmp_path):
    """capability mismatch: the adapter's perform is the ONE invocation site, and it refuses
    anything that is not a genuine, boundary-minted capability. A raw object cannot execute a write —
    this is what makes 'call the adapter directly, with no claim' impossible."""
    op = _op()
    operation = eb.build_invoice_write_operation(op, writer=FakeInvoiceWriter(approved_fp="x"))
    from freight_recon.checkpoint import ClaimParams
    params = ClaimParams(tenant=op.tenant, action_class="raise_invoice",
                         target_system=op.target_integration, target_resource_id=op.load_id,
                         target_operation="raise_invoice")
    with pytest.raises(eb.OrphanEffectDetected):
        operation.perform(object(), params)   # not a capability -> no write is possible


# ============================================================ the effect-capable adapter mints nothing

def test_the_effect_capable_adapter_cannot_construct_authority():
    """The adapter side cannot mint, refresh or alter a grant/witness/claim/capability. The capability
    type has NO public constructor (the type analogue of the checkpoint's unconstructable pass), and
    the bounded writer module imports no kernel authority to reach one."""
    with pytest.raises(eb.BoundaryError):
        eb.ExecutionCapability(tenant="t", grant_id="g", commit_key="k", op_id="A4.raise_invoice")
    src = (ROOT / "src/freight_recon/browser_use_write.py").read_text(encoding="utf-8")
    # POPULATION PROOF. The loop below is a negative over a file read: an empty
    # or truncated read satisfies every clause while proving nothing about the
    # adapter. SandboxInvoiceWriteAdapter is the bounded writer this module
    # exists to hold, so its absence means the read failed, not that the adapter
    # mints no authority.
    assert "SandboxInvoiceWriteAdapter" in src, (
        "browser_use_write does not contain SandboxInvoiceWriteAdapter - the read is degenerate, "
        "so the minting assertions below would be vacuously true"
    )
    for forbidden in ("_mint_capability", "claim_grant_cas", "run_checkpoint", "mint_grant"):
        assert forbidden not in src, f"the write adapter references authority minting: {forbidden!r}"


# ============================================================ DARKNESS

def test_a_non_sandbox_operation_is_refused_before_any_claim(tmp_path):
    op = _op(sandbox=False)
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    writer = FakeInvoiceWriter(approved_fp=fp)
    with pytest.raises(eb.BoundaryError):
        eb.execute_invoice_write(kernel, handle, op, writer=writer)
    assert len(writer.writes) == 0
    assert _grant_state(store, handle.grant_id) == "GRANTED", "a non-sandbox op must not claim"
    assert _security(store, "InvoiceWriteRefusedNotSandbox")


def test_the_default_writer_performs_no_real_write(tmp_path):
    """Ships dark: with the DEFAULT adapter (no sandbox runner wired), a fully-authorized, claimed
    write performs nothing and is recorded as a PROVEN non-occurrence — never a laundered success."""
    op = _op()
    store, kernel, clock, handle, fp = _mint(tmp_path, op)
    result = eb.execute_invoice_write(kernel, handle, op)   # default SandboxInvoiceWriteAdapter
    assert result.state == "FAILED"
    assert result.cause == "PROVEN_NON_OCCURRENCE"
    assert result.touched_world is False
    assert "dark" in result.failure_proof.lower()


def test_the_default_writer_refuses_a_real_host(tmp_path):
    """Even wired with a runner, a real (non-loopback) host is refused: no real external write."""
    op = _op(base_url="https://secure.truckingoffice.com")

    class _Runner:
        async def run(self, task, *, allowed_domains, headless):  # pragma: no cover - never reached
            raise AssertionError("a real host must be refused before the runner is called")

    adapter = bw.SandboxInvoiceWriteAdapter(runner=_Runner())
    with pytest.raises(bw.SandboxOnlyWriteRefused):
        adapter.write(op)


# ============================================================ removing the claim path FAILS acceptance

def test_removing_the_checkpoint_grant_claim_path_makes_the_write_impossible(tmp_path):
    """The acceptance depends on the claim: bypass it and no write is possible. Presenting the
    bounded operation without a claimed grant (no boundary-minted capability) cannot touch the
    world — proving the checkpoint/grant/claim path is load-bearing, not decorative."""
    op = _op()
    writer = FakeInvoiceWriter(approved_fp="x")
    operation = eb.build_invoice_write_operation(op, writer=writer)
    from freight_recon.checkpoint import ClaimParams
    params = ClaimParams(tenant=op.tenant, action_class="raise_invoice",
                         target_system=op.target_integration, target_resource_id=op.load_id,
                         target_operation="raise_invoice")
    # No claim happened, so there is no genuine capability to present -> the write is refused.
    with pytest.raises(eb.OrphanEffectDetected):
        operation.perform(object(), params)
    assert len(writer.writes) == 0
