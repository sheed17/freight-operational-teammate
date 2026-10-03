"""P9 deep-end 2 — the inference boundary: one way to a model, and what holds for every call.

Nothing in this file reaches a network. The scripted gateway and an injected fake client go through
exactly the execution path a live call does — the routing check, the budget, the bounded retry, the
typed validation, the telemetry — so each claim below is a claim about the real path.

### WHAT COULD FAIL, AND WOULD. `scripts/mutate_p9_interpretation.py` reintroduces the defect behind
each guard here (an unbounded retry, an unenforced budget, a live gateway constructible by default, a
replay miss that falls through to a provider, a key in telemetry) and confirms the named test turns
RED.
"""

from __future__ import annotations

import ast
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests"),
              str(ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from dark_surface_kit import SCRIPTS, SRC, callers_of, import_closure, population  # noqa: E402
from freight_corpus.reading import candidates, message, promise, status  # noqa: E402
from freight_recon.inference.contracts import (  # noqa: E402
    OUTPUT_MODELS,
    CandidateOption,
    CandidateRequest,
    MessageRequest,
    Route,
    RoutingViolation,
    Status,
    Task,
    Usage,
)
from freight_recon.inference.gateway import (  # noqa: E402
    ProviderRejection,
    ReplayGateway,
    TransportFailure,
    redact,
)
from freight_recon.inference.ledger import (  # noqa: E402
    InferenceBudget,
    InferenceLedger,
    load_ledger,
)
from freight_recon.inference.openai_responses import (  # noqa: E402
    LiveInferenceNotEnabled,
    OpenAIResponsesGateway,
)
from freight_recon.inference.prompts import INSTRUCTIONS  # noqa: E402
from freight_recon.inference.recording import RecordingStore, request_key  # noqa: E402
from freight_recon.inference.scripted import ScriptedGateway, UnscriptedCall, sequence  # noqa: E402
from freight_recon.inference.settings import (  # noqa: E402
    InferenceSettings,
    UnsupportedProvider,
    load_price_table,
)

BODY = "Checked in at the shipper 12:42, still waiting on a door. I'll update you in an hour."
READING = message(category="STATUS_UPDATE",
                  statuses=[status("ARRIVED", "PICKUP", "Checked in at the shipper 12:42")],
                  commitments=[promise("I'll update you in an hour", minutes=60,
                                       text="in an hour")])
#: A string shaped like a provider key. No real key appears anywhere in this repository.
KEY_SHAPED = "sk-proj-THISISNOTAREALKEY0123456789abcdef"
MODEL_SDKS = frozenset({"openai", "anthropic", "instructor", "litellm"})


def _request(body: str = BODY, *, needed: bool = True, task: Task = Task.INTERPRET_MESSAGE,
             source_id: str = "obs-1") -> MessageRequest:
    return MessageRequest(route=Route(task, needed, "test"), source_id=source_id, channel="sms",
                          sender_role="driver", sent_local="2026-06-01T12:44",
                          timezone="America/Chicago", subject="", body=body)


def _scripted(reply, **kwargs) -> ScriptedGateway:
    take = reply if callable(reply) else (lambda: reply)
    return ScriptedGateway(lambda task, request: take(), **kwargs)


# ============================================================ the routing boundary

def test_a_model_is_never_called_without_a_route_that_says_one_is_needed():
    """The gateway refuses a request the routing boundary did not send. Nothing is invoked, nothing
    is spent, and it is an error rather than a failed reading — a casual model call is a bug."""
    gateway = _scripted(READING)
    with pytest.raises(RoutingViolation):
        gateway.interpret_message(_request(needed=False))
    with pytest.raises(RoutingViolation):
        gateway.interpret_message(_request(task=Task.EXTRACT_COMMITMENTS))
    assert gateway.invocations == [] and gateway.ledger.calls == []
    assert gateway.interpret_message(_request()).ok
    assert len(gateway.invocations) == 1


def test_only_the_freight_interpreter_calls_a_gateway_task():
    """The four task methods have exactly one production caller. A second module asking a model
    something is a second, unreviewed place interpretation enters the system."""
    interpreter = "src/freight_recon/freight_domain/interpretation.py"
    for task in ("interpret_message", "interpret_document_text", "propose_entity_candidates"):
        assert callers_of(task) == {interpreter}, task
    assert callers_of("extract_commitments") == set(), (
        "extract_commitments has acquired a production caller; decide here whether it should")


# ============================================================ typed output or nothing

def test_a_reply_that_is_not_the_typed_contract_is_a_failure_not_a_best_effort_parse():
    for bad in ({"category": "STATUS_UPDATE"},                              # fields missing
                {**READING, "authorize_payment": True},                      # an extra field
                {**READING, "statuses": [{"status": "APPROVED", "stop": "PICKUP",
                                          "in_quoted_text": False, "evidence_text": "x"}]},
                "this is not json"):
        gateway = _scripted(bad)
        result = gateway.interpret_message(_request())
        assert result.status is Status.SCHEMA_FAILURE and result.output is None, bad
        assert result.attempts == 2, "a malformed reply gets exactly one bounded retry"
    # The failure code names WHERE the reply broke, never the offending content.
    result = _scripted({**READING, "leaked": BODY}).interpret_message(_request())
    assert "leaked" in result.detail and BODY not in result.detail


def test_no_output_model_has_a_field_that_could_carry_authority():
    """The vocabulary is the first guard: a model cannot approve, authorize, bind, pay or assign a
    provenance, because there is nowhere in any output schema to say so."""
    stems = ("approv", "authoriz", "provenance", "confidence", "payee", "pay", "paid", "bind",
             "bound", "resolv", "qualif", "decision", "decide", "grant", "witness")
    names: list[str] = []

    def walk(schema: dict) -> None:
        for name, sub in (schema.get("properties") or {}).items():
            names.append(name)
            walk(sub)
            walk(sub.get("items") or {})
        for sub in (schema.get("$defs") or {}).values():
            walk(sub)

    for model in OUTPUT_MODELS.values():
        walk(model.model_json_schema())
    assert len(names) > 60, f"only {len(names)} schema fields were inspected"
    # Whole tokens of each field name, matched by stem: `approver_named` -> approver, named.
    offenders = sorted({n for n in names for token in n.lower().split("_")
                        if token.startswith(stems)})
    # The only two fields about approval record what the SENDER claimed — the fraud signal on a
    # charge, and the name the sender dropped. Neither is, or can become, an approval.
    assert offenders == ["approver_named", "asserts_prior_approval"], offenders
    for model in OUTPUT_MODELS.values():
        assert model.model_config.get("extra") == "forbid"


# ============================================================ bounded retries

def test_retries_are_bounded_and_only_for_transport_or_schema_failure():
    recovering = _scripted(sequence(TransportFailure("APITimeoutError"), READING))
    result = recovering.interpret_message(_request())
    assert result.ok and result.attempts == 2
    assert recovering.ledger.calls[0].retry_count == 1

    dead = _scripted(sequence(*[TransportFailure("APIConnectionError")] * 9))
    result = dead.interpret_message(_request())
    assert result.status is Status.PROVIDER_FAILURE and result.attempts == 2
    assert len(dead.invocations) == 2, "the transport failure was retried past the bound"

    refused = _scripted(sequence(ProviderRejection("AuthenticationError:401"), READING))
    result = refused.interpret_message(_request())
    assert result.status is Status.PROVIDER_FAILURE and result.attempts == 1, (
        "a rejection was retried; only a transport or schema failure is")

    for attempts in (0, 4, 50):
        with pytest.raises(ValueError):
            ScriptedGateway(lambda task, request: READING, max_attempts=attempts)


def test_an_unscripted_call_is_a_failing_test_not_a_failed_reading():
    gateway = ScriptedGateway(lambda task, request: None)
    with pytest.raises(UnscriptedCall):
        gateway.interpret_message(_request())


# ============================================================ the budget

def test_the_run_budget_stops_calls_and_counts_retries():
    budget = InferenceBudget(max_calls=3, max_input_tokens=10_000, max_output_tokens=10_000)
    gateway = _scripted(sequence(READING, TransportFailure("APITimeoutError"), READING, READING,
                                 READING), budget=budget, usage=Usage(100, 0, 50, 0))
    assert gateway.interpret_message(_request(source_id="a")).ok            # 1 call
    assert gateway.interpret_message(_request(source_id="b")).ok            # 2 more: a retry counts
    blocked = gateway.interpret_message(_request(source_id="c"))
    assert blocked.status is Status.BUDGET_EXHAUSTED and blocked.attempts == 0
    assert len(gateway.invocations) == 3 and budget.calls == 3 and budget.exhausted

    tokens = InferenceBudget(max_calls=99, max_input_tokens=150, max_output_tokens=10_000)
    gateway = _scripted(READING, budget=tokens, usage=Usage(100, 0, 50, 0))
    assert gateway.interpret_message(_request(source_id="a")).ok
    assert gateway.interpret_message(_request(source_id="b")).ok            # 200 >= 150 after this
    assert gateway.interpret_message(_request(source_id="c")).status is Status.BUDGET_EXHAUSTED
    assert len(gateway.invocations) == 2


# ============================================================ telemetry

def test_every_call_is_recorded_with_tokens_and_no_content(tmp_path):
    sink = tmp_path / "ledger.jsonl"
    ledger = InferenceLedger(sink=sink)
    gateway = _scripted(sequence(TransportFailure("APITimeoutError"), READING, {"nope": 1},
                                 {"nope": 1}), ledger=ledger, usage=Usage(900, 300, 120, 40))
    assert gateway.interpret_message(_request(source_id="obs-a")).ok
    assert not gateway.interpret_message(_request(source_id="obs-b")).ok
    ledger.correlate("obs-a", "brokerage_load:L1")

    first, second = ledger.calls
    assert (first.provider, first.model, first.task) == ("scripted", "scripted-reader",
                                                         "interpret_message")
    assert (first.outcome, first.retry_count, first.input_tokens, first.cached_input_tokens,
            first.output_tokens, first.reasoning_tokens) == ("OK", 1, 900, 300, 120, 40)
    assert second.outcome == "SCHEMA_FAILURE" and second.input_tokens == 1800, (
        "the tokens of a failed attempt were billed and must still be counted")
    assert first.latency_ms >= 0 and len(first.content_digest) == 64
    assert first.content_digest == second.content_digest, "same content, same digest"

    written = sink.read_text(encoding="utf-8")
    assert len(written.splitlines()) == 3, "two calls and one correlation"
    for fragment in (BODY, "waiting on a door", "update you in an hour"):
        assert fragment not in written, f"telemetry holds message content: {fragment!r}"

    summary = load_ledger(sink).summary()
    assert summary == ledger.summary(), "the ledger does not survive a round trip through its file"
    assert summary["calls"] == 2 and summary["failures"] == 1 and summary["retries"] == 2
    assert summary["calls_by_task"]["interpret_message"]["input_tokens"] == 2700
    assert summary["calls_by_correlation"]["brokerage_load:L1"]["calls"] == 1
    assert summary["calls_by_correlation"]["uncorrelated"]["calls"] == 1
    assert summary["outcomes"] == {"OK": 1, "SCHEMA_FAILURE": 1}

    def walk(value) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                assert "amount" not in str(key) and "usd" not in str(key).lower(), key
                walk(item)
    walk(summary)


# ============================================================ record / replay

def test_a_recorded_reading_replays_without_any_provider(tmp_path, monkeypatch):
    path = tmp_path / "recording.json"
    recording = ScriptedGateway(lambda task, request: READING, recording=RecordingStore(path),
                                usage=Usage(1000, 0, 200, 60))
    live = recording.interpret_message(_request())
    assert live.ok and live.served_from == "scripted" and len(recording.invocations) == 1

    stored = path.read_text(encoding="utf-8")
    assert "still waiting on a door" not in stored, (
        "the recording holds the rendered input; it stores a digest and the validated reply only")
    assert json.loads(stored)["format"] == "neyma-inference-recording-1"

    def no_network(*args, **kwargs):
        raise AssertionError("a replay opened a socket")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)

    replay = ReplayGateway(provider="scripted", model="scripted-reader",
                           recording=RecordingStore(path))
    again = replay.interpret_message(_request())
    assert again.ok and again.served_from == "replay" and again.attempts == 0
    assert again.output == live.output
    assert again.usage == Usage(1000, 0, 200, 60), "the recorded token counts are replayed"
    assert replay.ledger.calls[0].served_from == "replay"
    assert replay.ledger.summary()["live_tokens"]["input_tokens"] == 0

    # A reading that was never recorded is a MISS. Nothing is called, because nothing can be.
    miss = replay.interpret_message(_request("a different message entirely"))
    assert miss.status is Status.REPLAY_MISS and miss.output is None and miss.attempts == 1

    # A replayed reading does not spend the budget; a recorded one is not paid for twice.
    budget = InferenceBudget(max_calls=0, max_input_tokens=1, max_output_tokens=1)
    free = ScriptedGateway(lambda task, request: None, recording=RecordingStore(path),
                           budget=budget)
    assert free.interpret_message(_request()).ok and free.invocations == []
    assert budget.calls == 0


