"""Tests for per-(tenant, lane) supervised->autonomous graduation + its effect on the router."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.lane_graduation import LaneGraduation  # noqa: E402
from freight_recon.operation_router import OperationRouter, freight_lanes  # noqa: E402
from freight_recon.operator_agent import OperatorAgent  # noqa: E402
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402


def _scripted_llm(actions):
    seq = list(actions)

    def complete(_p):
        return json.dumps(seq.pop(0)) if seq else json.dumps({"action": "DONE", "why": "done"})

    return complete


class _FakeActuator:
    def observe(self): return {"url": "x", "interactive": [], "errors": []}
    def navigate(self, u): return True
    def click(self, t): return True
    def type(self, t, v): return True
    def select(self, t, o): return True
    def read(self, t): return "INV-1"


def _operate(summary, params=None):
    return CommandIntent(CommandKind.OPERATE, summary, params or {})


def _agent_factory(llm):
    def build_agent(*, approved_amount=None, approve=None, prepare_only=False):
        return OperatorAgent(actuator=_FakeActuator(), complete=llm, approved_amount=approved_amount,
                             approve=approve, prepare_only=prepare_only)
    return build_agent


def test_defaults_to_supervised_and_is_audited(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")
    assert grad.is_autonomous("acme", "raise_invoice") is False  # fail-safe default
    grad.graduate("acme", "raise_invoice", actor="R", reason="proven over 20 runs")
    assert grad.is_autonomous("acme", "raise_invoice") is True
    # per (tenant, lane): says nothing about another tenant or lane
    assert grad.is_autonomous("beta", "raise_invoice") is False
    assert grad.is_autonomous("acme", "record_payable") is False
    grad.restrict("acme", "raise_invoice", actor="R", reason="saw an error")
    assert grad.is_autonomous("acme", "raise_invoice") is False
    history = json.loads((tmp_path / "grad.json").read_text())["history"]
    assert [h["autonomous"] for h in history] == [True, False]


def test_supervised_lane_escalates_without_human_approval(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")  # nothing graduated
    router = OperationRouter(
        lanes=freight_lanes(), build_agent=_agent_factory(_scripted_llm([])),
        approved_amount_for=lambda _i: "100.00", graduation=grad, tenant="acme",
    )
    # No human approve passed and the lane is supervised -> it must stop and ask, not run.
    res = router.run(_operate("invoice the load for Acme"))
    assert res.status == "ESCALATED" and "supervised" in res.note


def test_graduated_lane_runs_unattended(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")
    grad.graduate("acme", "raise_invoice", actor="R")
    llm = _scripted_llm([{"action": "CLICK", "target": "Save invoice"},
                         {"action": "DONE", "why": "invoice INV-1 created"}])
    router = OperationRouter(
        lanes=freight_lanes(), build_agent=_agent_factory(llm),
        approved_amount_for=lambda _i: "100.00", graduation=grad, tenant="acme",
    )
    res = router.run(_operate("invoice the load for Acme"))  # no human approval
    assert res.status == "DONE" and res.lane == "raise_invoice"


def test_human_approval_still_works_regardless_of_graduation(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")  # supervised
    llm = _scripted_llm([{"action": "DONE", "why": "ok"}])
    router = OperationRouter(
        lanes=freight_lanes(), build_agent=_agent_factory(llm),
        approved_amount_for=lambda _i: "100.00", graduation=grad, tenant="acme",
    )
    # An explicit human approval (the Slack-button path) runs even when not graduated.
    res = router.run(_operate("invoice the load for Acme"), approve=lambda a: True)
    assert res.status == "DONE"


def test_guardrails_block_over_ceiling_and_record_within_limit(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")
    grad.graduate("acme", "record_payable", actor="R", max_amount="2500.00", daily_cap=2)
    llm = _scripted_llm([{"action": "DONE", "why": "payable recorded"}])
    router = OperationRouter(
        lanes=freight_lanes(), build_agent=_agent_factory(llm),
        approved_amount_for=lambda i: i.params.get("amount", "1000.00"),
        graduation=grad, tenant="acme",
    )
    # Over the ceiling -> escalates with a readable reason, does not run.
    over = router.run(_operate("record the carrier payable for LD-1", {"amount": "9000.00"}))
    assert over.status == "ESCALATED" and "ceiling" in over.note
    assert grad.autonomous_runs_today("acme", "record_payable") == 0
    # Within the ceiling -> runs unattended and counts against the daily cap.
    ok = router.run(_operate("record the carrier payable for LD-2", {"amount": "1200.00"}))
    assert ok.status == "DONE"
    assert grad.autonomous_runs_today("acme", "record_payable") == 1


def test_guardrails_enforce_party_allowlist_and_daily_cap(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")
    grad.graduate("acme", "raise_invoice", actor="R", allowed_parties=["Acme Corp"], daily_cap=1)
    llm = _scripted_llm([{"action": "DONE", "why": "ok"}])
    router = OperationRouter(
        lanes=freight_lanes(), build_agent=_agent_factory(llm),
        approved_amount_for=lambda _i: "100.00", graduation=grad, tenant="acme",
    )
    # Party not on the allowlist -> escalates.
    off = router.run(_operate("invoice the load", {"customer": "Stranger LLC"}))
    assert off.status == "ESCALATED" and "allowlist" in off.note
    # Allowed party -> runs (and hits the daily cap of 1).
    on = router.run(_operate("invoice the load", {"customer": "Acme Corp"}))
    assert on.status == "DONE"
    capped = router.run(_operate("invoice the load", {"customer": "Acme Corp"}))
    assert capped.status == "ESCALATED" and "daily" in capped.note


def test_supervised_lane_prepares_and_a_commit_reply_finishes(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")  # present but nothing graduated -> supervised
    # The agent fills, then reaches the committing Save.
    llm = _scripted_llm([{"action": "CLICK", "target": "Save invoice"}, {"action": "DONE", "why": "ok"}])
    router = OperationRouter(
        lanes=freight_lanes(), build_agent=_agent_factory(llm),
        approved_amount_for=lambda _i: "100.00", graduation=grad, tenant="acme",
    )
    # Human tapped Approve, but supervised -> PREPARE: fill everything, stop before Save.
    staged = router.run(_operate("invoice the load for Acme"), approve=lambda a: True)
    assert staged.status == "PREPARED" and "Save invoice" in staged.note

    # A resume that carries commit=True (an owner's thread reply) actually commits.
    llm2 = _scripted_llm([{"action": "CLICK", "target": "Save invoice"}, {"action": "DONE", "why": "saved"}])
    router2 = OperationRouter(
        lanes=freight_lanes(), build_agent=_agent_factory(llm2),
        approved_amount_for=lambda _i: "100.00", graduation=grad, tenant="acme",
    )
    done = router2.run(_operate("invoice the load for Acme", {"commit": True}), approve=lambda a: True)
    assert done.status == "DONE"


def test_no_graduation_policy_keeps_old_behavior(tmp_path):
    # Backward compat: without a graduation policy, a no-approval money lane still escalates (supervised).
    router = OperationRouter(
        lanes=freight_lanes(), build_agent=_agent_factory(_scripted_llm([])),
        approved_amount_for=lambda _i: "100.00",
    )
    res = router.run(_operate("invoice the load for Acme"))
    assert res.status == "ESCALATED"
