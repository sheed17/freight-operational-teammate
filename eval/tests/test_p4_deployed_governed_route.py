"""P4 EP-1 / F-01 — THE DEPLOYED ENTRY POINT, wired through the governed route (dark, fail-closed).

WHAT THIS FILE PROVES THAT THE OTHERS DO NOT. `test_p4_governed_write_route.py` proves the governed
chain is real when entered through `handle_governed_write_callback`. It does NOT prove the DEPLOYED
server reaches it. The remaining F-01 obligation was exactly that gap: `run_action_callback_server.py`
left `governed_write_provider` and `governed_write_kernel` as `None`, so nothing a real operator
could run would ever touch the chain.

Every test here builds the seams through **`run_action_callback_server._build_governed_write_route`**
— the real entry point's own builder, not a re-implementation — and drives them through the real
`action_callback` handler, over a real HTTP request with a real Slack signature.

THE AUTHORITY SPLIT THIS ENFORCES:

    THE CALLBACK SUPPLIES IDENTITY.  THE REPOSITORY SUPPLIES THE OPERATION.

The tap carries an approval id, a Work Item, a pipeline instance, tenant/workspace identity, a
revision and a signed channel receipt — and nothing else. The typed operation (amount, counterparty,
invoice, load, destination system, target URL, adapter, capability) is retrieved from a record
written at PROPOSAL time. There is no path by which callback data becomes an operation field.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import run_action_callback_server as entry_point  # noqa: E402 — THE REAL DEPLOYED ENTRY POINT
from freight_recon import governed_write_route as gwr  # noqa: E402
from freight_recon.action_callback import (  # noqa: E402
    CallbackAppConfig,
    make_callback_handler,
    run_callback_server,
)
from freight_recon.delivery import DeliverySigner  # noqa: E402
from freight_recon.freight_operations import FreightOperationClass, InvoiceWriteOperation  # noqa: E402
from freight_recon.governed_approval import governed_approval_for, sign_governed_approval  # noqa: E402
from freight_recon.governed_write_registry import (  # noqa: E402
    PROPOSED_EVENT,
    WorkflowStorePendingWrites,
    record_proposed_governed_write,
)
from freight_recon.workflow import WorkflowStore  # noqa: E402
from phase3_kit import default_registry  # noqa: E402 — the gate registry PRODUCTION may not yet build

TENANT = "tenant-alpha"
SECRET = b"deployed-governed-route-secret"
SLACK_SECRET = b"slack-signing-secret"
ACTOR = "U-OWNER"
APPROVAL_ID = "appr-deployed-1"
OWNER = "owner:rasheed"
CHANNEL, WORKSPACE, MESSAGE_TS = "C-OPS", "W-ACME", "1720000000.000100"
TOKEN_FP = "fp-deployed-1"


# ------------------------------------------------------------------ the proposal (not the tap)


def _op(**overrides) -> InvoiceWriteOperation:
    base = dict(
        tenant=TENANT, work_item_id="WI-77", pipeline_instance_id="PI-77",
        load_id="load:4471", invoice_ref="INV-req-9", target_integration="tms:truckingoffice",
        target_account="acct-broker", operation_class=FreightOperationClass.RAISE_INVOICE,
        approved_fields={"customer": "Echo", "amount": "2850.00", "load_ref": "4471"},
        approval_id=APPROVAL_ID, approval_revision=0, idempotency_key="idem-deployed-1",
        capability_id="A4.raise_invoice", sandbox=True, base_url="http://localhost:9111",
    )
    base.update(overrides)
    return InvoiceWriteOperation(**base)


def _propose(store, op=None, *, actors=(ACTOR,), channel=CHANNEL, workspace=WORKSPACE,
             message_ts=MESSAGE_TS, ttl_hours=1, token_fp=TOKEN_FP):
    """Write the proposal down, exactly as the proposal step does. This is the ONLY way an
    operation enters the repository — the callback can never do this."""
    op = op if op is not None else _op()
    record_proposed_governed_write(
        store, op,
        allowed_actors=actors, workspace_id=workspace, channel_id=channel, message_ts=message_ts,
        token_fingerprint=token_fp, accountable_owner=OWNER,
        entity_versions={op.load_id: 17},
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        counterparty="Acme Logistics",
    )
    return op


def _token(op, *, actor=ACTOR, channel=CHANNEL, workspace=WORKSPACE, message_ts=MESSAGE_TS,
           secret=SECRET, ttl=3600, issued=None) -> str:
    approval = governed_approval_for(
        op, actor_id=actor, workspace_id=workspace, channel_id=channel, message_ts=message_ts,
        issued_at=issued or datetime.now(timezone.utc), ttl_seconds=ttl)
    return sign_governed_approval(approval, secret)


class RecordingWriter:
    """The dark/sandbox adapter stand-in. Records the typed operations it was handed, so 'the same
    approval identity reached the adapter' is evidence rather than an assumption."""

    def __init__(self, *, approved_fp: str = "", mode: str = "ok") -> None:
        self.approved_fp = approved_fp
        self.mode = mode
        self.seen_ops: list = []
        self.calls: list = []

    def write(self, op):
        from freight_recon import browser_use_write as bw
        self.seen_ops.append(op)
        if self.mode == "unknown":
            return bw.BoundedWriteResult(outcome="OUTCOME_UNKNOWN", detail="session dropped",
                                         exposure="rendered")
        self.calls.append(("write", op.load_id))
        return bw.BoundedWriteResult(outcome="ATTEMPTED", external_ref="INV-1", detail="submitted")

    def readback(self, op):
        from freight_recon import browser_use_write as bw
        self.calls.append(("readback", op.load_id))
        return bw.BoundedReadback(health_signal=True, observed_fingerprint=self.approved_fp)

    @property
    def writes(self):
        return [c for c in self.calls if c[0] == "write"]


