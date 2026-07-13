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
    workspace: str | None = None
    operation_cdp_url: str | None = None
    operation_url_filter: str | None = None
    # Optional fake/live Slack approval bridge for the bounded request->agent->result router. This is
    # callback-only: it returns a Slack response body and does not post or send on its own.
    operation_router: OperationRouter | None = None
    operation_result_poster: Callable[[dict], None] | None = None
    allowed_slack_users: tuple[str, ...] = ()
    allowed_slack_channel: str | None = None
    # Optional cheap completer for natural-language routing of unrecognized /neyma commands ("what's
    # outstanding?" -> the right read; "invoice the Northbound load" -> a gated proposal). Owner-only.
    nl_completer: Callable[[str], str] | None = None
    # Optional resolver: given a load ref, return that load's Total from the TMS. Lets "bill load 105"
    # fetch the deterministic amount itself instead of asking the owner to type it. The amount still
    # comes from the TMS record, never the model — the money fence is unchanged.
    load_amount_resolver: Callable[[str], "str | None"] | None = None
    # Optional reader of unpaid receivables from the TMS /invoices list, so "what's outstanding / who
    # owes us / aging" answers with a live aged-AR digest. Read-only — never sends a dunning note.
    # Returns the unpaid receivables, or None if the TMS couldn't be read (busy/error) — None must NOT
    # be shown as "nothing owed". ar_terms_days, if set (e.g. 30 for Net-30), lets the digest flag
    # genuinely past-due invoices; without it the digest makes no past-due claim.
    receivables_reader: Callable[[], "list | None"] | None = None
    ar_aging_min_days: int = 0
    ar_terms_days: int | None = None
    # Returns {"status_counts", "ready", "receivables"} for the "what's happening?" snapshot, or None
    # when the TMS couldn't be read (never rendered as an all-clear).
    tms_brief_reader: Callable[[], "dict | None"] | None = None
    # Optional reader: given a load ref, return that load's live row {status, customer, total, invoiced}
    # from the TMS /loads list, or None if unreadable/not found. Powers "what's the story on load X"
    # (answer, don't misroute to system health) and the already-invoiced guard on "bill X" (no double-bill).
    load_state_reader: Callable[[str], "dict | None"] | None = None
    # Optional reader: given a load ref, return the list of document filenames on that load (its FileSafe
    # attachments), or None if unreadable. Powers "did the POD get attached to 101?" (answer the question
    # instead of re-proposing the attach) and document-audit reads.
    load_docs_reader: Callable[[str], "list | None"] | None = None


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
                    # Not a single approval — is it the digest's [Approve all N] batch button?
                    batch = _parse_operation_batch_value(action_value, config.signer)
                    if batch is not None:
                        return self._handle_operation_batch_approval(payload, batch, action_value or "")
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
                if approval.approved_amount:
                    store.record_operation_token_amount(
                        token_fingerprint=_token_fingerprint(action_value or ""),
                        action_id=approval.action_id,
                        approved_amount=approval.approved_amount,
                        payload={"summary": approval.intent.summary, "params": approval.intent.params},
                    )
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

        def _handle_operation_batch_approval(self, payload: dict, batch: dict, action_value: str) -> bool:
            """The digest's [Approve all N] tap: same authorization + single-use + channel-binding as a
            single approval; each item then runs the full per-load fence + commit-once in one background
            pass with ONE consolidated receipt. The tap is the owner's thumbprint on the exact signed
            (load, customer, amount) list shown in the digest."""
            user_id = ((payload.get("user") or {}).get("id") or (payload.get("user") or {}).get("username"))
            channel_id = (
                (payload.get("channel") or {}).get("id")
                or (payload.get("container") or {}).get("channel_id")
                or payload.get("channel_id")
            )
            thread_ts = _slack_thread_ts(payload)
            ok, reason = authorize_command(
                user_id, channel_id,
                allowed_users=config.allowed_slack_users, allowed_channel=config.allowed_slack_channel,
            )
            if not ok or config.operation_router is None:
                store = WorkflowStore(config.db_path)
                try:
                    store.add_security_event(
                        "slack_operation_rejected", actor=str(user_id or "unknown"),
                        payload={"failure": "authorization", "reason": reason, "batch": True},
                    )
                finally:
                    store.close()
                self._write_json(200, {"replace_original": False, "text": f"Not authorized: {reason}."})
                return True
            expected_channel = batch.get("expected_channel_id")
            if expected_channel and channel_id and expected_channel != channel_id:
                self._write_json(200, {"replace_original": False,
                                       "text": "That Approve-all button belongs to a different channel."})
                return True
            store = WorkflowStore(config.db_path)
            try:
                claimed = store.claim_operation_action(
                    str(batch["action_id"]), actor=str(user_id or "unknown"),
                    payload={"batch": True, "items": len(batch["items"]), "channel_id": channel_id},
                )
                if not claimed:
                    self._write_json(200, {"replace_original": False,
                                           "text": "This Approve-all was already used. Wait for the next digest."})
                    return True
                store.add_security_event(
                    "slack_batch_operation_started", actor=str(user_id or "unknown"),
                    payload={"action_id": batch["action_id"], "lane": batch.get("lane"),
                             "items": batch["items"], "channel_id": channel_id, "thread_ts": thread_ts},
                )
            finally:
                store.close()
            _start_batch_background_run(
                db_path=config.db_path, router=config.operation_router, batch=batch,
                actor=str(user_id or "unknown"), channel_id=channel_id, thread_ts=thread_ts,
                poster=config.operation_result_poster,
            )
            n = len(batch["items"])
            self._write_json(200, {
                "replace_original": False, "response_type": "ephemeral",
                "text": f"Approved — posting {n} invoice{'s' if n != 1 else ''} to the TMS now. "
                        "One consolidated receipt will follow in-thread.",
            })
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
            reply_text = str(event.get("text", ""))
            # Resume ONLY when there's a pending op AND the reply is a resume signal ("submit"/"go"/…).
            # Any other message — a question, a new command — is answered conversationally, even inside a
            # thread that has a staged op, so "who owes us money?" is never hijacked into a resume.
            if resumable is None or not _is_resume_signal(reply_text):
                _respond_conversationally(
                    text=reply_text, actor=str(user_id or "owner"),
                    channel_id=channel_id, thread_ts=thread_ts, config=config,
                    pending_op=resumable,
                )
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
            # /neyma uses the SAME conversational recognizer as a thread reply — reads, controls, AR
            # aging, and gated operations all work, so the owner gets an answer, not a command dump.
            ops_control = OpsControl(Path(config.db_path).parent / "ops_control.json")
            store = WorkflowStore(config.db_path)
            try:
                routed = route_conversational_message(
                    text, actor=actor, channel_id=channel_id, config=config,
                    ops_control=ops_control, store=store,
                )
            finally:
                store.close()
            if routed.get("proposal") is not None:
                self._write_json(200, routed["proposal"])   # an operation -> its Approve-button proposal
                return
            # Ephemeral: only the operator who ran the command sees the reply.
            self._write_json(200, {"response_type": "ephemeral", "text": routed.get("text", "")})

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
    nl_completer: Callable[[str], str] | None = None,
    load_amount_resolver: Callable[[str], "str | None"] | None = None,
    receivables_reader: Callable[[], "list | None"] | None = None,
    tms_brief_reader: Callable[[], "dict | None"] | None = None,
    load_state_reader: Callable[[str], "dict | None"] | None = None,
    load_docs_reader: Callable[[str], "list | None"] | None = None,
    operation_cdp_url: str | None = None,
    operation_url_filter: str | None = None,
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
            workspace=str(Path(db_path).parent),
            operation_cdp_url=operation_cdp_url,
            operation_url_filter=operation_url_filter,
            operation_router=operation_router,
            operation_result_poster=operation_result_poster,
            allowed_slack_users=allowed_slack_users,
            allowed_slack_channel=allowed_slack_channel,
            nl_completer=nl_completer,
            load_amount_resolver=load_amount_resolver,
            receivables_reader=receivables_reader,
            tms_brief_reader=tms_brief_reader,
            load_state_reader=load_state_reader,
            load_docs_reader=load_docs_reader,
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