def test_a_recording_is_never_replayed_against_a_different_question():
    base = dict(provider="openai", model="gpt-6-luna", task=Task.INTERPRET_MESSAGE,
                prompt_version="p1", reasoning_effort="low", rendered_input="hello\nworld")
    key = request_key(**base)
    assert key == request_key(**{**base, "rendered_input": "hello  \r\nworld\n"}), (
        "trailing whitespace and line endings changed the key")
    for change in ({"model": "another-model"}, {"task": Task.EXTRACT_COMMITMENTS},
                   {"prompt_version": "p2"}, {"reasoning_effort": "high"},
                   {"provider": "another"}, {"rendered_input": "hello\nworld!"},
                   {"schema_version": "p9-interpretation-2"}):
        assert request_key(**{**base, **change}) != key, change


# ============================================================ the OpenAI adapter, with no network

class _FakeResponses:
    def __init__(self, replies) -> None:
        self.replies = list(replies)
        self.requests: list[dict] = []

    def parse(self, **kwargs):
        self.requests.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _response(payload=READING, *, status="completed", usage=None):
    parsed = None if payload is None else OUTPUT_MODELS[Task.INTERPRET_MESSAGE].model_validate(
        payload)
    return SimpleNamespace(
        output_parsed=parsed, status=status, model="gpt-6-luna-2026-09-23",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        usage=usage or SimpleNamespace(
            input_tokens=1400, output_tokens=310,
            input_tokens_details=SimpleNamespace(cached_tokens=1024),
            output_tokens_details=SimpleNamespace(reasoning_tokens=96)))


