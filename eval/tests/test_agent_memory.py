"""Tests for agent memory: recall learned facts into reasoning + crystallize what worked."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.agent_memory import (  # noqa: E402
    AgentMemory,
    domain_of,
    fact_from_successful_run,
)
from freight_recon.operator_agent import OperatorAgent, _decide_prompt  # noqa: E402


def test_domain_extraction():
    assert domain_of("https://neyma.transporters.io/orders/view/1002") == "transporters.io"
    assert domain_of("") == "unknown"


def test_facts_recall_per_tenant_and_system_deduped(tmp_path):
    m = AgentMemory(tmp_path / "mem.json")
    m.learn_fact("Nav is JS-driven; open an order by clicking its row, not a URL.",
                 tenant="acme", domain="transporters.io")
    m.learn_fact("Nav is JS-driven; open an order by clicking its row, not a URL.",  # dup
                 tenant="acme", domain="transporters.io")
    m.learn_fact("Invoices are raised from an order.", tenant="acme", domain="transporters.io")
    facts = m.recall_facts(tenant="acme", domain="transporters.io")
    assert len(facts) == 2  # deduped
    # scoped: another tenant / another system sees nothing
    assert m.recall_facts(tenant="beta", domain="transporters.io") == []
    assert m.recall_facts(tenant="acme", domain="truckingoffice.com") == []


def test_recipe_saved_only_from_successful_nav_steps_no_money(tmp_path):
    m = AgentMemory(tmp_path / "mem.json")
    steps = [
        {"action": "CLICK", "target": "View Orders", "ok": True},
        {"action": "CLICK", "target": "Northbound row", "ok": False},   # failed -> not in recipe
        {"action": "TYPE", "target": "Total Charge", "value": "2850.00", "ok": True},
        {"action": "DONE", "ok": True},
    ]
    m.save_recipe(steps, tenant="acme", task="raise_invoice")
    recipe = m.recall_recipe(tenant="acme", task="raise_invoice")
    assert {"action": "CLICK", "target": "View Orders"} in recipe
    assert all(s.get("action") != "DONE" for s in recipe)  # only real nav actions
    # money value is NOT stored in memory
    assert "2850.00" not in json.dumps(recipe)


def test_fact_derivation_from_a_working_run():
    steps = [
        {"action": "CLICK", "target": "View Orders", "ok": True},
        {"action": "CLICK", "target": "Northbound #1002", "ok": True},
        {"action": "CLICK", "target": "Billing", "ok": True},
        {"action": "READ", "target": "invoice number", "ok": True},
    ]
    fact = fact_from_successful_run(steps, task="raise an invoice", domain="transporters.io")
    assert "raise an invoice" in fact and "transporters.io" in fact
    assert "click View Orders" in fact and "click Billing" in fact


def test_prompt_injects_recalled_facts():
    p = _decide_prompt("raise an invoice", {"url": "x"}, [],
                       learned=["Nav is JS-driven; click the row.", "Invoices raised from an order."])
    assert "WHAT YOU'VE LEARNED ABOUT THIS SYSTEM" in p
    assert "click the row" in p and "raised from an order" in p


class _Actuator:
    def __init__(self): self.calls = []
    def observe(self): return {"url": "https://neyma.transporters.io/dashboard", "interactive": [], "errors": []}
    def navigate(self, u): return True
    def click(self, t): self.calls.append(t); return True
    def type(self, t, v): return True
    def select(self, t, o): return True
    def read(self, t): return "INV-1"


def test_agent_recalls_then_crystallizes_over_two_runs(tmp_path):
    mem = AgentMemory(tmp_path / "mem.json")
    seen_prompts = []

    def llm_run1(prompt):
        seen_prompts.append(("run1", prompt))
        # first run: no memory yet -> click around, then DONE
        if "View Orders" not in prompt:  # crude sequence via history length is hard; just drive to DONE
            pass
        return json.dumps({"action": "CLICK", "target": "View Orders"}) if len(seen_prompts) == 1 \
            else json.dumps({"action": "DONE", "why": "done"})

    a1 = OperatorAgent(actuator=_Actuator(), complete=llm_run1, memory=mem, tenant="acme", task="raise_invoice")
    r1 = a1.run("raise an invoice")
    assert r1.status == "DONE"
    # it learned a fact about transporters.io
    facts = mem.recall_facts(tenant="acme", domain="transporters.io")
    assert facts and any("transporters.io" in f for f in facts)

    # second run: the recalled fact is now injected into the agent's very first prompt
    run2_prompts = []
    def llm_run2(prompt):
        run2_prompts.append(prompt)
        return json.dumps({"action": "DONE", "why": "done"})
    a2 = OperatorAgent(actuator=_Actuator(), complete=llm_run2, memory=mem, tenant="acme", task="raise_invoice")
    a2.run("raise an invoice")
    assert "WHAT YOU'VE LEARNED ABOUT THIS SYSTEM" in run2_prompts[0]
