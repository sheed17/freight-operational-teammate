"""Local signed-action callback surface for the internal dogfood pilot.

This module is intentionally small and transport-neutral. It gives local email action links and
test callbacks somewhere to land without introducing a web framework or live outbound behavior.
Every accepted action still flows through ``delivery.submit_signed_action`` and the workflow state
machine; this layer only parses HTTP-ish inputs and formats a confirmation response.
"""

from __future__ import annotations

import json
import base64
import hashlib
import hmac
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, Field

from .operation_router import OperationRouter
from .delivery import (
    DeliveryActionOutcome,
    DeliveryExpiredError,
    DeliverySignatureError,
    DeliverySigner,
    render_delivery_message,
    submit_signed_action,
)
from pathlib import Path

from .ops_control import OpsControl, handle_ops_command
from .operation_router import OperationResult
from .reconciliation import FreightLoadForReconciliation
from .slack_adapter import SlackDeliveryAdapter, SlackError, SlackSignatureError, verify_slack_signature
from .slack_delegate import CommandIntent, CommandKind, authorize_command
from .thread_reply import find_resumable_operation, intent_from_resumable
from .workflow import WorkflowError, WorkflowStore

DEFAULT_OPERATION_TOKEN_TTL_SECONDS = 3600


class CallbackStatus(str):
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"


class CallbackResponse(BaseModel):
    status: str
    http_status: int
    title: str
    message: str
    run_id: int | None = None
    action_id: str | None = None
    mutation_text: str | None = None
    rendered_message: str | None = None
    errors: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class CallbackAppConfig:
    db_path: str
    signer: DeliverySigner
    follow_up_loads: dict[str, FreightLoadForReconciliation] | None = None
    # When set, the `/slack/actions` interactivity route is enabled. Slack requests are verified
    # against this signing secret before the carried action token is applied.
    slack_signing_secret: bytes | None = None
    post_action_executor: Callable[[WorkflowStore, DeliveryActionOutcome], None] | None = None
    # Loop heartbeat file, so the Slack `status` command can answer "what is Neyma doing right now?".
    status_file: str | None = None
    # Optional fake/live Slack approval bridge for the bounded request->agent->result router. This is
    # callback-only: it returns a Slack response body and does not post or send on its own.
    operation_router: OperationRouter | None = None
    operation_result_poster: Callable[[dict], None] | None = None
    allowed_slack_users: tuple[str, ...] = ()
    allowed_slack_channel: str | None = None


def handle_signed_action_callback(
    store: WorkflowStore,
    token: str | None,
    *,
    signer: DeliverySigner,
    follow_up_loads: dict[str, FreightLoadForReconciliation] | None = None,
    post_action_executor: Callable[[WorkflowStore, DeliveryActionOutcome], None] | None = None,
) -> CallbackResponse:
    """Apply one signed action token and return a response safe to show to a human."""
    if not token:
        return CallbackResponse(
            status=CallbackStatus.REJECTED,
            http_status=400,
            title="Missing action token",
            message="This Neyma action link is missing its signed token.",
            errors=["missing token"],
        )
    try:
        outcome = submit_signed_action(
            store,
            token,
            signer=signer,
            follow_up_loads=follow_up_loads,
        )
    except DeliveryExpiredError as exc:
        return CallbackResponse(
            status=CallbackStatus.REJECTED,
            http_status=410,
            title="Action link expired",
            message="This Neyma action link expired. Re-open the latest review message.",
            errors=[str(exc)],
        )
    except DeliverySignatureError as exc:
        return CallbackResponse(
            status=CallbackStatus.REJECTED,
            http_status=401,
            title="Action link rejected",
            message="This Neyma action link could not be verified.",
            errors=[str(exc)],
        )
    except WorkflowError as exc:
        return CallbackResponse(
            status=CallbackStatus.REJECTED,
            http_status=409,
            title="Action no longer available",
            message="The workflow state has changed, so this action was not applied.",
            errors=[str(exc)],
        )

    if post_action_executor is not None:
        _run_post_action_executor(store, outcome, post_action_executor)

    return CallbackResponse(
        status=CallbackStatus.APPLIED,
        http_status=200,
        title="Neyma action applied",
        message=outcome.mutation_text,
        run_id=outcome.run_id,
        action_id=outcome.action_id,
        mutation_text=outcome.mutation_text,
        rendered_message=render_delivery_message(outcome.message),
    )


def parse_callback_token(path: str, body: bytes | None = None) -> str | None:
    """Extract a token from a callback URL or a small JSON/form body."""
    query = parse_qs(urlsplit(path).query)
    if query.get("token"):
        return query["token"][0]
    if not body:
        return None
    try:
        raw = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {key: values[0] for key, values in parse_qs(raw).items()}
    if not isinstance(data, dict):
        return None
    token = data.get("token")
    return str(token) if token else None