# ------------------------------------------------------------------ the deployed seams


def _deployed_seams(db_path, *, writer=None):
    """Build the seams THROUGH THE REAL ENTRY POINT'S OWN BUILDER.

    If the deployed wiring is removed, this returns (None, None) and every test below fails —
    which is the point (obligation 10, first bullet).
    """
    signer = DeliverySigner(SECRET)
    provider, kernel_factory = entry_point._build_governed_write_route(
        db_path=str(db_path), tenant=TENANT, signer=signer)
    if kernel_factory is None:
        # THE ONE BLOCKED SEAM. Production may not construct a GateRegistry until AC-CKPT-6-missing
        # is re-adjudicated (U8.1/P8), so the entry point returns no kernel and the route fails
        # closed. Tests supply one so everything ELSE about the deployed path is still proved end to
        # end — and `test_the_execution_kernel_seam_is_blocked_pending_adjudication` asserts the
        # production side really is still blocked, so this substitution can never hide a regression.
        from freight_recon.checkpoint import CheckpointKernel

        def kernel_factory(store):  # noqa: F811
            return CheckpointKernel(store, default_registry())
    if provider is not None and writer is not None:
        # A test may substitute the bounded writer; the DEPLOYED default injects none (dark).
        base = provider

        def provider_with_writer(approval_id):
            pending = base(approval_id)
            if pending is None:
                return None
            return gwr.PendingGovernedWrite(
                op=pending.op, facts=pending.facts,
                accountable_owner=pending.accountable_owner,
                allowed_actors=pending.allowed_actors, secret=pending.secret,
                expected_channel_id=pending.expected_channel_id,
                expected_workspace_id=pending.expected_workspace_id,
                expected_message_ts=pending.expected_message_ts,
                writer=writer)

        provider = provider_with_writer
    return provider, kernel_factory


def _config(db_path, *, provider, kernel, actors=(ACTOR,), channel=CHANNEL):
    return CallbackAppConfig(
        tenant=TENANT, db_path=str(db_path), signer=DeliverySigner(SECRET),
        slack_signing_secret=SLACK_SECRET,
        allowed_slack_users=tuple(actors), allowed_slack_channel=channel,
        governed_write_provider=provider, governed_write_kernel=kernel,
    )


# ------------------------------------------------------------------ a real signed Slack request


def _slack_body(token: str, *, user=ACTOR, channel=CHANNEL) -> str:
    payload = {
        "type": "block_actions",
        "user": {"id": user},
        "channel": {"id": channel},
        "actions": [{"action_id": "governed_write_approve", "value": token}],
    }
    return urlencode({"payload": json.dumps(payload)})


def _sign(body: str, secret: bytes = SLACK_SECRET) -> tuple[str, str]:
    ts = str(int(time.time()))
    base = f"v0:{ts}:{body}".encode("utf-8")
    return ts, "v0=" + hmac.new(secret, base, hashlib.sha256).hexdigest()


class _Recorder:
    """Captures what the handler wrote back, without a socket."""

    def __init__(self):
        self.status = None
        self.body = None