def build_slack_batch_approval_value(
    items: list[dict],
    signer: DeliverySigner,
    *,
    lane: str = "raise_invoice",
    expected_channel_id: str | None = None,
    issued_at: datetime | None = None,
    ttl_seconds: int = DEFAULT_OPERATION_TOKEN_TTL_SECONDS,
    action_id: str | None = None,
) -> str:
    """Encode the digest's [Approve all N] button: ONE signed, single-use, channel-bound token whose
    items are the exact (load_ref, customer, amount) rows shown in the digest. The tap is the owner's
    informed thumbprint on that exact list — amounts are the TMS totals baked in at signing time, so the
    model can't alter them, and each item still runs the full per-load fence + commit-once."""
    if not items:
        raise ValueError("a batch approval needs at least one item")
    issued = issued_at or datetime.now(timezone.utc)
    claims = {
        "type": "operate_batch_approval",
        "action_id": action_id or uuid.uuid4().hex,
        "lane": lane,
        "items": [
            {"load_ref": str(i["load_ref"]), "customer": str(i.get("customer") or ""),
             "amount": str(i["amount"])}
            for i in items
        ],
        "expected_channel_id": expected_channel_id,
        "issued_at": issued.timestamp(),
        "expires_at": issued.timestamp() + ttl_seconds,
    }
    return _encode_operation_approval(claims, signer)


