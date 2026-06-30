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
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


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

    def graduate(
        self, tenant: str, lane: str, *, actor: str, reason: str = "",
        max_amount: str | None = None, allowed_parties: list[str] | None = None,
        daily_cap: int | None = None,
    ) -> None:
        """Graduate a lane to autonomous, with optional GUARDRAILS — the limits that make autonomy safe
        to flip on: a per-run dollar ceiling, an allowlist of carriers/customers, and a daily run cap."""
        self._set(
            tenant, lane, autonomous=True, actor=actor, reason=reason,
            max_amount=max_amount, allowed_parties=allowed_parties, daily_cap=daily_cap,
        )

    def restrict(self, tenant: str, lane: str, *, actor: str, reason: str = "") -> None:
        """Revoke autonomy — the lane goes back to supervised (needs per-run approval)."""
        self._set(tenant, lane, autonomous=False, actor=actor, reason=reason)

    def _set(
        self, tenant: str, lane: str, *, autonomous: bool, actor: str, reason: str,
        max_amount: str | None = None, allowed_parties: list[str] | None = None,
        daily_cap: int | None = None,
    ) -> None:
        data = self._read()
        lanes = data.setdefault("lanes", {})
        lanes[_key(tenant, lane)] = {
            "tenant": tenant,
            "lane": lane,
            "autonomous": autonomous,
            "max_amount": max_amount,
            "allowed_parties": [p.lower() for p in (allowed_parties or [])],
            "daily_cap": daily_cap,
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

    def guardrails(self, tenant: str, lane: str) -> dict:
        entry = self._read().get("lanes", {}).get(_key(tenant, lane)) or {}
        return {
            "max_amount": entry.get("max_amount"),
            "allowed_parties": entry.get("allowed_parties") or [],
            "daily_cap": entry.get("daily_cap"),
        }

    def autonomy_allows(
        self, tenant: str, lane: str, *, amount: str | None = None, party: str | None = None,
    ) -> tuple[bool, str]:
        """May this lane run UNATTENDED for this specific run? Checks graduation AND every guardrail.

        Returns ``(allowed, reason)``. A 'no' is always a reason the owner can read in the escalation —
        the whole point is that crossing a limit asks for approval instead of silently proceeding.
        """
        if not self.is_autonomous(tenant, lane):
            return False, "lane is supervised"
        rails = self.guardrails(tenant, lane)
        ceiling = rails["max_amount"]
        if ceiling and amount and _as_decimal(amount) > _as_decimal(ceiling):
            return False, f"amount ${amount} exceeds your autonomous ceiling ${ceiling}"
        allowed = rails["allowed_parties"]
        if allowed and (party or "").lower() not in allowed:
            return False, f"{party or 'this party'} is not on your autonomous allowlist for {lane}"
        cap = rails["daily_cap"]
        if cap is not None and self.autonomous_runs_today(tenant, lane) >= cap:
            return False, f"daily autonomous cap of {cap} for {lane} reached"
        return True, "within your autonomous limits"

    def autonomous_runs_today(self, tenant: str, lane: str, *, day: str | None = None) -> int:
        return int(self._read().get("runs", {}).get(_run_key(tenant, lane, day or _today()), 0))

    def record_autonomous_run(self, tenant: str, lane: str, *, day: str | None = None) -> None:
        data = self._read()
        runs = data.setdefault("runs", {})
        key = _run_key(tenant, lane, day or _today())
        runs[key] = int(runs.get(key, 0)) + 1
        self._write(data)

    def autonomous_lanes(self, tenant: str | None = None) -> list[dict]:
        lanes = self._read().get("lanes", {}).values()
        return [
            e for e in lanes
            if e.get("autonomous") and (tenant is None or e.get("tenant") == tenant)
        ]


def _run_key(tenant: str, lane: str, day: str) -> str:
    return f"{tenant}::{lane}::{day}"


def _as_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")