class APITimeoutError(Exception):
    pass


class AuthenticationError(Exception):
    status_code = 401
    code = "invalid_api_key"


def _openai(replies, **kwargs) -> tuple[OpenAIResponsesGateway, _FakeResponses]:
    responses = _FakeResponses(replies)
    gateway = OpenAIResponsesGateway(model="gpt-6-luna", client=SimpleNamespace(responses=responses),
                                     reasoning_effort="low", retry_backoff_s=0.0, **kwargs)
    return gateway, responses


def test_a_live_gateway_cannot_be_constructed_without_the_explicit_opt_in():
    with pytest.raises(LiveInferenceNotEnabled):
        OpenAIResponsesGateway(model="gpt-6-luna")
    with pytest.raises(LiveInferenceNotEnabled):
        OpenAIResponsesGateway(model="gpt-6-luna", allow_live=False)


def test_the_openai_adapter_sends_a_strict_typed_request_and_maps_usage():
    gateway, responses = _openai([_response()])
    result = gateway.interpret_message(_request())
    assert result.ok and result.provider == "openai" and result.served_from == "live"
    assert result.model == "gpt-6-luna-2026-09-23", "the model the provider reported is recorded"
    assert result.usage == Usage(1400, 1024, 310, 96)
    sent = responses.requests[0]
    assert sent["model"] == "gpt-6-luna"
    assert sent["text_format"] is OUTPUT_MODELS[Task.INTERPRET_MESSAGE]
    assert sent["instructions"] == INSTRUCTIONS[Task.INTERPRET_MESSAGE]
    assert BODY in sent["input"] and "untrusted data" in sent["input"]
    assert sent["store"] is False and sent["max_output_tokens"] > 0 and sent["timeout"] > 0
    assert sent["reasoning"] == {"effort": "low"}
    assert not {"tools", "tool_choice", "previous_response_id"} & set(sent), (
        "the request carries a tool or a conversation: there is no agent loop in this boundary")


