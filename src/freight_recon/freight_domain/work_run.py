"""P9 deep-end 3 — run freight histories THROUGH TIME and ask, after every record, what work remains.

`run_corpus` asks what Neyma concluded at the END of a load. This asks the operating question at
every step: a record arrives (or time simply passes), the canonical state settles, and each load of
that brokerage is evaluated again. Work is seen to OPEN, to change hands between waiting, Neyma and a
human, and to CLOSE.

### THE LIFECYCLE IS OBSERVED, NOT STORED. A need has no row. Its life is read by comparing one
evaluation with the next: an id that appears was opened, one that disappears was closed, and HOW it
closed is read from the canonical record that settled it. Run the same histories again and the same
lives come out.

### THE REPORT COUNTS; IT DOES NOT GRADE, AND IT CARRIES NO MONEY. Every figure is a count of needs,
signals or evaluations. Where a history labels a checkpoint it is CHECKED, one label at a time, and
every mismatch is listed. There is no "human minutes saved": nobody has measured a minute.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from .corpus_run import cross_tenant_violations
from .history import FreightHistory, TenantSetup, to_utc
from .intake import FreightIntake
from .interpretation import FreightInterpreter
from .load_work import (
    PASSIVE,
    Handling,
    LoadWorkState,
    NeedKind,
    OperationalNeed,
    evaluate_load_work,
    evaluate_unplaced_work,
)

WORK_REPORT_VERSION = "p9-load-work-report-1"

#: Kinds that are a wait or a watch. When one disappears because its deadline passed, it did not
#: close: it ESCALATED into the follow-up.
_PENDING_KINDS: tuple[NeedKind, ...] = (
    NeedKind.CARRIER_UPDATE_PENDING, NeedKind.ARRIVAL_PENDING, NeedKind.TRACKING_UPDATE_PENDING,
)


class WorkReasoner(Protocol):
    """What the runner needs of shadow reasoning. `advise` routes first and may call nothing."""

    def advise(self, state: LoadWorkState) -> Any: ...


@dataclass
class NeedLife:
    """One need, from the first evaluation that showed it to the one that no longer did."""

    need_id: str
    kind: str
    tenant_id: str
    load_id: str
    opened_step: int
    handlings: list[str] = field(default_factory=list)
    human_required: bool = False
    closed_step: int | None = None
    closed_how: str | None = None        # SATISFIED | RESOLVED | SUPERSEDED | ESCALATED | CLOSED
    reopened: int = 0

    @property
    def is_open(self) -> bool:
        return self.closed_step is None


@dataclass
class WorkStep:
    index: int
    history_id: str
    label: str
    tenant: str
    as_of: str
    disposition: str
    states: dict[str, LoadWorkState]


@dataclass
class WorkHistoryResult:
    history: FreightHistory
    checks: int = 0
    mismatches: list[str] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WorkRunResult:
    intakes: dict[str, FreightIntake]
    steps: list[WorkStep]
    lives: dict[tuple[str, str], NeedLife]
    histories: list[WorkHistoryResult]
    final: dict[tuple[str, str], LoadWorkState]
    advice: dict[tuple[str, str], Any]
    report: dict[str, Any]

    def state(self, tenant: str, load_number: str) -> LoadWorkState:
        for (owner, _), state in self.final.items():
            if owner == tenant and state.load_number == load_number:
                return state
        raise KeyError(f"{tenant} has no load currently numbered {load_number!r}")

    def at(self, history_id: str, label: str, load_number: str) -> LoadWorkState:
        """The work on a load just after the record labeled `label` arrived."""
        step = next(s for s in self.steps if s.history_id == history_id and s.label == label)
        for state in step.states.values():
            if state.load_number == load_number:
                return state
        raise KeyError(f"{history_id}/{label}: no load numbered {load_number!r}")

    def life(self, tenant: str, kind: str | NeedKind) -> list[NeedLife]:
        wanted = NeedKind(kind).value
        return [life for (owner, _), life in self.lives.items()
                if owner == tenant and life.kind == wanted]


def work_states(intake: FreightIntake, *, as_of: str | None = None) -> dict[str, LoadWorkState]:
    """Every load of this brokerage, evaluated at `as_of` (default: the intake's own clock). A pure
    read of the canonical state: it advances no clock and writes nothing."""
    moment = as_of or intake.foundation.now()
    projection = intake.projection()
    return {load_id: evaluate_load_work(view, setup=intake.setup, as_of=moment)
            for load_id, view in sorted(projection.loads.items())}


# --------------------------------------------------------------------------- labeled checkpoints

def _check(result: WorkHistoryResult, what: str, actual: Any, expected: Any) -> None:
    result.checks += 1
    if actual != expected:
        result.mismatches.append(f"{what}: expected {expected!r}, got {actual!r}")


def _triples(needs: Sequence[OperationalNeed]) -> list[tuple[str, str, str]]:
    return sorted((n.kind.value, n.status.value, n.handling.value) for n in needs)


def check_checkpoint(result: WorkHistoryResult, checkpoint: Mapping[str, Any],
                     state: LoadWorkState) -> None:
    """Assert one labeled moment. Only what the checkpoint LABELS is checked; `needs` is exact —
    a need the label does not name is a mismatch, because unlabeled noise is the defect."""
    where = f"{result.history.history_id}/{checkpoint['after']}/{checkpoint['load']}"
    by_kind: dict[str, list[OperationalNeed]] = {}
    for need in state.needs:
        by_kind.setdefault(need.kind.value, []).append(need)
    if "needs" in checkpoint:
        want = checkpoint["needs"]
        wanted = sorted((kind, status, handling) for kind, (status, handling) in want.items()) \
            if isinstance(want, Mapping) else sorted(tuple(item) for item in want)
        _check(result, f"{where} needs", _triples(state.needs), wanted)
    for key, attribute in (("stage", state.stage.value), ("posture", state.posture.value),
                           ("billing_ready", state.billing_ready),
                           ("human", bool(state.human_attention)),
                           ("quiet", state.routine_work_is_zero),
                           ("status", state.known_status)):
        if key in checkpoint:
            _check(result, f"{where} {key}", attribute, checkpoint[key])
    if "next_action" in checkpoint:
        _check(result, f"{where} next action",
               state.next_action.value if state.next_action else None, checkpoint["next_action"])
    for kind, codes in (checkpoint.get("reasons") or {}).items():
        have = {code for need in by_kind.get(kind, ()) for code in need.reason_codes}
        for code in ([codes] if isinstance(codes, str) else codes):
            _check(result, f"{where} {kind} reason {code}", code in have, True)
    for kind, actions in (checkpoint.get("actions") or {}).items():
        have = sorted({a.value for need in by_kind.get(kind, ()) for a in need.actions})
        _check(result, f"{where} {kind} actions", have, sorted(actions))
    for kind, how in (checkpoint.get("settled") or {}).items():
        _check(result, f"{where} settled {kind}",
               sorted({s.how for s in state.settled if s.kind.value == kind}), [how])
    if "housekeeping" in checkpoint:
        _check(result, f"{where} housekeeping", len(state.housekeeping),
               checkpoint["housekeeping"])
    if "together" in checkpoint:
        _check(result, f"{where} outreach groups", [len(g) for g in state.together],
               checkpoint["together"])
    for kind, due in (checkpoint.get("due") or {}).items():
        wanted_due = sorted(to_utc(d, what="due") for d in ([due] if isinstance(due, str) else due))
        _check(result, f"{where} {kind} due",
               sorted(n.due_by for n in by_kind.get(kind, ()) if n.due_by), wanted_due)


# --------------------------------------------------------------------------- the run

def _closure(life: NeedLife, state: LoadWorkState | None) -> str:
    """How a need that is no longer open ended, read from the state that no longer shows it."""
    if state is not None:
        settled = next((s for s in state.settled if s.need_id == life.need_id), None)
        if settled is not None:
            return settled.how
        if life.kind in {k.value for k in _PENDING_KINDS} \
                and state.need(NeedKind.CARRIER_STATUS_OVERDUE) is not None:
            return "ESCALATED"
    return "CLOSED"


def run_work_histories(conn: sqlite3.Connection, setups: Mapping[str, TenantSetup],
                       histories: Sequence[FreightHistory], *,
                       interpreter: FreightInterpreter | None = None,
                       reasoner: WorkReasoner | None = None) -> WorkRunResult:
    """Step every history through its brokerage's intake on one shared database, evaluating each of
    that brokerage's loads after every record.

    With no `reasoner` no model is asked anything, and the deterministic work stands alone. With
    one, each evaluation is ROUTED first; a model is asked only where act-or-wait is not settled by
    the record, and whatever it returns is advice laid beside the deterministic work, never in it."""
    intakes: dict[str, FreightIntake] = {}
    steps: list[WorkStep] = []
    lives: dict[tuple[str, str], NeedLife] = {}
    final: dict[tuple[str, str], LoadWorkState] = {}
    advice: dict[tuple[str, str], Any] = {}
    results: list[WorkHistoryResult] = []
    evaluations = 0
    signals_seen: set[tuple[str, str]] = set()

    for history in histories:
        intake = intakes.get(history.tenant)
        if intake is None:
            intake = FreightIntake(conn, setups[history.tenant], interpreter=interpreter)
            intakes[history.tenant] = intake
        result = WorkHistoryResult(history=history)
        results.append(result)
        checkpoints: dict[str, list[Mapping[str, Any]]] = {}
        for checkpoint in history.expected.get("work") or ():
            checkpoints.setdefault(checkpoint["after"], []).append(checkpoint)
        unknown = set(checkpoints) - {r.label for r in history.records}
        for label in sorted(unknown):
            result.checks += 1
            result.mismatches.append(f"{history.history_id}: a checkpoint names record {label!r}, "
                                     f"which this history does not have")

        for record in history.records:
            outcome = intake.ingest(record)
            as_of = intake.foundation.now()
            states = work_states(intake, as_of=as_of)
            step = WorkStep(index=len(steps), history_id=history.history_id, label=record.label,
                            tenant=history.tenant, as_of=as_of, disposition=outcome.disposition,
                            states=states)
            steps.append(step)
            evaluations += len(states)

            open_now: dict[str, tuple[OperationalNeed, LoadWorkState]] = {}
            for state in states.values():
                final[(history.tenant, state.load_id)] = state
                for need in state.needs:
                    # A held record offered to two loads is ONE need: the first load showing it
                    # owns the life, and it is open while any load still shows it.
                    open_now.setdefault(need.need_id, (need, state))
                    for origin in need.origins:
                        signals_seen.add((history.tenant, origin))
                if reasoner is not None:
                    advice[(history.tenant, state.load_id)] = reasoner.advise(state)
            for identity, (need, state) in open_now.items():
                life = lives.get((history.tenant, identity))
                if life is None:
                    life = NeedLife(need_id=identity, kind=need.kind.value,
                                    tenant_id=history.tenant, load_id=state.load_id,
                                    opened_step=step.index)
                    lives[(history.tenant, identity)] = life
                elif not life.is_open:
                    life.reopened += 1
                    life.closed_step, life.closed_how = None, None
                if need.handling.value not in life.handlings:
                    life.handlings.append(need.handling.value)
                life.human_required = life.human_required or need.human_required
            for (tenant, identity), life in lives.items():
                if tenant == history.tenant and life.is_open and identity not in open_now:
                    life.closed_step = step.index
                    life.closed_how = _closure(life, states.get(life.load_id))

            for checkpoint in checkpoints.get(record.label, ()):
                moment = (to_utc(checkpoint["at"], what="checkpoint instant")
                          if "at" in checkpoint else as_of)
                asked = states if moment == as_of else work_states(intake, as_of=moment)
                state = next((s for s in asked.values()
                              if s.load_number == checkpoint["load"]), None)
                result.checks += 1
                if state is None:
                    result.mismatches.append(
                        f"{history.history_id}/{record.label}: no load is numbered "
                        f"{checkpoint['load']!r}")
                    continue
                check_checkpoint(result, checkpoint, state)
                result.checkpoints.append({"after": record.label, "as_of": moment,
                                           "load": checkpoint["load"],
                                           "posture": state.posture.value})

    report = build_work_report(conn, intakes, steps=steps, lives=lives, final=final,
                               results=results, evaluations=evaluations,
                               signals=len(signals_seen), reasoner=reasoner)
    return WorkRunResult(intakes=intakes, steps=steps, lives=lives, histories=results,
                         final=final, advice=advice, report=report)


def _per_load(count: int, loads: int) -> float | None:
    return round(count / loads, 3) if loads else None


def build_work_report(conn: sqlite3.Connection, intakes: Mapping[str, FreightIntake], *,
                      steps: Sequence[WorkStep], lives: Mapping[tuple[str, str], NeedLife],
                      final: Mapping[tuple[str, str], LoadWorkState],
                      results: Sequence[WorkHistoryResult], evaluations: int, signals: int,
                      reasoner: WorkReasoner | None) -> dict[str, Any]:
    all_lives = list(lives.values())
    loads = len(final)
    closed: dict[str, int] = {}
    for life in all_lives:
        if life.closed_how:
            closed[life.closed_how] = closed.get(life.closed_how, 0) + 1
    passive = {h.value for h in PASSIVE}
    waits = [life for life in all_lives if set(life.handlings) & passive]
    candidates = [life for life in all_lives if set(life.handlings)
                  & {Handling.NEYMA_ACTION_CANDIDATE.value, Handling.MODEL_REASONING.value}]
    humans = [life for life in all_lives if life.human_required]
    blocked: dict[str, int] = {}
    for state in final.values():
        if not state.billing_ready:
            for blocker in state.billing_blockers:
                reason = blocker.split(":", 1)[0]
                blocked[reason] = blocked.get(reason, 0) + 1
    unplaced = 0
    for tenant, intake in intakes.items():
        unplaced += len(evaluate_unplaced_work(
            intake.projection(), setup=intake.setup, exceptions=intake.foundation.exceptions(),
            as_of=intake.foundation.now()))
    effects = {tenant: intake.foundation.effect_surface_counts()
               for tenant, intake in sorted(intakes.items())}
    kinds: dict[str, int] = {}
    for life in all_lives:
        kinds[life.kind] = kinds.get(life.kind, 0) + 1

    metrics: dict[str, Any] = {
        "histories_processed": len(results),
        "loads_evaluated": loads,
        "operational_state_evaluations": evaluations,
        "raw_operational_signals": signals,
        "unique_operational_needs": len(all_lives),
        "duplicate_needs_suppressed": max(signals - len(all_lives), 0),
        "needs_opened": len(all_lives) + sum(life.reopened for life in all_lives),
        "needs_reopened": sum(life.reopened for life in all_lives),
        "needs_automatically_satisfied": closed.get("SATISFIED", 0),
        "needs_resolved_by_a_human": closed.get("RESOLVED", 0),
        "needs_superseded_or_corrected": closed.get("SUPERSEDED", 0),
        "waits_that_escalated_to_a_follow_up": closed.get("ESCALATED", 0),
        "needs_closed_other": closed.get("CLOSED", 0),
        "needs_still_open": len([life for life in all_lives if life.is_open]),
        "waits": len(waits),
        "neyma_action_candidates": len(candidates),
        "human_required_needs": len(humans),
        "waits_per_load": _per_load(len(waits), loads),
        "neyma_action_candidates_per_load": _per_load(len(candidates), loads),
        "human_required_needs_per_load": _per_load(len(humans), loads),
        "loads_with_zero_routine_work": len([s for s in final.values()
                                             if s.routine_work_is_zero]),
        "loads_reaching_billing_ready": len([s for s in final.values() if s.billing_ready]),
        "loads_billing_ready_and_quiet": len([s for s in final.values()
                                              if s.billing_ready and s.routine_work_is_zero]),
        "loads_blocked_from_billing_ready": len([s for s in final.values()
                                                 if not s.billing_ready]),
        "cured_exceptions_awaiting_human_closure": sum(len(s.housekeeping)
                                                       for s in final.values()),
        "unplaced_work_needing_a_human": unplaced,
        "wrong_cross_tenant_mappings": len(cross_tenant_violations(conn)),
        "external_effect_rows": sum(sum(c.values()) for c in effects.values()),
        "labeled_checkpoints": sum(len(r.checkpoints) for r in results),
        "labeled_checks": sum(r.checks for r in results),
        "labeled_checks_failed": sum(len(r.mismatches) for r in results),
    }
    report: dict[str, Any] = {
        "report_version": WORK_REPORT_VERSION,
        "note": ("Synthetic development corpus. Nothing here is design-partner evidence, no "
                 "freight rule is validated by appearing in it, and no labor time was measured."),
        "metrics": metrics,
        "needs_by_kind": dict(sorted(kinds.items())),
        "billing_blockers": dict(sorted(blocked.items())),
        "effect_surface_rows": effects,
        "histories": [{"history_id": r.history.history_id, "title": r.history.title,
                       "tenant": r.history.tenant, "records": len(r.history.records),
                       "checkpoints": len(r.checkpoints), "labeled_checks": r.checks,
                       "labeled_mismatches": list(r.mismatches)} for r in results],
    }
    summary = getattr(reasoner, "summary", None)
    if callable(summary):
        report["reasoning"] = summary(loads=loads)
    return report


def render_work_run(result: WorkRunResult) -> str:
    """Every history, as the sequence of postures its loads went through."""
    lines: list[str] = []
    for item in result.histories:
        history = item.history
        lines.append(f"=== {history.history_id} - {history.title}")
        own = {r["load"] for r in history.expected.get("work") or ()}
        for step in result.steps:
            if step.history_id != history.history_id:
                continue
            for state in step.states.values():
                if own and state.load_number not in own:
                    continue                          # another history's load, in the same inbox
                needs = ", ".join(f"{n.kind.value}/{n.handling.value}" for n in state.needs)
                lines.append(f"  {step.as_of} {step.label:28s} {state.load_number or '?':10s} "
                             f"{state.stage.value:10s} {state.posture.value:15s} "
                             f"{needs or '-'}")
        lines.extend(f"  !! {m}" for m in item.mismatches)
        lines.append("")
    return "\n".join(lines)


__all__ = ["NeedLife", "WORK_REPORT_VERSION", "WorkHistoryResult", "WorkRunResult", "WorkStep",
           "build_work_report", "check_checkpoint", "render_work_run", "run_work_histories",
           "work_states"]