def _parse_operation_batch_value(value: str | None, signer: DeliverySigner) -> dict | None:
    """Verify + decode an [Approve all] batch token. Returns the claims dict or None (not a batch)."""
    if not value or value.count(".") != 1:
        return None
    try:
        raw = _decode_operation_approval(value, signer)
    except DeliverySignatureError as exc:
        raise SlackError("Slack batch approval signature is invalid") from exc
    if not isinstance(raw, dict) or raw.get("type") != "operate_batch_approval":
        return None
    items = raw.get("items")
    if not isinstance(items, list) or not items or not all(
        isinstance(i, dict) and i.get("load_ref") and i.get("amount") for i in items
    ):
        raise SlackError("Slack batch approval payload is malformed")
    if datetime.now(timezone.utc).timestamp() > float(raw.get("expires_at") or 0):
        raise SlackError("Slack batch approval is expired")
    return raw


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


def _extract_load_ref(text: str) -> str | None:
    """Pull a load reference out of a plain-English request ("bill load 105" -> "105"; "invoice LD-4471"
    -> "LD-4471"). Prefers an explicit load/order/# marker; falls back to a standalone 2–6 digit number."""
    text = text or ""
    # Money tokens must never read as a record ref ("invoice Acme amount 500.00" is NOT load 500).
    text = re.sub(r"(?:amount\s+|\$\s*)\$?\d[\d,]*(?:\.\d{1,2})?", " ", text, flags=re.I)
    text = re.sub(r"\b\d[\d,]*\.\d{1,2}\b", " ", text)          # bare decimals are amounts, not refs
    m = re.search(r"\b([A-Za-z]{2,4}-?\d{1,6})\b", text)      # a lettered ref: LD-4471, INV-5, PO1234
    if m:
        return m.group(1)
    m = re.search(r"\b(?:load|order|invoice)\s*#?\s*(\d{2,6})\b", text, re.I)   # "load 105", "invoice 560009"
    if m:
        return m.group(1)
    m = re.search(r"#\s*(\d{2,6})\b", text)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{2,6})\b", text)   # a bare number, only reached when no amount is present
    return m.group(1) if m else None


_AGING_HINTS = (
    "aging", "receivable", "past due", "overdue", "who owes", "owe us", "owes us",
    "unpaid", "collections", "outstanding invoice", "outstanding ar", "outstanding balance",
)


def _is_aging_query(text: str) -> bool:
    t = (text or "").lower()
    return any(h in t for h in _AGING_HINTS)


_BRIEF_HINTS = ("what's happening", "whats happening", "what is happening", "brief", "snapshot",
                "morning update", "rundown", "run down", "how do things look", "state of the tms",
                "tms status", "whats going on", "what's going on")


def _is_brief_query(text: str) -> bool:
    t = (text or "").lower()
    return any(h in t for h in _BRIEF_HINTS)


def render_tms_brief(status_counts: dict, ready_rows: list, aged: list) -> str:
    """The owner's pocket snapshot: loads by status, what's ready to bill, what's outstanding. Read-only
    and honest — sections it couldn't read say so instead of pretending zero."""
    from decimal import Decimal
    lines = [":truck: *TMS right now:*"]
    if status_counts:
        by = " · ".join(f"{n} {s}" for s, n in sorted(status_counts.items(), key=lambda kv: -kv[1]))
        lines.append(f"• Loads: {by}")
    else:
        lines.append("• Loads: couldn't read the loads list just now.")
    if ready_rows:
        total = sum(Decimal(str(r["amount"])) for r in ready_rows)
        lines.append(f"• Ready to bill: {len(ready_rows)} load{'s' if len(ready_rows) != 1 else ''} (${total:,.2f}) — the next digest will carry the buttons.")
    else:
        lines.append("• Ready to bill: nothing new.")
    if aged:
        out_total = sum(Decimal(r["balance_due"]) for r in aged)
        pd = [r for r in aged if r.get("past_due")]
        tail = f", {len(pd)} past due" if pd else ""
        lines.append(f"• Outstanding AR: ${out_total:,.2f} across {len(aged)} invoice{'s' if len(aged) != 1 else ''}{tail} — ask *who owes us the most* for the ranking.")
    else:
        lines.append("• Outstanding AR: all paid (or unreadable just now — ask *who owes us* to re-check).")
    return "\n".join(lines)


_LOAD_QUERY_HINTS = ("story", "status", "where is", "where's", "wheres", "going on", "happening",
                     "details", "detail", "look up", "pull up", "show me", "what about", "how is",
                     "how's", "hows", "update on", "up with", "tell me about")
_LOAD_COMMAND_VERBS = ("bill", "invoice", "attach", "file ", "upload", "credit", "pay ", "record",
                       "create", "mark ", "delete", "adjust")


def _is_load_query(text: str) -> bool:
    """Is this a QUESTION about one specific load ("what's the story on load 101", "status of 88")?
    It must name a load ref, ask a story/status question, and NOT be a command verb — so it is answered
    about that load instead of falling through to the system-health/readiness report (which is a
    misroute and also leaks internal ops state to the owner). Command verbs route to operations."""
    t = (text or "").lower()
    if not _extract_load_ref(text):
        return False
    if any(v in t for v in _LOAD_COMMAND_VERBS):
        return False
    return any(h in t for h in _LOAD_QUERY_HINTS)