def test_the_openai_adapter_classifies_failures_and_never_leaks_a_key():
    leaky = APITimeoutError(f"timed out; Authorization: Bearer {KEY_SHAPED}")
    gateway, responses = _openai([leaky, leaky])
    result = gateway.interpret_message(_request())
    assert result.status is Status.PROVIDER_FAILURE and result.attempts == 2
    assert len(responses.requests) == 2

    denied = AuthenticationError(f"Incorrect API key provided: {KEY_SHAPED}")
    gateway, responses = _openai([denied, _response()])
    result = gateway.interpret_message(_request())
    assert result.status is Status.PROVIDER_FAILURE and result.attempts == 1
    assert result.detail == "AuthenticationError:401:invalid_api_key"
    assert KEY_SHAPED not in result.debug and "[redacted-key]" in result.debug
    record = gateway.ledger.calls[0]
    assert all(KEY_SHAPED not in str(value) for value in vars(record).values()), (
        "a key-shaped string reached telemetry")
    assert "Incorrect API key" not in record.detail, "a provider's error text reached telemetry"
    assert redact(f"x {KEY_SHAPED} y") == "x [redacted-key] y"

    gateway, responses = _openai([_response(status="incomplete"), _response()])
    result = gateway.interpret_message(_request())
    assert result.status is Status.SCHEMA_FAILURE and result.attempts == 1
    assert result.detail == "incomplete_output:max_output_tokens"
    assert result.usage.input_tokens == 1400, "a truncated reply was still billed"

    gateway, _ = _openai([_response(None)])
    result = gateway.interpret_message(_request())
    assert result.status is Status.PROVIDER_FAILURE and result.detail == "refusal_or_empty_output"


