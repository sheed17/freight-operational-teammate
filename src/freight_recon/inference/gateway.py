"""The one execution path every inference gateway shares.

A provider implements `_invoke` and nothing else. Everything that must hold for EVERY model call —
whichever provider, live, replayed or scripted — is here, once:

  * the request's `Route` must say a model is needed, or the call is a `RoutingViolation`;
  * a recorded reading is replayed before anything is spent;
  * the run's budget is asked before EVERY attempt, retries included;
  * retries are bounded, and happen only for a transport failure or a reply that failed the typed
    contract — never for a rejection, a refusal or an exhausted budget;
  * the reply is validated against the task's output model, and an invalid reply is a failure, not a
    best-effort parse;
  * one telemetry record is written per call, with the tokens of every attempt summed.

### THERE IS NO LOOP HERE. One request produces one reading. Nothing in this module calls a tool,
feeds a reply back into a model, or decides to ask again because an answer looked incomplete.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError

from .contracts import (
    OUTPUT_MODELS,
    CandidateProposal,
    CandidateRequest,
    CommitmentExtraction,
    DocumentTextInterpretation,
    DocumentTextRequest,
    InferenceResult,
    LoadWorkReasoning,
    LoadWorkRequest,
    MessageInterpretation,
    MessageRequest,
    RoutingViolation,
    Status,
    Task,
    Usage,
)
from .ledger import CallRecord, InferenceBudget, InferenceLedger
from .prompts import INSTRUCTIONS, prompt_version_for, render
from .recording import RecordingStore, content_digest, request_key

_SECRET = re.compile(r"(sk|rk|pk)-[A-Za-z0-9_\-*.]{6,}")


def redact(text: str, *, limit: int = 300) -> str:
    """A provider's error text with anything key-shaped removed, truncated. Returned to the caller
    for a human to read on a failed eval; never written to telemetry."""
    return _SECRET.sub("[redacted-key]", str(text))[:limit]


class InferenceFailure(Exception):
    """A provider attempt produced no usable reply. `code` is a short, content-free reason."""

    retryable = False
    status = Status.PROVIDER_FAILURE

    def __init__(self, code: str, *, usage: Usage | None = None, debug: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.usage = usage or Usage()
        self.debug = redact(debug)


class TransportFailure(InferenceFailure):
    """Timeout, connection failure, rate limit, provider 5xx. Worth one bounded retry."""

    retryable = True


class ProviderRejection(InferenceFailure):
    """The provider refused the request or the model refused the task. A retry would not help."""


class SchemaFailure(InferenceFailure):
    """A reply arrived and is not the typed contract."""

    retryable = True
    status = Status.SCHEMA_FAILURE


class IncompleteOutput(SchemaFailure):
    """The reply was cut off at the output-token cap. The same cap would cut it off again."""

    retryable = False


class ReplayMiss(InferenceFailure):
    """Replay-only, and this reading was never recorded. Nothing is called."""

    status = Status.REPLAY_MISS


@dataclass(frozen=True)
class TaskCall:
    task: Task
    request: Any
    instructions: str
    rendered_input: str
    output_model: type[BaseModel]


@dataclass(frozen=True)
class ModelReply:
    payload: Any                        # a dict or a JSON string, validated by the caller
    usage: Usage
    model: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseGateway:
    """Implements the five task methods over one `_invoke`."""

    provider = "abstract"
    served_from = "live"

    def __init__(self, *, model: str, ledger: InferenceLedger | None = None,
                 budget: InferenceBudget | None = None, max_attempts: int = 2,
                 recording: RecordingStore | None = None, reasoning_effort: str | None = None,
                 clock: Callable[[], datetime] = _utc_now,
                 sleep: Callable[[float], None] = time.sleep,
                 retry_backoff_s: float = 1.0) -> None:
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError(
                f"max_attempts={max_attempts}: a model call is attempted between one and three "
                f"times. An unbounded retry is an unbounded bill.")
        self.model = model
        self.ledger = ledger if ledger is not None else InferenceLedger()
        self.budget = budget
        self.max_attempts = max_attempts
        self.recording = recording
        self.reasoning_effort = reasoning_effort
        self._clock = clock
        self._sleep = sleep
        self._retry_backoff_s = retry_backoff_s

    # ------------------------------------------------------------------ the five tasks

    def interpret_message(
            self, request: MessageRequest) -> InferenceResult[MessageInterpretation]:
        return self._execute(Task.INTERPRET_MESSAGE, request)

    def interpret_document_text(
            self, request: DocumentTextRequest) -> InferenceResult[DocumentTextInterpretation]:
        return self._execute(Task.INTERPRET_DOCUMENT_TEXT, request)

    def extract_commitments(
            self, request: MessageRequest) -> InferenceResult[CommitmentExtraction]:
        return self._execute(Task.EXTRACT_COMMITMENTS, request)

    def propose_entity_candidates(
            self, request: CandidateRequest) -> InferenceResult[CandidateProposal]:
        return self._execute(Task.PROPOSE_ENTITY_CANDIDATES, request)

    def reason_load_work(
            self, request: LoadWorkRequest) -> InferenceResult[LoadWorkReasoning]:
        return self._execute(Task.REASON_LOAD_WORK, request)

    # ------------------------------------------------------------------ provider hook

    def _invoke(self, call: TaskCall) -> ModelReply:
        raise NotImplementedError

    # ------------------------------------------------------------------ execution

    def _execute(self, task: Task, request: Any) -> InferenceResult[Any]:
        route = request.route
        if route.task is not task or not route.model_needed:
            raise RoutingViolation(
                f"{task.value} was requested with route ({route.task.value}, model_needed="
                f"{route.model_needed}, {route.reason!r}). A model is called only when the routing "
                f"boundary says language interpretation is required for THIS task.")
        call = TaskCall(task=task, request=request, instructions=INSTRUCTIONS[task],
                        rendered_input=render(task, request), output_model=OUTPUT_MODELS[task])
        key = request_key(provider=self.provider, model=self.model, task=task,
                          prompt_version=prompt_version_for(task),
                          reasoning_effort=self.reasoning_effort,
                          rendered_input=call.rendered_input)
        digest = content_digest(call.rendered_input)
        started = time.perf_counter()

        status, output, detail, debug = Status.PROVIDER_FAILURE, None, "", ""
        usage, attempts, served_from, model = Usage(), 0, self.served_from, self.model

        recorded = self.recording.get(key) if self.recording is not None else None
        if recorded is not None:
            served_from = "replay"
            usage = Usage(**recorded["usage"])
            try:
                output = call.output_model.model_validate(recorded["payload"])
                status = Status.OK
            except ValidationError as exc:
                status, detail = Status.SCHEMA_FAILURE, _validation_code(exc)
        else:
            while attempts < self.max_attempts:
                if self.budget is not None and not self.budget.admit():
                    status, detail = Status.BUDGET_EXHAUSTED, "run_budget_exhausted"
                    break
                attempts += 1
                try:
                    reply = self._invoke(call)
                except InferenceFailure as failure:
                    usage = usage + failure.usage
                    if self.budget is not None:
                        self.budget.spend(failure.usage)
                    status, detail, debug = failure.status, failure.code, failure.debug
                    if failure.retryable and attempts < self.max_attempts:
                        self._sleep(self._retry_backoff_s)
                        continue
                    break
                usage = usage + reply.usage
                if self.budget is not None:
                    self.budget.spend(reply.usage)
                model = reply.model or model
                try:
                    output = _validate(call.output_model, reply.payload)
                except ValidationError as exc:
                    status, detail = Status.SCHEMA_FAILURE, _validation_code(exc)
                    if attempts < self.max_attempts:
                        continue
                    break
                status, detail = Status.OK, ""
                if self.recording is not None:
                    self.recording.put(
                        key, task=task, provider=self.provider, model=self.model,
                        payload=output.model_dump(mode="json"), usage=reply.usage,
                        recorded_at=_instant(self._clock()), input_digest=digest)
                break

        latency_ms = int((time.perf_counter() - started) * 1000)
        interpreted_at = _instant(self._clock())
        self.ledger.record_call(CallRecord(
            at=interpreted_at, provider=self.provider, model=model, task=task.value,
            outcome=status.value, input_tokens=usage.input_tokens,
            cached_input_tokens=usage.cached_input_tokens, output_tokens=usage.output_tokens,
            reasoning_tokens=usage.reasoning_tokens, latency_ms=latency_ms,
            retry_count=max(attempts - 1, 0), subject_ref=request.source_id,
            correlation_id=request.correlation_id, content_digest=digest, request_digest=key,
            served_from=served_from, detail=detail))
        return InferenceResult(
            task=task, status=status, output=output if status is Status.OK else None,
            provider=self.provider, model=model, interpreted_at=interpreted_at, usage=usage,
            attempts=attempts, latency_ms=latency_ms, request_digest=key,
            served_from=served_from, detail=detail, debug=debug)


def _validate(output_model: type[BaseModel], payload: Any) -> BaseModel:
    if isinstance(payload, (str, bytes)):
        return output_model.model_validate_json(payload)
    return output_model.model_validate(payload)


def _validation_code(exc: ValidationError) -> str:
    """Where a reply broke the contract, by field path and error type. The offending VALUES are left
    out: they are message content."""
    parts = [f"{'.'.join(str(p) for p in e['loc']) or '<root>'}:{e['type']}"
             for e in exc.errors(include_input=False, include_url=False)[:4]]
    return "invalid_reply[" + ",".join(parts) + "]"


def _instant(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class ReplayGateway(BaseGateway):
    """Replay-only. It answers from a recording and from nothing else: a reading that was never
    recorded is a `REPLAY_MISS`, and no provider is contacted because there is none to contact.

    `provider` and `model` name what the recording was made with — they are part of its key."""

    served_from = "replay"

    def __init__(self, *, provider: str, model: str, recording: RecordingStore,
                 reasoning_effort: str | None = None,
                 ledger: InferenceLedger | None = None,
                 clock: Callable[[], datetime] = _utc_now) -> None:
        super().__init__(model=model, ledger=ledger, recording=recording, max_attempts=1,
                         reasoning_effort=reasoning_effort, clock=clock)
        self.provider = provider

    def _invoke(self, call: TaskCall) -> ModelReply:
        raise ReplayMiss("not_recorded")
