"""Inference telemetry and the per-run budget: what every model call cost, and what avoided one.

### TOKENS ARE THE DURABLE TRUTH. A record carries the provider's token counts, the model and the
task. Dollar cost is computed from tokens and a versioned price table at report time (`settings.py`)
and is never written into a call record: prices change, token counts do not.

### NO CONTENT, NO CREDENTIAL. A record identifies what was read by a SHA-256 digest of the rendered
input. It never holds the message, the document, the prompt or an API key, and a failure is recorded
as a short code, never as a provider's error text.

### A ROUTING RECORD IS A MODEL CALL THAT DID NOT HAPPEN. The routing boundary records every piece of
work it settled deterministically, with the reason. That is what makes the deterministic-vs-model
rate measurable instead of asserted.

### THE BUDGET IS A FUSE, NOT A BILLING SYSTEM. It stops one run from looping through real money. The
provider-side project budget remains the financial backstop.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .contracts import Status, Task, Usage

UNCORRELATED = "uncorrelated"


@dataclass(frozen=True)
class CallRecord:
    at: str
    provider: str
    model: str
    task: str
    outcome: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    latency_ms: int
    retry_count: int
    subject_ref: str
    correlation_id: str | None
    content_digest: str
    request_digest: str
    served_from: str
    detail: str = ""
    kind: str = "call"


@dataclass(frozen=True)
class RoutingRecord:
    at: str
    task: str
    model_needed: bool
    reason: str
    subject_ref: str
    correlation_id: str | None
    content_digest: str
    kind: str = "routing"


@dataclass
class InferenceBudget:
    """The most one run may spend. `admit` is asked before EVERY attempt, retries included."""

    max_calls: int
    max_input_tokens: int
    max_output_tokens: int
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def exhausted(self) -> bool:
        return (self.calls >= self.max_calls or self.input_tokens >= self.max_input_tokens
                or self.output_tokens >= self.max_output_tokens)

    def admit(self) -> bool:
        if self.exhausted:
            return False
        self.calls += 1
        return True

    def spend(self, usage: Usage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    def as_document(self) -> dict[str, int]:
        return {"max_calls": self.max_calls, "max_input_tokens": self.max_input_tokens,
                "max_output_tokens": self.max_output_tokens, "calls": self.calls,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens}


@dataclass
class InferenceLedger:
    """Every call and every routing decision of one run, optionally appended to a JSONL file as it
    happens so a crashed run still leaves a spend record."""

    sink: Path | None = None
    calls: list[CallRecord] = field(default_factory=list)
    routings: list[RoutingRecord] = field(default_factory=list)
    correlations: dict[str, str] = field(default_factory=dict)

    def _append(self, document: dict[str, Any]) -> None:
        if self.sink is None:
            return
        self.sink.parent.mkdir(parents=True, exist_ok=True)
        with self.sink.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(document, sort_keys=True) + "\n")

    def record_call(self, record: CallRecord) -> None:
        self.calls.append(record)
        self._append(asdict(record))

    def record_routing(self, record: RoutingRecord) -> None:
        self.routings.append(record)
        self._append(asdict(record))

    def correlate(self, subject_ref: str, correlation_id: str) -> None:
        """Name the load (or work item) a subject turned out to belong to. Interpretation happens
        before binding, so the correlation is usually learned after the call was recorded."""
        if self.correlations.get(subject_ref) == correlation_id:
            return
        self.correlations[subject_ref] = correlation_id
        self._append({"kind": "correlation", "subject_ref": subject_ref,
                      "correlation_id": correlation_id})

    def correlation_of(self, record: CallRecord | RoutingRecord) -> str:
        return (self.correlations.get(record.subject_ref) or record.correlation_id
                or UNCORRELATED)

    # ------------------------------------------------------------------ aggregation

    def model_calls(self, task: Task | None = None) -> list[CallRecord]:
        return [c for c in self.calls if task is None or c.task == task.value]

    def summary(self) -> dict[str, Any]:
        """Counts only. Safe to print, log and commit: no content, no money."""
        by_task: dict[str, dict[str, int]] = {}
        by_correlation: dict[str, dict[str, int]] = {}
        outcomes: dict[str, int] = {}
        served: dict[str, int] = {}
        total = Usage()
        live = Usage()
        for call in self.calls:
            usage = Usage(call.input_tokens, call.cached_input_tokens, call.output_tokens,
                          call.reasoning_tokens)
            total = total + usage
            if call.served_from == "live":
                live = live + usage
            outcomes[call.outcome] = outcomes.get(call.outcome, 0) + 1
            served[call.served_from] = served.get(call.served_from, 0) + 1
            for bucket, key in ((by_task, call.task), (by_correlation, self.correlation_of(call))):
                row = bucket.setdefault(key, {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                              "failures": 0, "retries": 0})
                row["calls"] += 1
                row["input_tokens"] += call.input_tokens
                row["output_tokens"] += call.output_tokens
                row["failures"] += int(call.outcome != Status.OK.value)
                row["retries"] += call.retry_count
        routed: dict[str, dict[str, int]] = {}
        reasons: dict[str, int] = {}
        for routing in self.routings:
            row = routed.setdefault(routing.task, {"deterministic": 0, "model": 0})
            row["deterministic"] += 1
            reasons[routing.reason] = reasons.get(routing.reason, 0) + 1
        for call in self.calls:
            routed.setdefault(call.task, {"deterministic": 0, "model": 0})["model"] += 1
        deterministic = len(self.routings)
        decisions = deterministic + len(self.calls)
        return {
            "calls": len(self.calls),
            "calls_by_task": dict(sorted(by_task.items())),
            "calls_by_correlation": dict(sorted(by_correlation.items())),
            "outcomes": dict(sorted(outcomes.items())),
            "served_from": dict(sorted(served.items())),
            "failures": sum(v for k, v in outcomes.items() if k != Status.OK.value),
            "retries": sum(c.retry_count for c in self.calls),
            "tokens": asdict(total),
            "live_tokens": asdict(live),
            "latency_ms_total": sum(c.latency_ms for c in self.calls),
            "routing": {
                "decisions": decisions,
                "settled_deterministically": deterministic,
                "sent_to_model": len(self.calls),
                "deterministic_rate": (round(deterministic / decisions, 4) if decisions else None),
                "by_task": dict(sorted(routed.items())),
                "deterministic_reasons": dict(sorted(reasons.items())),
            },
        }


def load_ledger(path: Path) -> InferenceLedger:
    """Rebuild a ledger from its JSONL file, for aggregation after the run that wrote it."""
    ledger = InferenceLedger()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        document = json.loads(line)
        kind = document.get("kind")
        if kind == "call":
            ledger.calls.append(CallRecord(**document))
        elif kind == "routing":
            ledger.routings.append(RoutingRecord(**document))
        elif kind == "correlation":
            ledger.correlations[document["subject_ref"]] = document["correlation_id"]
    return ledger
