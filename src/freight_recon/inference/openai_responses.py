"""The OpenAI implementation of the inference gateway — the Responses API, strict structured outputs.

This is the ONLY module in the inference boundary that imports the OpenAI SDK, and it imports it
lazily, at the first live call. Nothing here leaks an OpenAI object: `_invoke` returns a plain
`ModelReply`, and every provider exception becomes a content-free `InferenceFailure` code.

### LIVE CALLS ARE OPT-IN, STRUCTURALLY. Constructing this class without `allow_live=True` (and
without an injected client) raises. An ordinary test or CI run cannot reach the network through it
by accident; `scripts/run_freight_interpretation_eval.py` is the one place that passes the flag.

### THE SDK DOES NOT RETRY BEHIND OUR BACK. The client is built with `max_retries=0`: the bounded
retry in `gateway.py` is the only retry, so every attempt is counted, budgeted and recorded.

### THE KEY IS READ, NEVER SHOWN. The API key is taken from the environment and handed to the SDK. It
is not stored on this object, not logged, and a provider's error text — which can echo part of a key
— is redacted before it is returned and is never written to telemetry.
"""

from __future__ import annotations

import os
from typing import Any

from .contracts import Usage
from .gateway import (
    BaseGateway,
    IncompleteOutput,
    InferenceFailure,
    ModelReply,
    ProviderRejection,
    SchemaFailure,
    TaskCall,
    TransportFailure,
)

DEFAULT_TIMEOUT_S = 45.0
DEFAULT_MAX_OUTPUT_TOKENS = 4000


class LiveInferenceNotEnabled(RuntimeError):
    """A live model gateway was constructed without the explicit opt-in."""


class OpenAIResponsesGateway(BaseGateway):
    provider = "openai"
    served_from = "live"

    def __init__(self, *, model: str, allow_live: bool = False, client: Any = None,
                 timeout_s: float = DEFAULT_TIMEOUT_S,
                 max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
                 api_key_env: str = "OPENAI_API_KEY", **kwargs: Any) -> None:
        if client is None and not allow_live:
            raise LiveInferenceNotEnabled(
                "OpenAIResponsesGateway makes paid network calls. Pass allow_live=True to opt in "
                "(the live eval script does), or use ScriptedGateway / ReplayGateway. Ordinary "
                "tests and CI never construct a live gateway.")
        super().__init__(model=model, **kwargs)
        self._client = client
        self._timeout_s = timeout_s
        self._max_output_tokens = max_output_tokens
        self._api_key_env = api_key_env

    def _ensure_client(self) -> Any:
        if self._client is None:
            if not os.environ.get(self._api_key_env):
                raise ProviderRejection("api_key_missing")
            from openai import OpenAI

            self._client = OpenAI(api_key=os.environ[self._api_key_env], max_retries=0,
                                  timeout=self._timeout_s)
        return self._client

    def _invoke(self, call: TaskCall) -> ModelReply:
        client = self._ensure_client()
        arguments: dict[str, Any] = {
            "model": self.model,
            "instructions": call.instructions,
            "input": call.rendered_input,
            "text_format": call.output_model,
            "max_output_tokens": self._max_output_tokens,
            "store": False,
            "timeout": self._timeout_s,
        }
        if self.reasoning_effort:
            arguments["reasoning"] = {"effort": self.reasoning_effort}
        try:
            response = client.responses.parse(**arguments)
        except Exception as exc:  # noqa: BLE001 - every provider failure becomes a typed, safe code
            raise _classify(exc) from None
        usage = _usage(getattr(response, "usage", None))
        if getattr(response, "status", None) == "incomplete":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", "unknown")
            raise IncompleteOutput(f"incomplete_output:{reason}", usage=usage)
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ProviderRejection("refusal_or_empty_output", usage=usage)
        payload = parsed.model_dump(mode="json") if hasattr(parsed, "model_dump") else parsed
        return ModelReply(payload=payload, usage=usage, model=getattr(response, "model", None))


def _usage(raw: Any) -> Usage:
    if raw is None:
        return Usage()
    input_details = getattr(raw, "input_tokens_details", None)
    output_details = getattr(raw, "output_tokens_details", None)
    return Usage(
        input_tokens=int(getattr(raw, "input_tokens", 0) or 0),
        cached_input_tokens=int(getattr(input_details, "cached_tokens", 0) or 0),
        output_tokens=int(getattr(raw, "output_tokens", 0) or 0),
        reasoning_tokens=int(getattr(output_details, "reasoning_tokens", 0) or 0))


def _classify(exc: Exception) -> InferenceFailure:
    """A provider exception as a content-free failure. Classified by the exception's own class name
    and HTTP status, so this needs no SDK import and works on an injected client's errors too."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    status = getattr(exc, "status_code", None)
    code = getattr(exc, "code", None)
    label = f"{type(exc).__name__}" + (f":{status}" if status else "") + (f":{code}" if code else "")
    debug = str(exc)
    if "ValidationError" in names:
        return SchemaFailure("invalid_reply[sdk_parse]", debug=debug)
    if "LengthFinishReasonError" in names:
        return IncompleteOutput("incomplete_output:max_output_tokens", debug=debug)
    if code == "insufficient_quota":
        return ProviderRejection(label, debug=debug)
    if names & {"APITimeoutError", "APIConnectionError", "RateLimitError", "InternalServerError",
                "TimeoutError", "ConnectionError"}:
        return TransportFailure(label, debug=debug)
    if isinstance(status, int) and status >= 500:
        return TransportFailure(label, debug=debug)
    return ProviderRejection(label, debug=debug)
