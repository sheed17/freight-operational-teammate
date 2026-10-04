"""P9 deep-end 3 — shadow load reasoning: ONE bounded question a model may be asked about a load's
work, and everything the answer is not allowed to do.

    LoadWorkState (deterministic)
        -> route      is act-or-wait genuinely unsettled by the record?  (almost always it is not)
        -> ask        the supplied needs, the closed actions each may take, the evidence behind them
        -> screen     every id it names must be one it was handed, or that PART is refused
        -> WorkAdvice laid BESIDE the deterministic work, never in it

### THE DETERMINISTIC WORK STANDS, WHATEVER HAPPENS HERE. `advise` returns advice and changes no need.
A timeout, a refusal, a malformed reply or an exhausted budget leaves the work exactly as the
projection produced it, with the undecided need still listing both of its answers.

### WHEN A MODEL IS ASKED. Only when at least one need is `MODEL_REASONING`: a carrier-directed need
is open while that carrier has a promise still pending, and the canonical record does not say what
the promise was ABOUT — only its words do. Whether to act now or wait for it is then a question about
language, and that is the one thing a model is for. A quiet load, a waiting load, a load whose
candidates each have one action, and a load that only needs a human are all settled without a call.

### WHAT A MODEL CANNOT DO, BY CONSTRUCTION RATHER THAN BY INSTRUCTION.
  * Name a need, an action or a piece of evidence it was not handed. Each is checked against the
    request; an unknown one is refused, and the rest of the reply still stands.
  * Choose an action the need does not offer. The closed set is per need.
  * Suppress a human's need. A need that is `human_required` never offers WAIT, so the choice cannot
    be made; and the effective posture is recomputed here from the surviving choices — the reply's
    own `posture` field is compared, reported when it disagrees, and has no effect.
  * Create a fact, a deadline, a need or an effect. There is no field for one, and nothing reads
    the advice into canonical state.

### THE SAME QUESTION IS NOT PAID FOR TWICE. Advice is remembered per load against a digest of the
QUESTION — the needs, their statuses, their actions and their evidence. While that is unchanged, the
next evaluation reuses the answer and records a call that did not happen.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..inference.contracts import (
    InferenceGateway,
    LoadWorkReasoning,
    LoadWorkRequest,
    Route,
    Task,
    Usage,
    WorkEvidenceItem,
    WorkNeedOption,
)
from ..inference.ledger import InferenceLedger, RoutingRecord
from ..inference.settings import load_price_table
from .load_work import (
    PASSIVE,
    Handling,
    LoadWorkState,
    OperationalNeed,
    Posture,
    ShadowAction,
)

REASONER_VERSION = "p9-work-reasoner-1"

NOT_NEEDED = "NOT_NEEDED"
ADVISED = "ADVISED"
REUSED = "REUSED"
FAILED = "FAILED"

#: The most a model is shown of one load. A load with more open needs than this is a human's
#: problem, not a longer prompt.
MAX_NEEDS = 12
MAX_EVIDENCE = 16
MAX_EXCERPT = 240
MAX_EXPLANATION = 400


def route_load_work(state: LoadWorkState) -> Route:
    """Whether this load's work needs a model at all. It needs one only when a need's next step is
    act-or-wait and the record cannot settle which."""
    task = Task.REASON_LOAD_WORK
    if not state.needs:
        return Route(task, False, "quiet")
    if any(n.handling is Handling.MODEL_REASONING for n in state.needs):
        return Route(task, True, "act_or_wait_not_settled_by_the_record")
    if all(n.handling in PASSIVE for n in state.needs):
        return Route(task, False, "only_waiting")
    if all(n.human_required or n.handling in PASSIVE for n in state.needs):
        return Route(task, False, "human_attention_only")
    return Route(task, False, "deterministic_work_is_sufficient")


def question_digest(state: LoadWorkState) -> str:
    """What makes the question the SAME question: the needs, not the clock. Time passing with
    nothing changing does not ask again; a need opening, closing or changing hands does."""
    material = [[n.need_id, n.status.value, n.handling.value, [a.value for a in n.actions],
                 list(n.reason_codes), [e.evidence_id for e in n.evidence]] for n in state.needs]
    text = json.dumps([state.tenant_id, state.load_id, material], sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_request(state: LoadWorkState, route: Route) -> LoadWorkRequest:
    """The bounded canonical summary a model is shown. One load, one brokerage, its own ids — and
    nothing that is money: the projection carries none, and none is added here."""
    needs = state.needs[:MAX_NEEDS]
    shown: dict[str, WorkEvidenceItem] = {}
    options: list[WorkNeedOption] = []
    for need in needs:
        ids: list[str] = []
        for item in need.evidence:
            if item.evidence_id not in shown and len(shown) >= MAX_EVIDENCE:
                continue
            shown.setdefault(item.evidence_id, WorkEvidenceItem(
                evidence_id=item.evidence_id, kind=item.kind, note=item.note,
                excerpt=item.excerpt[:MAX_EXCERPT] if item.excerpt else None))
            ids.append(item.evidence_id)
        options.append(WorkNeedOption(
            need_id=need.need_id, kind=need.kind.value, status=need.status.value,
            handling=need.handling.value, human_required=need.human_required,
            reasons=need.reason_codes, summary=need.why, due_by=need.due_by,
            actions=tuple(a.value for a in need.actions), evidence_ids=tuple(ids),
            counterparty=need.counterparty))
    load = f"brokerage_load:{state.load_id}"
    return LoadWorkRequest(route=route, source_id=load, as_of=state.as_of,
                           stage=state.stage.value, needs=tuple(options),
                           evidence=tuple(shown.values()), correlation_id=load)


@dataclass(frozen=True)
class WorkAdvice:
    """What shadow reasoning came to for one load. Advice: nothing reads it into canonical state."""

    route: Route
    status: str                                       # NOT_NEEDED | ADVISED | REUSED | FAILED
    picks: Mapping[str, str] = field(default_factory=dict)      # undecided need -> chosen action
    next_need_id: str | None = None
    groups: tuple[tuple[str, ...], ...] = ()
    explanation: str = ""
    refused: tuple[str, ...] = ()
    stated_posture: str | None = None                 # what the reply SAID; reported, never used
    posture: str | None = None                        # recomputed here from the surviving picks
    failure: str | None = None
    digest: str | None = None

    def as_document(self) -> dict[str, Any]:
        return {"model_needed": self.route.model_needed, "route_reason": self.route.reason,
                "status": self.status, "picks": dict(self.picks),
                "next_need_id": self.next_need_id, "groups": [list(g) for g in self.groups],
                "explanation": self.explanation, "refused": list(self.refused),
                "posture": self.posture, "stated_posture": self.stated_posture,
                "failure": self.failure}


def effective_posture(state: LoadWorkState, picks: Mapping[str, str]) -> str:
    """The posture once each undecided need takes its chosen action. A human's need decides it
    first and nothing a model returned can move it: the picks cannot name one."""
    if state.human_attention:
        return Posture.HUMAN_ATTENTION.value
    acting = False
    for need in state.needs:
        if need.handling is Handling.NEYMA_ACTION_CANDIDATE:
            acting = True
        elif need.handling is Handling.MODEL_REASONING:
            # Undecided and unadvised, the candidate still stands: nothing is assumed away.
            acting = acting or picks.get(need.need_id) != ShadowAction.WAIT.value
    if acting:
        return Posture.NEYMA_CAN_ACT.value
    return Posture.WAIT.value if state.needs else Posture.QUIET.value


def screen_advice(output: LoadWorkReasoning, state: LoadWorkState,
                  request: LoadWorkRequest) -> WorkAdvice:
    """The reply, minus everything it was not entitled to say. Each part stands or falls alone."""
    supplied = {n.need_id: n for n in state.needs if n.need_id in
                {option.need_id for option in request.needs}}
    offered = {option.need_id: set(option.actions) for option in request.needs}
    evidence = {option.need_id: set(option.evidence_ids) for option in request.needs}
    all_evidence = {item.evidence_id for item in request.evidence}
    refused: list[str] = []
    picks: dict[str, str] = {}

    for item in output.advice:
        need = supplied.get(item.need_id)
        if need is None:
            refused.append("need_id_not_supplied")
            continue
        if item.recommended_action not in offered[item.need_id]:
            # An action outside the closed vocabulary, or one this need does not offer — which is
            # how WAIT on a human's need arrives, and why it goes nowhere.
            refused.append("action_not_offered_for_need")
            continue
        unknown = [e for e in item.evidence_ids if e not in all_evidence]
        if unknown:
            refused.extend("evidence_id_not_supplied" for _ in unknown)
        if not [e for e in item.evidence_ids if e in evidence[item.need_id]]:
            refused.append("advice_cites_no_supplied_evidence_of_the_need")
            continue
        if need.handling is not Handling.MODEL_REASONING:
            # A need the record already settled is not re-decided by a model. Agreeing with it is
            # harmless and is simply not recorded as a pick.
            continue
        if item.need_id in picks and picks[item.need_id] != item.recommended_action:
            refused.append("contradictory_advice_for_one_need")
            del picks[item.need_id]
            continue
        picks[item.need_id] = item.recommended_action

    next_need_id = output.next_need_id
    if next_need_id is not None and next_need_id not in supplied:
        refused.append("next_need_id_not_supplied")
        next_need_id = None

    groups: list[tuple[str, ...]] = []
    for group in output.groups:
        members = tuple(dict.fromkeys(group.need_ids))
        needs = [supplied.get(m) for m in members]
        if any(n is None for n in needs):
            refused.append("group_names_a_need_not_supplied")
            continue
        usable = [n for n in needs if n is not None]
        if len(usable) < 2 or any(n.human_required for n in usable) \
                or len({n.counterparty for n in usable}) != 1 or usable[0].counterparty is None \
                or any(_acts(n, picks) is False for n in usable):
            refused.append("group_is_not_one_outreach")
            continue
        groups.append(members)

    posture = effective_posture(state, picks)
    stated = {"WAIT": Posture.WAIT.value, "ACT": Posture.NEYMA_CAN_ACT.value,
              "HUMAN": Posture.HUMAN_ATTENTION.value}[output.posture]
    if stated != posture:
        refused.append("stated_posture_disagrees_with_the_work")
    return WorkAdvice(
        route=request.route, status=ADVISED, picks=picks, next_need_id=next_need_id,
        groups=tuple(groups), explanation=output.explanation.strip()[:MAX_EXPLANATION],
        refused=tuple(refused), stated_posture=output.posture, posture=posture)


def _acts(need: OperationalNeed, picks: Mapping[str, str]) -> bool:
    """Whether a need is to be ACTED on now, given the picks."""
    if need.handling is Handling.NEYMA_ACTION_CANDIDATE:
        return True
    if need.handling is Handling.MODEL_REASONING:
        return picks.get(need.need_id) not in (None, ShadowAction.WAIT.value)
    return False


class LoadWorkReasoner:
    """Shadow reasoning over one brokerage's or many brokerages' loads. It holds no tenant: every
    request is built from ONE `LoadWorkState`, and the ids in it are that brokerage's own."""

    def __init__(self, gateway: InferenceGateway, ledger: InferenceLedger) -> None:
        self._gateway = gateway
        self.ledger = ledger
        self._answered: dict[tuple[str, str], WorkAdvice] = {}
        self.evaluations = 0
        self.outcomes: dict[str, int] = {}
        self.refused_parts = 0

    def _count(self, status: str) -> None:
        self.outcomes[status] = self.outcomes.get(status, 0) + 1

    def _avoided(self, state: LoadWorkState, reason: str, digest: str) -> None:
        self.ledger.record_routing(RoutingRecord(
            at=state.as_of, task=Task.REASON_LOAD_WORK.value, model_needed=False, reason=reason,
            subject_ref=f"brokerage_load:{state.load_id}",
            correlation_id=f"brokerage_load:{state.load_id}", content_digest=digest))

    def advise(self, state: LoadWorkState) -> WorkAdvice:
        """Route, and ask a model only if the record left act-or-wait open. Never raises on a model
        failure and never changes `state`."""
        self.evaluations += 1
        route = route_load_work(state)
        digest = question_digest(state)
        key = (state.tenant_id, state.load_id)
        if not route.model_needed:
            self._avoided(state, route.reason, digest)
            self._count(NOT_NEEDED)
            self._answered.pop(key, None)
            return WorkAdvice(route=route, status=NOT_NEEDED,
                              posture=state.posture.value, digest=digest)
        previous = self._answered.get(key)
        if previous is not None and previous.digest == digest and previous.status == ADVISED:
            self._avoided(state, "question_unchanged", digest)
            self._count(REUSED)
            return WorkAdvice(**{**previous.__dict__, "status": REUSED})
        request = build_request(state, route)
        result = self._gateway.reason_load_work(request)
        if not result.ok or result.output is None:
            self._count(FAILED)
            return WorkAdvice(route=route, status=FAILED,
                              posture=effective_posture(state, {}), digest=digest,
                              failure=f"{result.status.value}:{result.detail}")
        advice = screen_advice(result.output, state, request)
        advice = WorkAdvice(**{**advice.__dict__, "digest": digest})
        self.refused_parts += len(advice.refused)
        self._count(ADVISED)
        self._answered[key] = advice
        return advice

    def summary(self, *, loads: int) -> dict[str, Any]:
        """Counts and tokens. No content, and no money except an ESTIMATE of what the calls cost."""
        calls = self.ledger.model_calls(Task.REASON_LOAD_WORK)
        usage = Usage()
        for call in calls:
            usage = usage + Usage(call.input_tokens, call.cached_input_tokens, call.output_tokens,
                                  call.reasoning_tokens)
        reasons: dict[str, int] = {}
        for routing in self.ledger.routings:
            if routing.task == Task.REASON_LOAD_WORK.value:
                reasons[routing.reason] = reasons.get(routing.reason, 0) + 1
        avoided = sum(reasons.values())
        prices = load_price_table()
        model = getattr(self._gateway, "model", "")
        return {
            "reasoner_version": REASONER_VERSION,
            "evaluations_routed": self.evaluations,
            "model_reasoning_calls": len(calls),
            "model_calls_avoided": avoided,
            "avoided_by_reason": dict(sorted(reasons.items())),
            "outcomes": dict(sorted(self.outcomes.items())),
            "failed_calls": len([c for c in calls if c.outcome != "OK"]),
            "refused_parts": self.refused_parts,
            "input_tokens": usage.input_tokens, "cached_input_tokens": usage.cached_input_tokens,
            "output_tokens": usage.output_tokens, "reasoning_tokens": usage.reasoning_tokens,
            "latency_ms_total": sum(c.latency_ms for c in calls),
            "calls_per_load": round(len(calls) / loads, 3) if loads else None,
            "tokens_per_load": (round((usage.input_tokens + usage.output_tokens) / loads, 1)
                                if loads else None),
            "estimated_cost_usd": prices.estimate_usd(model, usage),
            "estimated_cost_usd_per_load": (
                round(cost / loads, 6) if loads and (cost := prices.estimate_usd(model, usage))
                is not None else None),
            "price_table": prices.version,
        }


__all__ = ["ADVISED", "FAILED", "LoadWorkReasoner", "NOT_NEEDED", "REASONER_VERSION", "REUSED",
           "WorkAdvice", "build_request", "effective_posture", "question_digest",
           "route_load_work", "screen_advice"]