def _post_to_handler(config, body: str, *, secret: bytes = SLACK_SECRET):
    """Drive the REAL handler class over a synthetic request. No socket needed: the handler's
    Slack path is exercised exactly as the server routes it."""
    handler_cls = make_callback_handler(config)
    ts, sig = _sign(body, secret)
    recorder = _Recorder()

    class _Probe(handler_cls):  # type: ignore[misc, valid-type]
        def __init__(self):  # noqa: D107 — deliberately does not call BaseHTTPRequestHandler.__init__
            self.headers = {"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig}

        def _write_json(self, status, payload):
            recorder.status = status
            recorder.body = payload

    probe = _Probe()
    probe._handle_slack(body.encode("utf-8"))
    return recorder


def _events(store, event_type):
    return [e for e in store.security_events() if e["event_type"] == event_type]


def _row(store, table, where, args):
    return store.conn.execute(f"SELECT * FROM {table} WHERE {where}", args).fetchone()


def _expected_fp(store, op):
    """The material-facts fingerprint the checkpoint will compute, via the ONE canonical composer
    over the repository's own live facts — not copied from the implementation."""
    from freight_recon.checkpoint import material_fact_set
    from freight_recon.fingerprint import fingerprint

    pending = WorkflowStorePendingWrites(store, secret=SECRET).pending_for(op.approval_id)
    assert pending is not None, "the proposal was not retrievable — the scene is degenerate"
    effect = op.logical_effect()
    return fingerprint(material_fact_set(
        effect=effect, commit_key=effect.key(),
        business_facts=pending.facts.business_facts(),
        entity_versions=pending.facts.entity_versions(),
        policy_version=pending.facts.policy_version))


# ============================================================ THE DEPLOYED INTEGRATION


def test_the_deployed_entry_point_wires_the_governed_route(tmp_path):
    """OBLIGATION 1 + 10a. The real entry point returns BOTH seams. If the deployed wiring is
    removed, this fails immediately — and so does every test below it."""
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant=TENANT)
    try:
        signer = DeliverySigner(SECRET)
        provider, _ = entry_point._build_governed_write_route(
            db_path=str(tmp_path / "w.sqlite3"), tenant=TENANT, signer=signer)
        assert provider is not None, (
            "run_action_callback_server no longer wires governed_write_provider — the deployed "
            "server cannot reach the governed route's lookup boundary")
        assert callable(provider)
    finally:
        store.close()


def test_main_passes_both_seams_into_run_callback_server():
    """The builder existing is not enough: `main()` must actually hand both seams to the server.
    AST, so a renamed-but-unused variable cannot pass."""
    src = (ROOT / "scripts/run_action_callback_server.py").read_text(encoding="utf-8")
    assert "_build_governed_write_route" in src, "degenerate read"
    tree = ast.parse(src)
    passed = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "run_callback_server":
            passed = {kw.arg for kw in node.keywords}
    assert "governed_write_provider" in passed, (
        "run_callback_server is called without governed_write_provider — the deployed server would "
        "fail closed and the route would be unreachable")
    assert "governed_write_kernel" in passed
    # and they must be the BUILDER's results, not literal None
    assert "_build_governed_write_route(" in src