def test_the_sdk_client_is_built_without_hidden_retries_and_the_key_is_not_kept(monkeypatch):
    """With the opt-in and no key, nothing is built. With a key, the SDK client gets
    `max_retries=0` — the gateway's bounded retry is the only retry — and the key is not stored on
    the gateway. `openai.OpenAI` is replaced, so nothing here can reach a network."""
    import openai

    built: list[dict] = []

    class FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            built.append(kwargs)
            self.responses = _FakeResponses([_response()])

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gateway = OpenAIResponsesGateway(model="gpt-6-luna", allow_live=True, retry_backoff_s=0.0)
    result = gateway.interpret_message(_request())
    assert result.status is Status.PROVIDER_FAILURE and result.detail == "api_key_missing"
    assert built == [], "a client was built with no key"

    monkeypatch.setenv("OPENAI_API_KEY", KEY_SHAPED)
    gateway = OpenAIResponsesGateway(model="gpt-6-luna", allow_live=True, retry_backoff_s=0.0)
    assert gateway.interpret_message(_request()).ok
    assert len(built) == 1 and built[0]["max_retries"] == 0 and built[0]["timeout"] > 0
    held = [name for name, value in vars(gateway).items() if value == KEY_SHAPED]
    assert held == [], f"the gateway object keeps the API key in {held}"
    assert KEY_SHAPED not in json.dumps([vars(c) for c in gateway.ledger.calls], default=str)


