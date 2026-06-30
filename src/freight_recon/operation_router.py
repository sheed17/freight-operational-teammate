"""The request->agent->result bridge: a request becomes a BOUNDED goal the embedded agent drives.

This is "Version B" of the delegate loop. The owner makes a request; Neyma recognizes it as one of a
small set of KNOWN workflow lanes (raise an invoice, record a carrier payable, ...) and hands the
agent a *bounded* goal scoped to that lane. The agent (``OperatorAgent``) then drives the live TMS
toward the goal — money-fenced and approval-gated — and the result is rendered back as a receipt the
owner reads in Slack ("Done — invoice #4912, $2,850, verified" / "Stuck on the customer field").

Why a lane registry instead of "do whatever the request says":
- An open-ended "free goal" agent is the demo version; in money ops it eventually does something
  confident and wrong. The lane registry is the boundary that makes autonomous operation safe: a
  request that matches no known lane is REFUSED, not improvised.
- The lane decides the goal; the human-approved amount (never the model) supplies money; the agent's
  own consequential gate still fires on the committing action. Three independent guards, all reused.

Pure and injectable: ``build_agent`` constructs the (real or fake) ``OperatorAgent``, so the routing +
boundedness + receipt logic is unit-tested without a browser or a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from freight_recon.operator_agent import AgentResult, OperatorAgent
from freight_recon.slack_delegate import CommandIntent

GoalBuilder = Callable[[CommandIntent], str]


@dataclass
class OperationLane:
    """A known, safe-to-run workflow the agent is allowed to drive.

    ``matches`` decides if this lane handles an intent (keyword/param based for now). ``build_goal``
    renders the BOUNDED goal handed to the agent. ``requires_amount`` marks a money lane: it must have a
    human-approved amount bound before it may run, or the router refuses at the front door.
    """

    name: str
    keywords: tuple[str, ...]
    build_goal: GoalBuilder
    requires_amount: bool = True

    def matches(self, intent: CommandIntent) -> bool:
        hint = (intent.summary or "") + " " + " ".join(str(v) for v in (intent.params or {}).values())
        hint = hint.lower()
        if str((intent.params or {}).get("lane", "")).lower() == self.name:
            return True
        return any(k in hint for k in self.keywords)


@dataclass
class OperationResult:
    """The outcome of a request, rendered for the owner. ``status`` mirrors the agent plus REFUSED."""

    status: str  # DONE | ESCALATED | FAILED | REFUSED
    lane: str | None
    note: str
    steps: list[dict] = field(default_factory=list)

    def to_slack(self) -> str:
        lane = f" (lane: {self.lane})" if self.lane else ""
        if self.status == "DONE":
            return f"✅ Done{lane} — {self.note}"
        if self.status == "ESCALATED":
            return f"✋ I need you{lane} — {self.note}"
        if self.status == "REFUSED":
            return f"🚫 I won't improvise on this — {self.note}"
        return f"⚠️ Couldn't finish{lane} — {self.note}"


class OperationRouter:
    """Routes a recognized OPERATE intent to a known lane and drives the agent through it (gated).

    ``build_agent(goal_amount, approve)`` returns an :class:`OperatorAgent` wired to the real Actuator +
    model at the edge (a fake in tests). ``approved_amount_for(intent)`` yields the human-approved amount
    for a money lane — there is no fallback to a model-chosen number; if a money lane has no approved
    amount, the request is refused fail-closed.
    """

    def __init__(
        self,
        *,
        lanes: list[OperationLane],
        build_agent: Callable[..., OperatorAgent],
        approved_amount_for: Callable[[CommandIntent], str | None] | None = None,
        graduation=None,
        tenant: str = "default",
    ) -> None:
        self.lanes = lanes
        self.build_agent = build_agent
        self.approved_amount_for = approved_amount_for or (lambda _i: None)
        # Optional LaneGraduation policy: governs whether a consequential lane may run WITHOUT a
        # per-run human approval. Absent/ungraduated => supervised (fail-safe).
        self.graduation = graduation
        self.tenant = tenant

    def lane_for(self, intent: CommandIntent) -> OperationLane | None:
        for lane in self.lanes:
            if lane.matches(intent):
                return lane
        return None

    def run(self, intent: CommandIntent, *, approve: Callable | None = None) -> OperationResult:
        lane = self.lane_for(intent)
        if lane is None:
            return OperationResult(
                "REFUSED", None,
                "no known workflow lane handles this request, and I don't act on requests I haven't "
                "been taught to run safely. Ask for a supported action (e.g. invoicing a delivered load).",
            )

        amount = self.approved_amount_for(intent) if lane.requires_amount else None
        if lane.requires_amount and not amount:
            # Money fence at the front door: a money lane never runs off a model-chosen figure.
            return OperationResult(
                "ESCALATED", lane.name,
                "this is a money action but no human-approved amount is bound to it yet — approve an "
                "amount and I'll run it through the gates.",
            )

        # Supervised vs autonomous: a consequential (money) lane with no per-run human approval may
        # only proceed if it has been graduated to autonomous for this tenant. Otherwise it stops and
        # asks — autonomy is earned per lane, never assumed.
        if approve is None and lane.requires_amount:
            if self.graduation is not None and self.graduation.is_autonomous(self.tenant, lane.name):
                approve = _autonomous_approval()
            else:
                return OperationResult(
                    "ESCALATED", lane.name,
                    "this lane is supervised — it needs your approval to run. Graduate it to autonomous "
                    "once you trust it and I'll handle it unattended.",
                )

        goal = lane.build_goal(intent)
        agent = self.build_agent(approved_amount=amount, approve=approve)
        result: AgentResult = agent.run(goal)
        return OperationResult(result.status, lane.name, result.note, list(result.steps))


def _autonomous_approval() -> Callable[[object], bool]:
    """A single-use approval a graduated lane grants itself: exactly ONE consequential commit may run
    unattended; any further consequential action still escalates (autonomy is bounded, not blanket)."""
    used = {"spent": False}

    def approve(_action) -> bool:
        if used["spent"]:
            return False
        used["spent"] = True
        return True

    return approve


def freight_lanes() -> list[OperationLane]:
    """The default freight back-office lanes — the workflows Neyma is taught to run autonomously.

    Each goal is deliberately bounded and ends with a read-back-to-confirm instruction, so the agent
    verifies its own work rather than declaring victory blind. Money fields are filled with the approved
    amount the runtime substitutes (the goal text tells the agent not to choose a number).
    """

    def _p(intent: CommandIntent, key: str, default: str) -> str:
        val = (intent.params or {}).get(key)
        return str(val) if val not in (None, "") else default

    def invoice_goal(intent: CommandIntent) -> str:
        customer = _p(intent, "customer", "the customer on the load")
        load_ref = _p(intent, "load_ref", "the delivered load")
        return (
            f"Create a customer invoice (accounts receivable) for {customer} for {load_ref}. "
            "Open the new-invoice screen, set the bill-to to that customer, enter a charge description, "
            "and fill the amount field (the system supplies the approved amount — do not choose one). "
            "Save the invoice, then READ the saved invoice number back to confirm it was created."
        )

    def payable_goal(intent: CommandIntent) -> str:
        carrier = _p(intent, "carrier", "the carrier on the load")
        load_ref = _p(intent, "load_ref", "the load")
        return (
            f"Record a carrier payable (accounts payable) to {carrier} for {load_ref}. "
            "Open the payable/settlement entry screen, set the carrier, enter a description, and fill the "
            "amount field (the system supplies the approved amount — do not choose one). Save it, then "
            "READ the saved record back to confirm it was created."
        )

    return [
        OperationLane("raise_invoice", ("invoice", "bill ", "raise", "receivable", " ar "), invoice_goal),
        OperationLane("record_payable", ("payable", "settle", "carrier pay", "carrier bill", " ap "), payable_goal),
    ]
