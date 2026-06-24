"""Internal multi-day dogfood pilot session ledger.

The one-command dogfood runner proves a single operational batch. This module turns those batches
into a repeatable internal pilot with day-level artifacts and a top-level readiness ledger.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PilotDayResult(BaseModel):
    day: int
    workspace: str
    report_path: str | None = None
    ready: bool
    gates: dict[str, bool] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)


class PilotSessionLedger(BaseModel):
    company: str = "Neyma Test Freight LLC"
    operator: str = "Rasheed"
    days_requested: int
    days_completed: int
    ready_for_design_partner: bool
    days: list[PilotDayResult]
    totals: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    next_step: str


PilotRunFn = Callable[..., dict[str, Any]]


def run_pilot_session(
    *,
    session_workspace: Path,
    run_pilot: PilotRunFn,
    days: int = 7,
    loads_per_day: int = 18,
    seed: int = 42,
    age_hours: int = 48,
) -> PilotSessionLedger:
    """Run a multi-day internal dogfood pilot and write a readiness ledger.

    ``run_pilot`` is injected so tests can use a fast fixture runner while the CLI can call the
    real dogfood pipeline.
    """
    if days <= 0:
        raise ValueError("days must be positive")
    if loads_per_day <= 0:
        raise ValueError("loads_per_day must be positive")
    session_workspace.mkdir(parents=True, exist_ok=True)
    day_results: list[PilotDayResult] = []
    for day in range(1, days + 1):
        day_workspace = session_workspace / f"day_{day:02d}"
        report = run_pilot(
            workspace=day_workspace,
            loads_count=loads_per_day,
            seed=seed + day - 1,
            age_hours=age_hours,
        )
        day_result = evaluate_pilot_day(day=day, workspace=day_workspace, report=report)
        day_results.append(day_result)
        (day_workspace / "pilot_day_result.json").write_text(day_result.model_dump_json(indent=2), encoding="utf-8")

    ledger = build_session_ledger(days_requested=days, day_results=day_results)
    (session_workspace / "pilot_session_ledger.json").write_text(ledger.model_dump_json(indent=2), encoding="utf-8")
    (session_workspace / "pilot_session_summary.txt").write_text(render_pilot_session(ledger), encoding="utf-8")
    return ledger


def evaluate_pilot_day(*, day: int, workspace: Path, report: dict[str, Any]) -> PilotDayResult:
    """Evaluate one dogfood report against internal pilot gates."""
    artifacts = report.get("artifacts") or {}
    gates = {
        "email_ingestion_linking_clean": _metric_at_least(report, ("email_ingestion", "packet_link_accuracy"), 1.0),
        "email_ingestion_doc_type_clean": _metric_at_least(report, ("email_ingestion", "doc_type_accuracy"), 1.0),
        "noise_rejection_clean": _metric_at_least(report, ("email_ingestion", "noise_rejection_rate"), 1.0),
        "mailbox_messages_scanned": int((report.get("mailbox_workflow") or {}).get("scanned") or 0) > 0,
        "mailbox_packets_created": int((report.get("mailbox_workflow") or {}).get("packet_runs") or 0) > 0,
        "mailbox_reviews_match_delivery": _mailbox_reviews_match_delivery(report),
        "mailbox_workflow_artifact_written": _artifact_exists(artifacts.get("mailbox_workflow")),
        "mailbox_safety_missing_docs_reviewed": _metric_at_least(
            report, ("mailbox_safety", "missing_required_reviews"), 1.0
        ),
        "mailbox_safety_extraneous_reviewed": _metric_at_least(
            report, ("mailbox_safety", "extraneous_reviews"), 1.0
        ),
        "mailbox_safety_duplicates_reviewed": _metric_at_least(
            report, ("mailbox_safety", "duplicate_reviews"), 1.0
        ),
        "mailbox_request_backup_loop_exercised": (
            int((report.get("workflow_states") or {}).get("REQUESTED_BACKUP") or 0) > 0
        ),
        "review_messages_created": int(report.get("delivery_messages") or 0) > 0,
        "packet_pages_created": int(report.get("packet_pages") or 0) > 0,
        "signed_money_action_applied": bool(report.get("signed_action_applied")),
        "callback_action_applied": bool(report.get("local_callback_action_applied")),
        "tms_readback_verified": bool(report.get("tms_readback_verified")),
        "mock_tms_write_verified": bool(report.get("mock_tms_write_verified")),
        "no_real_tms_write": _no_real_tms_write(report),
        "tokens_redacted": _tokens_redacted_in_artifacts(
            artifacts.get("delivery_messages"),
            artifacts.get("mailbox_workflow"),
        ),
        "callback_artifact_written": _artifact_exists(artifacts.get("callback_action_response")),
        "daily_summary_written": _artifact_exists(artifacts.get("daily_summary")),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    metrics = {
        "loads_generated": report.get("loads_generated"),
        "review_payloads": report.get("review_payloads"),
        "delivery_messages": report.get("delivery_messages"),
        "mailbox_workflow": report.get("mailbox_workflow", {}),
        "mailbox_safety": report.get("mailbox_safety", {}),
        "workflow_states": report.get("workflow_states", {}),
        "found_money_line_present": "Month to date:" in (report.get("daily_summary_text") or ""),
    }
    gates["found_money_summary_visible"] = bool(metrics["found_money_line_present"])
    if not gates["found_money_summary_visible"]:
        blockers.append("found_money_summary_visible")
    report_path = artifacts.get("pilot_report")
    return PilotDayResult(
        day=day,
        workspace=str(workspace),
        report_path=report_path,
        ready=not blockers,
        gates=gates,
        metrics=metrics,
        blockers=blockers,
    )


def build_session_ledger(*, days_requested: int, day_results: list[PilotDayResult]) -> PilotSessionLedger:
    blockers: list[str] = []
    for day in day_results:
        blockers.extend(f"day_{day.day:02d}:{blocker}" for blocker in day.blockers)
    totals = {
        "loads_generated": sum(int(day.metrics.get("loads_generated") or 0) for day in day_results),
        "review_payloads": sum(int(day.metrics.get("review_payloads") or 0) for day in day_results),
        "delivery_messages": sum(int(day.metrics.get("delivery_messages") or 0) for day in day_results),
        "ready_days": sum(1 for day in day_results if day.ready),
    }
    ready = len(day_results) == days_requested and not blockers
    next_step = (
        "prepare design-partner deployment planning; keep real sends/writes gated"
        if ready
        else "fix failed internal pilot gates before any design-partner deployment planning"
    )
    return PilotSessionLedger(
        days_requested=days_requested,
        days_completed=len(day_results),
        ready_for_design_partner=ready,
        days=day_results,
        totals=totals,
        blockers=blockers,
        next_step=next_step,
    )


def render_pilot_session(ledger: PilotSessionLedger) -> str:
    lines = [
        "Neyma Internal Dogfood Pilot Ledger",
        f"Company: {ledger.company}",
        f"Operator: {ledger.operator}",
        f"Days: {ledger.days_completed}/{ledger.days_requested}",
        f"Ready for design partner planning: {'yes' if ledger.ready_for_design_partner else 'no'}",
        (
            f"Totals: {ledger.totals.get('loads_generated', 0)} loads - "
            f"{ledger.totals.get('review_payloads', 0)} review packets - "
            f"{ledger.totals.get('delivery_messages', 0)} delivery messages"
        ),
        "",
        "Daily gates:",
    ]
    for day in ledger.days:
        status = "PASS" if day.ready else "FAIL"
        lines.append(f"- Day {day.day:02d}: {status} ({day.workspace})")
        if day.blockers:
            lines.append(f"  Blockers: {', '.join(day.blockers)}")
    lines.extend(["", f"Next step: {ledger.next_step}"])
    return "\n".join(lines)


def _metric_at_least(report: dict[str, Any], path: tuple[str, ...], threshold: float) -> bool:
    value: Any = report
    for key in path:
        if not isinstance(value, dict):
            return False
        value = value.get(key)
    try:
        return float(value) >= threshold
    except (TypeError, ValueError):
        return False


def _no_real_tms_write(report: dict[str, Any]) -> bool:
    drill = report.get("sample_tms_write_drill") or {}
    return bool(drill) and drill.get("mode") == "mock_only" and drill.get("real_tms_write") is False


def _mailbox_reviews_match_delivery(report: dict[str, Any]) -> bool:
    mailbox = report.get("mailbox_workflow") or {}
    try:
        return (
            int(mailbox.get("review_payloads") or 0) == int(report.get("review_payloads") or 0)
            and int(mailbox.get("delivery_messages") or 0) == int(report.get("delivery_messages") or 0)
        )
    except (TypeError, ValueError):
        return False


def _tokens_redacted_in_artifacts(*paths: str | None) -> bool:
    return all(_delivery_tokens_redacted(path) for path in paths if path)


def _artifact_exists(path: str | None) -> bool:
    return bool(path) and Path(path).exists()


def _delivery_tokens_redacted(path: str | None) -> bool:
    if not path or not Path(path).exists():
        return False
    try:
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    tokens = list(_signed_tokens(artifact))
    return bool(tokens) and all(token.startswith("redacted:") for token in tokens)


def _signed_tokens(value: Any):
    if isinstance(value, dict):
        token = value.get("signed_token")
        if isinstance(token, str) and token:
            yield token
        for child in value.values():
            yield from _signed_tokens(child)
    elif isinstance(value, list):
        for child in value:
            yield from _signed_tokens(child)
