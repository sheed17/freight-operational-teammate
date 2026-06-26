"""Owner-reachable operational switches, persisted and audited.

The first switch is the TMS-writes **brake**: an owner can pause all payable entry from Slack the
moment something looks wrong, and resume it later — no config edit, no redeploy. The executor reads
this before entering any payable, so a pause holds APPROVED runs in place rather than failing them.

Backed by a small JSON file (one per workspace) so a Slack command can flip it and the gated write
path can read it. Every flip appends an audit entry (who, when, why).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OpsControl:
    """Persisted, audited operational switches for one workspace."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"tms_writes_paused": False, "paused_by": None, "paused_at": None, "reason": None, "log": []}

    def _write(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # --- TMS-writes brake -------------------------------------------------

    def is_tms_writes_paused(self) -> bool:
        return bool(self._read().get("tms_writes_paused"))

    def pause_tms_writes(self, *, actor: str, reason: str = "") -> dict:
        state = self._read()
        if not state.get("tms_writes_paused"):
            state["log"] = [*state.get("log", []), {"action": "pause", "actor": actor, "reason": reason, "at": _now()}]
        state.update({"tms_writes_paused": True, "paused_by": actor, "paused_at": _now(), "reason": reason})
        self._write(state)
        return state

    def resume_tms_writes(self, *, actor: str) -> dict:
        state = self._read()
        if state.get("tms_writes_paused"):
            state["log"] = [*state.get("log", []), {"action": "resume", "actor": actor, "at": _now()}]
        state.update({"tms_writes_paused": False, "paused_by": None, "paused_at": None, "reason": None})
        self._write(state)
        return state

    def status(self) -> dict:
        state = self._read()
        return {
            "tms_writes_paused": bool(state.get("tms_writes_paused")),
            "paused_by": state.get("paused_by"),
            "paused_at": state.get("paused_at"),
            "reason": state.get("reason"),
        }


class TmsWritesPausedError(Exception):
    """Raised when a payable entry is attempted while the TMS-writes brake is engaged."""


# Run states an owner still needs to deal with (for "show unresolved").
_OPEN_STATES = {"NEEDS_REVIEW", "DISPUTED", "FAILED", "WAITING_FOR_SESSION", "REQUESTED_BACKUP"}

_HELP = (
    "Commands: `pause tms writes` | `resume tms writes` | `status` | "
    "`show unresolved` | `status <LOAD-ID>`"
)


def handle_ops_command(text: str, *, actor: str, ops_control: OpsControl, store=None) -> str:
    """Parse one lightweight owner command from Slack into an action + reply. Channel-neutral."""
    raw = text.strip()
    cmd = " ".join(raw.lower().split())
    if cmd in ("pause", "pause tms writes", "pause writes", "pause tms"):
        ops_control.pause_tms_writes(actor=actor, reason="paused from Slack")
        return f":lock: TMS writes *PAUSED* by {actor}. No payables will be entered until resumed."
    if cmd in ("resume", "resume tms writes", "resume writes", "resume tms"):
        ops_control.resume_tms_writes(actor=actor)
        return f":unlock: TMS writes *RESUMED* by {actor}."
    if cmd in ("status", "ops status"):
        state = ops_control.status()
        if state["tms_writes_paused"]:
            reason = f", {state['reason']}" if state.get("reason") else ""
            return f":lock: TMS writes are *PAUSED* (by {state['paused_by']}{reason})."
        return ":white_check_mark: TMS writes are *ACTIVE*."
    if cmd in ("show unresolved", "unresolved", "show open") and store is not None:
        return _render_unresolved(store)
    if cmd.startswith("status ") and store is not None:
        return _render_load_status(store, raw.split(None, 1)[1].strip())
    return _HELP


def _state_of(run) -> str:
    return run.state.value if hasattr(run.state, "value") else str(run.state)


def _render_unresolved(store) -> str:
    rows = []
    for run in store.list_runs():
        state = _state_of(run)
        if state in _OPEN_STATES:
            tail = f" — {run.reason[:60]}" if getattr(run, "reason", None) else ""
            rows.append(f"• {run.load_id} — {state}{tail}")
    if not rows:
        return ":white_check_mark: No unresolved items."
    return "*Unresolved items:*\n" + "\n".join(rows[:25])


def _render_load_status(store, load_id: str) -> str:
    matches = [r for r in store.list_runs() if str(r.load_id).upper() == load_id.upper()]
    if not matches:
        return f"No run found for {load_id}."
    run = matches[-1]
    tail = f" — {run.reason}" if getattr(run, "reason", None) else ""
    return f"*{run.load_id}* — {_state_of(run)}{tail}"
