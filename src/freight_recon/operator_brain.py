"""The Operator Brain: a goal-directed orchestrator that understands a system and plans the path.

This is the headline System-Operator architecture (see docs/CODEX_HANDOFF.md). Instead of a rigid
"fill one discovered form" pipeline, the Brain reasons about an unfamiliar system the way a sharp
back-office hire would — "to invoice here I must first open an order, add line-items, then raise the
invoice" — and produces an ordered multi-step plan over the existing deterministic tools.

The same safety split as the rest of Neyma:
- **observe** (here) is deterministic — read the nav + current screen, no LLM.
- **plan** is the one LLM step (injectable `Completer`) — the genuinely human reasoning.
- **act / verify** are deterministic tools, and **consequential steps (writes/money) NEVER execute on
  the Brain's say-so** — they route through the gated path + human approval. "Brain proposes, gates
  dispose." This module marks which steps are consequential so the executor (next brick) can enforce it.

This first brick is the planning core: `observe()` + `plan_flow()` + the typed plan. Wiring steps to
the CDP/discovery/ledger tools and the crystallize→replay of a learned flow-recipe is the next brick.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Protocol

from freight_recon.screen_discovery import _parse_llm_json  # hardened JSON extraction (reused)


class BrowserSession(Protocol):
    def navigate(self, url: str) -> None: ...
    def evaluate(self, expression: str): ...


# prompt -> completion text; injectable so planning is unit-testable with a scripted fake.
Completer = Callable[[str], str]


class StepAction(str, Enum):
    NAVIGATE = "NAVIGATE"                # go to a URL / menu screen
    DISCOVER_FORM = "DISCOVER_FORM"      # author a field map for the screen (screen_discovery)
    RESOLVE_CUSTOMER = "RESOLVE_CUSTOMER"  # entity resolution (find/create the bill-to)
    FILL_AND_SUBMIT = "FILL_AND_SUBMIT"  # CONSEQUENTIAL write — must pass the Safety Spine + approval
    READBACK_VERIFY = "READBACK_VERIFY"  # deterministic verify of the system of record
    ESCALATE = "ESCALATE"                # blocked/uncertain -> ask the human in Slack


# Steps that change state / money. These never run on the Brain's say-so; the executor must route
# them through enter_approved_payable (approved-amount binding, deterministic readback, fail-closed)
# and human approval. Keeping this set explicit is the load-bearing safety contract of the Brain.
CONSEQUENTIAL_ACTIONS = frozenset({StepAction.FILL_AND_SUBMIT})


@dataclass
class FlowStep:
    action: StepAction
    target: str = ""           # url / customer name / form url, depending on action
    why: str = ""              # the Brain's rationale (for audit + human review)
    params: dict = field(default_factory=dict)

    def is_consequential(self) -> bool:
        return self.action in CONSEQUENTIAL_ACTIONS


@dataclass
class FlowPlan:
    goal: str
    steps: list[FlowStep]
    notes: list[str] = field(default_factory=list)

    def consequential_steps(self) -> list[FlowStep]:
        return [s for s in self.steps if s.is_consequential()]

    def is_actionable(self) -> bool:
        # A plan that neither writes nor explicitly escalates isn't a plan to accomplish a goal.
        return any(s.action in (StepAction.FILL_AND_SUBMIT, StepAction.ESCALATE) for s in self.steps)


@dataclass
class Observation:
    url: str
    nav: list[dict]            # [{"text":..., "href":...}]
    headings: list[str]
    has_form: bool

    def to_prompt_json(self) -> str:
        import json

        return json.dumps(
            {
                "current_url": self.url,
                "headings": self.headings[:10],
                "has_form_on_screen": self.has_form,
                "navigation": [n for n in self.nav if n.get("href")][:40],
            },
            indent=2,
        )


def observe(session: BrowserSession, url: str | None = None) -> Observation:
    """Deterministically read the system's current state: nav menu, headings, whether a form is here."""
    if url:
        session.navigate(url)
    data = session.evaluate(_OBSERVE_JS) or {}
    return Observation(
        url=data.get("url", url or ""),
        nav=data.get("nav", []),
        headings=data.get("headings", []),
        has_form=bool(data.get("has_form")),
    )


def plan_flow(goal: str, observation: Observation, *, complete: Completer) -> FlowPlan:
    """Ask the Brain to reason an ordered, multi-step plan to reach ``goal`` from what it can see.

    The plan uses only the fixed StepAction vocabulary so a deterministic executor can run it and so
    consequential (write) steps are explicit and gateable.
    """
    parsed = _parse_llm_json(complete(_plan_prompt(goal, observation)))
    steps: list[FlowStep] = []
    for raw in parsed.get("steps", []) if isinstance(parsed, dict) else []:
        action = raw.get("action") if isinstance(raw, dict) else None
        if action not in StepAction._value2member_map_:
            continue  # ignore actions outside the known vocabulary (the executor only trusts these)
        steps.append(
            FlowStep(
                action=StepAction(action),
                target=str(raw.get("target", "")),
                why=str(raw.get("why", "")),
                params=raw.get("params", {}) if isinstance(raw.get("params"), dict) else {},
            )
        )
    notes = parsed.get("notes", []) if isinstance(parsed, dict) and isinstance(parsed.get("notes"), list) else []
    return FlowPlan(goal=goal, steps=steps, notes=notes)