_COMPLAINT_HINTS = ("too long", "too slow", "so slow", "taking forever", "this sucks", "come on man",
                    "wtf", "frustrat", "annoying", "not working", "isn't working", "isnt working",
                    "broken", "ugh", "useless", "hurry up", "what's the holdup", "whats the holdup")


def _is_complaint(text: str) -> bool:
    """Owner venting / frustration (not an actionable request). Deserves a human acknowledgement, not the
    generic 'I didn't quite get that' fallback."""
    return any(h in (text or "").lower() for h in _COMPLAINT_HINTS)


_DOC_WORDS = ("pod", "proof of delivery", "bol", "bill of lading", "rate con", "document", "paperwork",
              "attachment", "attached", "filed", "on file")
_QUESTION_STARTS = ("did", "do ", "does", "is ", "are ", "has ", "have ", "was ", "were ", "any ", "what")


def _is_doc_status_query(text: str) -> bool:
    """Is this a QUESTION about whether a document is on a load ("did the POD get attached to 101?",
    "do we have the BOL for 88?")? It must name a load, mention a document, and be interrogative — so it
    is ANSWERED from the load's document list instead of being (mis)read as a command to attach again."""
    t = (text or "").lower().strip()
    if not _extract_load_ref(text):
        return False
    if "?" not in t and not t.startswith(_QUESTION_STARTS):
        return False
    return any(w in t for w in _DOC_WORDS)


def _render_load_docs(ref: str, docs: list, text: str) -> str:
    """Answer a document-status question from the load's attachment list."""
    low = (text or "").lower()
    want = ("POD" if "pod" in low or "proof of delivery" in low
            else "BOL" if "bol" in low or "bill of lading" in low
            else "rate con" if "rate con" in low else "")
    if not docs:
        return f":page_facing_up: Load {ref} has *no documents on file* yet" + (f" — no {want}." if want else ".")
    if want:
        match = [d for d in docs if want.replace(" ", "").lower() in d.lower().replace(" ", "")
                 or (want == "POD" and "pod" in d.lower()) or (want == "BOL" and "bol" in d.lower())]
        if match:
            return f":white_check_mark: Yes — load {ref} has the {want} on file: {', '.join(match)}."
        return (f":warning: No {want} on load {ref} yet. On file: {', '.join(docs)}." if docs
                else f":warning: No {want} on load {ref} yet.")
    return f":page_facing_up: Load {ref} documents on file: {', '.join(docs)}."


def _render_load_state(state: dict) -> str:
    """The per-load 'story' answer from the TMS /loads row: status, customer, total, billing state."""
    ref = state.get("load_ref")
    status = (state.get("status") or "").strip()
    cust = (state.get("customer") or "").strip()
    total = (state.get("total") or "").strip()
    parts = [f":package: *Load {ref}*"]
    if cust:
        parts.append(cust)
    if status:
        parts.append(f"status *{status}*")
    if total:
        parts.append(total)
    line = " · ".join(parts)
    low = status.lower()
    if "invoiced" in low:
        line += "\n_Already invoiced — nothing to bill._"
    elif "delivered" in low:
        line += "\n_Delivered — ready to bill (say *bill it*)._"
    return line


_RESUME_WORDS = {
    "submit", "commit", "approve", "approved", "confirm", "confirmed", "proceed",
    "yes", "yep", "yeah", "okay", "retry",   # note: NOT "resume" (that's the 'resume tms writes' control)
}
_RESUME_PHRASES = ("go ahead", "do it", "send it", "try again", "run it", "go for it", "commit it")


def _is_resume_signal(text: str) -> bool:
    """Does this thread reply mean 'continue/commit the pending operation' (vs a new question)? Only a
    resume signal should resume — otherwise a plain question like 'who owes us money?' would hijack the
    staged op instead of being answered."""
    t = " ".join((text or "").lower().split())
    if not t:
        return False
    if set(re.findall(r"[a-z']+", t)) & _RESUME_WORDS:
        return True
    return any(p in t for p in _RESUME_PHRASES)


