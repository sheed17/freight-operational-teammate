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


# --- content moderation: the shared, Slack-rendered, prompt-injected store must never carry abuse ---

def test_local_floor_refuses_slurs_and_is_scunthorpe_safe():
    from freight_recon.knowledge import content_rejection_reason as r
    assert r("n1gger") is not None                 # leet
    assert r("f a g g o t") is not None            # letter-spaced
    for ok in ("always attach the POD before billing", "classify the cocoon shipment",
               "pass the analysis to accounting", "Coyote often short-pays detention"):
        assert r(ok) is None                       # legit business text with no slur-as-substring


def test_learn_refuses_abusive_content_on_every_path(tmp_path):
    kb = KnowledgeBase(tmp_path / "k.json")
    assert kb.learn("n1gger", tenant="acme", kind=FactKind.BUSINESS, source="owner") is None
    assert kb.recall(tenant="acme") == []          # nothing stored
    assert kb.learn("always attach the POD", tenant="acme", kind=FactKind.PROCEDURE) is not None


def test_deep_without_api_is_the_local_floor():
    from freight_recon.knowledge import deep_content_rejection_reason as deep
    assert deep("n1gger", use_api=False) is not None
    assert deep("always attach the POD before billing", use_api=False) is None


def test_deep_maps_api_categories_to_reasons(monkeypatch):
    # Mock the OpenAI moderation client so the mapping is locked without a network call.
    import types
    from freight_recon import knowledge

    class _Cats:
        def model_dump(self):
            return {"violence": True, "harassment": False, "sexual/minors": False}

    class _Result:
        flagged = True
        categories = _Cats()

    class _Mods:
        def create(self, **_):
            return types.SimpleNamespace(results=[_Result()])

    class _FakeOpenAI:
        def __init__(self, *a, **k): self.moderations = _Mods()

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_FakeOpenAI))
    assert knowledge.deep_content_rejection_reason("...") == "it contains violent content"
