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

from freight_recon.operator_agent import AgentResult, LiveActionKind, OperatorAgent
from freight_recon.slack_delegate import CommandIntent
from freight_recon.workflow import WorkflowStore, normalize_money_amount

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
        commit_store: WorkflowStore | None = None,
    ) -> None:
        self.lanes = lanes
        self.build_agent = build_agent
        self.approved_amount_for = approved_amount_for or (lambda _i: None)
        # Optional LaneGraduation policy: governs whether a consequential lane may run WITHOUT a
        # per-run human approval. Absent/ungraduated => supervised (fail-safe).
        self.graduation = graduation
        self.tenant = tenant
        self.commit_store = commit_store

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
        commit_identity = _commit_identity(self.tenant, lane.name, intent, amount)

        # Supervised vs autonomous: a consequential (money) lane with no per-run human approval may only
        # proceed if it is graduated AND the run is within the owner's guardrails (dollar ceiling, party
        # allowlist, daily cap). Otherwise it stops and asks — crossing a limit escalates, never slips.
        autonomous_run = False
        # Autonomous entry point: callers deliberately pass approve=None. The normal Slack approval
        # callback passes an explicit approver, so it stays supervised and never consumes autonomy caps.
        if approve is None and lane.requires_amount:
            party = _party_of(intent)
            allowed, reason = (
                self.graduation.autonomy_allows(self.tenant, lane.name, amount=amount, party=party)
                if self.graduation is not None else (False, "lane is supervised")
            )
            if not allowed:
                return OperationResult(
                    "ESCALATED", lane.name,
                    f"needs your approval — {reason}. Graduate it (with limits) once you trust it and "
                    "I'll handle it unattended.",
                )
            if self.commit_store is not None and commit_identity is None:
                return OperationResult(
                    "ESCALATED",
                    lane.name,
                    "needs your approval — missing load reference or party for commit-once protection",
                )
            if self.graduation is not None and self.commit_store is not None:
                cap = self.graduation.guardrails(self.tenant, lane.name).get("daily_cap")
                if cap is not None:
                    claimed, used = self.commit_store.claim_autonomous_run(self.tenant, lane.name, cap=int(cap))
                    if not claimed:
                        return OperationResult(
                            "ESCALATED",
                            lane.name,
                            f"needs your approval — daily autonomous cap of {cap} for {lane.name} reached",
                            [{"autonomous_runs_today": used}],
                        )
            approve = _autonomous_approval()
            autonomous_run = True

        # PREPARE vs COMMIT: with a graduation policy present, a supervised (ungraduated) money lane
        # PREPARES — the agent fills everything and stops before Save, and the human commits (safe on a
        # flaky TMS; full-auto is the graduation). A graduated/autonomous run commits, and an explicit
        # resume ("submit", params['commit']) commits. No graduation policy = old behavior (commit).
        commit_requested = bool((intent.params or {}).get("commit"))
        verify_only = bool((intent.params or {}).get("verify_only"))
        if verify_only and lane.requires_amount:
            return OperationResult(
                "DONE",
                lane.name,
                "operation was already committed; resume is verify-only and will not repeat the TMS commit",
                [{"committed": True, "verify_only": True}],
            )
        prepare_only = (
            self.graduation is not None
            and lane.requires_amount
            and not autonomous_run
            and not commit_requested
        )
        will_commit = lane.requires_amount and not prepare_only
        commit_reserved = False
        if will_commit and self.commit_store is not None and commit_identity is None:
            return OperationResult(
                "ESCALATED",
                lane.name,
                "needs your approval — missing load reference or party for commit-once protection",
            )
        if will_commit and self.commit_store is not None and commit_identity is not None:
            reserved_payload = {"status": "RESERVED", "summary": intent.summary, "params": intent.params or {}}
            commit_reserved = self.commit_store.claim_operation_commit(**commit_identity, payload=reserved_payload)
            if not commit_reserved:
                existing = self.commit_store.operation_commit_claim(**commit_identity)
                return OperationResult(
                    "DONE",
                    lane.name,
                    "already committed or reserved; refusing to repeat the TMS commit",
                    [
                        {
                            "committed": True,
                            "commit_key": existing["commit_key"] if existing else None,
                            "reused_commit_claim": True,
                        }
                    ],
                )

        goal = lane.build_goal(intent)
        agent = self.build_agent(
            approved_amount=amount,
            approve=approve,
            prepare_only=prepare_only,
        )
        # Tell the agent which record it's on so crystallized recipes parameterize the ref out (learn a
        # workflow once, replay across records). Set post-build so no build_agent factory needs changing.
        if hasattr(agent, "record_ref"):
            agent.record_ref = _load_ref_of(intent) or ""
        result: AgentResult = agent.run(goal)
        steps = list(result.steps)
        committed = _result_committed(result)
        if committed and commit_identity is not None:
            commit_payload = {"status": result.status, "note": result.note, "steps": steps[-5:]}
            if self.commit_store is not None:
                self.commit_store.update_operation_commit_payload(**commit_identity, payload=commit_payload)
                existing = self.commit_store.operation_commit_claim(**commit_identity)
                steps.append(
                    {
                        "committed": True,
                        "commit_key": existing["commit_key"] if existing else None,
                    }
                )
            else:
                steps.append({"committed": True})
        elif commit_reserved and self.commit_store is not None and commit_identity is not None:
            self.commit_store.release_operation_commit(**commit_identity)
        # Count an unattended run against the daily cap only once it actually ran.
        if autonomous_run and self.graduation is not None and self.commit_store is None:
            self.graduation.record_autonomous_run(self.tenant, lane.name)
        return OperationResult(result.status, lane.name, result.note, steps)


