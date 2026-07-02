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
from decimal import Decimal, InvalidOperation
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
    """Keeps the model away from money.

    Numeric TYPE values are treated as money-risky by value inspection. They may only be written into a
    designated money field, where the runtime substitutes the approved amount; otherwise the agent
    escalates instead of typing a model-chosen number into an unknown field.
    """
    is_money_field: Callable[[LiveAction], bool] = lambda a: bool(
        a.kind == LiveActionKind.TYPE
        and any(
            k in (a.target or "").lower()
            for k in (
                "amount",
                "price",
                "total",
                "charge",
                "rate",
                "line haul",
                "linehaul",
                "freight",
                "settlement",
                "balance due",
                "cost",
                "pay",
                "value",
                "accessorial",
            )
        )
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
        stuck_after: int = 3,
        prepare_only: bool = False,
        memory=None,
        tenant: str = "default",
        task: str = "",
    ) -> None:
        self.actuator = actuator
        self.complete = complete
        self.approved_amount = approved_amount
        self.approve = approve
        self.fence = money_fence or MoneyFence()
        self.max_steps = max_steps
        self.stuck_after = stuck_after  # escalate after this many identical actions in a row
        # prepare_only: drive + fill everything but STOP before the committing action, so a human does
        # the final Save. This is the safe default for a supervised lane (full-auto is the graduation).
        self.prepare_only = prepare_only
        # Memory makes the agent improve with repetition: recall learned facts about this system, and
        # crystallize what worked (per tenant). Optional — without it the agent just reasons fresh.
        self.memory = memory
        self.tenant = tenant
        self.task = task

    def run(self, goal: str) -> AgentResult:
        history: list[dict] = []
        repeats = 0
        last_sig: tuple | None = None
        domain = "unknown"
        self._committed = False           # has a consequential action succeeded this run?
        self._commit_approved: bool | None = None  # cached approval so a failed commit click can retry
        # Business knowledge about whoever/whatever this goal is about (recalled up front, from the goal).
        business = self.memory.recall_business(tenant=self.tenant, text=goal) if self.memory is not None else []
        procedures = self.memory.recall_procedures(tenant=self.tenant, text=goal) if self.memory is not None else []
        learned: list[str] = list(business)
        for _ in range(self.max_steps):
            observation = self.actuator.observe()
            # First real screen: recall what we've learned about THIS system, so the agent reasons with
            # memory instead of from scratch (what makes it faster the tenth time than the first).
            if self.memory is not None and domain == "unknown":
                from freight_recon.agent_memory import domain_of

                domain = domain_of(observation.get("url"))
                if domain != "unknown":
                    learned = self.memory.recall_facts(tenant=self.tenant, domain=domain) + business
            # If the agent has been repeating itself, warn it to change tack before it decides again.
            nudge = None
            if repeats >= 1:
                nudge = (f"You have already taken this exact action {repeats + 1} time(s) with no progress. "
                         "Do NOT repeat it. Choose a DIFFERENT action — e.g. NAVIGATE directly to a URL from "
                         "the page's navigation — or ESCALATE if you are stuck.")
            action = self._decide(goal, observation, history, nudge=nudge, learned=learned, procedures=procedures)

            # No-progress guard: identical action repeated too many times -> stop, don't grind/loop.
            sig = (action.kind, action.target)
            repeats = repeats + 1 if sig == last_sig else 0
            last_sig = sig
            if repeats >= self.stuck_after and action.kind not in (LiveActionKind.DONE, LiveActionKind.ESCALATE):
                return AgentResult(goal, "ESCALATED", history,
                                   f"stuck: repeated {action.kind.value} {action.target!r} with no progress")

            if action.kind == LiveActionKind.DONE:
                self._crystallize(history, domain)  # learn from what just worked
                return AgentResult(goal, "DONE", history, action.why or "goal achieved")
            if action.kind == LiveActionKind.ESCALATE:
                return AgentResult(goal, "ESCALATED", history, action.target or action.why or "agent escalated")

            # MONEY FENCE: the model never supplies a monetary value. Any numeric TYPE is money-risky:
            # allowed money fields receive the approved amount; unexpected numeric writes escalate.
            if _looks_numeric(action.value):
                if not self.fence.is_money_field(action):
                    return AgentResult(
                        goal,
                        "ESCALATED",
                        history,
                        f"unexpected numeric write to non-money field: {action.target}",
                    )
                if not self.approved_amount:
                    return AgentResult(goal, "ESCALATED", history, "money field but no approved amount bound")
                action = LiveAction(action.kind, action.target, self.approved_amount, action.why + " [amount from approval]")

            # CONSEQUENTIAL GATE: the committing action.
            if self.fence.is_consequential(action):
                # PREPARE MODE: everything is filled and staged — stop here and let the human commit.
                if self.prepare_only:
                    return AgentResult(goal, "PREPARED", history,
                                       f"Everything is filled and staged; I stopped before the final "
                                       f"step ({action.target}) so you can commit it. Reply 'submit' to "
                                       "commit, or do the final action in the browser.")
                # Already committed once this run -> never repeat a consequential action (double-pay guard).
                if self._committed:
                    return AgentResult(goal, "DONE", history, "already committed; refusing to repeat the commit")
                # Ask for approval ONCE and cache it — a FAILED commit click must not burn the approval,
                # so retries of the same commit are allowed until one actually succeeds.
                if self._commit_approved is None:
                    self._commit_approved = bool(self.approve is not None and self.approve(action))
                if not self._commit_approved:
                    return AgentResult(goal, "ESCALATED", history, f"consequential action needs approval: {action.target}")

            ok, observed = self._execute(action)
            if ok and self.fence.is_consequential(action):
                self._committed = True  # a consequential action succeeded — commit is done
            entry = {"action": action.kind.value, "target": action.target,
                     "value": action.value, "why": action.why, "ok": ok}
            if observed is not None:
                # Feed the result back so the model can actually USE what it read (it was blind to this).
                entry["observed"] = str(observed)[:300]
            if not ok:
                entry["note"] = "action failed; agent may adapt"
            history.append(entry)

        return AgentResult(goal, "FAILED", history, f"did not finish within {self.max_steps} steps")

    def _crystallize(self, history: list[dict], domain: str) -> None:
        """Learn from a run that just worked: save the path as a recipe + a recallable fact. Never lets
        a memory hiccup break a successful run."""
        if self.memory is None:
            return
        try:
            from freight_recon.agent_memory import fact_from_successful_run

            self.memory.save_recipe(history, tenant=self.tenant, task=self.task or "task")
            fact = fact_from_successful_run(history, task=self.task or "the task", domain=domain)
            if fact:
                self.memory.learn_fact(fact, tenant=self.tenant, domain=domain)
        except Exception:  # noqa: BLE001 - memory is best-effort; a success must still be a success
            pass

    def _decide(self, goal: str, observation: dict, history: list[dict], nudge: str | None = None,
                learned: list[str] | None = None, procedures: list[str] | None = None) -> LiveAction:
        parsed = _parse_llm_json(
            self.complete(_decide_prompt(goal, observation, history, nudge, learned, procedures)))
        raw = parsed.get("action") if isinstance(parsed, dict) else None
        if raw not in LiveActionKind._value2member_map_:
            return LiveAction(LiveActionKind.ESCALATE, why=f"model returned unknown action {raw!r}")
        return LiveAction(
            kind=LiveActionKind(raw),
            target=str(parsed.get("target", "")),
            value=str(parsed.get("value", "")),
            why=str(parsed.get("why", "")),
        )

    def _execute(self, action: LiveAction) -> tuple[bool, str | None]:
        """Run an action. Returns (ok, observed) — observed is the read-back text for READ, else None."""
        if action.kind == LiveActionKind.NAVIGATE:
            return bool(self.actuator.navigate(action.target)), None
        if action.kind == LiveActionKind.CLICK:
            return bool(self.actuator.click(action.target)), None
        if action.kind == LiveActionKind.TYPE:
            return bool(self.actuator.type(action.target, action.value)), None
        if action.kind == LiveActionKind.SELECT:
            return bool(self.actuator.select(action.target, action.value)), None
        if action.kind == LiveActionKind.READ:
            value = self.actuator.read(action.target)
            return True, (value or "")
        return False, None