def _plan_prompt(goal: str, observation: Observation) -> str:
    return (
        "You are an operations agent learning to use an unfamiliar freight TMS, like a new back-office "
        "hire. Your GOAL:\n"
        f"  {goal}\n\n"
        "Here is what you can currently see (navigation menu + current screen):\n"
        f"{observation.to_prompt_json()}\n\n"
        "Produce an ORDERED, minimal plan to reach the goal, reasoning about this system's model (e.g. "
        "many TMSs require creating an order before an invoice can be raised). Use ONLY these step "
        "actions:\n"
        "  NAVIGATE (target=url) — go to a screen\n"
        "  DISCOVER_FORM (target=url) — map a form's fields before filling it\n"
        "  RESOLVE_CUSTOMER (target=customer name) — find or create the bill-to\n"
        "  FILL_AND_SUBMIT (target=form url) — submit the financial record (this is gated + needs human approval)\n"
        "  READBACK_VERIFY — confirm the record landed by reading the system of record\n"
        "  ESCALATE (target=reason) — if the goal cannot be reached, ask the human instead of guessing\n\n"
        'Respond with ONLY JSON: {"steps": [{"action": "...", "target": "...", "why": "..."}], "notes": ["..."]}. '
        "Never invent an amount; amounts come from the approved record, not from you."
    )


@dataclass
class StepResult:
    step: "FlowStep"
    ok: bool
    detail: str = ""


@dataclass
class FlowResult:
    goal: str
    step_results: list[StepResult]
    completed: bool
    escalated: bool
    note: str
    replans: int = 0

    def trace(self) -> list[str]:
        return [f"{r.step.action.value}{'' if r.ok else ' FAILED'}: {r.detail}".strip() for r in self.step_results]


# A handler runs ONE step against the real tools, reading/writing the shared `context` dict (so e.g.
# DISCOVER_FORM stores the field map that FILL_AND_SUBMIT later uses). Signature: (step, context)->StepResult.
StepHandler = Callable[["FlowStep", dict], StepResult]


class FlowExecutor:
    """Drive a Brain plan step-by-step through injected tool handlers — brain proposes, gates dispose.

    The executor itself performs NO writes: it only dispatches each step to its handler. The handler for
    a CONSEQUENTIAL action (FILL_AND_SUBMIT) MUST be wired to the gated path (enter_approved_payable +
    human approval); if a plan contains a consequential step with no handler, the executor halts fail-
    closed rather than proceed. ESCALATE halts and surfaces to the human. On a step failure it re-plans
    (bounded) if a re-planner was provided, else halts — the observe→act→re-plan loop.
    """

    def __init__(
        self,
        *,
        handlers: dict["StepAction", StepHandler],
        observe_fn: Callable[[], "Observation"] | None = None,
        replan_fn: Callable[[str, "Observation | None", str], "FlowPlan"] | None = None,
        max_replans: int = 1,
    ) -> None:
        self.handlers = handlers
        self.observe_fn = observe_fn
        self.replan_fn = replan_fn
        self.max_replans = max_replans

    def run(self, plan: "FlowPlan", context: dict | None = None) -> FlowResult:
        context = context if context is not None else {}
        results: list[StepResult] = []
        steps = list(plan.steps)
        replans = 0
        i = 0
        while i < len(steps):
            step = steps[i]
            handler = self.handlers.get(step.action)
            if handler is None:
                # Fail-closed: a consequential step with no wired (gated) handler must never be skipped
                # or improvised. Halt.
                results.append(StepResult(step, ok=False, detail=f"no handler wired for {step.action.value}"))
                return FlowResult(plan.goal, results, completed=False, escalated=False,
                                  note=f"halted: no handler for {step.action.value}", replans=replans)

            if step.action == StepAction.ESCALATE:
                results.append(StepResult(step, ok=True, detail=step.target or "escalated to human"))
                return FlowResult(plan.goal, results, completed=False, escalated=True,
                                  note=step.target or "escalated to human", replans=replans)

            result = handler(step, context)
            results.append(result)
            if not result.ok:
                if self.replan_fn is not None and replans < self.max_replans:
                    replans += 1
                    observation = self.observe_fn() if self.observe_fn else None
                    steps = list(self.replan_fn(plan.goal, observation, result.detail).steps)
                    i = 0
                    continue
                return FlowResult(plan.goal, results, completed=False, escalated=False,
                                  note=f"halted at {step.action.value}: {result.detail}", replans=replans)
            i += 1

        return FlowResult(plan.goal, results, completed=True, escalated=False,
                          note="flow complete", replans=replans)


_OBSERVE_JS = r"""
(function(){
  var nav=[...document.querySelectorAll('nav a[href], .sidebar a[href], aside a[href], .menu a[href], .nav a[href], a[href]')]
    .map(function(a){return {text:(a.innerText||'').trim().slice(0,40), href:a.getAttribute('href')||''};})
    .filter(function(n){return n.text && n.href && n.href!=='#' && n.href.indexOf('javascript:')!==0;})
    .slice(0,60);
  // de-dupe by href
  var seen={}, uniq=[];
  for(var i=0;i<nav.length;i++){ if(!seen[nav[i].href]){seen[nav[i].href]=1; uniq.push(nav[i]);} }
  return {
    url: location.href,
    nav: uniq.slice(0,40),
    headings: [...document.querySelectorAll('h1,h2,h3')].map(function(e){return e.innerText.trim();}).filter(Boolean).slice(0,10),
    has_form: !!document.querySelector('form input, form select, form textarea')
  };
})()
"""
