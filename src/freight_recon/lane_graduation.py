"""Per-(tenant, lane) supervised->autonomous graduation: how a lane earns the right to run unattended.

The trust model the product is sold on: every workflow lane starts SUPERVISED — a human approves each
consequential run. Once a lane has proven itself for a specific tenant, the owner can GRADUATE it to
autonomous, and only then may Neyma run that one lane without a per-run approval. Graduation is:

- **per (tenant, lane)** — autonomy for "raise_invoice" at Acme says nothing about it at Beta, or about
  "record_payable" at Acme;
- **supervised by default** — absent an explicit graduation, a lane is supervised (fail-safe);
- **persisted + audited** — every graduate/restrict appends who/when/why, and the owner can revoke
  instantly.

Backed by a small JSON file per workspace, mirroring ``OpsControl`` so a Slack command can flip it and
the OperationRouter can read it before deciding whether a no-human-approval run is allowed to proceed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(tenant: str, lane: str) -> str:
    return f"{tenant}::{lane}"


class LaneGraduation:
    """Persisted, audited record of which (tenant, lane) pairs may run autonomously."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                return {}
        return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def is_autonomous(self, tenant: str, lane: str) -> bool:
        """True only if this exact (tenant, lane) has been explicitly graduated. Fail-safe default."""
        entry = self._read().get("lanes", {}).get(_key(tenant, lane))
        return bool(entry and entry.get("autonomous"))

    def graduate(self, tenant: str, lane: str, *, actor: str, reason: str = "") -> None:
        self._set(tenant, lane, autonomous=True, actor=actor, reason=reason)

    def restrict(self, tenant: str, lane: str, *, actor: str, reason: str = "") -> None:
        """Revoke autonomy — the lane goes back to supervised (needs per-run approval)."""
        self._set(tenant, lane, autonomous=False, actor=actor, reason=reason)

    def _set(self, tenant: str, lane: str, *, autonomous: bool, actor: str, reason: str) -> None:
        data = self._read()
        lanes = data.setdefault("lanes", {})
        lanes[_key(tenant, lane)] = {
            "tenant": tenant,
            "lane": lane,
            "autonomous": autonomous,
            "updated_by": actor,
            "updated_at": _now(),
            "reason": reason,
        }
        history = data.setdefault("history", [])
        history.append({
            "tenant": tenant, "lane": lane, "autonomous": autonomous,
            "actor": actor, "at": _now(), "reason": reason,
        })
        self._write(data)

    def autonomous_lanes(self, tenant: str | None = None) -> list[dict]:
        lanes = self._read().get("lanes", {}).values()
        return [
            e for e in lanes
            if e.get("autonomous") and (tenant is None or e.get("tenant") == tenant)
        ]
