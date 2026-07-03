"""Safe browser-learning primitives for client-specific TMS operation.

This is the self-improvement layer, not an authority layer. It records what screens looked like and
which navigation/action path worked, then turns successful runs into reusable macros. The sanitizer
removes money-like values so memory can speed up navigation without changing amounts, approvals, or
write policy.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .atomic_io import atomic_write_json

MONEY_RE = re.compile(r"(?<!\w)(?:usd\s*\$?\s*|\$)\d[\d,]*(?:\.\d{1,2})?\b|\b\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?\b", re.I)


def scrub_money_text(text: str) -> str:
    return MONEY_RE.sub("[amount redacted]", " ".join(str(text or "").split()))


def screen_fingerprint(observation: dict[str, Any] | None) -> dict[str, Any]:
    obs = observation or {}
    headings = [str(h) for h in (obs.get("headings") or []) if str(h).strip()][:6]
    actions = [str(a) for a in (obs.get("actions") or []) if str(a).strip()][:20]
    table_headers: list[list[str]] = []
    for table in (obs.get("tables") or [])[:5]:
        headers = [str(h) for h in (table.get("headers") or []) if str(h).strip()][:12]
        if headers:
            table_headers.append(headers)
    raw = json.dumps(
        {
            "url": obs.get("url", ""),
            "headings": headings,
            "actions": actions,
            "table_headers": table_headers,
        },
        sort_keys=True,
    )
    return {
        "hash": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
        "url": obs.get("url", ""),
        "headings": headings,
        "actions": actions[:10],
        "table_headers": table_headers,
    }


def sanitized_macro_steps(steps: list[dict[str, Any]], *, max_steps: int = 10) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for step in steps or []:
        action = str(step.get("action") or "")
        if action not in {"NAVIGATE", "CLICK", "SELECT", "TYPE", "READ"}:
            continue
        if step.get("ok") is not True:
            continue
        target = scrub_money_text(str(step.get("target") or ""))[:160]
        item = {"action": action, "target": target}
        if action in {"SELECT", "TYPE"}:
            value = scrub_money_text(str(step.get("value") or ""))[:80]
            if value:
                item["value"] = "[text redacted]" if action == "TYPE" else value
        if target:
            out.append(item)
        if len(out) >= max_steps:
            break
    return out


@dataclass
class BrowserTraceEvent:
    step: int
    observation_fingerprint: dict[str, Any]
    action: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    screenshot_path: str | None = None
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BrowserRunTrace:
    """Append-only trace artifact for a browser operation run."""

    def __init__(self, path: str | Path, *, tenant: str, task: str, domain: str = "unknown") -> None:
        self.path = Path(path)
        self.tenant = tenant
        self.task = task
        self.domain = domain
        self.events: list[BrowserTraceEvent] = []

    def record(
        self,
        *,
        step: int,
        observation: dict[str, Any] | None,
        action: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        screenshot_path: str | None = None,
    ) -> None:
        self.events.append(
            BrowserTraceEvent(
                step=step,
                observation_fingerprint=screen_fingerprint(observation),
                action=_scrub_dict(action),
                result=_scrub_dict(result),
                screenshot_path=screenshot_path,
            )
        )

    def write(self, *, status: str, note: str) -> str:
        payload = {
            "tenant": self.tenant,
            "task": self.task,
            "domain": self.domain,
            "status": status,
            "note": scrub_money_text(note),
            "events": [event.__dict__ for event in self.events],
        }
        atomic_write_json(self.path, payload, indent=2, sort_keys=True)
        return str(self.path)


def _scrub_dict(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    return json.loads(json.dumps(data), object_hook=lambda obj: {k: scrub_money_text(v) if isinstance(v, str) else v for k, v in obj.items()})

