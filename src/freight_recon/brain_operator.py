"""The Brain Operator: one front door for all work — owner requests AND inbound events.

This is the unifying layer the rest of the system plugs into. Any trigger — an authenticated owner
command in Slack, an inbound email/document, or a system event — funnels through ONE brain that decides
what it is and what to do with it, then produces a Decision: answer it, propose a gated action, escalate,
or ignore. Capabilities (create invoice, dispute, request backup, pay, query…) are pluggable; the
invoicing flow was just the first.

The two structural safety boundaries hold here at the front door:
- **Injection boundary.** Only an authenticated OWNER_COMMAND can be obeyed as an instruction. Inbound
  docs/events are UNTRUSTED: they are *classified as data* and can only ever yield a PROPOSE (human
  approval required) — content that arrives in an email can never self-authorize an action.
- **Brain proposes, gates dispose.** A read-only query is answered immediately; anything consequential
  becomes a PROPOSE flagged requires_approval and runs through the money gates on approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from freight_recon.operator_brain import FlowPlan, StepAction
from freight_recon.slack_delegate import CommandIntent, CommandKind, authorize_command


class TriggerSource(str, Enum):
    OWNER_COMMAND = "OWNER_COMMAND"   # authenticated Slack message from the owner/controller (trusted)
    INBOUND_DOC = "INBOUND_DOC"       # an email/document arrived (UNTRUSTED — data, never a command)
    EVENT = "EVENT"                   # a system event (timer, health, status change)


@dataclass
class Trigger:
    source: TriggerSource
    text: str = ""
    actor: str | None = None
    channel: str | None = None
    payload: dict = field(default_factory=dict)


class DecisionKind(str, Enum):
    ANSWER = "ANSWER"        # immediate (read-only) reply
    PROPOSE = "PROPOSE"      # a planned action awaiting human approval (gated)
    ESCALATE = "ESCALATE"    # can't be done safely — hand to the human
    IGNORE = "IGNORE"        # not actionable / not authorized


@dataclass
class Decision:
    kind: DecisionKind
    text: str
    requires_approval: bool = False
    plan: FlowPlan | None = None
    capability: str | None = None


class BrainOperator:
    """One dispatcher for every trigger. Reuses the delegate's authz/interpret for commands and an
    injected classifier for inbound docs; turns actionable work into a gated proposal via an injected
    planner (``plan_capability(summary) -> (FlowPlan, text)``)."""

    def __init__(
        self,
        *,
        allowed_users=None,
        allowed_channel: str | None = None,
        interpret: Callable[[str], CommandIntent],
        classify: Callable[[Trigger], dict],
        plan_capability: Callable[[str], tuple[FlowPlan, str]],
        on_query: Callable[[CommandIntent], str],
        on_control: Callable[[CommandIntent], str],
    ) -> None:
        self.allowed_users = allowed_users
        self.allowed_channel = allowed_channel
        self.interpret = interpret
        self.classify = classify
        self.plan_capability = plan_capability
        self.on_query = on_query
        self.on_control = on_control

    def dispatch(self, trigger: Trigger) -> Decision:
        if trigger.source == TriggerSource.OWNER_COMMAND:
            return self._dispatch_owner_command(trigger)
        # INBOUND_DOC / EVENT are untrusted: classify as data; never obey their content as a command.
        return self._dispatch_inbound(trigger)

    def _dispatch_owner_command(self, trigger: Trigger) -> Decision:
        ok, reason = authorize_command(
            trigger.actor, trigger.channel, allowed_users=self.allowed_users, allowed_channel=self.allowed_channel
        )
        if not ok:
            return Decision(DecisionKind.IGNORE, f"Not authorized: {reason}.")
        intent = self.interpret(trigger.text)
        if intent.kind == CommandKind.QUERY:
            return Decision(DecisionKind.ANSWER, self.on_query(intent))
        if intent.kind == CommandKind.CONTROL:
            return Decision(DecisionKind.ANSWER, self.on_control(intent))
        if intent.kind == CommandKind.OPERATE:
            return self._propose(intent.summary)
        return Decision(
            DecisionKind.IGNORE,
            "I didn't understand that — ask a question (e.g. \"what's outstanding?\") or an action "
            "(e.g. \"invoice today's delivered loads\").",
        )

    def _dispatch_inbound(self, trigger: Trigger) -> Decision:
        result = self.classify(trigger) or {}
        if not result.get("actionable"):
            return Decision(DecisionKind.IGNORE, str(result.get("reason", "nothing actionable")))
        # Inbound work ALWAYS becomes a proposal needing approval — it can never auto-execute.
        decision = self._propose(str(result.get("summary", "")))
        decision.capability = result.get("capability")
        return decision

    def _propose(self, summary: str) -> Decision:
        plan, text = self.plan_capability(summary)
        if plan is not None and plan.consequential_steps():
            return Decision(DecisionKind.PROPOSE, text, requires_approval=True, plan=plan, capability=summary)
        if plan is not None and any(s.action == StepAction.ESCALATE for s in plan.steps):
            return Decision(DecisionKind.ESCALATE, text, plan=plan, capability=summary)
        # A non-consequential, non-escalating plan still surfaces for confirmation, but binds no money.
        return Decision(DecisionKind.PROPOSE, text, requires_approval=False, plan=plan, capability=summary)