def route_conversational_message(text, *, actor, channel_id, config, ops_control, store) -> dict:
    """The conversational assistant surface: interpret a free-text owner message and produce a response —
    an immediate ANSWER for a read/control, or a gated PROPOSAL (money actions carry the same signed
    Approve button + fence as everywhere else). Returns ``{'text': str}`` and/or ``{'proposal': dict}``.

    Reuses the exact interpreter + gates the ``/neyma`` slash path uses, so nothing here bypasses them —
    the owner just no longer needs the slash prefix; they reply to Neyma in plain English and it acts.
    """
    # "What's happening?" -> the pocket TMS snapshot (loads by status + ready-to-bill + outstanding AR).
    if _is_brief_query(text) and getattr(config, "tms_brief_reader", None) is not None:
        brief = config.tms_brief_reader()
        if brief is None:
            return {"text": ":warning: I couldn't read the TMS just now (browser busy or unreachable) — "
                            "ask me again in a moment."}
        from datetime import date

        from .ar_collections import aged_unpaid
        aged = aged_unpaid(brief.get("receivables") or [], as_of=date.today(),
                           min_days=getattr(config, "ar_aging_min_days", 0),
                           terms_days=getattr(config, "ar_terms_days", None))
        return {"text": render_tms_brief(brief.get("status_counts") or {}, brief.get("ready") or [], aged)}
    # AR aging is a read: "what's outstanding / who owes us / aging" -> a live aged-receivables digest.
    if _is_aging_query(text) and getattr(config, "receivables_reader", None) is not None:
        from datetime import date

        from .ar_collections import aged_unpaid, render_aging_digest
        receivables = config.receivables_reader()
        if receivables is None:
            # A busy/failed read must NOT render as "nothing owed" — a false all-clear on cash is worse
            # than an error. Say we couldn't read it.
            return {"text": ":warning: I couldn't read the invoices just now (the browser is busy with a "
                            "write, or the TMS didn't respond) — ask me again in a moment."}
        aged = aged_unpaid(receivables, as_of=date.today(),
                           min_days=getattr(config, "ar_aging_min_days", 0),
                           terms_days=getattr(config, "ar_terms_days", None))
        # "who owes us the MOST / top / biggest debtors" -> ranked by customer (the chief-of-staff view);
        # otherwise the per-invoice outstanding digest.
        if re.search(r"\b(most|top|biggest|largest|rank)\b", (text or "").lower()):
            from .ar_collections import render_top_debtors
            return {"text": render_top_debtors(aged)}
        return {"text": render_aging_digest(aged)}
    # Owner venting ("this is taking too long") -> a human acknowledgement, not the generic fallback.
    if _is_complaint(text):
        return {"text": "I hear you — I'm on it. If something's slow or looks wrong, tell me the load "
                        "(*what's the story on load 105*) or ask *what's happening* and I'll get you a "
                        "straight answer."}
    # A document-status QUESTION ("did the POD get attached to 101?") is ANSWERED from the load's
    # document list — never (mis)read as a command to attach it again.
    if _is_doc_status_query(text) and getattr(config, "load_docs_reader", None) is not None:
        ref = _extract_load_ref(text)
        docs = config.load_docs_reader(ref) if ref else None
        if docs is None:
            return {"text": f":warning: I couldn't read load {ref}'s documents just now — ask me again in a moment."}
        return {"text": _render_load_docs(ref, docs, text)}
    # A per-load QUESTION ("what's the story on load 101") is answered about THAT load — it must never
    # fall through to handle_ops_command and come back as the system-health/pilot-readiness report.
    if _is_load_query(text) and getattr(config, "load_state_reader", None) is not None:
        ref = _extract_load_ref(text)
        state = config.load_state_reader(ref) if ref else None
        if state is None:
            return {"text": f":warning: I couldn't read load {ref} just now (browser busy, or no load "
                            f"{ref} in the TMS) — ask me again in a moment."}
        return {"text": _render_load_state(state)}
    reply = handle_ops_command(
        text,
        actor=actor,
        ops_control=ops_control,
        store=store,
        status_file=config.status_file,
        workspace=getattr(config, "workspace", None),
        db_path=getattr(config, "db_path", None),
        cdp_url=getattr(config, "operation_cdp_url", None),
        url_filter=getattr(config, "operation_url_filter", None),
    )
    if not reply.startswith("Commands:"):
        return {"text": reply}  # a recognized read/control -> answer immediately (no gates needed)
    if config.operation_router is None:
        return {"text": reply}
    # DOCUMENT FENCE at PROPOSE time: an attach/file request must have a real file to attach, or say so
    # up front — don't propose an attach for a document we don't have (fixes proposing on load 102 with
    # no POD). Mirrors the router's requires_document fence, but surfaced at proposal instead of run.
    _low = (text or "").lower()
    if any(k in _low for k in ("attach", "file pod", "file the pod", "file bol", "upload pod",
                               "upload bol", "file document", "file the bol")):
        _docfn = getattr(config.operation_router, "document_for", None)
        if callable(_docfn):
            _ref = _extract_load_ref(text)
            _intent = CommandIntent(kind=CommandKind.OPERATE, summary=text,
                                    params={"load_ref": _ref} if _ref else {})
            if _docfn(_intent) is None:
                _dt = "POD" if "pod" in _low else "BOL" if "bol" in _low else "document"
                return {"text": f":open_file_folder: I don't have a {_dt} for load {_ref or '(that load)'} "
                                "to file yet — send it to me (email it or drop the file in) and I'll attach it."}
    # ALREADY-INVOICED GUARD: "bill 101" on a load that's already Invoiced must NOT offer to bill again
    # (double-bill / double-cash risk). Answer with its state instead of proposing raise_invoice.
    if re.search(r"\b(bill|invoice|raise)\b", (text or "").lower()) and getattr(config, "load_state_reader", None) is not None:
        _ref = _extract_load_ref(text)
        if _ref:
            _state = config.load_state_reader(_ref)
            if _state and "invoiced" in (_state.get("status") or "").lower():
                return {"text": f":information_source: Load {_ref} is *already invoiced* "
                                f"({(_state.get('customer') or '').strip()} · {(_state.get('total') or '').strip()}). "
                                "Nothing to bill — reply *record a payment on it* if they've paid."}
    # "bill load 105" with no amount: fetch the load's Total from the TMS (deterministic, not model-
    # chosen) so the owner doesn't have to type it. Falls back to asking if it can't be resolved.
    amount_source = text
    if _extract_command_amount(text) is None and getattr(config, "load_amount_resolver", None) is not None:
        load_ref = _extract_load_ref(text)
        if load_ref:
            resolved = config.load_amount_resolver(load_ref)
            if resolved:
                amount_source = f"{text} amount {resolved}"
    proposal = _build_operation_command_proposal(
        text, signer=config.signer, router=config.operation_router, channel_id=channel_id,
        amount_source_text=amount_source,
    )
    if proposal is not None:
        return {"proposal": proposal}
    if config.nl_completer is not None:  # plain words -> route to a read (answer) or an operation (propose)
        from .nl_command import interpret_slash

        routed = interpret_slash(text, complete=config.nl_completer)
        if routed.get("read"):
            return {"text": handle_ops_command(
                routed["read"], actor=actor, ops_control=ops_control, store=store,
                status_file=config.status_file,
                workspace=getattr(config, "workspace", None),
                db_path=getattr(config, "db_path", None),
                cdp_url=getattr(config, "operation_cdp_url", None),
                url_filter=getattr(config, "operation_url_filter", None),
            )}
        if routed.get("operate"):
            proposal = _build_operation_command_proposal(
                routed["operate"], signer=config.signer, router=config.operation_router,
                channel_id=channel_id, amount_source_text=text,
            )
            if proposal is not None:
                return {"proposal": proposal}
    # Unrecognized: dump the full command list only when the owner ASKS for it — a conversational miss
    # ("thats not what i mean tho") gets a short human reply, not a wall of commands (live-found).
    if reply.startswith("Commands:") and not re.search(r"\b(help|commands?|what can you do)\b", (text or "").lower()):
        return {"text": "I didn't quite get that. Ask me things like *who owes us money?*, *what's happening?*, "
                        "or tell me an action like *bill load 102* — or say *help* for everything I know."}
    return {"text": reply}


