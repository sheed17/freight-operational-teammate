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
    handle_signed_action_callback,
    parse_callback_token,
    run_callback_server,
)
from freight_recon.delivery import DeliverySigner, build_delivery_message, record_delivery_message  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewDecision  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore, process_load_packet  # noqa: E402


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
            raw = sock.recv(4096).decode("utf-8")
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
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


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