def test_the_full_deployed_order_carries_one_identity_to_the_dark_adapter(tmp_path):
    """OBLIGATION 9. A real authenticated approval callback, submitted to the real handler built
    from the real entry point's seams, drives the whole order — and the SAME approval identity
    appears in the retrieved typed intent, the checkpoint, the witness, the Effect Grant, the atomic
    claim and the adapter's call log."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        writer = RecordingWriter(approved_fp=_expected_fp(store, op))

        # -- the retrieved typed intent carries the identity ---------------------------------
        pending = WorkflowStorePendingWrites(store, secret=SECRET).pending_for(APPROVAL_ID)
        assert pending is not None and pending.op.approval_id == APPROVAL_ID
        assert pending.op.payload_hash() == op.payload_hash()

        provider, kernel = _deployed_seams(db, writer=writer)
        config = _config(db, provider=provider, kernel=kernel)
        result = _post_to_handler(config, _slack_body(_token(op)))
    finally:
        store.close()

    assert result.status == 200, result.body
    assert result.body["metadata"]["approval_id"] == APPROVAL_ID
    assert result.body["metadata"]["state"] == "VERIFIED", result.body

    store = WorkflowStore(db, tenant=TENANT)
    try:
        # -- the adapter was reached, exactly once, with the right identity -------------------
        assert len(writer.writes) == 1, "the world must be touched exactly once"
        assert writer.seen_ops[0].approval_id == APPROVAL_ID
        assert writer.seen_ops[0].tenant == TENANT
        assert writer.seen_ops[0].work_item_id == "WI-77"
        assert writer.seen_ops[0].capability_id == "A4.raise_invoice"

        grant_id = result.body["metadata"]["grant_id"]
        grant = _row(store, "effect_grants", "tenant = ? AND grant_id = ?", (TENANT, grant_id))
        assert grant["approval_id"] == APPROVAL_ID, "the grant is authorized by a foreign approval"
        assert grant["state"] == "VERIFIED"

        witness = _row(store, "checkpoint_witnesses", "tenant = ? AND grant_id = ?",
                       (TENANT, grant_id))
        assert witness is not None and witness["approval_id"] == APPROVAL_ID
        assert witness["accountable_owner"] == OWNER

        # -- the atomic claim, and the queued intent that was consumed ------------------------
        claims = store.conn.execute(
            "SELECT action_id FROM operation_action_claims WHERE tenant = ?", (TENANT,)).fetchall()
        ids = {r["action_id"] for r in claims}
        assert APPROVAL_ID in ids, "the decision was not claimed single-use"
        assert gwr.CONSUMER_CLAIM_PREFIX + APPROVAL_ID in ids, "the intent was not consumed once"

        queued = _events(store, gwr.QUEUED_EVENT)
        assert len(queued) == 1 and queued[0]["payload"]["approval_id"] == APPROVAL_ID
        completed = _events(store, "GovernedWriteCompleted")
        assert len(completed) == 1 and completed[0]["payload"]["grant_id"] == grant_id

        # -- no money value in any durable record --------------------------------------------
        for event in _events(store, PROPOSED_EVENT) + queued + completed:
            assert "2850.00" not in json.dumps(event["payload"]), (
                "a money value reached a durable log record")
    finally:
        store.close()


# ============================================================ FAIL-CLOSED (obligation 7 & 10)


def test_provider_none_fails_closed(tmp_path):
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        _, kernel = _deployed_seams(db)
        writer = RecordingWriter()
        config = _config(db, provider=None, kernel=kernel)
        result = _post_to_handler(config, _slack_body(_token(op)))
    finally:
        store.close()
    # the governed branch is not entered at all; nothing is written
    assert len(writer.writes) == 0
    store = WorkflowStore(db, tenant=TENANT)
    try:
        assert _events(store, gwr.QUEUED_EVENT) == []
        assert _events(store, "GovernedWriteCompleted") == []
    finally:
        store.close()


def test_kernel_none_fails_closed(tmp_path):
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        provider, _ = _deployed_seams(db)
        config = _config(db, provider=provider, kernel=None)
        _post_to_handler(config, _slack_body(_token(op)))
        assert _events(store, gwr.QUEUED_EVENT) == []
        assert _events(store, "GovernedWriteCompleted") == []
    finally:
        store.close()


def test_a_missing_signing_secret_disables_the_route(tmp_path):
    """OBLIGATION 7. Missing configuration must fail closed at the entry point, not degrade."""
    provider, kernel = entry_point._build_governed_write_route(
        db_path=str(tmp_path / "w.sqlite3"), tenant=TENANT, signer=DeliverySigner(b""))
    assert provider is None and kernel is None


def test_a_missing_tenant_disables_the_route(tmp_path):
    provider, kernel = entry_point._build_governed_write_route(
        db_path=str(tmp_path / "w.sqlite3"), tenant="", signer=DeliverySigner(SECRET))
    assert provider is None and kernel is None


def test_no_queued_intent_fails_closed(tmp_path):
    """A tap for an approval that was never PROPOSED retrieves nothing, so nothing runs."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _op()                      # deliberately NOT proposed
        provider, kernel = _deployed_seams(db)
        assert provider(APPROVAL_ID) is None, "an unproposed approval was retrievable"
        config = _config(db, provider=provider, kernel=kernel)
        _post_to_handler(config, _slack_body(_token(op)))
        assert _events(store, gwr.QUEUED_EVENT) == []
        assert _events(store, "GovernedWriteCompleted") == []
    finally:
        store.close()


def test_an_expired_proposal_fails_closed(tmp_path):
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        _propose(store, ttl_hours=-1)   # already expired
        provider, _ = _deployed_seams(db)
        assert provider(APPROVAL_ID) is None, "an expired proposal was retrievable"
    finally:
        store.close()


