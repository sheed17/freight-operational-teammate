"""Tests for the local signed-action callback server."""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.action_callback import (  # noqa: E402
    CallbackStatus,
    _build_operation_command_proposal,
    _scrub_money_from_text,
    build_slack_operation_approval_value,
    handle_signed_action_callback,
    parse_callback_token,
    run_callback_server,
)
from freight_recon.delivery import DeliverySigner, build_delivery_message, record_delivery_message  # noqa: E402
from freight_recon.operation_router import OperationRouter, freight_lanes  # noqa: E402
from freight_recon.operator_agent import AgentResult  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewDecision  # noqa: E402
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore, process_load_packet  # noqa: E402
from run_gmail_to_slack_dogfood import _redacted_workflow_json  # noqa: E402
from run_action_callback_server import _build_receivables_reader  # noqa: E402


def _delivered(tmp_path, load_id="LD-560008"):
    signer = DeliverySigner(b"callback-secret")
    corpus = tmp_path / "corpus"
    generate(corpus, 8, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    load_by_id = {load.load_id: load for load in loads}
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    seen: set[tuple[str, str]] = set()
    selected = None
    for load in loads:
        run = process_load_packet(
            store,
            load,
            primary_document_path=corpus / load.documents["carrier_invoice"],
            seen_invoice_keys=seen,
        )
        payload = build_review_payload(run, load, age_hours=48)
        if payload is not None:
            record_review_payload(store, payload)
            if load.load_id == load_id:
                selected = payload
    assert selected is not None
    message = build_delivery_message(selected, signer, actor="Rasheed")
    record_delivery_message(store, message)
    return store, signer, message, load_by_id


def _token_for(message, decision):
    return next(button.signed_token for button in message.actions if button.decision == decision)


def _noop_router():
    def build_agent(*, approved_amount=None, approve=None, prepare_only=False):
        return None

    return OperationRouter(
        lanes=freight_lanes(),
        build_agent=build_agent,
        approved_amount_for=lambda intent: (intent.params or {}).get("approved_amount"),
    )


def test_direct_callback_applies_signed_action_and_formats_confirmation(tmp_path):
    store, signer, message, loads = _delivered(tmp_path)
    token = _token_for(message, ReviewDecision.REQUEST_BACKUP)

    response = handle_signed_action_callback(store, token, signer=signer, follow_up_loads=loads)

    assert response.status == CallbackStatus.APPLIED
    assert response.http_status == 200
    assert response.run_id == message.run_id
    assert "Backup requested by Rasheed" in response.message
    assert "Backup requested by Rasheed" in response.rendered_message
    run = store.get_run(message.run_id)
    assert run is not None
    assert run.state == WorkflowState.REQUESTED_BACKUP
    store.close()



def test_gmail_workflow_report_redacts_signed_tokens(tmp_path):
    from types import SimpleNamespace

    store, signer, message, _loads = _delivered(tmp_path, load_id="LD-560003")
    raw_token = message.actions[0].signed_token
    workflow = SimpleNamespace(
        delivery_messages=[message],
        model_copy=lambda update: SimpleNamespace(
            delivery_messages=update["delivery_messages"],
            model_dump_json=lambda indent=2: json.dumps(
                [item.model_dump(mode="json") for item in update["delivery_messages"]],
                indent=indent,
            ),
        ),
    )

    report = _redacted_workflow_json(workflow)

    assert raw_token not in report
    assert "redacted:" in report
    store.close()


def test_operation_proposal_extracts_amount_from_original_owner_text_not_model_rewrite():
    signer = DeliverySigner(b"callback-secret")
    proposal = _build_operation_command_proposal(
        "invoice the delivered load for Acme for 9999.00",
        signer=signer,
        router=_noop_router(),
        channel_id="C1",
        amount_source_text="invoice load 105 for Acme",
    )

    assert proposal is not None
    assert "need an approved amount" in proposal["text"]


def test_operation_proposal_uses_original_text_amount_even_when_model_rewrite_changes_it():
    signer = DeliverySigner(b"callback-secret")
    proposal = _build_operation_command_proposal(
        "invoice the delivered load for Acme for 9999.00",
        signer=signer,
        router=_noop_router(),
        channel_id="C1",
        amount_source_text="invoice load 105 for Acme for 2850.00",
    )

    assert proposal is not None
    assert "Approve $2850.00" in json.dumps(proposal)
    assert "9999.00" in json.dumps(proposal)
    assert "Approve $9999.00" not in json.dumps(proposal)


def test_scrub_money_from_text_removes_currency_but_keeps_order_reference():
    scrubbed = _scrub_money_from_text("it's order #1002, pay $4,500 and USD 25.50 lumper")

    assert "$" not in scrubbed
    assert "4,500" not in scrubbed
    assert "25.50" not in scrubbed
    assert "order #1002" in scrubbed
    assert scrubbed.count("[amount redacted]") == 2



def test_post_action_executor_failure_is_audited_without_breaking_callback(tmp_path):
    store, signer, message, loads = _delivered(tmp_path, load_id="LD-560003")
    token = _token_for(message, ReviewDecision.APPROVE_EXPECTED_AMOUNT)

    def _boom(_store, _outcome):
        raise RuntimeError("execution service down")

    response = handle_signed_action_callback(
        store,
        token,
        signer=signer,
        follow_up_loads=loads,
        post_action_executor=_boom,
    )

    assert response.status == CallbackStatus.APPLIED
    assert store.get_run(message.run_id).state == WorkflowState.APPROVED
    events = store.audit_events(message.run_id)
    assert any(event["event_type"] == "post_action_executor_failed" for event in events)
    store.close()


def test_direct_callback_rejects_missing_token_without_state_change(tmp_path):
    store, signer, message, _ = _delivered(tmp_path)

    response = handle_signed_action_callback(store, None, signer=signer)

    assert response.status == CallbackStatus.REJECTED
    assert response.http_status == 400
    run = store.get_run(message.run_id)
    assert run is not None
    assert run.state == WorkflowState.NEEDS_REVIEW
    store.close()


def test_http_callback_accepts_email_link_and_returns_json(tmp_path):
    store, signer, message, loads = _delivered(tmp_path)
    db_path = store.db_path
    token = _token_for(message, ReviewDecision.REQUEST_BACKUP)
    store.close()
    server = run_callback_server(
        host="127.0.0.1",
        port=0,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=loads,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("GET", f"/email/action?token={token}", headers={"Accept": "application/json"})
        result = conn.getresponse()
        body = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert body["status"] == CallbackStatus.APPLIED
    assert body["run_id"] == message.run_id
    assert "Backup requested by Rasheed" in body["message"]
    check_store = WorkflowStore(db_path)
    try:
        run = check_store.get_run(message.run_id)
        assert run is not None
        assert run.state == WorkflowState.REQUESTED_BACKUP
    finally:
        check_store.close()


def test_http_callback_rejects_unknown_path(tmp_path):
    store, signer, _, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    server = run_callback_server(
        host="127.0.0.1",
        port=0,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=loads,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/nope", headers={"Accept": "application/json"})
        result = conn.getresponse()
        body = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 404
    assert body["status"] == CallbackStatus.REJECTED


def test_signed_action_endpoint_is_post_only(tmp_path):
    store, signer, message, loads = _delivered(tmp_path)
    db_path = store.db_path
    token = _token_for(message, ReviewDecision.REQUEST_BACKUP)
    store.close()
    server = run_callback_server(
        host="127.0.0.1",
        port=0,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=loads,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("GET", f"/actions/signed?token={token}", headers={"Accept": "application/json"})
        result = conn.getresponse()
        body = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 405
    assert body["status"] == CallbackStatus.REJECTED
    check_store = WorkflowStore(db_path)
    try:
        run = check_store.get_run(message.run_id)
        assert run is not None
        assert run.state == WorkflowState.NEEDS_REVIEW
    finally:
        check_store.close()


def test_http_callback_rejects_malformed_content_length(tmp_path):
    store, signer, _, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    server = run_callback_server(
        host="127.0.0.1",
        port=0,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=loads,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with socket.create_connection((host, port), timeout=5) as sock:
            sock.sendall(
                b"POST /actions/signed HTTP/1.1\r\n"
                + f"Host: {host}:{port}\r\n".encode("ascii")
                + b"Accept: application/json\r\n"
                + b"Content-Length: nope\r\n"
                + b"\r\n"
            )
            sock.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks).decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "400" in raw
    assert "invalid content-length" in raw


_SLACK_SECRET = b"slack-callback-secret"


def _slack_interaction_body(token):
    payload = {
        "type": "block_actions",
        "user": {"id": "U1", "username": "rasheed"},
        "actions": [{"action_id": "request_backup_0", "value": token}],
    }
    return urlencode({"payload": json.dumps(payload)})


def _slack_operation_body(value, *, user_id="U_OWNER", channel_id="C_OPS", message_ts="1710000000.000100"):
    payload = {
        "type": "block_actions",
        "user": {"id": user_id, "username": "rasheed"},
        "channel": {"id": channel_id},
        "message": {"ts": message_ts},
        "container": {"channel_id": channel_id, "message_ts": message_ts},
        "actions": [{"action_id": "approve_operation_0", "value": value}],
    }
    return urlencode({"payload": json.dumps(payload)})


def _slack_headers(body, *, secret=_SLACK_SECRET, timestamp=None):
    ts = timestamp or str(int(time.time()))
    sig = "v0=" + hmac.new(secret, f"v0:{ts}:{body}".encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
    }


def _serve(db_path, signer, loads):
    server = run_callback_server(
        host="127.0.0.1",
        port=0,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=loads,
        slack_signing_secret=_SLACK_SECRET,
        allowed_slack_users=("U1",),
        allowed_slack_channel="C_OPS",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class _FakeRouterAgent:
    def __init__(self, calls, approve):
        self.calls = calls
        self.approve = approve

    def run(self, goal):
        self.calls.append(("goal", goal))
        self.calls.append(("approval_gate_first", bool(self.approve and self.approve(object()))))
        self.calls.append(("approval_gate_second", bool(self.approve and self.approve(object()))))
        return AgentResult(goal=goal, status="DONE", steps=[{"action": "DONE"}], note="invoice INV-9001 verified")


class _BoomRouter:
    def run(self, _intent, *, approve=None):
        raise RuntimeError("browser session crashed")


def _serve_with_operation_router(db_path, signer, loads, *, approved_amount="2850.00"):
    calls = []

    def build_agent(*, approved_amount=None, approve=None, prepare_only=False):
        calls.append(("approved_amount", approved_amount))
        return _FakeRouterAgent(calls, approve)

    router = OperationRouter(
        lanes=freight_lanes(),
        build_agent=build_agent,
        approved_amount_for=lambda intent: intent.params.get("approved_amount"),
    )
    server = run_callback_server(
        host="127.0.0.1",
        port=0,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=loads,
        slack_signing_secret=_SLACK_SECRET,
        operation_router=router,
        allowed_slack_users=("U_OWNER",),
        allowed_slack_channel="C_OPS",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, calls


def _wait_for_security_event(db_path, event_type, *, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        store = WorkflowStore(db_path)
        try:
            matches = [e for e in store.security_events() if e["event_type"] == event_type]
            if matches:
                return matches[-1]
        finally:
            store.close()
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {event_type}")


def test_slack_interactivity_applies_signed_action(tmp_path):
    store, signer, message, loads = _delivered(tmp_path)
    db_path = store.db_path
    token = _token_for(message, ReviewDecision.REQUEST_BACKUP)
    store.close()
    body = _slack_interaction_body(token)
    server, thread = _serve(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert payload.get("replace_original") is True  # Slack replaces the original card
    check = WorkflowStore(db_path)
    try:
        assert check.get_run(message.run_id).state == WorkflowState.REQUESTED_BACKUP
    finally:
        check.close()


def test_slack_operation_approval_runs_router_and_returns_receipt(tmp_path):
    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    intent = CommandIntent(
        kind=CommandKind.OPERATE,
        summary="invoice the delivered load for Acme",
        params={"approved": True, "customer": "Acme", "load_ref": "LD-9001"},
    )
    value = build_slack_operation_approval_value(
        intent,
        signer,
        action_id="op-approval-1",
        approved_amount="2850.00",
        expected_channel_id="C_OPS",
        expected_thread_ts="1710000000.000100",
    )
    body = _slack_operation_body(value)
    server, thread, calls = _serve_with_operation_router(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert "operating in the TMS" in payload["text"]
    assert payload["metadata"] == {
        "action_id": "op-approval-1",
        "status": "RUNNING",
        "channel_id": "C_OPS",
        "thread_ts": "1710000000.000100",
    }
    applied = _wait_for_security_event(db_path, "slack_operation_applied")
    assert ("approved_amount", "2850.00") in calls
    assert ("approval_gate_first", True) in calls
    assert ("approval_gate_second", False) in calls
    assert any(call[0] == "goal" and "Create a customer invoice" in call[1] for call in calls)
    assert applied["payload"]["status"] == "DONE"
    assert applied["payload"]["token_fingerprint"]


def test_slack_operation_approval_token_is_single_use(tmp_path):
    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    intent = CommandIntent(
        kind=CommandKind.OPERATE,
        summary="invoice the delivered load for Acme",
        params={"approved": True, "customer": "Acme", "load_ref": "LD-9001"},
    )
    value = build_slack_operation_approval_value(
        intent,
        signer,
        action_id="fixed-op-approval",
        approved_amount="2850.00",
        expected_channel_id="C_OPS",
        expected_thread_ts="1710000000.000100",
    )
    body = _slack_operation_body(value)
    server, thread, calls = _serve_with_operation_router(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        first = conn.getresponse()
        first_payload = json.loads(first.read().decode("utf-8"))
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        second = conn.getresponse()
        second_payload = json.loads(second.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert first.status == 200 and first_payload["metadata"]["status"] == "RUNNING"
    assert second.status == 200
    assert "already used" in second_payload["text"]
    assert [call[0] for call in calls].count("goal") == 1


def test_operation_action_claim_is_atomic(tmp_path):
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        assert store.claim_operation_action("op-1", actor="a", payload={"first": True}) is True
        assert store.claim_operation_action("op-1", actor="b", payload={"second": True}) is False
    finally:
        store.close()


def test_delivery_action_claim_is_atomic(tmp_path):
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        assert store.claim_delivery_action("review-1", run_id=1, actor="a", payload={"first": True}) is True
        assert store.claim_delivery_action("review-1", run_id=1, actor="b", payload={"second": True}) is False
    finally:
        store.close()


def test_signed_review_action_token_reuse_is_idempotent_without_reapplying(tmp_path):
    store, signer, message, loads = _delivered(tmp_path)
    token = _token_for(message, ReviewDecision.REQUEST_BACKUP)

    first = handle_signed_action_callback(store, token, signer=signer, follow_up_loads=loads)
    second = handle_signed_action_callback(store, token, signer=signer, follow_up_loads=loads)

    assert first.status == CallbackStatus.APPLIED
    assert second.status == CallbackStatus.APPLIED
    events = [e for e in store.audit_events(message.run_id) if e["event_type"] == "delivery_action_applied"]
    assert len(events) == 1
    store.close()


def test_slack_operation_approval_rejects_unauthorized_user_before_router(tmp_path):
    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    intent = CommandIntent(
        kind=CommandKind.OPERATE,
        summary="invoice the delivered load for Acme",
        params={"approved": True},
    )
    body = _slack_operation_body(
        build_slack_operation_approval_value(intent, signer, approved_amount="2850.00"),
        user_id="U_STRANGER",
    )
    server, thread, calls = _serve_with_operation_router(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert payload["replace_original"] is False
    assert "Not authorized" in payload["text"]
    assert calls == []
    check = WorkflowStore(db_path)
    try:
        rejected = [e for e in check.security_events() if e["event_type"] == "slack_operation_rejected"]
        assert rejected and rejected[-1]["payload"]["failure"] == "authorization"
    finally:
        check.close()


def test_slack_operation_approval_rejects_wrong_message_context_before_router(tmp_path):
    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    intent = CommandIntent(
        kind=CommandKind.OPERATE,
        summary="invoice the delivered load for Acme",
        params={"approved": True, "customer": "Acme", "load_ref": "LD-9001"},
    )
    value = build_slack_operation_approval_value(
        intent,
        signer,
        approved_amount="2850.00",
        expected_channel_id="C_OTHER",
        expected_thread_ts="1710000000.000100",
    )
    body = _slack_operation_body(value)
    server, thread, calls = _serve_with_operation_router(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert "does not belong" in payload["text"]
    assert calls == []
    check = WorkflowStore(db_path)
    try:
        rejected = [e for e in check.security_events() if e["event_type"] == "slack_operation_rejected"]
        assert rejected and rejected[-1]["payload"]["failure"] == "channel_mismatch"
    finally:
        check.close()


def test_slack_operation_router_exception_returns_receipt_and_audits(tmp_path):
    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    intent = CommandIntent(
        kind=CommandKind.OPERATE,
        summary="invoice the delivered load for Acme",
        params={"approved": True, "customer": "Acme", "load_ref": "LD-9001"},
    )
    value = build_slack_operation_approval_value(intent, signer, approved_amount="2850.00")
    body = _slack_operation_body(value)
    server = run_callback_server(
        host="127.0.0.1",
        port=0,
        db_path=str(db_path),
        signer=signer,
        follow_up_loads=loads,
        slack_signing_secret=_SLACK_SECRET,
        operation_router=_BoomRouter(),
        allowed_slack_users=("U_OWNER",),
        allowed_slack_channel="C_OPS",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert payload["metadata"]["status"] == "RUNNING"
    assert "operating in the TMS" in payload["text"]
    failed = _wait_for_security_event(db_path, "slack_operation_failed")
    assert failed["payload"]["error_type"] == "RuntimeError"


def test_slack_operation_approval_refuses_unapproved_money_lane_without_agent(tmp_path):
    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    intent = CommandIntent(
        kind=CommandKind.OPERATE,
        summary="invoice the delivered load for Acme",
        params={"approved": False},
    )
    body = _slack_operation_body(build_slack_operation_approval_value(intent, signer))
    server, thread, calls = _serve_with_operation_router(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert payload["metadata"]["status"] == "RUNNING"
    applied = _wait_for_security_event(db_path, "slack_operation_applied")
    assert applied["payload"]["status"] == "ESCALATED"
    assert "no human-approved amount" in applied["payload"]["note"]
    assert calls == []


def test_slack_operation_forged_signature_does_not_run_router(tmp_path):
    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    intent = CommandIntent(
        kind=CommandKind.OPERATE,
        summary="invoice the delivered load for Acme",
        params={"approved": True},
    )
    body = _slack_operation_body(build_slack_operation_approval_value(intent, signer, approved_amount="2850.00"))
    server, thread, calls = _serve_with_operation_router(db_path, signer, loads)
    try:
        host, port = server.server_address
        headers = _slack_headers(body)
        headers["X-Slack-Signature"] = "v0=deadbeef"
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=headers)
        result = conn.getresponse()
        result.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 401
    assert calls == []


def test_slack_operation_malformed_approval_returns_400_without_router(tmp_path):
    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    body = _slack_operation_body("not-a-valid-operation-token.signature")
    server, thread, calls = _serve_with_operation_router(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 400
    assert payload["error"] == "malformed Slack operation approval"
    assert calls == []


def test_slack_interactivity_rejects_forged_signature_without_state_change(tmp_path):
    store, signer, message, loads = _delivered(tmp_path)
    db_path = store.db_path
    token = _token_for(message, ReviewDecision.REQUEST_BACKUP)
    store.close()
    body = _slack_interaction_body(token)
    server, thread = _serve(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        headers = _slack_headers(body)
        headers["X-Slack-Signature"] = "v0=deadbeef"  # forged
        conn.request("POST", "/slack/actions", body=body, headers=headers)
        result = conn.getresponse()
        result.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 401
    check = WorkflowStore(db_path)
    try:
        assert check.get_run(message.run_id).state == WorkflowState.NEEDS_REVIEW  # unchanged
        rejected = [e for e in check.security_events() if e["event_type"] == "slack_request_rejected"]
        assert rejected and rejected[-1]["payload"]["failure"] == "signature"
    finally:
        check.close()


def test_slack_command_pause_flips_brake(tmp_path):
    from pathlib import Path

    from freight_recon.ops_control import OpsControl

    store, signer, message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    body = urlencode(
        {"command": "/neyma", "text": "pause tms writes", "user_id": "U1", "user_name": "rasheed", "channel_id": "C_OPS"}
    )
    server, thread = _serve(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/commands", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert payload["response_type"] == "ephemeral" and "PAUSED" in payload["text"]
    assert OpsControl(Path(db_path).parent / "ops_control.json").is_tms_writes_paused() is True


def test_slack_command_can_render_operation_proposal_button(tmp_path):
    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    body = urlencode(
        {
            "command": "/neyma",
            "text": "invoice LD-9001 for Acme amount 2850.00",
            "user_id": "U_OWNER",
            "user_name": "rasheed",
            "channel_id": "C_OPS",
        }
    )
    server, thread, calls = _serve_with_operation_router(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/commands", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert payload["response_type"] == "in_channel"
    assert "raise_invoice" in payload["text"]
    actions = next(block for block in payload["blocks"] if block["type"] == "actions")
    button = actions["elements"][0]
    assert button["text"]["text"] == "Approve $2850.00"
    assert button["value"].count(".") == 1
    assert calls == []


def test_receivables_reader_returns_none_when_browser_is_busy(tmp_path):
    from freight_recon.browser_lock import BrowserLock

    lock_path = tmp_path / "browser.busy"
    reader = _build_receivables_reader(
        cdp_url="http://localhost:1",
        url_filter="truckingoffice",
        invoices_url="https://secure.truckingoffice.com/invoices",
        lock_path=lock_path,
    )
    with BrowserLock(lock_path).hold(holder="write"):
        assert reader() is None


def test_slack_command_rejects_unauthorized_user(tmp_path):
    from pathlib import Path

    from freight_recon.ops_control import OpsControl

    store, signer, _message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    body = urlencode(
        {
            "command": "/neyma",
            "text": "pause tms writes",
            "user_id": "U_STRANGER",
            "user_name": "x",
            "channel_id": "C_OPS",
        }
    )
    server, thread = _serve(db_path, signer, loads)
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/commands", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        payload = json.loads(result.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 200
    assert "Not authorized" in payload["text"]
    assert OpsControl(Path(db_path).parent / "ops_control.json").is_tms_writes_paused() is False


def test_slack_command_rejects_forged_signature(tmp_path):
    from pathlib import Path

    from freight_recon.ops_control import OpsControl

    store, signer, message, loads = _delivered(tmp_path)
    db_path = store.db_path
    store.close()
    body = urlencode(
        {"command": "/neyma", "text": "pause tms writes", "user_id": "U1", "user_name": "x", "channel_id": "C_OPS"}
    )
    server, thread = _serve(db_path, signer, loads)
    try:
        host, port = server.server_address
        headers = _slack_headers(body)
        headers["X-Slack-Signature"] = "v0=deadbeef"  # forged
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/commands", body=body, headers=headers)
        result = conn.getresponse()
        result.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 401
    # forged command must not flip the brake
    assert OpsControl(Path(db_path).parent / "ops_control.json").is_tms_writes_paused() is False


def test_slack_interactivity_disabled_without_signing_secret(tmp_path):
    store, signer, message, loads = _delivered(tmp_path)
    db_path = store.db_path
    token = _token_for(message, ReviewDecision.REQUEST_BACKUP)
    store.close()
    body = _slack_interaction_body(token)
    # No slack_signing_secret configured → route is disabled (404), action not applied.
    server = run_callback_server(host="127.0.0.1", port=0, db_path=str(db_path), signer=signer, follow_up_loads=loads)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/slack/actions", body=body, headers=_slack_headers(body))
        result = conn.getresponse()
        result.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.status == 404
    check = WorkflowStore(db_path)
    try:
        assert check.get_run(message.run_id).state == WorkflowState.NEEDS_REVIEW
    finally:
        check.close()


def test_invalid_utf8_body_is_structured_missing_token_rejection():
    assert parse_callback_token("/actions/signed", b"\xff\xfe") is None


def test_non_object_json_body_is_structured_missing_token_rejection():
    assert parse_callback_token("/actions/signed", b'["not", "an", "object"]') is None


def test_local_dev_secret_cannot_bind_non_loopback():
    script = Path(__file__).resolve().parents[2] / "scripts" / "run_action_callback_server.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--host",
            "0.0.0.0",
            "--allow-local-dev-secret",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "loopback host" in result.stderr


def test_env_enabled_local_dev_secret_cannot_bind_non_loopback():
    script = Path(__file__).resolve().parents[2] / "scripts" / "run_action_callback_server.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--host",
            "0.0.0.0",
        ],
        text=True,
        capture_output=True,
        check=False,
        env={"NEYMA_ALLOW_LOCAL_DELIVERY_SECRET": "1"},
    )

    assert result.returncode != 0
    assert "loopback host" in result.stderr
