"""Agent memory: how Neyma's operators get better with repetition, like a human employee.

A new hire is slow the first time through an unfamiliar system — they reason out every click. By the
tenth time they move on muscle memory. This gives our agents the same arc, PER CLIENT:

- **Facts** — durable lessons about a specific system, learned from what worked and from the owner's
  corrections: "transporters.io nav is JS-driven; open an order by clicking its row, not a URL",
  "Northbound Freight Brokers → order #1002". These are RECALLED into the agent's reasoning on the next
  run, so it doesn't re-derive them — it just knows.
- **Recipes** — the successful action sequence for a (tenant, task), crystallized so a routine flow can
  later be replayed deterministically instead of re-reasoned (the cost + speed win).

Scoped per (tenant, system) so one client's learning never leaks to another; persisted as JSON so it
survives restarts and compounds over time. Safe by construction: memory is guidance + recorded paths —
it never carries a money value, and the money fence / gates / anti-hallucination guards still hold.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from .atomic_io import atomic_write_json


def domain_of(url: str | None) -> str:
    """The system a fact/recipe belongs to — the host (e.g. 'transporters.io'), stripped of subdomain
    noise where obvious. Falls back to 'unknown' so memory never crashes a run."""
    host = (urlsplit(url or "").netloc or "").lower()
    if not host:
        return "unknown"
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _key(*parts: str) -> str:
    return "::".join(p or "" for p in parts)


class AgentMemory:
    """The driving agent's memory: SYSTEM facts (delegated to the shared KnowledgeBase so every surface
    shares them) + per-(tenant, task) crystallized recipes. One JSON file; facts live in the
    ``knowledge`` section, recipes in ``recipes`` — each preserves the other on write."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        from freight_recon.knowledge import KnowledgeBase

        self.kb = KnowledgeBase(path)  # facts flow into the shared per-client knowledge base

    def _read(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                return {}
        return {}

    def _write(self, data: dict) -> None:
        atomic_write_json(self.path, data, indent=2, sort_keys=True)

    # --- facts (recalled into reasoning) — delegate to the shared knowledge base -------------

    def recall_facts(self, *, tenant: str, domain: str, limit: int = 12) -> list[str]:
        from freight_recon.knowledge import FactKind

        return self.kb.recall(tenant=tenant, kind=FactKind.SYSTEM, subject=domain, limit=limit)

    def learn_fact(self, fact: str, *, tenant: str, domain: str) -> None:
        from freight_recon.knowledge import FactKind

        self.kb.learn(fact, tenant=tenant, kind=FactKind.SYSTEM, subject=domain, source="agent")

    def recall_business(self, *, tenant: str, text: str, limit: int = 8) -> list[str]:
        """BUSINESS facts relevant to what the agent is doing right now: general ones, plus any whose
        subject (a carrier/customer/load) is named in the goal — so "Northbound -> order #1002" surfaces
        exactly when it's working on Northbound."""
        return self._recall_relevant("business", tenant=tenant, text=text, limit=limit)

    def recall_procedures(self, *, tenant: str, text: str, limit: int = 8) -> list[str]:
        """The company's SOPs + preferences relevant to this task: how THIS company does things (from
        onboarding), so the agent follows the handbook — general ones plus any scoped to the task."""
        procs = self._recall_relevant("procedure", tenant=tenant, text=text, limit=limit)
        prefs = self._recall_relevant("preference", tenant=tenant, text=text, limit=limit)
        return (procs + prefs)[-limit:]

    def _recall_relevant(self, kind: str, *, tenant: str, text: str, limit: int) -> list[str]:
        tl = (text or "").lower()
        out = []
        for f in self.kb.facts(tenant=tenant):
            if f["kind"] != kind:
                continue
            subj = (f.get("subject") or "").lower()
            if not subj or subj in tl:
                out.append(f["text"])
        return out[-limit:]

    # --- recipes (crystallized successful paths, for later replay) --------------------------

    def recall_recipe(self, *, tenant: str, task: str) -> list[dict] | None:
        return self._read().get("recipes", {}).get(_key(tenant, task)) or None

    def save_recipe(self, steps: list[dict], *, tenant: str, task: str) -> None:
        """Crystallize the action sequence that worked, so a routine flow can be replayed, not re-reasoned.
        Money values are never stored — only the navigation shape (action + target)."""
        clean = []
        for s in (steps or []):
            if not (s.get("ok") and s.get("action") in ("NAVIGATE", "CLICK", "SELECT", "TYPE", "READ")):
                continue
            item = {"action": s.get("action"), "target": s.get("target")}
            # Values are NEVER stored (money-safety) — EXCEPT the "{record}" placeholder, which is a record
            # identifier, never an amount, and is needed to re-fill a search/filter step on replay.
            if s.get("value") == "{record}":
                item["value"] = "{record}"
            clean.append(item)
        if not clean:
            return
        data = self._read()
        data.setdefault("recipes", {})[_key(tenant, task)] = clean
        self._write(data)


def fact_from_successful_run(steps: list[dict], *, task: str, domain: str) -> str:
    """Derive a compact, reusable lesson from a run that worked — the key navigation moves — so next
    time the agent recalls the path instead of rediscovering it."""
    moves: list[str] = []
    for s in steps or []:
        if not s.get("ok") or s.get("action") not in ("NAVIGATE", "CLICK", "SELECT"):
            continue
        target = " ".join(str(s.get("target") or "").split())[:40]
        if target:
            moves.append(f"{str(s.get('action')).lower()} {target}")
        if len(moves) >= 6:
            break
    if not moves:
        return ""
    return f"To {task or 'complete this'} on {domain}: " + " → ".join(moves) + "."