def _party_of(intent: CommandIntent) -> str | None:
    """The counterparty an autonomy allowlist is checked against — the customer (AR) or carrier (AP)."""
    params = intent.params or {}
    for key in ("customer", "carrier", "party"):
        if params.get(key):
            return str(params[key])
    return None


def _load_ref_of(intent: CommandIntent) -> str | None:
    params = intent.params or {}
    for key in ("load_ref", "load_id", "pro", "invoice_number"):
        if params.get(key):
            return str(params[key])
    return None


def _commit_identity(tenant: str, lane: str, intent: CommandIntent, amount: str | None) -> dict | None:
    if not amount:
        return None
    load_ref = _load_ref_of(intent)
    party = _party_of(intent)
    if not load_ref or not party:
        return None
    return {
        "tenant": tenant,
        "lane": lane,
        "load_ref": load_ref,
        "party": party,
        "approved_amount": normalize_money_amount(amount),
    }


def _result_committed(result: AgentResult) -> bool:
    for step in result.steps:
        if step.get("committed") is True:
            return True
        if (
            step.get("ok") is True
            and step.get("action") == LiveActionKind.CLICK.value
            and any(k in str(step.get("target", "")).lower() for k in ("save", "submit", "create", "raise", "confirm", "pay"))
        ):
            return True
    return False


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

    def _guidance(intent: CommandIntent) -> str:
        # An owner's in-thread reply to a prior escalation — used to get unstuck (e.g. "I'm logged in,
        # proceed" or "it's Acme Corp"). Never a money value.
        g = (intent.params or {}).get("operator_guidance")
        return (f" The operator has given guidance to get past where you were stuck: \"{g}\". "
                "Follow it, then continue.") if g else ""

    def invoice_goal(intent: CommandIntent) -> str:
        customer = _p(intent, "customer", "the customer on the load")
        load_ref = _p(intent, "load_ref", "the delivered load")
        return (
            f"Create a customer invoice (accounts receivable) for {customer} for {load_ref}. "
            f"Open the delivered load/order {load_ref} and use its billing/invoicing action to start the "
            "invoice (fall back to a standalone new-invoice screen only if the record has no billing action). "
            f"Set the bill-to to {customer}, enter a charge description, and fill the amount field (the system "
            "supplies the approved amount — do not choose one). "
            "Save the invoice, then READ the saved invoice number back to confirm it was created."
            + _guidance(intent)
        )

    def payable_goal(intent: CommandIntent) -> str:
        carrier = _p(intent, "carrier", "the carrier on the load")
        load_ref = _p(intent, "load_ref", "the load")
        return (
            f"Record a carrier payable (accounts payable) to {carrier} for {load_ref}. "
            f"Open the load/order {load_ref} and use its settlement/payable action to record the payable "
            "(fall back to a standalone payable-entry screen only if the record has no such action). "
            "Set the carrier, enter a description, and fill the "
            "amount field (the system supplies the approved amount — do not choose one). Save it, then "
            "READ the saved record back to confirm it was created."
            + _guidance(intent)
        )

    return [
        OperationLane("raise_invoice", ("invoice", "bill ", "raise", "receivable", " ar "), invoice_goal),
        OperationLane("record_payable", ("payable", "settle", "carrier pay", "carrier bill", "pay ", " ap "), payable_goal),
    ]
