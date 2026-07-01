"""Tests for the shared company knowledge base: learn/recall/inspect/correct, per tenant, no leak."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.knowledge import FactKind, KnowledgeBase  # noqa: E402


def test_learn_recall_dedup_and_kinds(tmp_path):
    kb = KnowledgeBase(tmp_path / "k.json")
    kb.learn("Nav is JS-driven; open an order by clicking its row.", tenant="acme",
             kind=FactKind.SYSTEM, subject="transporters.io")
    kb.learn("Nav is JS-driven; open an order by clicking its row.", tenant="acme",  # dup
             kind=FactKind.SYSTEM, subject="transporters.io")
    kb.learn("Northbound Freight Brokers is order #1002.", tenant="acme",
             kind=FactKind.BUSINESS, subject="Northbound")
    kb.learn("Auto-invoice under $3000.", tenant="acme", kind=FactKind.PREFERENCE)

    sys_facts = kb.recall(tenant="acme", kind=FactKind.SYSTEM, subject="transporters.io")
    assert len(sys_facts) == 1  # deduped
    prefs = kb.recall(tenant="acme", kind=FactKind.PREFERENCE)
    assert prefs == ["Auto-invoice under $3000."]


def test_recall_returns_subject_and_general_facts(tmp_path):
    kb = KnowledgeBase(tmp_path / "k.json")
    kb.learn("general system quirk", tenant="acme", kind=FactKind.SYSTEM)  # no subject
    kb.learn("transporters-specific quirk", tenant="acme", kind=FactKind.SYSTEM, subject="transporters.io")
    kb.learn("truckingoffice quirk", tenant="acme", kind=FactKind.SYSTEM, subject="truckingoffice.com")
    recalled = kb.recall(tenant="acme", kind=FactKind.SYSTEM, subject="transporters.io")
    assert "transporters-specific quirk" in recalled and "general system quirk" in recalled
    assert "truckingoffice quirk" not in recalled  # other system's fact not leaked in


def test_per_tenant_isolation(tmp_path):
    kb = KnowledgeBase(tmp_path / "k.json")
    kb.learn("acme secret", tenant="acme", kind=FactKind.BUSINESS)
    assert kb.recall(tenant="beta", kind=FactKind.BUSINESS) == []


def test_inspect_and_correct(tmp_path):
    kb = KnowledgeBase(tmp_path / "k.json")
    fid = kb.learn("Northbound is a broker in Dallas.", tenant="acme", kind=FactKind.BUSINESS, subject="Northbound")
    text = kb.render(tenant="acme")
    assert "What I've learned" in text and "Northbound is a broker" in text and fid in text
    # correct by id
    assert kb.forget(fid, tenant="acme") == 1
    assert kb.facts(tenant="acme") == []
    # correct by words
    kb.learn("Coyote often short-pays detention.", tenant="acme", kind=FactKind.BUSINESS)
    assert kb.forget("short-pays", tenant="acme") == 1


def test_no_money_and_agent_memory_shares_the_store(tmp_path):
    # AgentMemory's SYSTEM facts flow into the SAME knowledge base (one shared memory).
    from freight_recon.agent_memory import AgentMemory

    path = tmp_path / "agent_memory.json"
    mem = AgentMemory(path)
    mem.learn_fact("transporters.io invoices are raised from an order.", tenant="acme", domain="transporters.io")
    kb = KnowledgeBase(path)
    facts = kb.recall(tenant="acme", kind=FactKind.SYSTEM, subject="transporters.io")
    assert any("raised from an order" in f for f in facts)
    # recipes (also in the same file) coexist and don't clobber the knowledge section
    mem.save_recipe([{"action": "CLICK", "target": "View Orders", "ok": True}], tenant="acme", task="raise_invoice")
    assert mem.recall_recipe(tenant="acme", task="raise_invoice")
    assert kb.recall(tenant="acme", kind=FactKind.SYSTEM, subject="transporters.io")  # still there
