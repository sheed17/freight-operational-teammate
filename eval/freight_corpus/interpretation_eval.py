"""The freight-interpretation eval: run a gateway over labeled freight language and score it.

Provider-agnostic. Every function here takes an `InferenceGateway` — the scripted one in tests, a
replay of recorded readings by default, the live one only when the eval script is explicitly told to
spend. Nothing in this module can make a paid call on its own.

    smoke      five representative messages; prints nothing, returns the converted readings
    labeled    24 labeled messages + 6 correlation cases, scored field by field; plus the narrow
               `extract_commitments` task on the commitment cases
    corpus     the twenty hostile histories in raw form, through the real spine: the histories' own
               labeled outcomes, and per-message agreement with the fixtures' structured asserts
    scenarios  the nine raw-language histories, through the real spine

### THE DENOMINATOR IS ALWAYS REPORTED. Every score is `passed / checked`, with the failed checks
listed. A stage that checked nothing reports zero checks, never a pass.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from freight_recon.freight_domain.corpus_run import CorpusResult, run_corpus
from freight_recon.freight_domain.history import FreightHistory, parse_record
from freight_recon.freight_domain.interpretation import (
    FreightInterpreter,
    commitment_deadline,
    convert_message,
    ground,
    screen_candidates,
)
from freight_recon.inference.contracts import (
    CandidateRequest,
    InferenceGateway,
    MessageRequest,
    Route,
    Status,
    Task,
)
from freight_recon.inference.ledger import InferenceLedger
from freight_recon.workflow import WorkflowStore

from .histories import build_corpus
from .interpretation_cases import (
    CORRELATION_CASES,
    LABELED_MESSAGES,
    CorrelationCase,
    LabeledMessage,
    coverage,
    expected_fields,
    score_correlation,
    score_message,
)
from .parties import SETUPS
from .raw import build_raw_corpus, raw_message_labels
from .raw_histories import build_raw_histories

SMOKE_CASES: tuple[str, ...] = ("LM01", "LM02", "LM05", "LM07", "LM10")
STAGES: tuple[str, ...] = ("smoke", "labeled", "corpus", "scenarios")
#: The stop keys every corpus load uses. A fixture names a stop by key; a reading names its kind.
_STOP_KIND = {"S1": "PICKUP", "S2": "DELIVERY", None: None}


def _message_request(case: LabeledMessage, task: Task) -> MessageRequest:
    return MessageRequest(
        route=Route(task, True, "labeled_eval"), source_id=f"eval:{case.case_id}",
        channel=case.channel, sender_role=case.sender_role, sent_local=case.sent,
        timezone=case.zone, subject=case.subject, body=case.body,
        correlation_id=f"eval:{case.case_id}")


def run_labeled_messages(gateway: InferenceGateway,
                         cases: Sequence[LabeledMessage] = LABELED_MESSAGES) -> dict[str, Any]:
    """Read each labeled message and score what the application would use."""
    results: list[dict[str, Any]] = []
    checked = passed = failed_calls = dropped = 0
    for case in cases:
        reading = gateway.interpret_message(_message_request(case, Task.INTERPRET_MESSAGE))
        if not reading.ok or reading.output is None:
            failed_calls += 1
            results.append({"case": case.case_id, "tags": list(case.tags),
                            "call": f"{reading.status.value}:{reading.detail}",
                            "debug": reading.debug, "fields": {}, "passed": False})
            continue
        converted = convert_message(reading.output, body=case.body, subject=case.subject,
                                    as_of_utc=case.sent_utc(), zone=case.zone)
        verdicts = score_message(case, converted.asserts, converted.mentions)
        checked += len(verdicts)
        passed += sum(v["ok"] for v in verdicts.values())
        dropped += len(converted.dropped)
        results.append({
            "case": case.case_id, "tags": list(case.tags), "call": "OK",
            "category": reading.output.category,
            "passed": all(v["ok"] for v in verdicts.values()),
            "fields": {name: v for name, v in verdicts.items() if not v["ok"]},
            "asserts": converted.asserts, "mentions": converted.mentions,
            "dropped": converted.dropped})
    return {"cases": len(cases), "cases_fully_correct": sum(r["passed"] for r in results),
            "fields_checked": checked, "fields_correct": passed, "failed_calls": failed_calls,
            "items_dropped_by_grounding": dropped, "results": results}


def run_correlation_cases(gateway: InferenceGateway,
                          cases: Sequence[CorrelationCase] = CORRELATION_CASES) -> dict[str, Any]:
    """Ask for candidate loads and score the SCREENED answer — after every id the request did not
    supply has been refused. `ids_refused` counts how often the model offered one."""
    results: list[dict[str, Any]] = []
    refused_total = failed_calls = 0
    for case in cases:
        reading = gateway.propose_entity_candidates(CandidateRequest(
            route=Route(Task.PROPOSE_ENTITY_CANDIDATES, True, "labeled_eval"),
            source_id=f"eval:{case.case_id}", text=case.text, options=case.options,
            correlation_id=f"eval:{case.case_id}"))
        if not reading.ok or reading.output is None:
            failed_calls += 1
            results.append({"case": case.case_id, "tags": list(case.tags), "ok": False,
                            "call": f"{reading.status.value}:{reading.detail}",
                            "debug": reading.debug})
            continue
        accepted, refused = screen_candidates(reading.output, options=case.options,
                                              text=case.text)
        verdict = score_correlation(case, [c["candidate_id"] for c in accepted], refused)
        refused_total += len(refused)
        results.append({"case": case.case_id, "tags": list(case.tags), "call": "OK", **verdict,
                        "proposed": [c.candidate_id for c in reading.output.candidates]})
    return {"cases": len(cases), "cases_correct": sum(bool(r["ok"]) for r in results),
            "ids_refused": refused_total, "failed_calls": failed_calls, "results": results}


def run_commitment_task(gateway: InferenceGateway,
                        cases: Sequence[LabeledMessage] = LABELED_MESSAGES) -> dict[str, Any]:
    """The NARROW task on the cases tagged `commitment`: does asking only for commitments find the
    same deadlines, and what does the smaller question cost?"""
    chosen = [c for c in cases if "commitment" in c.tags]
    results: list[dict[str, Any]] = []
    for case in chosen:
        reading = gateway.extract_commitments(_message_request(case, Task.EXTRACT_COMMITMENTS))
        if not reading.ok or reading.output is None:
            results.append({"case": case.case_id, "ok": False,
                            "call": f"{reading.status.value}:{reading.detail}"})
            continue
        dues = sorted(
            due for item in reading.output.commitments
            if not item.in_quoted_text
            and ground(item.evidence_text, body=case.body, subject=case.subject) is not None
            and (due := commitment_deadline(item, as_of_utc=case.sent_utc(), zone=case.zone)))
        want = expected_fields(case)["commitments"]
        results.append({"case": case.case_id, "ok": dues == want, "expected": want,
                        "observed": dues, "call": "OK"})
    return {"cases": len(chosen), "cases_correct": sum(bool(r["ok"]) for r in results),
            "results": results}


# --------------------------------------------------------------------------- through the spine

def _signature(asserts: Sequence[Mapping[str, Any]]) -> list[tuple[Any, ...]]:
    """One message's asserts as comparable facts, the same for a fixture's and a reading's."""
    out: list[tuple[Any, ...]] = []
    for item in asserts:
        kind = item["type"]
        if kind == "status":
            stop = item.get("stop_type") or _STOP_KIND.get(item.get("stop_key"))
            out.append(("status", item["status"],
                        None if item["status"] == "IN_TRANSIT" else stop))
        elif kind == "commitment":
            out.append(("quoted_commitment",) if item["in_quoted_text"]
                       else ("commitment", item["due_by"]))
        elif kind == "appointment":
            if "start_local" in item:
                out.append(("appointment", _STOP_KIND.get(item["stop_key"]), item["start_local"]))
            else:
                out.append(("appointment", item["stop_type"],
                            f"{item['local_date']}T{item['start_time']}"))
        elif kind == "accessorial_claim":
            out.append(("accessorial", item["charge_type"], item["amount_minor"],
                        item["claims_authorization"]))
        elif kind == "rate":
            out.append(("rate", item["amount_minor"]))
        # A `delay` is deliberately not compared: it drives no machine (it is a timeline line), and
        # the fixtures structured it for some messages that mention one and not for others.
    return sorted(out, key=repr)