def _render_pending_op_context(pending_op: dict, reply_text: str) -> str:
    """Answer a question/challenge about the pending operation in this thread — what it did, why it
    stopped, and how to redirect it. LIVE-FOUND: the owner's complaint ("did i not say 100, why are you
    attaching this to 101?") was keyword-routed into a NEW lane proposal instead of being answered."""
    lane = pending_op.get("lane") or "operation"
    summary = str(pending_op.get("summary") or lane)
    note = str(pending_op.get("note") or "").strip()
    steps = [s for s in (pending_op.get("steps") or []) if isinstance(s, dict) and s.get("action")]
    lines = [f"About this run (*{summary}* — {pending_op.get('status', 'pending')}):"]
    if note:
        lines.append(f"> {note[:280]}")
    if steps:
        from .roi_ledger import build_run_trace
        trace = build_run_trace(steps)
        if trace:
            lines.append("What I actually did:")
            lines.extend(f"  • {t}" for t in trace[-6:])
    lines.append(
        "_If I worked the wrong record or you want changes: give me the correction as a fresh request "
        "naming the exact load/invoice and approved amount, then approve that new proposal. This run "
        "stays paused. Reply `submit` only if you want THIS run to continue as-is._"
    )
    return "\n".join(lines)


def _is_pending_op_challenge(text: str, pending_op: dict | None) -> bool:
    """Is this reply challenging/questioning the active operation rather than starting a new one?

    This runs before generic lane matching. In a pending operation thread, phrases like "why are you
    attaching 101" must explain the active run, not become a fresh file_document proposal because the
    word "attaching" matched a lane keyword.
    """
    if pending_op is None:
        return False
    t = " ".join((text or "").lower().split())
    if not t:
        return False
    challenge_markers = (
        "why", "did i not", "didn't i", "wrong", "not that", "not this", "what do you mean",
        "thats not", "that's not", "that is not", "i said", "i asked", "why are you",
        "why did you", "why'd you", "hold on", "wait", "stop",
    )
    if any(marker in t for marker in challenge_markers):
        return True
    params = pending_op.get("params") or {}
    named = {str(v).lower() for k, v in params.items() if k in ("load_ref", "load_id", "invoice_ref") and v}
    if named and re.search(r"\b(wrong|different|other|instead|not)\b", t):
        return True
    return False


