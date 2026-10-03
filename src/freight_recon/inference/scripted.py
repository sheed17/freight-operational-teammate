"""The deterministic gateway: the one every ordinary test and CI run uses.

A `ScriptedGateway` answers from a responder function the test supplies. It goes through exactly the
same execution path as the live gateway — routing check, budget, bounded retry, typed validation,
telemetry — so what a test proves about a failure, a retry or a refused reply is true of the real
thing. It opens no socket and imports no SDK.

An unscripted call is an `UnscriptedCall`, raised and never swallowed: a test states every model call
it expects, so an unexpected one is a failing test rather than a silent pass.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel

from .contracts import Task, Usage
from .gateway import BaseGateway, InferenceFailure, ModelReply, TaskCall

#: `(task, request) -> reply`. A reply is a typed output, a dict, a JSON string, or an
#: `InferenceFailure` to raise. Returning None means "not scripted".
Responder = Callable[[Task, Any], Any]


class UnscriptedCall(AssertionError):
    """A model call the test did not script. Not an `InferenceFailure`: it must not be absorbed into
    a failed reading."""


class ScriptedGateway(BaseGateway):
    provider = "scripted"
    served_from = "scripted"

    def __init__(self, responder: Responder, *, model: str = "scripted-reader",
                 usage: Usage = Usage(), **kwargs: Any) -> None:
        kwargs.setdefault("retry_backoff_s", 0.0)
        super().__init__(model=model, **kwargs)
        self._responder = responder
        self._usage = usage
        #: Every attempt that reached the "model", in order. Tests assert on this.
        self.invocations: list[tuple[Task, Any]] = []

    def _invoke(self, call: TaskCall) -> ModelReply:
        self.invocations.append((call.task, call.request))
        reply = self._responder(call.task, call.request)
        if reply is None:
            raise UnscriptedCall(
                f"no scripted reply for {call.task.value} on {call.request.source_id!r}. A test "
                f"scripts every model call it expects.")
        if isinstance(reply, InferenceFailure):
            raise reply
        if isinstance(reply, BaseModel):
            reply = reply.model_dump(mode="json")
        return ModelReply(payload=reply, usage=self._usage)

    def invocations_of(self, task: Task) -> list[Any]:
        return [request for seen, request in self.invocations if seen is task]


def sequence(*replies: Any) -> Callable[[], Any]:
    """Replies handed out one per call — a failure followed by a success, for retry tests."""
    queue = list(replies)

    def take() -> Any:
        return queue.pop(0) if queue else None
    return take


def by_text(scripts: Mapping[Task, Mapping[str, Any]]) -> Responder:
    """A responder keyed by the text a request carries: a message's body, a document's text, a
    candidate request's record text. A scripted value that is callable is called with the request
    (a `sequence(...)` is called with nothing)."""

    def respond(task: Task, request: Any) -> Any:
        text = getattr(request, "body", None) or getattr(request, "text", "")
        reply = (scripts.get(task) or {}).get(text)
        if callable(reply):
            try:
                return reply(request)
            except TypeError:
                return reply()
        return reply
    return respond