def test_candidates_are_requested_with_the_supplied_ids_only():
    options = (CandidateOption("brokerage_load:aaa", "references: LD-1 (load_ref)"),
               CandidateOption("brokerage_load:bbb", "references: LD-2 (load_ref)"))
    request = CandidateRequest(route=Route(Task.PROPOSE_ENTITY_CANDIDATES, True, "test"),
                               source_id="obs-9", text="POD for 1", options=options)
    gateway = ScriptedGateway(lambda task, r: candidates(("brokerage_load:aaa", "CLEAR", "1")))
    result = gateway.propose_entity_candidates(request)
    assert result.ok and [c.candidate_id for c in result.output.candidates] == [
        "brokerage_load:aaa"]
    assert "brokerage_load:aaa" in gateway.invocations[0][1].options[0].candidate_id


# ============================================================ configuration

def test_the_default_model_is_luna_and_only_openai_is_implemented():
    default = InferenceSettings.from_env({})
    assert (default.provider, default.model, default.model_source) == ("openai", "gpt-6-luna",
                                                                       "default")
    assert default.reasoning_effort == "low"
    # The legacy vision surface's setting does not choose — or price — the model that reads messages.
    legacy = InferenceSettings.from_env({"OPENAI_MODEL": "a-pricier-vision-model",
                                         "EXTRACTION_PROVIDER": "anthropic"})
    assert (legacy.provider, legacy.model, legacy.model_source) == ("openai", "gpt-6-luna",
                                                                    "default")
    own = InferenceSettings.from_env({"OPENAI_MODEL": "x", "NEYMA_INFERENCE_MODEL": "y"})
    assert (own.model, own.model_source) == ("y", "NEYMA_INFERENCE_MODEL")
    for provider in ("anthropic", "azure", "local"):
        with pytest.raises(UnsupportedProvider):
            InferenceSettings.from_env({"NEYMA_INFERENCE_PROVIDER": provider})


def test_a_dollar_estimate_comes_from_tokens_and_a_versioned_table_or_not_at_all():
    table = load_price_table()
    assert table.version and table.as_of and table.source.startswith("https://")
    usage = Usage(input_tokens=1_000_000, cached_input_tokens=400_000, output_tokens=200_000)
    price = table.models["gpt-6-luna"]
    expected = round((600_000 * price["input_per_mtok_usd"]
                      + 400_000 * price["cached_input_per_mtok_usd"]
                      + 200_000 * price["output_per_mtok_usd"]) / 1_000_000, 6)
    assert table.estimate_usd("gpt-6-luna", usage) == expected
    assert table.estimate_usd("a-model-nobody-priced", usage) is None, (
        "an unlisted model got a guessed price")


# ============================================================ structure: where a model can be reached