def _respond_conversationally(*, text, actor, channel_id, thread_ts, config, pending_op: dict | None = None) -> None:
    """Route a non-resume owner thread reply through the conversational surface and post the result to
    the thread (an answer, or a proposal carrying its Approve button in blocks). When the thread has a
    PENDING op and the reply isn't a clean read/control, answer about THAT op instead of lane-matching
    the owner's words into an unrelated new proposal."""
    if config.operation_result_poster is None or not (text or "").strip():
        return
    if _is_pending_op_challenge(text, pending_op):
        try:
            config.operation_result_poster({
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "text": _render_pending_op_context(pending_op or {}, text),
            })
        except Exception:  # noqa: BLE001 - a conversational reply must never crash the events endpoint
            return
        return
    ops_control = OpsControl(Path(config.db_path).parent / "ops_control.json")
    store = WorkflowStore(config.db_path)
    try:
        routed = route_conversational_message(
            text, actor=actor, channel_id=channel_id, config=config, ops_control=ops_control, store=store
        )
    finally:
        store.close()
    proposal = routed.get("proposal")
    post = {"channel_id": channel_id, "thread_ts": thread_ts}
    routed_text = routed.get("text") or ""
    if pending_op is not None and (proposal is not None or routed_text.startswith("Commands:") or not routed_text):
        # In a pending-op thread, a message that would have become a new proposal or a help-dump is
        # almost certainly ABOUT the op (a challenge, a question, a correction) — answer that.
        post["text"] = _render_pending_op_context(pending_op, text)
    elif proposal is not None:
        post["text"] = proposal.get("text", "Neyma proposal")
        if proposal.get("blocks"):
            post["blocks"] = proposal["blocks"]
    else:
        post["text"] = routed_text or "I didn't catch that — try \"what's outstanding?\" or \"invoice load …\"."
    try:
        config.operation_result_poster(post)
    except Exception:  # noqa: BLE001 - a conversational reply must never crash the events endpoint
        return


def _receipt_text(result, amount, diag) -> str:
    """Owner receipt, with the 'why it struggled' appended when the run wasn't clean."""
    from .roi_ledger import receipt_from_result, render_operation_receipt
    from .run_diagnostics import render_diagnosis

    text = render_operation_receipt(receipt_from_result(result, amount=amount))
    if diag is not None and not diag.is_clean():
        text += "\n" + render_diagnosis(diag)
    return text


