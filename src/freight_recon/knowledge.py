"""The shared company knowledge base — Neyma's one memory that every surface reads and writes.

This is what turns "the TMS agent learns" into "Neyma learns." A single per-client store of durable
FACTS that the TMS agent, the Slack delegate, and the inbox all draw on, so a thing learned in one
place is known everywhere. Three kinds, mirroring how a human hire gets better:

- SYSTEM — how to operate a client's tools ("transporters.io nav is JS-driven; open an order by
  clicking its row"). Written by the driving agent when a run works.
- BUSINESS — the client's world ("Northbound Freight Brokers → order #1002"; "TQL often bills
  detention with no backup"). Written from corrections and observed patterns.
- PREFERENCE — how the owner likes things ("auto-invoice under $3k"; "keep dispute notes short").
  Written from the owner's Slack commands.

Two properties make it an assistant and not a black box:
- **Inspectable + correctable.** The owner can ask what Neyma knows and tell it to forget/relearn —
  wrong facts never silently accumulate (critical near money).
- **Never money, never cross-tenant.** Facts are guidance + identity only (no amounts), scoped per
  tenant. Confidence from memory makes Neyma faster; it never weakens the money fence or the gates.

Backed by JSON per workspace (a `knowledge` section; the agent's crystallized recipes live alongside in
a `recipes` section, managed by AgentMemory — both preserve each other's section on write).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .atomic_io import atomic_write_json


class FactKind(str, Enum):
    SYSTEM = "system"          # how to operate the tools (learned by the driving agent)
    BUSINESS = "business"      # the client's world (carriers, customers, entities)
    PREFERENCE = "preference"  # how the owner likes things
    PROCEDURE = "procedure"    # the company's SOPs — how THIS company does a task (from onboarding)


def _norm(text: str) -> str:
    return " ".join((text or "").split()).strip()


class KnowledgeBase:
    """Per-(tenant) durable facts, categorized, inspectable, correctable."""

    def __init__(self, path: str | Path, *, max_facts_per_tenant: int = 500) -> None:
        self.path = Path(path)
        self.max_facts = max_facts_per_tenant

    def _read(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                return {}
        return {}

    def _write(self, data: dict) -> None:
        atomic_write_json(self.path, data, indent=2, sort_keys=True)

    def learn(self, text: str, *, tenant: str, kind: FactKind = FactKind.SYSTEM,
              subject: str | None = None, source: str = "system") -> str | None:
        """Record a durable fact. Deduplicated on (kind, subject, text). Returns its id (or None)."""
        text = _norm(text)
        if not text:
            return None
        subject = _norm(subject) or None
        data = self._read()
        facts = data.setdefault("knowledge", {}).setdefault(tenant, [])
        for f in facts:
            if f["kind"] == kind.value and (f.get("subject") or None) == subject \
                    and f["text"].lower() == text.lower():
                return f["id"]  # already known
        fid = uuid.uuid4().hex[:8]
        facts.append({
            "id": fid, "kind": kind.value, "subject": subject, "text": text,
            "source": source, "at": datetime.now(timezone.utc).isoformat(),
        })
        if len(facts) > self.max_facts:
            del facts[0 : len(facts) - self.max_facts]
        self._write(data)
        return fid

    def recall(self, *, tenant: str, kind: FactKind | None = None, subject: str | None = None,
               limit: int = 12) -> list[str]:
        """Facts for the agent's reasoning. When ``subject`` is given, returns facts for that subject
        AND general (subjectless) facts of the same kind."""
        subject = _norm(subject) or None
        out = []
        for f in self._read().get("knowledge", {}).get(tenant, []):
            if kind is not None and f["kind"] != kind.value:
                continue
            if subject is not None and (f.get("subject") or None) not in (subject, None):
                continue
            out.append(f["text"])
        return out[-limit:]

    def facts(self, *, tenant: str, query: str | None = None) -> list[dict]:
        """Full fact records, for the inspect surface. Optional substring filter on text/subject."""
        q = _norm(query).lower() if query else None
        rows = self._read().get("knowledge", {}).get(tenant, [])
        if not q:
            return list(rows)
        return [f for f in rows if q in f["text"].lower() or q in (f.get("subject") or "").lower()]

    def forget(self, needle: str, *, tenant: str) -> int:
        """Correct the record: remove facts matching an id or a text/subject substring. Returns count."""
        needle = _norm(needle)
        if not needle:
            return 0
        data = self._read()
        rows = data.setdefault("knowledge", {}).setdefault(tenant, [])
        nl = needle.lower()
        keep = [f for f in rows if not (f["id"] == needle or nl in f["text"].lower()
                                        or nl in (f.get("subject") or "").lower())]
        removed = len(rows) - len(keep)
        if removed:
            data["knowledge"][tenant] = keep
            self._write(data)
        return removed

    def render(self, *, tenant: str, query: str | None = None, limit: int = 25) -> str:
        """Owner-readable 'what Neyma knows' (for `/neyma know`)."""
        rows = self.facts(tenant=tenant, query=query)
        if not rows:
            scope = f" about '{query}'" if query else ""
            return f":thinking_face: I haven't learned anything{scope} yet."
        icon = {"system": "⚙️", "business": "🏢", "preference": "⭐", "procedure": "📋"}
        lines = ["*What I've learned*" + (f" about '{query}'" if query else "") + ":"]
        for f in rows[-limit:]:
            subj = f" ({f['subject']})" if f.get("subject") else ""
            lines.append(f"{icon.get(f['kind'], '•')} {f['text']}{subj}  ·  _{f['id']}_")
        lines.append("_Correct me: `/neyma forget <id or words>`._")
        return "\n".join(lines)
