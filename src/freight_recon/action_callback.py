"""Local signed-action callback surface for the internal dogfood pilot.

This module is intentionally small and transport-neutral. It gives local email action links and
test callbacks somewhere to land without introducing a web framework or live outbound behavior.
Every accepted action still flows through ``delivery.submit_signed_action`` and the workflow state
machine; this layer only parses HTTP-ish inputs and formats a confirmation response.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, Field

from .delivery import (
    DeliveryExpiredError,
    DeliverySignatureError,
    DeliverySigner,
    render_delivery_message,
    submit_signed_action,
)
from .reconciliation import FreightLoadForReconciliation
from .slack_adapter import SlackDeliveryAdapter, SlackError, SlackSignatureError
from .workflow import WorkflowError, WorkflowStore


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


def handle_signed_action_callback(
    store: WorkflowStore,
    token: str | None,
    *,
    signer: DeliverySigner,
    follow_up_loads: dict[str, FreightLoadForReconciliation] | None = None,
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
        )
    )
    return ThreadingHTTPServer((host, port), handler)


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