def message_agreement(result: CorpusResult, raw: Sequence[FreightHistory]) -> dict[str, Any]:
    """For every message the raw corpus left to a reader: do the asserts the reading produced equal
    the ones the structured fixture supplied? Compared as facts, per message, with every difference
    listed. A quoted commitment is compared on being recognized as quoted, not on its date."""
    structured = {h.history_id: h for h in build_corpus()}
    wanted = set(raw_message_labels(list(raw)))
    rows: list[dict[str, Any]] = []
    for history in raw:
        intake = result.intakes[history.tenant]
        for record in history.records:
            if (history.history_id, record.label) not in wanted:
                continue
            original = next(r for r in structured[history.history_id].records
                            if r.label == record.label)
            want = _signature(parse_record(original)["payload"]["asserts"])
            observation = intake.foundation.observation_by_external(record.source_system,
                                                                    record.external_id)
            parsed = (observation or {}).get("parsed") or {}
            got = _signature(parsed.get("payload", {}).get("asserts", ()))
            reading = parsed.get("interpretation") or {}
            rows.append({"message": f"{history.history_id}/{record.label}", "ok": want == got,
                         "reading": reading.get("status"), "expected": want, "observed": got,
                         "dropped": reading.get("dropped", [])})
    return {"messages": len(rows), "messages_agreeing": sum(r["ok"] for r in rows),
            "differences": [r for r in rows if not r["ok"]]}