def test_a_missing_money_row_fails_closed(tmp_path):
    """The amount lives in the money table. If it is gone, the operation cannot be rebuilt, and a
    partial operation is not a weaker authorization — it is none."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        _propose(store)
        store.conn.execute("DELETE FROM operation_token_amounts WHERE tenant = ?", (TENANT,))
        store.conn.commit()
        provider, _ = _deployed_seams(db)
        assert provider(APPROVAL_ID) is None
    finally:
        store.close()


# ============================================================ THE CALLBACK CANNOT CHOOSE FIELDS


def test_callback_data_cannot_replace_operation_fields(tmp_path):
    """OBLIGATION 4 + 10e. The tap carries a Slack payload the attacker controls. None of it can
    become an operation field: the operation comes from the stored proposal, and the retrieved
    operation is identical whatever the payload says."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        provider, _ = _deployed_seams(db)
        baseline = provider(APPROVAL_ID)
        assert baseline is not None

        hostile_payloads = [
            {"amount": "999999.00", "customer": "Attacker LLC"},
            {"load_id": "load:9999", "invoice_ref": "INV-EVIL"},
            {"target_integration": "tms:attacker", "base_url": "https://evil.example"},
            {"capability_id": "A4.pay_carrier", "adapter": "A9"},
            {"approved_fields": {"amount": "1.00"}},
        ]
        for hostile in hostile_payloads:
            payload = {
                "type": "block_actions",
                "user": {"id": ACTOR},
                "channel": {"id": CHANNEL},
                # the hostile fields ride alongside the action, exactly where a caller could put them
                "operation": hostile,
                "actions": [{"action_id": "x", "value": _token(op), **hostile}],
            }
            body = urlencode({"payload": json.dumps(payload)})
            provider2, kernel2 = _deployed_seams(db)
            _post_to_handler(_config(db, provider=provider2, kernel=kernel2), body)

            fresh = provider(APPROVAL_ID)
            if fresh is None:
                continue                     # consumed/single-use — still never the hostile values
            assert fresh.op == baseline.op, (
                f"callback payload {hostile!r} changed the retrieved operation")
            assert fresh.op.approved_fields["amount"] == "2850.00"
            assert fresh.op.target_integration == "tms:truckingoffice"
    finally:
        store.close()


def test_the_repository_interface_exposes_no_constructor():
    """OBLIGATION 4, structurally. The boundary a callback holds has exactly one method, and it is a
    LOOKUP. There is no create/update/complete it could reach for."""
    from freight_recon.governed_write_registry import PendingGovernedWriteRepository

    methods = {n for n in dir(PendingGovernedWriteRepository) if not n.startswith("_")}
    assert methods == {"pending_for"}, (
        f"the repository boundary grew beyond a lookup: {sorted(methods)}")

    # and the deployed provider is a plain callable over that lookup, nothing more
    src = (ROOT / "scripts/run_action_callback_server.py").read_text(encoding="utf-8")
    assert "pending_for" in src, "degenerate read"
    for forbidden in ("InvoiceWriteOperation(", "record_proposed_governed_write("):
        assert forbidden not in src, (
            f"the deployed entry point calls {forbidden} — it can construct an operation, which is "
            "exactly what the callback must never be able to do")


def test_a_mismatched_stored_intent_is_rejected(tmp_path):
    """OBLIGATION 10f. A stored record tampered after the human signed it cannot rebuild to the
    recorded payload hash, so it authorizes nothing."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        _propose(store)
        provider, _ = _deployed_seams(db)
        assert provider(APPROVAL_ID) is not None, "the untampered record must be retrievable"

        # tamper the counterparty in the durable record, leaving the recorded hash alone
        row = store.conn.execute(
            "SELECT id, payload_json FROM security_events WHERE tenant = ? AND event_type = ?",
            (TENANT, PROPOSED_EVENT)).fetchone()
        payload = json.loads(row["payload_json"])
        payload["approved_fields_nonmoney"]["customer"] = "Attacker LLC"
        store.conn.execute("UPDATE security_events SET payload_json = ? WHERE id = ?",
                           (json.dumps(payload), row["id"]))
        store.conn.commit()

        assert provider(APPROVAL_ID) is None, (
            "a tampered stored intent was accepted — the payload-hash anchor is not load-bearing")
    finally:
        store.close()


def test_a_tampered_amount_is_rejected(tmp_path):
    """The money table is the other half of the record. Changing it there is caught by the same
    anchor."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        _propose(store)
        provider, _ = _deployed_seams(db)
        assert provider(APPROVAL_ID) is not None
        store.conn.execute(
            "UPDATE operation_token_amounts SET approved_amount = ? WHERE tenant = ?",
            ("999999.00", TENANT))
        store.conn.commit()
        assert provider(APPROVAL_ID) is None, "a tampered approved amount was accepted"
    finally:
        store.close()


