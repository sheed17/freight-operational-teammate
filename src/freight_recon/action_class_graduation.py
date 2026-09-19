"""Per-(tenant, action_class) supervised->autonomous graduation: how an action class earns the right
to run unattended.

### VOCABULARY (U8.5): this module used to be `lane_graduation.py` and its identifier was `lane`.
Mechanically, that identifier is an **action_class** — it is fed OperationRouter's ``route.name`` (the
WHAT-effect: ``raise_invoice`` / ``record_payable`` / ...), which is the same population U8.1 registers
(``commit_key.OCCURRENCE_RULES``); there is no second registry. The graduation SCOPE is that action
class (M11's own policy `scope` is also read as the action_class at checkpoint step 6), so U8.5
renames the identifier to `action_class`. This is mechanical and BEHAVIOR-FREE: it broadens nothing,
graduates nothing new, changes no cap, and enables no unattended execution. It remains a PRE-P8,
ships-dark autonomy store — the deployed callback server wires no OperationRouter, so nothing here runs
an effect. It is NOT the P8 checkpoint/M11 authority and mints no gate; autonomy stays prohibited until
its own later phase.

The trust model the product is sold on: every action class starts SUPERVISED — a human approves each
consequential run. Once an action class has proven itself for a specific tenant, the owner can GRADUATE
it to autonomous, and only then may Neyma run that one action class without a per-run approval.
Graduation is:

- **per (tenant, action_class)** — autonomy for "raise_invoice" at Acme says nothing about it at Beta,
  or about "record_payable" at Acme;
- **supervised by default** — absent an explicit graduation, an action class is supervised (fail-safe);
- **persisted + audited** — every graduate/restrict appends who/when/why, and the owner can revoke
  instantly.

Backed by a small JSON file per workspace, mirroring ``OpsControl`` so a Slack command can flip it and
the OperationRouter can read it before deciding whether a no-human-approval run is allowed to proceed.

### ON-DISK COMPATIBILITY (U8.5, bounded and one-directional). The store reads ``action_class`` fields
and translates a legacy ``lane`` field ONCE, at read time, from a pre-U8.5 JSON file (its old
``lane_graduation.json`` name is accepted via ``legacy_path``). New writes emit ONLY the canonical
vocabulary, so the legacy word never survives internally as authority and both fields can never
independently control behaviour.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .atomic_io import atomic_write_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _key(tenant: str, action_class: str) -> str:
    return f"{tenant}::{action_class}"


def _migrate_legacy_shape(data: dict) -> dict:
    """Translate a pre-U8.5 JSON shape to the canonical one, ONCE, at read time.

    Bounded and one-directional: the top-level ``lanes`` map becomes ``action_classes``, each entry's
    ``lane`` field becomes ``action_class``, and each history record's ``lane`` becomes
    ``action_class``. The value is never reinterpreted — an action class carried under the old field
    name is the same string under the new one. The ``runs`` map is value-keyed (``tenant::value::day``)
    and needs no change.
    """
    if not isinstance(data, dict):
        return {}
    entries = data.get("action_classes")
    if entries is None:
        entries = data.get("lanes") or {}
    canonical_entries = {}
    for k, entry in entries.items():
        e = dict(entry)
        if "action_class" not in e and "lane" in e:
            e["action_class"] = e.pop("lane")
        e.pop("lane", None)
        canonical_entries[k] = e
    history = []
    for h in data.get("history", []):
        rec = dict(h)
        if "action_class" not in rec and "lane" in rec:
            rec["action_class"] = rec.pop("lane")
        rec.pop("lane", None)
        history.append(rec)
    return {
        "action_classes": canonical_entries,
        "history": history,
        "runs": dict(data.get("runs", {})),
    }


class ActionClassGraduation:
    """Persisted, audited record of which (tenant, action_class) pairs may run autonomously."""

    def __init__(self, path: str | Path, *, legacy_path: str | Path | None = None) -> None:
        self.path = Path(path)
        # The pre-U8.5 filename (`lane_graduation.json`). Read ONE-DIRECTIONALLY when the canonical
        # file does not yet exist, then never again once a canonical write lands.
        self.legacy_path = Path(legacy_path) if legacy_path is not None else None

    def _read(self) -> dict:
        raw: dict | None = None
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raw = {}
        elif self.legacy_path is not None and self.legacy_path.exists():
            try:
                raw = json.loads(self.legacy_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raw = {}
        if raw is None:
            return {}
        return _migrate_legacy_shape(raw)

    def _write(self, data: dict) -> None:
        atomic_write_json(self.path, data, indent=2, sort_keys=True)

    def is_autonomous(self, tenant: str, action_class: str) -> bool:
        """True only if this exact (tenant, action_class) has been explicitly graduated. Fail-safe."""
        entry = self._read().get("action_classes", {}).get(_key(tenant, action_class))
        return bool(entry and entry.get("autonomous"))

    def graduate(
        self, tenant: str, action_class: str, *, actor: str, reason: str = "",
        max_amount: str | None = None, allowed_parties: list[str] | None = None,
        daily_cap: int | None = None,
    ) -> None:
        """Graduate an action class to autonomous, with optional GUARDRAILS — the limits that make
        autonomy safe to flip on: a per-run dollar ceiling, an allowlist of carriers/customers, and a
        daily run cap."""
        self._set(
            tenant, action_class, autonomous=True, actor=actor, reason=reason,
            max_amount=max_amount, allowed_parties=allowed_parties, daily_cap=daily_cap,
        )

    def restrict(self, tenant: str, action_class: str, *, actor: str, reason: str = "") -> None:
        """Revoke autonomy — the action class goes back to supervised (needs per-run approval)."""
        self._set(tenant, action_class, autonomous=False, actor=actor, reason=reason)

    def _set(
        self, tenant: str, action_class: str, *, autonomous: bool, actor: str, reason: str,
        max_amount: str | None = None, allowed_parties: list[str] | None = None,
        daily_cap: int | None = None,
    ) -> None:
        data = self._read()
        entries = data.setdefault("action_classes", {})
        entries[_key(tenant, action_class)] = {
            "tenant": tenant,
            "action_class": action_class,
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
            "tenant": tenant, "action_class": action_class, "autonomous": autonomous,
            "actor": actor, "at": _now(), "reason": reason,
        })
        self._write(data)

    def guardrails(self, tenant: str, action_class: str) -> dict:
        entry = self._read().get("action_classes", {}).get(_key(tenant, action_class)) or {}
        return {
            "max_amount": entry.get("max_amount"),
            "allowed_parties": entry.get("allowed_parties") or [],
            "daily_cap": entry.get("daily_cap"),
        }

    def autonomy_allows(
        self, tenant: str, action_class: str, *, amount: str | None = None, party: str | None = None,
    ) -> tuple[bool, str]:
        """May this action class run UNATTENDED for this specific run? Checks graduation AND every
        guardrail.

        Returns ``(allowed, reason)``. A 'no' is always a reason the owner can read in the escalation —
        the whole point is that crossing a limit asks for approval instead of silently proceeding.
        """
        if not self.is_autonomous(tenant, action_class):
            return False, "action class is supervised"
        rails = self.guardrails(tenant, action_class)
        ceiling = rails["max_amount"]
        if ceiling and amount and _as_decimal(amount) > _as_decimal(ceiling):
            return False, f"amount ${amount} exceeds your autonomous ceiling ${ceiling}"
        allowed = rails["allowed_parties"]
        if allowed and (party or "").lower() not in allowed:
            return False, f"{party or 'this party'} is not on your autonomous allowlist for {action_class}"
        cap = rails["daily_cap"]
        if cap is not None and self.autonomous_runs_today(tenant, action_class) >= cap:
            return False, f"daily autonomous cap of {cap} for {action_class} reached"
        return True, "within your autonomous limits"

    def autonomous_runs_today(self, tenant: str, action_class: str, *, day: str | None = None) -> int:
        return int(self._read().get("runs", {}).get(_run_key(tenant, action_class, day or _today()), 0))

    def record_autonomous_run(self, tenant: str, action_class: str, *, day: str | None = None) -> None:
        data = self._read()
        runs = data.setdefault("runs", {})
        key = _run_key(tenant, action_class, day or _today())
        runs[key] = int(runs.get(key, 0)) + 1
        self._write(data)

    def autonomous_action_classes(self, tenant: str | None = None) -> list[dict]:
        entries = self._read().get("action_classes", {}).values()
        return [
            e for e in entries
            if e.get("autonomous") and (tenant is None or e.get("tenant") == tenant)
        ]


def _run_key(tenant: str, action_class: str, day: str) -> str:
    return f"{tenant}::{action_class}::{day}"


def _as_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")