def _start_batch_background_run(
    *,
    db_path: str,
    router: OperationRouter,
    batch: dict,
    actor: str,
    channel_id: str | None,
    thread_ts: str | None,
    poster: Callable[[dict], None] | None,
) -> threading.Thread:
    """Run the digest's approved batch: each item through the SAME per-load fence + commit-once (a
    partial failure is contained — the rest still bill), then ONE consolidated receipt in-thread."""
    lane = str(batch.get("lane") or "raise_invoice")

    def _run() -> None:
        outcomes: list[tuple[str, str, str]] = []  # (load_ref, status, note)
        for item in batch["items"]:
            load_ref, customer, amount = str(item["load_ref"]), str(item.get("customer") or ""), str(item["amount"])
            intent = CommandIntent(
                kind=CommandKind.OPERATE,
                summary=f"Invoice {customer or 'the customer'} for {load_ref}",
                params={"lane": lane, "customer": customer, "load_ref": load_ref,
                        "approved_amount": amount, "commit": True},
            )
            try:
                result = router.run(intent, approve=_single_consequential_approval())
                status, note = result.status, result.note
            except Exception as exc:  # noqa: BLE001 - one bad item must not sink the batch
                status, note = "FAILED", f"{type(exc).__name__}: {exc}"[:300]
            outcomes.append((load_ref, status, note))
            store = WorkflowStore(db_path)
            try:
                store.add_security_event(
                    "slack_operation_applied", actor=actor,
                    payload={"batch_action_id": batch["action_id"], "lane": lane, "load_ref": load_ref,
                             "approved_amount": amount, "status": status, "note": note,
                             "channel_id": channel_id, "thread_ts": thread_ts,
                             "summary": f"Invoice {customer} for {load_ref}"},
                )
            finally:
                store.close()
        if poster is not None:
            done = [o for o in outcomes if o[1] == "DONE"]
            rest = [o for o in outcomes if o[1] != "DONE"]
            lines = [f"✅ Batch finished — {len(done)}/{len(outcomes)} invoiced."]
            for ref, _s, note in done:
                lines.append(f"  • {ref}: done — {note[:80]}")
            for ref, s, note in rest:
                lines.append(f"  ✋ {ref}: {s} — {note[:120]}")
            try:
                poster({"channel_id": channel_id, "thread_ts": thread_ts,
                        "text": "\n".join(lines), "status": "BATCH_DONE", "lane": lane})
            except Exception:  # noqa: BLE001 - the receipt is best-effort; the audit log has the truth
                pass

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


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

        scrubbed = _scrub_money_from_text(str(guidance))
        if not scrubbed.strip():
            return
        KnowledgeBase(_Path(db_path).parent / "agent_memory.json").learn(
            scrubbed, tenant="default", kind=FactKind.BUSINESS, subject=subject, source="correction",
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
    amount_source_text: str | None = None,
) -> dict | None:
    # Only treat this as an operation request if it actually matches a known lane (e.g. "invoice ...",
    # "record payable ..."). Otherwise it's just an unrecognized command -> return None so the caller
    # shows the help, instead of nagging about an approved amount.
    lane = router.lane_for(CommandIntent(kind=CommandKind.OPERATE, summary=text, params={}))
    if lane is None:
        return None
    # Anchor the operation to the record the owner NAMED. Without this the goal says "...the delivered
    # load" and the agent picks a record itself — live-found: owner said load 100, agent drove 101.
    # The ORIGINAL owner text is the authority (same rule as the amount): a model rewrite must not be
    # able to change which record gets operated.
    load_ref = _extract_load_ref(amount_source_text) if amount_source_text is not None else None
    if load_ref is None:
        load_ref = _extract_load_ref(text)
    if load_ref is None and lane.name != "create_load":  # every other lane acts ON a specific record
        return {
            "response_type": "ephemeral",
            "text": f"To run *{lane.name}* I need to know which load/invoice. "
                    "Name the record, e.g. `bill load 102` or `record a payment on invoice 560009`.",
        }
    params: dict = {"lane": lane.name}
    if load_ref is not None:
        params["load_ref"] = load_ref
    customer = _extract_customer(text)
    if customer:
        params["customer"] = customer
    elif lane.name == "raise_invoice" and load_ref is not None:
        # AR invoice requests often arrive as "bill load 100 amount 2850". The browser can read the
        # bill-to from the load, but commit-once still needs a stable party dimension. Use an explicit
        # load-scoped placeholder rather than leaving the commit identity unprotected.
        params["party"] = f"customer_on_load:{load_ref}"
    amount = _extract_command_amount(amount_source_text if amount_source_text is not None else text)
    if lane.requires_amount and amount is None:
        return {
            "response_type": "ephemeral",
            "text": f"To run *{lane.name}* on {load_ref or 'that record'} I need an approved amount — "
                    "add it like `amount 2400.00` (or name a load and I'll fetch its total from the TMS).",
        }
    if amount is not None:
        params["approved_amount"] = amount
    intent = CommandIntent(kind=CommandKind.OPERATE, summary=text, params=params)
    value = build_slack_operation_approval_value(
        intent,
        signer,
        approved_amount=amount,
        expected_channel_id=channel_id,
    )
    record_field = f"*Record*\n{load_ref}" if load_ref else "*Record*\n(new)"
    amount_field = f"*Approved amount*\n${amount}" if amount else "*Amount*\n(none — not a money action)"
    button_label = f"Approve ${amount}" if amount else f"Approve {lane.name}"
    headline = f"Neyma proposal: {lane.name}" + (f" on {load_ref}" if load_ref else "") + (f" for ${amount}" if amount else "")
    return {
        "response_type": "in_channel",
        "text": headline,
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "Neyma operation proposal"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Lane*\n{lane.name}"},
                    {"type": "mrkdwn", "text": record_field},
                    {"type": "mrkdwn", "text": amount_field},
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
                        "text": {"type": "plain_text", "text": button_label},
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


def _extract_customer(text: str) -> str | None:
    """Best-effort deterministic customer capture from typed owner commands.

    This is not allowed to invent a party. It only binds clear phrases such as
    ``invoice LD-9001 for Acme amount 2850`` or ``customer Acme``. If absent, the AR lane uses the
    load-scoped party fallback above and lets the TMS load supply the bill-to.
    """
    t = (text or "").strip()
    if not t:
        return None
    patterns = (
        r"\bcustomer\s+(.+?)(?:\s+(?:load|order|invoice|amount|\$)\b|$)",
        r"\bfor\s+(.+?)\s+amount\b",
        r"\bfor\s+(.+?)\s+\$",
    )
    for pattern in patterns:
        match = re.search(pattern, t, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip(" \t-:,.")
        if not value:
            continue
        if re.fullmatch(r"\$?\d[\d,]*(?:\.\d{1,2})?", value):
            continue
        # Avoid swallowing record phrases as parties.
        value = re.sub(r"\b(load|order|invoice)\s*#?\s*\w+\b", "", value, flags=re.IGNORECASE).strip(" \t-:,.")
        return value or None
    return None


def _scrub_money_from_text(text: str) -> str:
    scrubbed = re.sub(
        r"(?<!\w)(?:usd\s*\$?\s*|\$)\d[\d,]*(?:\.\d{1,2})?\b",
        "[amount redacted]",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", scrubbed).strip()


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