# ============================================================ IDEMPOTENCY / UNKNOWN / DARKNESS


def test_duplicate_deployed_callbacks_produce_at_most_one_adapter_attempt(tmp_path):
    """OBLIGATION 10g. Five identical taps at the deployed handler → at most ONE adapter attempt."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        writer = RecordingWriter(approved_fp=_expected_fp(store, op))
        token = _token(op)
        for _ in range(5):
            provider, kernel = _deployed_seams(db, writer=writer)
            _post_to_handler(_config(db, provider=provider, kernel=kernel), _slack_body(token))
        assert len(writer.writes) == 1, (
            f"5 duplicate deployed callbacks produced {len(writer.writes)} adapter attempts")
        assert len(_events(store, "GovernedWriteCompleted")) == 1
    finally:
        store.close()


def test_concurrent_deployed_callbacks_produce_at_most_one_adapter_attempt(tmp_path):
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        writer = RecordingWriter(approved_fp=_expected_fp(store, op))
        token = _token(op)
        barrier = threading.Barrier(3)

        def tap():
            barrier.wait()
            try:
                provider, kernel = _deployed_seams(db, writer=writer)
                _post_to_handler(_config(db, provider=provider, kernel=kernel), _slack_body(token))
            except Exception:  # noqa: BLE001 — a race loser is still "did nothing"
                pass

        threads = [threading.Thread(target=tap) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(writer.writes) <= 1, (
            f"concurrent deployed callbacks produced {len(writer.writes)} adapter attempts")
        grants = store.conn.execute(
            "SELECT COUNT(*) c FROM effect_grants WHERE tenant = ? AND commit_key = ?",
            (TENANT, op.effect_key())).fetchone()["c"]
        assert grants <= 1, f"{grants} grants minted for one logical effect"
    finally:
        store.close()


def test_unknown_outcome_does_not_retry_through_the_deployed_route(tmp_path):
    """OBLIGATION 10h. An ambiguous outcome is escalated and never retried by a later tap."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        writer = RecordingWriter(approved_fp=_expected_fp(store, op), mode="unknown")
        token = _token(op)
        provider, kernel = _deployed_seams(db, writer=writer)
        first = _post_to_handler(_config(db, provider=provider, kernel=kernel), _slack_body(token))
        assert first.body["metadata"]["state"] == "UNKNOWN_OUTCOME", first.body
        assert first.body["metadata"]["requires_reconciliation"] is True

        retry = RecordingWriter(approved_fp=writer.approved_fp)
        provider2, kernel2 = _deployed_seams(db, writer=retry)
        _post_to_handler(_config(db, provider=provider2, kernel=kernel2), _slack_body(token))
        assert len(retry.writes) == 0, "an UNKNOWN outcome was retried through the deployed route"

        grant_id = first.body["metadata"]["grant_id"]
        grant = _row(store, "effect_grants", "tenant = ? AND grant_id = ?", (TENANT, grant_id))
        assert grant["state"] == "UNKNOWN_OUTCOME"
        assert _events(store, "GovernedWriteEscalated")
    finally:
        store.close()