def _looks_numeric(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    raw = raw.replace("$", "").replace(",", "")
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    try:
        Decimal(raw)
        return True
    except InvalidOperation:
        return False


def _decide_prompt(goal: str, observation: dict, history: list[dict], nudge: str | None = None,
                   learned: list[str] | None = None, procedures: list[str] | None = None) -> str:
    warn = f"\n!!! {nudge}\n" if nudge else ""
    # Recalled memory: what we've learned about THIS system before, so the agent reasons like an
    # experienced hire instead of a first-day one.
    memory = ""
    if learned:
        memory = ("\nWHAT YOU'VE LEARNED ABOUT THIS SYSTEM (from past runs — use it to move faster; "
                  "still verify against the current screen):\n- " + "\n- ".join(learned[:12]) + "\n")
    # Company SOPs from onboarding — how THIS company does things. Follow them, but they NEVER override
    # the money fence / gates (an SOP can't authorize an unapproved amount or a duplicate).
    sop = ""
    if procedures:
        sop = ("\nCOMPANY PROCEDURES (this company's way — follow these; they never override the money "
               "fence or the safety gates):\n- " + "\n- ".join(procedures[:10]) + "\n")
    return (
        "You are an autonomous back-office agent operating an unfamiliar freight TMS in a browser, one "
        "step at a time, to accomplish a goal. Decide the SINGLE next action from the current screen.\n"
        + warn + memory + sop + "\n"
        f"GOAL: {goal}\n\n"
        f"CURRENT SCREEN (observation):\n{json.dumps(observation, indent=1)[:3500]}\n\n"
        f"RECENT ACTIONS:\n{json.dumps(history[-6:], indent=1)[:1500]}\n\n"
        "Allowed actions (use exactly these): NAVIGATE(target=url), CLICK(target=button/link text or "
        "selector), TYPE(target=field, value=text), SELECT(target=field, value=option), READ(target=field), "
        "DONE(why=...), ESCALATE(target=reason). Rules: take the minimal next step; if you are blocked or "
        "unsure, ESCALATE rather than guess. NEVER decide a monetary amount — for money fields the system "
        "supplies the approved value, so just TYPE into the amount field and the value will be substituted. "
        "To open a specific record (order, load, invoice), CLICK it by its visible reference text in the "
        "list/table — do NOT NAVIGATE to a guessed record URL like /orders/1002; you don't know the internal "
        "id and it will 404. If an action fails twice, switch approach (a nav link, or CLICK the row by its "
        "reference text) rather than repeating it. "
        "If you search for the record and it is NOT in this system (the search returns no matching results), "
        "ESCALATE with target 'record not found: <reference>' — do NOT keep hunting, invent a record, or act "
        "on a different one; a missing record is the human's decision (create it, correct the reference, or "
        "skip), never yours.\n"
        "HOW FREIGHT TMSs ARE USUALLY SHAPED (navigation, not a rule to force) — raising an invoice or "
        "recording a payable is almost always an ACTION ON a specific delivered load/order, not a standalone "
        "top-level form. So first OPEN the relevant load/order (find it in the loads/orders list and CLICK it "
        "by its reference), THEN use that record's billing action — often under a 'Billing', 'Invoice', "
        "'Invoicing', 'Accounting', 'Settlement', or 'Actions' menu on the record. Look for a standalone "
        "'new invoice' form only if the opened record has no such action. If the current screen already shows "
        "the billing form, just fill it — don't navigate away.\n"
        "EDGE CASES — when anything is unclear, ESCALATE with a specific reason; never guess on money:\n"
        "- ALREADY EXISTS: if a matching invoice/payable for this reference already exists, ESCALATE "
        "'already exists: <reference>' — NEVER create a duplicate (that double-pays/double-bills).\n"
        "- AMBIGUOUS: if multiple records match the reference, ESCALATE 'ambiguous: <reference>' and let "
        "the human pick — do not choose one.\n"
        "- BLOCKED / NO PERMISSION: if the screen says you lack permission or the action is disabled, "
        "ESCALATE 'blocked: <what>'.\n"
        "- REJECTED: if the system rejects the form with a validation error you can't fix from the visible "
        "message in one try, ESCALATE 'rejected: <error>' rather than retrying blindly.\n"
        "DO NOT HALLUCINATE — this is a money system:\n"
        "- Decide ONLY from what is actually on the CURRENT SCREEN above. Never describe a record, number, "
        "button, or confirmation you have not actually seen in the observation.\n"
        "- Only report DONE AFTER you have READ the saved record back and seen it exists with the correct "
        "details. If you cannot confirm it saved, ESCALATE — never claim a success you have not verified.\n"
        "- If you are unsure whether something worked, READ to check or ESCALATE; do not assume.\n\n"
        'Respond with ONLY JSON: {"action": "...", "target": "...", "value": "...", "why": "..."}'
    )