def _through_spine(gateway: InferenceGateway, ledger: InferenceLedger,
                   histories: Sequence[FreightHistory], *,
                   agreement: bool = False) -> dict[str, Any]:
    """Run histories through the real spine on a throwaway database and summarize. Everything that
    reads the database is computed before it is closed."""
    with tempfile.TemporaryDirectory(prefix="neyma-interpretation-eval-") as scratch:
        store = WorkflowStore(Path(scratch) / "eval.db", tenant=histories[0].tenant)
        try:
            result = run_corpus(store.conn, SETUPS, histories,
                                interpreter=FreightInterpreter(gateway, ledger))
            summary = _spine_summary(result)
            if agreement:
                summary["message_agreement"] = message_agreement(result, histories)
            return summary
        finally:
            store.close()


def _spine_summary(result: CorpusResult) -> dict[str, Any]:
    metrics = result.report["metrics"]
    return {
        "histories": metrics["histories_processed"],
        "labeled_outcomes_checked": metrics["labeled_expectations_checked"],
        "labeled_outcomes_failed": metrics["labeled_expectations_failed"],
        "mismatches": [m for h in result.histories for m in h.mismatches],
        "model_readings": metrics["model_readings"],
        "model_reading_failures": metrics["model_reading_failures"],
        "model_candidate_requests": metrics["model_candidate_requests"],
        "model_candidates_refused": metrics["model_candidates_refused"],
        "model_inferred_ambiguities": metrics["model_inferred_ambiguities"],
        "wrong_cross_tenant_mappings": metrics["wrong_cross_tenant_mappings"],
        "external_effect_rows": metrics["external_effect_rows"],
        "loads": metrics["canonical_loads_produced"],
    }


def run_raw_corpus(gateway: InferenceGateway, ledger: InferenceLedger) -> dict[str, Any]:
    """The twenty hostile histories, raw, through the real spine."""
    histories, _ = build_raw_corpus()
    return _through_spine(gateway, ledger, histories, agreement=True)


def run_raw_histories(gateway: InferenceGateway, ledger: InferenceLedger) -> dict[str, Any]:
    """The nine raw-language histories through the real spine."""
    return _through_spine(gateway, ledger, build_raw_histories())


def run_stage(stage: str, gateway: InferenceGateway, ledger: InferenceLedger) -> dict[str, Any]:
    if stage == "smoke":
        cases = [c for c in LABELED_MESSAGES if c.case_id in SMOKE_CASES]
        return {"messages": run_labeled_messages(gateway, cases)}
    if stage == "labeled":
        return {"coverage": coverage(), "messages": run_labeled_messages(gateway),
                "correlation": run_correlation_cases(gateway),
                "commitments_only_task": run_commitment_task(gateway)}
    if stage == "corpus":
        return run_raw_corpus(gateway, ledger)
    if stage == "scenarios":
        return run_raw_histories(gateway, ledger)
    raise ValueError(f"unknown stage {stage!r}; the stages are {list(STAGES)}")


def calls_failed(ledger: InferenceLedger) -> dict[str, int]:
    out: dict[str, int] = {}
    for call in ledger.calls:
        if call.outcome != Status.OK.value:
            out[call.outcome] = out.get(call.outcome, 0) + 1
    return out