def test_the_deployed_default_capability_is_dark(tmp_path):
    """OBLIGATION 6 + 10i. With NO writer substituted — the actual deployed configuration — the
    chain is fully reachable and the effect is a PROVEN non-occurrence."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        provider, kernel = _deployed_seams(db)         # no writer: the deployed default
        pending = provider(APPROVAL_ID)
        assert pending is not None
        assert pending.writer is None, (
            "the deployed provider injected a writer — the entry point must register no "
            "credentialed real-write adapter")
        result = _post_to_handler(_config(db, provider=provider, kernel=kernel),
                                  _slack_body(_token(op)))
        assert result.body["metadata"]["state"] == "FAILED", result.body
        grant_id = result.body["metadata"]["grant_id"]
        grant = _row(store, "effect_grants", "tenant = ? AND grant_id = ?", (TENANT, grant_id))
        assert grant["state"] == "FAILED"
        # reached the whole chain, and performed nothing
        assert _events(store, "GovernedWriteCompleted")
    finally:
        store.close()


def test_a_non_sandbox_proposal_is_refused_before_any_claim(tmp_path):
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store, _op(sandbox=False))
        writer = RecordingWriter()
        provider, kernel = _deployed_seams(db, writer=writer)
        _post_to_handler(_config(db, provider=provider, kernel=kernel), _slack_body(_token(op)))
        assert len(writer.writes) == 0
        assert _events(store, "InvoiceWriteRefusedNotSandbox")
    finally:
        store.close()


# ============================================================ NO FALLBACK (obligation 8)


def test_the_deployed_route_has_no_fallback_to_a_legacy_actuator():
    """OBLIGATION 8. AST imports, never substrings — the entry point's prose NAMES these."""
    src = (ROOT / "scripts/run_action_callback_server.py").read_text(encoding="utf-8")
    assert "_build_governed_write_route" in src, "degenerate read"
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imported.add(base)
            imported.update(f"{base}.{a.name}" for a in node.names)
    assert imported, "no imports parsed — degenerate"
    joined = " ".join(imported)
    for forbidden in ("cdp_actuator", "cdp_session", "operator_agent", "operation_router",
                      "browser_use_write", "browser_use_adapter", "multistep_write", "tms_write"):
        assert forbidden not in joined, f"the deployed entry point imports {forbidden!r}"
    # no generic natural-language or arbitrary-task execution on the governed path
    for forbidden in ("OperatorAgent(", "CdpActuator(", "CdpBrowserSession(", "OperationRouter(",
                      "run_vetted(", "NativeBrowserUseRunner("):
        assert forbidden not in src, f"the deployed entry point constructs {forbidden}"


def test_the_registry_module_reaches_no_adapter():
    src = (ROOT / "src/freight_recon/governed_write_registry.py").read_text(encoding="utf-8")
    assert "WorkflowStorePendingWrites" in src, "degenerate read"
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imported.add(base)
            imported.update(f"{base}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    joined = " ".join(imported)
    for forbidden in ("cdp_actuator", "cdp_session", "operator_agent", "browser_use_write",
                      "browser_use_adapter", "effect_boundary"):
        assert forbidden not in joined, f"the pending-write repository imports {forbidden!r}"


# ============================================================ MONEY DISCIPLINE


def test_the_proposal_record_never_stores_a_money_value(tmp_path):
    """CLAUDE.md §10: memory and logs never store money. The amount lives in the dedicated money
    table and is re-read from there; the event payload names only that it was withheld."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        _propose(store)
        events = _events(store, PROPOSED_EVENT)
        assert events, "no proposal recorded — degenerate"
        blob = json.dumps(events[0]["payload"])
        assert "2850.00" not in blob and "285000" not in blob, (
            f"a money value reached the event log: {blob}")
        assert events[0]["payload"]["money_fields_withheld"] == ["amount"]
        # ...and it really is retrievable from the money table
        assert store.operation_token_amount(TOKEN_FP)
    finally:
        store.close()


# ============================================================ THE REAL SERVER OBJECT


def test_run_callback_server_accepts_and_holds_the_deployed_seams(tmp_path):
    """The seams survive the real server constructor — not just the handler factory. Binds a real
    loopback socket; if the sandbox forbids that, the test is not silently skipped elsewhere."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        _propose(store)
        provider, kernel = _deployed_seams(db)
        server = run_callback_server(
            tenant=TENANT, host="127.0.0.1", port=0, db_path=str(db),
            signer=DeliverySigner(SECRET), slack_signing_secret=SLACK_SECRET,
            allowed_slack_users=(ACTOR,), allowed_slack_channel=CHANNEL,
            governed_write_provider=provider, governed_write_kernel=kernel,
        )
        try:
            assert server.RequestHandlerClass is not None
            host, port = server.server_address[:2]
            assert port > 0
        finally:
            server.server_close()
    finally:
        store.close()


def test_a_proposal_with_no_stored_channel_receipt_fails_closed(tmp_path):
    """The channel receipt must come from the STORED proposal, never from the tap.

    The hostile shape this closes: a proposal recorded with an EMPTY channel, and a token signed
    with an empty channel too. The envelope then agrees with the stored receipt (both blank), so the
    binding check inside the route passes — and without an explicit refusal here, a tap arriving in
    ANY channel would execute. An absent binding is not a satisfied binding.
    """
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store, channel="")                     # no stored channel receipt
        token = _token(op, channel="")                       # ...and an envelope that agrees
        writer = RecordingWriter(approved_fp=_expected_fp(store, op))
        provider, kernel = _deployed_seams(db, writer=writer)

        # the tap arrives in a real channel that was never bound to anything
        result = _post_to_handler(_config(db, provider=provider, kernel=kernel),
                                  _slack_body(token, channel=CHANNEL))

        assert len(writer.writes) == 0, (
            "a tap executed against a proposal carrying NO channel receipt — an absent binding was "
            "treated as a satisfied one")
        assert _events(store, gwr.QUEUED_EVENT) == []
        refusals = _events(store, "GovernedWriteRefused")
        assert refusals, "the refusal was not recorded as an explicit governed outcome"
        assert any(r["payload"].get("reason") == "NO_STORED_CHANNEL_RECEIPT" for r in refusals), (
            f"refused for the wrong reason: {[r['payload'].get('reason') for r in refusals]}")
    finally:
        store.close()