def _sdk_importers(files: list[Path]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [node.module or ""]
            hits = {name.split(".")[0] for name in names} & MODEL_SDKS
            if hits:
                found.setdefault(path.relative_to(ROOT).as_posix(), set()).update(hits)
    return found


def test_one_module_in_the_inference_boundary_imports_a_model_sdk():
    """The new boundary has ONE SDK importer. The four legacy modules that reach a provider directly
    are named here by exact set, so a fifth cannot arrive unnoticed — and they are debt, not a
    pattern: new intelligence goes through the gateway."""
    importers = _sdk_importers(population())
    print(f"swept {len(population())} modules; model-SDK importers: {sorted(importers)}")
    package = sorted(p for p in importers if "/inference/" in p)
    assert package == ["src/freight_recon/inference/openai_responses.py"], package
    assert importers["src/freight_recon/inference/openai_responses.py"] == {"openai"}
    legacy = sorted(p for p in importers if "/inference/" not in p)
    assert legacy == ["src/freight_recon/document_identifier.py",
                      "src/freight_recon/extraction.py", "src/freight_recon/knowledge.py",
                      "src/freight_recon/screen_discovery.py"], legacy
    # Importing the boundary's contracts imports no SDK: the closure of everything the freight
    # domain depends on stops short of the provider module.
    closure: set[str] = set()
    for path in sorted((SRC / "freight_domain").rglob("*.py")):
        closure |= import_closure(path)
    assert {"contracts", "ledger", "prompts", "recording"} <= closure, sorted(closure)
    assert "openai_responses" not in closure and "scripted" not in closure, (
        "the freight domain can reach a concrete gateway; it must be handed one")


def test_only_the_eval_script_opts_in_to_live_inference_and_it_needs_two_switches(monkeypatch):
    """`allow_live=True` is written in exactly one place under src/ and scripts/. That script then
    refuses to spend without the environment switch as well, and refuses before any client exists."""
    sites: list[str] = []
    files = population(scripts=True)
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.keyword) and node.arg == "allow_live" \
                    and isinstance(node.value, ast.Constant) and node.value.value is True:
                sites.append(path.relative_to(ROOT).as_posix())
    print(f"swept {len(files)} modules; allow_live=True sites: {sites}")
    assert sites == ["scripts/run_freight_interpretation_eval.py"], sites

    import run_freight_interpretation_eval as script

    def no_network(*args, **kwargs):
        raise AssertionError("the eval script opened a socket")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.delenv(script.LIVE_ENV, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", KEY_SHAPED)
    monkeypatch.setattr(script, "_load_dotenv", lambda: pytest.fail(
        "a refused run read the local .env: secrets were loaded for a run that may not spend"))
    with pytest.raises(SystemExit) as refused:
        script.main(["--live", "--stage", "smoke"])
    assert script.LIVE_ENV in str(refused.value) and "Nothing was called" in str(refused.value)


def test_the_eval_script_defaults_to_replay_and_calls_nothing(tmp_path, monkeypatch, capsys):
    import run_freight_interpretation_eval as script

    def no_network(*args, **kwargs):
        raise AssertionError("a replay run opened a socket")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setenv(script.LIVE_ENV, "1")          # the env switch alone is not enough
    monkeypatch.setenv("OPENAI_API_KEY", KEY_SHAPED)
    monkeypatch.setenv("OPENAI_MODEL", "a-pricier-vision-model")
    monkeypatch.delenv("NEYMA_INFERENCE_MODEL", raising=False)
    monkeypatch.setattr(script, "_load_dotenv", lambda: pytest.fail(
        "a replay run read the local .env: it needs no credential and must load none"))
    code = script.main(["--stage", "smoke", "--recording", str(tmp_path / "empty.json"),
                        "--report", str(tmp_path / "report.json")])
    printed = capsys.readouterr().out
    assert code == 1, "an unrecorded replay must not report success"
    assert "mode=replay" in printed and "REPLAY_MISS" in printed
    assert "model=gpt-6-luna (from default)" in printed, printed.splitlines()[0]
    assert KEY_SHAPED not in printed
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["mode"] == "replay" and report["inference"]["live_tokens"]["input_tokens"] == 0
    assert KEY_SHAPED not in json.dumps(report)


def test_ordinary_ci_holds_no_model_credential_and_no_live_switch():
    """CI is the source of truth for green, and it must cost nothing: the workflow neither carries a
    provider key nor sets the live switch, and no test file in the suite sets it either."""
    workflows = sorted((ROOT / ".github" / "workflows").glob("ci.yml"))
    assert workflows, "the CI workflow was not found"
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        for token in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "NEYMA_LIVE_INFERENCE"):
            assert token not in text, f"{path.name} references {token}"
    tests = sorted((ROOT / "eval" / "tests").rglob("test_*.py"))
    assert len(tests) > 100
    setters: list[str] = []
    for path in tests:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.keyword) and node.arg == "allow_live" \
                    and isinstance(node.value, ast.Constant) and node.value.value is True:
                setters.append(path.name)
    # This file opts in exactly where `openai.OpenAI` has been replaced by a fake.
    assert sorted(set(setters)) == ["test_p9_inference_gateway.py"], setters
    assert (SCRIPTS / "run_freight_interpretation_eval.py").is_file()