def make_callback_handler(config: CallbackAppConfig) -> type[BaseHTTPRequestHandler]:
    """Build a stdlib HTTP handler bound to a workflow DB and signer."""

    class NeymaActionCallbackHandler(BaseHTTPRequestHandler):
        server_version = "NeymaActionCallback/0.1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            self._handle(method="GET", body=None)

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
            except ValueError:
                self._write(
                    CallbackResponse(
                        status=CallbackStatus.REJECTED,
                        http_status=400,
                        title="Malformed callback request",
                        message="Content-Length must be an integer.",
                        errors=["invalid content-length"],
                    )
                )
                return
            if length < 0:
                self._write(
                    CallbackResponse(
                        status=CallbackStatus.REJECTED,
                        http_status=400,
                        title="Malformed callback request",
                        message="Content-Length cannot be negative.",
                        errors=["negative content-length"],
                    )
                )
                return
            self._handle(method="POST", body=self.rfile.read(length) if length else b"")

        def _handle(self, *, method: Literal["GET", "POST"], body: bytes | None) -> None:
            path = urlsplit(self.path).path
            if path == "/slack/actions":
                if config.slack_signing_secret is None:
                    # Disabled route looks identical (404) regardless of method — no existence leak.
                    self._write(
                        CallbackResponse(
                            status=CallbackStatus.REJECTED,
                            http_status=404,
                            title="Not found",
                            message="Unknown Neyma callback path.",
                        )
                    )
                    return
                if method != "POST":
                    self._write(_method_not_allowed("Use POST for Slack interactivity."))
                    return
                self._handle_slack(body or b"")
                return
            if path == "/slack/commands":
                if config.slack_signing_secret is None:
                    self._write(
                        CallbackResponse(
                            status=CallbackStatus.REJECTED,
                            http_status=404,
                            title="Not found",
                            message="Unknown Neyma callback path.",
                        )
                    )
                    return
                if method != "POST":
                    self._write(_method_not_allowed("Use POST for Slack commands."))
                    return
                self._handle_slack_command(body or b"")
                return
            if path == "/slack/events":
                if config.slack_signing_secret is None:
                    self._write(CallbackResponse(status=CallbackStatus.REJECTED, http_status=404,
                                                 title="Not found", message="Unknown Neyma callback path."))
                    return
                if method != "POST":
                    self._write(_method_not_allowed("Use POST for Slack events."))
                    return
                self._handle_slack_events(body or b"")
                return
            if path == "/email/action" and method != "GET":
                self._write(_method_not_allowed("Use GET for email action links."))
                return
            if path == "/actions/signed" and method != "POST":
                self._write(_method_not_allowed("Use POST for signed action callbacks."))
                return
            if path not in {"/email/action", "/actions/signed"}:
                self._write(
                    CallbackResponse(
                        status=CallbackStatus.REJECTED,
                        http_status=404,
                        title="Not found",
                        message="Unknown Neyma callback path.",
                    )
                )
                return
            token = parse_callback_token(self.path, body)
            store = WorkflowStore(config.db_path)
            try:
                response = handle_signed_action_callback(
                    store,
                    token,
                    signer=config.signer,
                    follow_up_loads=config.follow_up_loads,
                    post_action_executor=config.post_action_executor,
                )
            finally:
                store.close()
            self._write(response)

        def _handle_slack(self, body: bytes) -> None:
            """Verify a Slack interactive request and apply the carried signed action.

            Slack POSTs ``payload=<json>`` (form-encoded) with ``X-Slack-Signature`` and
            ``X-Slack-Request-Timestamp`` headers. We verify the Slack signature, then feed the
            button's token into the same signed action intake. The 200 response replaces the
            original Slack message with the mutated card.
            """
            if config.slack_signing_secret is None:
                self._write_json(404, {"error": "slack interactivity is not enabled on this server"})
                return
            timestamp = self.headers.get("X-Slack-Request-Timestamp", "")
            signature = self.headers.get("X-Slack-Signature", "")
            body_str = body.decode("utf-8", errors="replace")
            if config.operation_router is not None:
                operation_response = self._maybe_handle_slack_operation_approval(
                    body_str,
                    timestamp=timestamp,
                    signature=signature,
                )
                if operation_response is not None:
                    return
            store = WorkflowStore(config.db_path)
            try:
                adapter = SlackDeliveryAdapter(
                    store, signer=config.signer, signing_secret=config.slack_signing_secret
                )
                outcome, update = adapter.handle_interaction(
                    body=body_str,
                    timestamp=timestamp,
                    signature=signature,
                    follow_up_loads=config.follow_up_loads,
                )
                if config.post_action_executor is not None:
                    _run_post_action_executor(store, outcome, config.post_action_executor)
            except SlackSignatureError:
                # Audit the rejected request at the transport boundary (untrusted: dedicated
                # security log, no body/token retained) so probing a live endpoint leaves a trace.
                store.add_security_event(
                    "slack_request_rejected",
                    actor="system",
                    payload={"failure": "signature"},
                )
                self._write_json(401, {"error": "invalid Slack signature"})
                return
            except DeliveryExpiredError:
                self._write_json(
                    200,
                    {"text": "This action expired. Re-open the latest review message.", "replace_original": False},
                )
                return
            except WorkflowError as exc:
                self._write_json(
                    200,
                    {"text": f"Action no longer available: {exc}", "replace_original": False},
                )
                return
            except SlackError:
                # Keep the HTTP body generic so no payload-derived text is ever echoed back.
                self._write_json(400, {"error": "malformed Slack interaction"})
                return
            finally:
                store.close()
            self._write_json(200, update)

        def _maybe_handle_slack_operation_approval(
            self,
            body: str,
            *,
            timestamp: str,
            signature: str,
        ) -> bool | None:
            """Handle a Slack-approved bounded operation request, if this interaction is one.

            This is the Version-B callback bridge: Slack button approval -> authorized owner/channel
            -> known OperationRouter lane -> agent receipt. Unknown button payloads fall through to
            the normal review-action handler.
            """
            try:
                verify_slack_signature(
                    config.slack_signing_secret or b"",
                    timestamp=timestamp,
                    body=body,
                    signature=signature,
                )
            except SlackSignatureError:
                store = WorkflowStore(config.db_path)
                try:
                    store.add_security_event(
                        "slack_request_rejected",
                        actor="system",
                        payload={"failure": "signature", "route": "operation_approval"},
                    )
                finally:
                    store.close()
                self._write_json(401, {"error": "invalid Slack signature"})
                return True

            try:
                payload = _parse_slack_payload(body)
            except SlackError:
                return None
            action_value = _first_slack_action_value(payload)
            try:
                approval = _verify_operation_approval_value(action_value, config.signer)
                if approval is None:
                    return None
            except SlackError:
                self._write_json(400, {"error": "malformed Slack operation approval"})
                return True

            user_id = ((payload.get("user") or {}).get("id") or (payload.get("user") or {}).get("username"))
            channel_id = (
                (payload.get("channel") or {}).get("id")
                or (payload.get("container") or {}).get("channel_id")
                or payload.get("channel_id")
            )
            thread_ts = _slack_thread_ts(payload)
            ok, reason = authorize_command(
                user_id,
                channel_id,
                allowed_users=config.allowed_slack_users,
                allowed_channel=config.allowed_slack_channel,
            )
            if not ok:
                store = WorkflowStore(config.db_path)
                try:
                    store.add_security_event(
                        "slack_operation_rejected",
                        actor=str(user_id or "unknown"),
                        payload={"failure": "authorization", "reason": reason},
                    )
                finally:
                    store.close()
                self._write_json(
                    200,
                    {
                        "replace_original": False,
                        "text": f"Not authorized: {reason}.",
                    },
                )
                return True
            context_reason = _operation_context_mismatch(
                approval,
                channel_id=channel_id,
                thread_ts=thread_ts,
            )
            if context_reason:
                store = WorkflowStore(config.db_path)
                try:
                    store.add_security_event(
                        "slack_operation_rejected",
                        actor=str(user_id or "unknown"),
                        payload={
                            "failure": context_reason,
                            "action_id": approval.action_id,
                            "token_fingerprint": _token_fingerprint(action_value or ""),
                            "channel_id": channel_id,
                            "thread_ts": thread_ts,
                            "expected_channel_id": approval.expected_channel_id,
                            "expected_thread_ts": approval.expected_thread_ts,
                        },
                    )
                finally:
                    store.close()
                self._write_json(
                    200,
                    {
                        "replace_original": False,
                        "text": "That approval button does not belong to this Slack message context. "
                        "Use the latest proposal.",
                    },
                )
                return True

            assert config.operation_router is not None
            store = WorkflowStore(config.db_path)
            try:
                claimed = store.claim_operation_action(
                    approval.action_id,
                    actor=str(user_id or "unknown"),
                    payload={
                        "token_fingerprint": _token_fingerprint(action_value or ""),
                        "channel_id": channel_id,
                        "thread_ts": thread_ts,
                    },
                )
                if not claimed:
                    self._write_json(
                        200,
                        {
                            "replace_original": False,
                            "text": "This operation approval was already used. Re-open the latest proposal.",
                        },
                    )
                    return True
                store.add_security_event(
                    "slack_operation_started",
                    actor=str(user_id or "unknown"),
                    payload={
                        "action_id": approval.action_id,
                        "token_fingerprint": _token_fingerprint(action_value or ""),
                        "channel_id": channel_id,
                        "thread_ts": thread_ts,
                        "approved_amount": approval.approved_amount,
                        "summary": approval.intent.summary,
                        "params": approval.intent.params,
                    },
                )
            finally:
                store.close()
            _start_operation_background_run(
                db_path=config.db_path,
                router=config.operation_router,
                approval=approval,
                action_value=action_value or "",
                actor=str(user_id or "unknown"),
                channel_id=channel_id,
                thread_ts=thread_ts,
                poster=config.operation_result_poster,
            )
            self._write_json(
                200,
                {
                    "replace_original": False,
                    "response_type": "ephemeral",
                    "text": "Approved. Neyma is operating in the TMS now and will post the verified receipt in-thread.",
                    "metadata": {
                        "action_id": approval.action_id,
                        "status": "RUNNING",
                        "channel_id": channel_id,
                        "thread_ts": thread_ts,
                    },
                },
            )
            return True

        def _handle_slack_events(self, body: bytes) -> None:
            """Slack Events API: an owner's reply in an escalated operation's thread resumes it.

            Fast-acks (Slack's 3s rule) and does the work in the background. Only an authenticated owner
            reply in the authorized channel, in a thread tied to an ESCALATED operation, resumes anything
            — the reply is a trusted command; nothing here obeys arbitrary message content."""
            body_str = body.decode("utf-8", errors="replace")
            try:
                payload = json.loads(body_str)
            except json.JSONDecodeError:
                self._write_json(400, {"error": "invalid Slack event JSON"})
                return
            # URL-verification handshake (Slack sends this when you set the events request URL).
            if payload.get("type") == "url_verification":
                self._write_json(200, {"challenge": payload.get("challenge", "")})
                return
            try:
                verify_slack_signature(
                    config.slack_signing_secret or b"",
                    timestamp=self.headers.get("X-Slack-Request-Timestamp", ""),
                    body=body_str,
                    signature=self.headers.get("X-Slack-Signature", ""),
                )
            except SlackSignatureError:
                self._write_json(401, {"error": "invalid Slack signature"})
                return

            event = payload.get("event") or {}
            # Only act on a human message that is a thread reply; ack everything else fast.
            if (
                config.operation_router is None
                or event.get("type") != "message"
                or event.get("bot_id")
                or event.get("subtype")
                or not event.get("thread_ts")
            ):
                self._write_json(200, {"ok": True})
                return
            user_id = event.get("user")
            channel_id = event.get("channel")
            ok, _reason = authorize_command(
                user_id, channel_id,
                allowed_users=config.allowed_slack_users, allowed_channel=config.allowed_slack_channel,
            )
            if not ok:  # a reply from anyone but the owner in the authorized channel is ignored
                self._write_json(200, {"ok": True})
                return
            thread_ts = event.get("thread_ts")
            event_id = payload.get("event_id") or ""
            store = WorkflowStore(config.db_path)
            try:
                # Dedup Slack's at-least-once event retries so a reply resumes exactly once.
                if event_id and not store.claim_operation_action(
                    f"evt:{event_id}", actor=str(user_id or "owner"), payload={"thread_ts": thread_ts}
                ):
                    self._write_json(200, {"ok": True})
                    return
                resumable = find_resumable_operation(store, thread_ts)
            finally:
                store.close()
            if resumable is None:  # reply not tied to an escalated operation
                self._write_json(200, {"ok": True})
                return
            # Immediate acknowledgement so the owner gets a fast reply while the (slower) run proceeds.
            if config.operation_result_poster is not None:
                try:
                    config.operation_result_poster({
                        "channel_id": channel_id, "thread_ts": thread_ts,
                        "text": "👍 On it — resuming now…", "status": "RESUMING",
                        "lane": resumable.get("lane"),
                    })
                except Exception:  # noqa: BLE001 - the ack is best-effort
                    pass
            _start_resume_background_run(
                db_path=config.db_path,
                router=config.operation_router,
                intent=intent_from_resumable(resumable, str(event.get("text", ""))),
                actor=str(user_id or "owner"),
                channel_id=channel_id,
                thread_ts=thread_ts,
                poster=config.operation_result_poster,
            )
            self._write_json(200, {"ok": True})

        def _handle_slack_command(self, body: bytes) -> None:
            """Verify a Slack slash command and run it (the owner's brake + status surface).

            Slack POSTs ``command``/``text``/``user_name`` form-encoded with the same signing headers
            as interactivity. We verify the signature, then run a lightweight ops command and reply
            ephemerally. Commands: ``pause/resume tms writes``, ``status``, ``show unresolved``.
            """
            if config.slack_signing_secret is None:
                self._write_json(404, {"error": "slack commands are not enabled on this server"})
                return
            timestamp = self.headers.get("X-Slack-Request-Timestamp", "")
            signature = self.headers.get("X-Slack-Signature", "")
            body_str = body.decode("utf-8", errors="replace")
            try:
                verify_slack_signature(
                    config.slack_signing_secret, timestamp=timestamp, body=body_str, signature=signature
                )
            except SlackSignatureError:
                store = WorkflowStore(config.db_path)
                try:
                    store.add_security_event(
                        "slack_request_rejected", actor="system", payload={"failure": "signature", "route": "commands"}
                    )
                finally:
                    store.close()
                self._write_json(401, {"error": "invalid Slack signature"})
                return
            fields = {key: values[0] for key, values in parse_qs(body_str).items()}
            text = (fields.get("text") or "").strip()
            user_id = fields.get("user_id")
            channel_id = fields.get("channel_id")
            actor = user_id or fields.get("user_name") or "slack-user"
            ok, reason = authorize_command(
                user_id,
                channel_id,
                allowed_users=config.allowed_slack_users,
                allowed_channel=config.allowed_slack_channel,
            )
            if not ok:
                store = WorkflowStore(config.db_path)
                try:
                    store.add_security_event(
                        "slack_command_rejected",
                        actor=str(user_id or "unknown"),
                        payload={"failure": "authorization", "reason": reason, "channel_id": channel_id},
                    )
                finally:
                    store.close()
                self._write_json(200, {"response_type": "ephemeral", "text": f"Not authorized: {reason}."})
                return
            ops_control = OpsControl(Path(config.db_path).parent / "ops_control.json")
            store = WorkflowStore(config.db_path)
            try:
                reply = handle_ops_command(
                    text, actor=actor, ops_control=ops_control, store=store, status_file=config.status_file
                )
                if reply.startswith("Commands:") and config.operation_router is not None:
                    proposal = _build_operation_command_proposal(
                        text,
                        signer=config.signer,
                        router=config.operation_router,
                        channel_id=channel_id,
                    )
                    if proposal is not None:
                        self._write_json(200, proposal)
                        return
            finally:
                store.close()
            # Ephemeral: only the operator who ran the command sees the reply.
            self._write_json(200, {"response_type": "ephemeral", "text": reply})

        def _write_json(self, http_status: int, data: dict) -> None:
            payload = json.dumps(data).encode("utf-8")
            self.send_response(http_status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _write(self, response: CallbackResponse) -> None:
            accept = self.headers.get("Accept", "")
            if "application/json" in accept:
                payload = response.model_dump_json(indent=2).encode("utf-8")
                content_type = "application/json; charset=utf-8"
            else:
                payload = _render_html(response).encode("utf-8")
                content_type = "text/html; charset=utf-8"
            self.send_response(response.http_status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            # Keep local dogfood output quiet; audit events remain in WorkflowStore.
            return

    return NeymaActionCallbackHandler


def run_callback_server(
    *,
    host: str,
    port: int,
    db_path: str,
    signer: DeliverySigner,
    follow_up_loads: dict[str, FreightLoadForReconciliation] | None = None,
    slack_signing_secret: bytes | str | None = None,
    post_action_executor: Callable[[WorkflowStore, DeliveryActionOutcome], None] | None = None,
    status_file: str | None = None,
    operation_router: OperationRouter | None = None,
    operation_result_poster: Callable[[dict], None] | None = None,
    allowed_slack_users: tuple[str, ...] = (),
    allowed_slack_channel: str | None = None,
) -> ThreadingHTTPServer:
    """Create a local callback server. Caller owns ``serve_forever`` / shutdown."""
    secret = (
        slack_signing_secret.encode("utf-8") if isinstance(slack_signing_secret, str) else slack_signing_secret
    )
    handler = make_callback_handler(
        CallbackAppConfig(
            db_path=db_path,
            signer=signer,
            follow_up_loads=follow_up_loads,
            slack_signing_secret=secret,
            post_action_executor=post_action_executor,
            status_file=status_file,
            operation_router=operation_router,
            operation_result_poster=operation_result_poster,
            allowed_slack_users=allowed_slack_users,
            allowed_slack_channel=allowed_slack_channel,
        )
    )
    return ThreadingHTTPServer((host, port), handler)


class SlackOperationApproval(BaseModel):
    type: str = "operate_approval"
    intent: CommandIntent
    action_id: str
    approved_amount: str | None = None
    expected_channel_id: str | None = None
    expected_thread_ts: str | None = None
    issued_at: float
    expires_at: float


def build_slack_operation_approval_value(
    intent: CommandIntent,
    signer: DeliverySigner,
    *,
    approved_amount: str | None = None,
    expected_channel_id: str | None = None,
    expected_thread_ts: str | None = None,
    issued_at: datetime | None = None,
    ttl_seconds: int = DEFAULT_OPERATION_TOKEN_TTL_SECONDS,
    action_id: str | None = None,
) -> str:
    """Encode a bounded operation approval payload for a Slack button value."""
    if intent.kind != CommandKind.OPERATE:
        raise ValueError("Slack operation approvals require an OPERATE intent")
    issued = issued_at or datetime.now(timezone.utc)
    claims = SlackOperationApproval(
        intent=intent,
        action_id=action_id or uuid.uuid4().hex,
        approved_amount=approved_amount,
        expected_channel_id=expected_channel_id,
        expected_thread_ts=expected_thread_ts,
        issued_at=issued.timestamp(),
        expires_at=issued.timestamp() + ttl_seconds,
    ).model_dump(mode="json")
    return _encode_operation_approval(claims, signer)


def _parse_slack_payload(body: str) -> dict:
    fields = parse_qs(body)
    raw = fields.get("payload")
    if not raw:
        raise SlackError("Slack interaction payload missing")
    try:
        payload = json.loads(raw[0])
    except json.JSONDecodeError as exc:
        raise SlackError("Slack interaction payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise SlackError("Slack interaction payload must be an object")
    return payload


def _first_slack_action_value(payload: dict) -> str | None:
    actions = payload.get("actions") or []
    if not actions or not isinstance(actions[0], dict):
        return None
    value = actions[0].get("value")
    return str(value) if value else None


def _slack_thread_ts(payload: dict) -> str | None:
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    container = payload.get("container") if isinstance(payload.get("container"), dict) else {}
    value = (
        message.get("thread_ts")
        or message.get("ts")
        or container.get("thread_ts")
        or container.get("message_ts")
    )
    return str(value) if value else None


def _parse_operation_approval_value(value: str | None, signer: DeliverySigner) -> SlackOperationApproval | None:
    if not value:
        return None
    if value.count(".") != 1:
        # Non-operation Slack buttons carry signed review-action tokens here; let those fall through.
        return None
    try:
        raw = _decode_operation_approval(value, signer)
    except DeliverySignatureError as exc:
        raise SlackError("Slack operation approval signature is invalid") from exc
    if not isinstance(raw, dict) or raw.get("type") != "operate_approval":
        return None
    try:
        approval = SlackOperationApproval.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - malformed operation approval falls through as malformed
        raise SlackError("Slack operation approval payload is malformed") from exc
    if approval.intent.kind != CommandKind.OPERATE:
        raise SlackError("Slack operation approval must carry an OPERATE intent")
    if datetime.now(timezone.utc).timestamp() > approval.expires_at:
        raise SlackError("Slack operation approval is expired")
    return approval


def _encode_operation_approval(claims: dict, signer: DeliverySigner) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(signer.secret, body, hashlib.sha256).hexdigest()
    return f"{body.decode('ascii')}.{signature}"


def _decode_operation_approval(token: str, signer: DeliverySigner) -> dict:
    body_part, signature = token.split(".", 1)
    body = body_part.encode("ascii")
    expected = hmac.new(signer.secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise DeliverySignatureError("operation approval signature mismatch")
    try:
        return json.loads(base64.urlsafe_b64decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise DeliverySignatureError("operation approval payload is not valid JSON") from exc


def _verify_operation_approval_value(value: str | None, signer: DeliverySigner) -> SlackOperationApproval | None:
    return _parse_operation_approval_value(value, signer)


def _intent_with_signed_approved_amount(approval: SlackOperationApproval) -> CommandIntent:
    if not approval.approved_amount:
        return approval.intent
    params = dict(approval.intent.params or {})
    params["approved_amount"] = approval.approved_amount
    return CommandIntent(kind=approval.intent.kind, summary=approval.intent.summary, params=params)


def _record_run_diagnosis(store, result, *, actor, channel_id, thread_ts) -> object:
    """Diagnose a finished run and, when it wasn't clean, record it as a learnable lesson. Returns the
    diagnosis so the caller can append the 'why' to the receipt."""
    from .run_diagnostics import diagnose_run

    diag = diagnose_run(
        getattr(result, "steps", None) or [],
        status=str(getattr(result, "status", "")),
        note=str(getattr(result, "note", "") or ""),
    )
    if not diag.is_clean():
        try:
            store.add_security_event("run_diagnosis", actor=actor, payload={
                "channel_id": channel_id, "thread_ts": thread_ts,
                "lane": getattr(result, "lane", None), "outcome": diag.outcome,
                "summary": diag.summary, "repeated_failures": diag.repeated_failures,
                "dead_ends": diag.dead_ends, "suggested_fixes": diag.suggested_fixes,
                "exhausted": diag.exhausted_steps,
            })
        except Exception:  # noqa: BLE001
            pass
    return diag


def _receipt_text(result, amount, diag) -> str:
    """Owner receipt, with the 'why it struggled' appended when the run wasn't clean."""
    from .roi_ledger import receipt_from_result, render_operation_receipt
    from .run_diagnostics import render_diagnosis

    text = render_operation_receipt(receipt_from_result(result, amount=amount))
    if diag is not None and not diag.is_clean():
        text += "\n" + render_diagnosis(diag)
    return text


def _start_operation_background_run(
    *,
    db_path: str,
    router: OperationRouter,
    approval: SlackOperationApproval,
    action_value: str,
    actor: str,
    channel_id: str | None,
    thread_ts: str | None,
    poster: Callable[[dict], None] | None,
) -> threading.Thread:
    def _run() -> None:
        store = WorkflowStore(db_path)
        result: OperationResult
        try:
            result = router.run(
                _intent_with_signed_approved_amount(approval),
                approve=_single_consequential_approval(),
            )
            event_type = "slack_operation_applied"
            payload = _operation_receipt_payload(
                approval,
                action_value=action_value,
                channel_id=channel_id,
                thread_ts=thread_ts,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001 - background operation failures must still receipt
            result = OperationResult(
                "FAILED",
                None,
                "operation failed before it could complete; check the audit and retry with a fresh approval.",
                [],
            )
            event_type = "slack_operation_failed"
            payload = {
                "action_id": approval.action_id,
                "token_fingerprint": _token_fingerprint(action_value),
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "approved_amount": approval.approved_amount,
                "summary": approval.intent.summary,
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            }
        try:
            store.add_security_event(event_type, actor=actor, payload=payload)
            diag = _record_run_diagnosis(store, result, actor=actor, channel_id=channel_id, thread_ts=thread_ts)
        finally:
            store.close()
        if poster is not None:
            try:
                poster(
                    {
                        "channel_id": channel_id,
                        "thread_ts": thread_ts,
                        "text": _receipt_text(result, approval.approved_amount, diag),
                        "status": result.status,
                        "lane": result.lane,
                    }
                )
            except Exception:
                return

    thread = threading.Thread(target=_run, name=f"neyma-operation-{approval.action_id[:8]}", daemon=True)
    thread.start()
    return thread


def _learn_correction(db_path: str, intent, result) -> None:
    """When an owner's thread reply gets the run unstuck, remember it — the reply becomes a BUSINESS
    fact (e.g. "it's order #1002") so next time Neyma knows it instead of asking again. Best-effort;
    never a money value; only kept when the guidance actually helped (DONE/PREPARED)."""
    try:
        guidance = (intent.params or {}).get("operator_guidance")
        if not guidance or getattr(result, "status", "") not in ("DONE", "PREPARED"):
            return
        subject = (intent.params or {}).get("customer") or (intent.params or {}).get("carrier") \
            or (intent.params or {}).get("load_ref")
        from pathlib import Path as _Path

        from .knowledge import FactKind, KnowledgeBase

        KnowledgeBase(_Path(db_path).parent / "agent_memory.json").learn(
            str(guidance), tenant="default", kind=FactKind.BUSINESS, subject=subject, source="correction",
        )
    except Exception:  # noqa: BLE001 - learning must never break the run
        pass


def _start_resume_background_run(
    *,
    db_path: str,
    router: OperationRouter,
    intent,
    actor: str,
    channel_id: str | None,
    thread_ts: str | None,
    poster: Callable[[dict], None] | None,
) -> threading.Thread:
    """Resume an escalated operation from an owner's thread reply (intent already carries guidance)."""
    amount = (intent.params or {}).get("approved_amount")

    def _run() -> None:
        store = WorkflowStore(db_path)
        try:
            try:
                result = router.run(intent, approve=_single_consequential_approval())
                event_type, extra = "slack_operation_applied", {
                    "params": intent.params, "lane": result.lane, "status": result.status,
                    "note": result.note, "steps": result.steps,
                }
            except Exception as exc:  # noqa: BLE001 - a resume failure must still receipt
                result = OperationResult("FAILED", None, "resume failed before it could complete.", [])
                event_type, extra = "slack_operation_failed", {
                    "error_type": type(exc).__name__, "error": str(exc)[:500],
                }
            payload = {
                "channel_id": channel_id, "thread_ts": thread_ts,
                "approved_amount": amount, "summary": intent.summary, "resumed": True, **extra,
            }
            store.add_security_event(event_type, actor=actor, payload=payload)
            diag = _record_run_diagnosis(store, result, actor=actor, channel_id=channel_id, thread_ts=thread_ts)
            _learn_correction(db_path, intent, result)
        finally:
            store.close()
        if poster is not None:
            try:
                poster({
                    "channel_id": channel_id, "thread_ts": thread_ts,
                    "text": _receipt_text(result, amount, diag),
                    "status": result.status, "lane": result.lane,
                })
            except Exception:  # noqa: BLE001
                return

    thread = threading.Thread(target=_run, name="neyma-resume", daemon=True)
    thread.start()
    return thread


def _operation_receipt_payload(
    approval: SlackOperationApproval,
    *,
    action_value: str,
    channel_id: str | None,
    thread_ts: str | None,
    result: OperationResult,
) -> dict:
    return {
        "action_id": approval.action_id,
        "token_fingerprint": _token_fingerprint(action_value),
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "approved_amount": approval.approved_amount,
        "summary": approval.intent.summary,
        "params": approval.intent.params,
        "lane": result.lane,
        "status": result.status,
        "note": result.note,
        "steps": result.steps,
    }


def _build_operation_command_proposal(
    text: str,
    *,
    signer: DeliverySigner,
    router: OperationRouter,
    channel_id: str | None,
) -> dict | None:
    amount = _extract_command_amount(text)
    if amount is None:
        return {
            "response_type": "ephemeral",
            "text": "I can propose that operation, but I need an explicit approved amount first. "
            "Example: `invoice LD-560006 for Acme amount 2850.00`.",
        }
    intent = CommandIntent(
        kind=CommandKind.OPERATE,
        summary=text,
        params={"approved_amount": amount},
    )
    lane = router.lane_for(intent)
    if lane is None:
        return {
            "response_type": "ephemeral",
            "text": "I won't improvise on that request because no known workflow lane handles it yet.",
        }
    value = build_slack_operation_approval_value(
        intent,
        signer,
        approved_amount=amount,
        expected_channel_id=channel_id,
    )
    return {
        "response_type": "in_channel",
        "text": f"Neyma proposal: {lane.name} for ${amount}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "Neyma operation proposal"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Lane*\n{lane.name}"},
                    {"type": "mrkdwn", "text": f"*Approved amount*\n${amount}"},
                ],
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Request*\n{text}"}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Approving starts one bounded TMS operation. Neyma will post a verified receipt in-thread.",
                    }
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "approve_operation_0",
                        "text": {"type": "plain_text", "text": f"Approve ${amount}"},
                        "style": "primary",
                        "value": value,
                    }
                ],
            },
        ],
    }