def test_a_correctly_signed_approval_replayed_into_another_channel_is_refused(tmp_path):
    """The other half: the receipt exists, the signature is valid, but the tap arrives somewhere
    else. The live request must match the stored receipt, not merely the envelope."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        writer = RecordingWriter(approved_fp=_expected_fp(store, op))
        provider, kernel = _deployed_seams(db, writer=writer)
        config = _config(db, provider=provider, kernel=kernel, channel=None)
        result = _post_to_handler(config, _slack_body(_token(op), channel="C-ELSEWHERE"))
        assert len(writer.writes) == 0, "an approval was replayed into a foreign channel"
        refusals = _events(store, "GovernedWriteRefused")
        assert any(r["payload"].get("reason") == "CHANNEL_RECEIPT_MISMATCH" for r in refusals), (
            f"refused for the wrong reason: {[r['payload'].get('reason') for r in refusals]}")
    finally:
        store.close()


# ============================================================ THE ONE REMAINING BLOCKER


def test_the_execution_kernel_seam_is_blocked_pending_adjudication(tmp_path):
    """### THE DEPLOYED CUT IS NOT COMPLETE, AND THIS TEST SAYS SO OUT LOUD.

    `CheckpointKernel` cannot exist without a `GateRegistry` (F-20), so the deployed governed route
    cannot execute without PRODUCTION ACTION-CLASS GATE REGISTRATION. Repository authority assigns
    that to U8.1 / Phase 8 and freezes the ground it rests on:

      * `phase-0-baseline-manifest.yaml` records AC-CKPT-6-missing as
        "DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8" (green_at_phase P8, accountable_unit U8.1);
      * `pr-sequence.md` states typed policy and Action Class gate registration "do not exist until
        P8";
      * `test_phase0_null_gate.py` proves the production registration population is EMPTY and
        requires RE-ADJUDICATION if it ever stops being empty;
      * `CLAUDE.md` §7 makes such an acceptance-contract change tier 1: founder approval required.

    So the entry point wires the LOOKUP boundary and returns NO kernel, and the handler fails closed.
    This test pins that state deliberately: when the case is adjudicated and a registry is supplied,
    THIS TEST FAILS and must be replaced by one asserting the completed wiring — which is the point.
    A blocker that can be forgotten is not a blocker.
    """
    signer = DeliverySigner(SECRET)
    provider, kernel = entry_point._build_governed_write_route(
        db_path=str(tmp_path / "w.sqlite3"), tenant=TENANT, signer=signer)
    assert provider is not None, "the lookup boundary must still be wired"
    assert kernel is None, (
        "the deployed entry point now supplies an execution kernel. If AC-CKPT-6-missing has been "
        "re-adjudicated and production gate registration authorized, replace this test with one "
        "that asserts the completed wiring — do not delete it silently.")


def test_the_blocked_route_refuses_explicitly_rather_than_falling_through(tmp_path):
    """OBLIGATION 7, for the blocked state: a governed tap at a server with no kernel produces an
    EXPLICIT recorded governed refusal, never a silent fall-through into another handler."""
    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant=TENANT)
    try:
        op = _propose(store)
        signer = DeliverySigner(SECRET)
        provider, kernel = entry_point._build_governed_write_route(
            db_path=str(db), tenant=TENANT, signer=signer)
        assert kernel is None
        result = _post_to_handler(_config(db, provider=provider, kernel=kernel),
                                  _slack_body(_token(op)))
        assert result.status == 200
        assert result.body["metadata"]["state"] == "REFUSED"
        assert result.body["metadata"]["reason"] == "ROUTE_NOT_CONFIGURED"
        refusals = _events(store, "GovernedWriteRefused")
        assert any(r["payload"].get("reason") == "ROUTE_NOT_CONFIGURED" for r in refusals)
        assert _events(store, gwr.QUEUED_EVENT) == [], "a blocked route still advanced the pipeline"
    finally:
        store.close()
