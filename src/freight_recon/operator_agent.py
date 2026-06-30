"""The embedded Operator Agent: the model-in-the-loop driver that operates a TMS on its own.

This is the agent that lives INSIDE Neyma's runtime and does what a human (or the dev driving in a
sidebar) would do — but autonomously: observe the current screen, reason about the single next move
toward a goal, do it, observe the result, repeat, until done or stuck. Its "brain" is a reasoning model
(Claude/GPT via API), injected as ``complete``. It is system-agnostic: nothing here is TMS-specific.

The money fence makes it safe to let it drive unattended:
- The agent decides NAVIGATION and which field to fill, but it NEVER chooses a monetary value. When it
  types into a money field, the runtime substitutes the human-APPROVED amount — the model's own number
  is discarded.
- A CONSEQUENTIAL action (the committing submit) requires the gate/approval before it executes; without
  it, the agent escalates rather than commit.
- Bounded steps; ESCALATE and exhaustion both fail closed.

The loop is pure and injectable (``Actuator`` for the browser, ``complete`` for the model), so it is
unit-tested with fakes; the real Actuator drives Chrome over CDP (with real keyboard/mouse input).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Protocol

from freight_recon.screen_discovery import _parse_llm_json

Completer = Callable[[str], str]


class LiveActionKind(str, Enum):
    NAVIGATE = "NAVIGATE"
    CLICK = "CLICK"
    TYPE = "TYPE"
    SELECT = "SELECT"
    READ = "READ"            # read a value back (for the agent's own verification)
    DONE = "DONE"            # goal achieved
    ESCALATE = "ESCALATE"    # stuck/unsafe -> hand to the human


@dataclass
class LiveAction:
    kind: LiveActionKind
    target: str = ""         # url / element label / selector / option text
    value: str = ""          # text to type / option to choose
    why: str = ""


@dataclass
class AgentResult:
    goal: str
    status: str              # DONE | ESCALATED | FAILED
    steps: list[dict]
    note: str


class Actuator(Protocol):
    """The browser the agent drives. The real impl is CDP (with real input); tests pass a fake."""
    def observe(self) -> dict: ...                       # {url, interactive:[...], errors:[...], headings:[...]}
    def navigate(self, url: str) -> bool: ...
    def click(self, target: str) -> bool: ...
    def type(self, target: str, value: str) -> bool: ...
    def select(self, target: str, option: str) -> bool: ...
    def read(self, target: str) -> str: ...


@dataclass
class MoneyFence:
    """Keeps the model away from money. ``is_money_field`` flags fields whose value must be the approved
    amount; ``is_consequential`` flags the committing action that needs approval."""
    is_money_field: Callable[[LiveAction], bool] = lambda a: bool(
        a.kind == LiveActionKind.TYPE and any(k in (a.target or "").lower() for k in ("amount", "price", "total", "charge"))
    )
    is_consequential: Callable[[LiveAction], bool] = lambda a: bool(
        a.kind == LiveActionKind.CLICK and any(k in (a.target or "").lower() for k in ("save", "submit", "create", "raise", "confirm", "pay"))
    )


class OperatorAgent:
    def __init__(
        self,
        *,
        actuator: Actuator,
        complete: Completer,
        approved_amount: str | None = None,
        approve: Callable[[LiveAction], bool] | None = None,
        money_fence: MoneyFence | None = None,
        max_steps: int = 20,
    ) -> None:
        self.actuator = actuator
        self.complete = complete
        self.approved_amount = approved_amount
        self.approve = approve
        self.fence = money_fence or MoneyFence()
        self.max_steps = max_steps

    def run(self, goal: str) -> AgentResult:
        history: list[dict] = []
        for _ in range(self.max_steps):
            observation = self.actuator.observe()
            action = self._decide(goal, observation, history)

            if action.kind == LiveActionKind.DONE:
                return AgentResult(goal, "DONE", history, action.why or "goal achieved")
            if action.kind == LiveActionKind.ESCALATE:
                return AgentResult(goal, "ESCALATED", history, action.target or action.why or "agent escalated")

            # MONEY FENCE: the model never supplies a monetary value — the approved amount is substituted.
            if self.fence.is_money_field(action):
                if not self.approved_amount:
                    return AgentResult(goal, "ESCALATED", history, "money field but no approved amount bound")
                action = LiveAction(action.kind, action.target, self.approved_amount, action.why + " [amount from approval]")

            # CONSEQUENTIAL GATE: the committing action needs human approval before it runs.
            if self.fence.is_consequential(action):
                if self.approve is None or not self.approve(action):
                    return AgentResult(goal, "ESCALATED", history, f"consequential action needs approval: {action.target}")

            ok = self._execute(action)
            history.append({"action": action.kind.value, "target": action.target,
                            "value": action.value, "why": action.why, "ok": ok})
            if not ok:
                # let the model see the failure and adapt on the next loop (self-heal); don't hard-stop
                history[-1]["note"] = "action failed; agent may adapt"

        return AgentResult(goal, "FAILED", history, f"did not finish within {self.max_steps} steps")

    def _decide(self, goal: str, observation: dict, history: list[dict]) -> LiveAction:
        parsed = _parse_llm_json(self.complete(_decide_prompt(goal, observation, history)))
        raw = parsed.get("action") if isinstance(parsed, dict) else None
        if raw not in LiveActionKind._value2member_map_:
            return LiveAction(LiveActionKind.ESCALATE, why=f"model returned unknown action {raw!r}")
        return LiveAction(
            kind=LiveActionKind(raw),
            target=str(parsed.get("target", "")),
            value=str(parsed.get("value", "")),
            why=str(parsed.get("why", "")),
        )

    def _execute(self, action: LiveAction) -> bool:
        if action.kind == LiveActionKind.NAVIGATE:
            return bool(self.actuator.navigate(action.target))
        if action.kind == LiveActionKind.CLICK:
            return bool(self.actuator.click(action.target))
        if action.kind == LiveActionKind.TYPE:
            return bool(self.actuator.type(action.target, action.value))
        if action.kind == LiveActionKind.SELECT:
            return bool(self.actuator.select(action.target, action.value))
        if action.kind == LiveActionKind.READ:
            self.actuator.read(action.target)
            return True
        return False


def _decide_prompt(goal: str, observation: dict, history: list[dict]) -> str:
    return (
        "You are an autonomous back-office agent operating an unfamiliar freight TMS in a browser, one "
        "step at a time, to accomplish a goal. Decide the SINGLE next action from the current screen.\n\n"
        f"GOAL: {goal}\n\n"
        f"CURRENT SCREEN (observation):\n{json.dumps(observation, indent=1)[:3500]}\n\n"
        f"RECENT ACTIONS:\n{json.dumps(history[-6:], indent=1)[:1500]}\n\n"
        "Allowed actions (use exactly these): NAVIGATE(target=url), CLICK(target=button/link text or "
        "selector), TYPE(target=field, value=text), SELECT(target=field, value=option), READ(target=field), "
        "DONE(why=...), ESCALATE(target=reason). Rules: take the minimal next step; if you are blocked or "
        "unsure, ESCALATE rather than guess. NEVER decide a monetary amount — for money fields the system "
        "supplies the approved value, so just TYPE into the amount field and the value will be substituted.\n\n"
        'Respond with ONLY JSON: {"action": "...", "target": "...", "value": "...", "why": "..."}'
    )