def _extract_command_amount(text: str) -> str | None:
    match = re.search(r"(?:amount|for|\$)\s*\$?([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text, flags=re.IGNORECASE)
    if not match:
        return None
    return f"{float(match.group(1).replace(',', '')):.2f}"


def _operation_context_mismatch(
    approval: SlackOperationApproval,
    *,
    channel_id: str | None,
    thread_ts: str | None,
) -> str | None:
    if approval.expected_channel_id and channel_id != approval.expected_channel_id:
        return "channel_mismatch"
    if approval.expected_thread_ts and thread_ts != approval.expected_thread_ts:
        return "thread_mismatch"
    return None


def _single_consequential_approval() -> Callable[[object], bool]:
    approved = {"used": False}

    def approve(_action) -> bool:
        if approved["used"]:
            return False
        approved["used"] = True
        return True

    return approve


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _run_post_action_executor(
    store: WorkflowStore,
    outcome: DeliveryActionOutcome,
    executor: Callable[[WorkflowStore, DeliveryActionOutcome], None],
) -> None:
    try:
        executor(store, outcome)
    except Exception as exc:  # noqa: BLE001 - post-action work must not break callback ack
        store.add_audit_event(
            outcome.run_id,
            "post_action_executor_failed",
            actor="system",
            payload={"error_type": type(exc).__name__, "error": str(exc)[:500]},
        )


def _render_html(response: CallbackResponse) -> str:
    detail = response.rendered_message or response.message
    return f"""<!doctype html>
<html><head>
  <meta charset="utf-8">
  <title>{_escape(response.title)}</title>
  <style>
    body {{ font-family: Inter, Arial, sans-serif; color: #172033; margin: 32px; max-width: 920px; }}
    .status {{ display: inline-block; padding: 6px 10px; border-radius: 6px; background: #edf7ee; color: #176b37; font-weight: 700; }}
    .status.rejected {{ background: #fff1f0; color: #9f1d16; }}
    pre {{ white-space: pre-wrap; background: #f7f8fb; border: 1px solid #d9deea; padding: 16px; border-radius: 8px; }}
  </style>
</head><body>
  <p class="status {'rejected' if response.status == CallbackStatus.REJECTED else ''}">{_escape(response.status)}</p>
  <h1>{_escape(response.title)}</h1>
  <p>{_escape(response.message)}</p>
  <pre>{_escape(detail)}</pre>
</body></html>"""


def _method_not_allowed(message: str) -> CallbackResponse:
    return CallbackResponse(
        status=CallbackStatus.REJECTED,
        http_status=405,
        title="Method not allowed",
        message=message,
        errors=["method not allowed"],
    )


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
